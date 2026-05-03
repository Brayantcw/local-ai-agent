import os
import time
import uuid
import logging
from collections import OrderedDict

import httpx

from src.metrics import (
    llm_request_duration,
    llm_requests_total,
    llm_tokens_input,
    llm_tokens_output,
    llm_errors_total,
    llm_context_usage,
    llm_context_usage_ratio,
    llm_context_window_size,
    CONTEXT_WINDOW_SIZE,
)

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama.llm-serving.svc.cluster.local:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e2b")
MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", "100"))
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "20"))

SYSTEM_PROMPT = """You are a helpful AI assistant deployed on Kubernetes. 
You can answer questions, help with tasks, and provide information.
Be concise and helpful in your responses."""


class SessionStore:
    """In-memory conversation history with LRU eviction."""

    def __init__(self, max_sessions: int = MAX_SESSIONS):
        self._sessions: OrderedDict[str, list[dict]] = OrderedDict()
        self._max = max_sessions

    def create(self) -> str:
        sid = uuid.uuid4().hex[:16]
        self._sessions[sid] = []
        self._evict()
        return sid

    def get(self, sid: str) -> list[dict] | None:
        if sid in self._sessions:
            self._sessions.move_to_end(sid)
            return self._sessions[sid]
        return None

    def append(self, sid: str, role: str, content: str) -> None:
        history = self.get(sid)
        if history is not None:
            history.append({"role": role, "content": content})
            # Keep only the last N turns (each turn = user + assistant)
            if len(history) > MAX_HISTORY_TURNS * 2:
                del history[:2]

    def _evict(self) -> None:
        while len(self._sessions) > self._max:
            self._sessions.popitem(last=False)


sessions = SessionStore()


def _build_prompt(history: list[dict], message: str) -> str:
    """Build a prompt string with conversation history."""
    parts = [f"System: {SYSTEM_PROMPT}\n"]
    for msg in history:
        role = "Human" if msg["role"] == "user" else "Assistant"
        parts.append(f"{role}: {msg['content']}")
    parts.append(f"Human: {message}")
    parts.append("Assistant:")
    return "\n\n".join(parts)


async def get_agent_response(message: str, conversation_id: str | None = None) -> dict:
    """Get a response from the LLM agent with token metrics and conversation history."""
    # Resolve or create session
    if conversation_id and sessions.get(conversation_id) is not None:
        sid = conversation_id
    else:
        sid = sessions.create()

    history = sessions.get(sid)
    full_prompt = _build_prompt(history, message)

    logger.info(f"Processing message: {message[:50]}... (session={sid}, history_turns={len(history)//2})")
    start_time = time.time()

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": full_prompt,
                    "stream": False,
                    "keep_alive": -1,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        duration = time.time() - start_time
        response_text = data.get("response", "")
        input_tokens = data.get("prompt_eval_count", 0)
        output_tokens = data.get("eval_count", 0)

        # Record metrics
        llm_request_duration.labels(model=OLLAMA_MODEL).observe(duration)
        llm_requests_total.labels(model=OLLAMA_MODEL, status="success").inc()
        llm_tokens_input.labels(model=OLLAMA_MODEL).inc(input_tokens)
        llm_tokens_output.labels(model=OLLAMA_MODEL).inc(output_tokens)

        # Context window metrics
        context_used = input_tokens + output_tokens
        llm_context_usage.labels(model=OLLAMA_MODEL).set(context_used)
        llm_context_usage_ratio.labels(model=OLLAMA_MODEL).set(context_used / CONTEXT_WINDOW_SIZE)
        llm_context_window_size.labels(model=OLLAMA_MODEL).set(CONTEXT_WINDOW_SIZE)

        logger.info(
            f"Response generated: duration={duration:.2f}s "
            f"input_tokens={input_tokens} output_tokens={output_tokens} "
            f"context_used={context_used}/{CONTEXT_WINDOW_SIZE} ({context_used/CONTEXT_WINDOW_SIZE*100:.1f}%)"
        )

        # Save to conversation history
        sessions.append(sid, "user", message)
        sessions.append(sid, "assistant", response_text)

        return {
            "response": response_text,
            "conversation_id": sid,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "duration_seconds": round(duration, 2),
        }

    except Exception as e:
        llm_errors_total.labels(model=OLLAMA_MODEL).inc()
        llm_requests_total.labels(model=OLLAMA_MODEL, status="error").inc()
        logger.error(f"LLM call failed: {e}")
        raise
