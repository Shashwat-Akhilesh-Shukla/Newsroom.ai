"""
API Server for AI Newsroom.
Provides a FastAPI app with a WebSocket endpoint for the frontend to stream events.
"""

import sys
from pathlib import Path
import os
import asyncio
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import redis.asyncio as aioredis

# Ensure src is in python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title="AI Newsroom API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("newsroom.api")
logging.basicConfig(level=logging.INFO)

# Mount output directory if it exists
output_dir = Path(__file__).parent.parent.parent / "output"
output_dir.mkdir(exist_ok=True)
app.mount("/output", StaticFiles(directory=str(output_dir)), name="output")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Active clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Active clients: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Failed to send to client, removing connection: {e}")
                self.disconnect(connection)

manager = ConnectionManager()

async def redis_listener():
    """Background task to listen to Redis and broadcast to websockets."""
    try:
        redis_client = aioredis.from_url(REDIS_URL)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("newsroom:events", "newsroom:logs")
        logger.info(f"Subscribed to Redis channels at {REDIS_URL}")
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"].decode("utf-8")
                if manager.active_connections:
                    await manager.broadcast(data)
    except Exception as e:
        logger.error(f"Redis listener error (is Redis running?): {e}")

@app.on_event("startup")
async def startup_event():
    # Start Redis subscription in the background
    asyncio.create_task(redis_listener())

@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep the connection open - the client is just listening
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)
