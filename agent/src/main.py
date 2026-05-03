import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from prometheus_fastapi_instrumentator import Instrumentator

from src.routes import router
from src.telemetry import setup_telemetry

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "info").upper())

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Agent...")
    setup_telemetry()
    yield
    logger.info("Shutting down AI Agent...")


app = FastAPI(
    title="AI Agent API",
    version="0.1.0",
    lifespan=lifespan,
)

# Prometheus metrics
Instrumentator().instrument(app).expose(app)

# Routes
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")


# Serve static files (CSS, JS if needed in future)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
