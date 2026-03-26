"""WebSocket manager for real-time event broadcasting."""

import json
import logging
from typing import Set
from fastapi import WebSocket
from models.schemas import WSEvent

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and broadcasts events to all connected clients."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, event: WSEvent):
        """Broadcast a WSEvent to all connected clients."""
        data = event.model_dump_json()
        dead = set()
        for conn in self.active_connections:
            try:
                await conn.send_text(data)
            except Exception:
                dead.add(conn)
        for conn in dead:
            self.active_connections.discard(conn)

    async def broadcast_task_update(self, task_data: dict):
        await self.broadcast(WSEvent(type="task_update", data=task_data))

    async def broadcast_agent_update(self, agent_data: dict):
        await self.broadcast(WSEvent(type="agent_update", data=agent_data))

    async def broadcast_log(self, log_data: dict):
        await self.broadcast(WSEvent(type="log", data=log_data))

    async def broadcast_hitl_request(self, hitl_data: dict):
        await self.broadcast(WSEvent(type="hitl_request", data=hitl_data))


# Singleton instance
ws_manager = WebSocketManager()
