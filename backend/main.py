"""FastAPI application entrypoint for the Olympus backend."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load .env before anything else
load_dotenv()

from models.database import init_db
from orchestrator.router import router
from orchestrator.websocket import ws_manager
from config import get_settings

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    settings = get_settings()
    logger.info("🚀 Olympus starting up...")
    await init_db()
    logger.info("✅ Database initialized")

    # Ensure agent working directory exists and log it clearly.
    backend_root = os.path.dirname(os.path.abspath(__file__))
    if os.path.isabs(settings.shell_working_dir):
        workspace = os.path.abspath(settings.shell_working_dir)
    else:
        workspace = os.path.abspath(os.path.join(backend_root, settings.shell_working_dir))
    os.makedirs(workspace, exist_ok=True)
    logger.info(f"📁 Agent working directory: {workspace}")

    yield

    logger.info("🛑 Olympus shutting down...")


# --- App ---
app = FastAPI(
    title="Olympus",
    description="Orchestrator for multi-agent AI systems with HITL support",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for Electron renderer
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routes
app.include_router(router, prefix="/api")


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive — client sends pings
            data = await websocket.receive_text()
            logger.debug(f"WS received: {data}")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# Health check
@app.get("/health")
async def health():
    return {"status": "ok", "service": "olympus"}


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=False,
    )
