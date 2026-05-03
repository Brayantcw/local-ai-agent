import os
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.agent import get_agent_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    conversation_id: str | None = None
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    duration_seconds: float = 0.0


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        result = await get_agent_response(request.message, request.conversation_id)
        return ChatResponse(
            response=result["response"],
            conversation_id=result["conversation_id"],
            model=os.getenv("OLLAMA_MODEL", "gemma4:e2b"),
            input_tokens=result["input_tokens"],
            output_tokens=result["output_tokens"],
            duration_seconds=result["duration_seconds"],
        )
    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/models")
async def list_models():
    return {
        "models": [os.getenv("OLLAMA_MODEL", "gemma4:e2b")],
        "default": os.getenv("OLLAMA_MODEL", "gemma4:e2b"),
    }
