"""
API Server for AI Newsroom.
Provides a FastAPI app with:
  - WebSocket endpoint /ws/events  (streams Redis events to frontend)
  - POST /api/run                  (trigger workflow in background)
  - GET  /api/runs                 (list available output run directories)
  - Static mount /output           (serve generated article files)
"""

import sys
import subprocess
from pathlib import Path
import os
import asyncio
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
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

# ─── WebSocket Connection Manager ────────────────────
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

# ─── Redis Listener ───────────────────────────────────
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
    asyncio.create_task(redis_listener())

# ─── WebSocket Endpoint ──────────────────────────────
@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep the connection open; client is a listener only
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ─── REST: Trigger Workflow ───────────────────────────
_workflow_process = None

@app.post("/api/run")
async def trigger_run():
    """
    Launch the newsroom workflow as a background subprocess.
    Only one run at a time is allowed.
    """
    global _workflow_process

    # Check if a workflow is already running
    if _workflow_process is not None and _workflow_process.returncode is None:
        return JSONResponse(
            status_code=409,
            content={"status": "error", "message": "A workflow is already running."}
        )

    root = Path(__file__).parent.parent.parent
    python = sys.executable

    try:
        _workflow_process = await asyncio.create_subprocess_exec(
            python, "-m", "src.main",
            cwd=str(root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        # Stream stdout to connected WebSocket clients
        asyncio.create_task(_stream_process_output(_workflow_process))

        logger.info(f"Workflow subprocess started (PID {_workflow_process.pid})")
        return JSONResponse({"status": "started", "pid": _workflow_process.pid})

    except Exception as e:
        logger.error(f"Failed to start workflow subprocess: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


async def _stream_process_output(proc):
    """Read subprocess stdout and broadcast each line as a log event."""
    import json as _json
    try:
        async for raw_line in proc.stdout:
            line = raw_line.decode("utf-8", errors="replace").rstrip()
            if line:
                payload = _json.dumps({"type": "log", "message": line})
                await manager.broadcast(payload)
    except Exception as e:
        logger.error(f"Process output streaming error: {e}")
    finally:
        await proc.wait()
        logger.info(f"Workflow process exited with code {proc.returncode}")
        # Notify frontend
        import json as _json2
        done_msg = _json2.dumps({
            "type": "log",
            "message": f">>> Workflow process exited (code {proc.returncode})"
        })
        await manager.broadcast(done_msg)


# ─── REST: List Output Runs ───────────────────────────
@app.get("/api/runs")
async def list_runs():
    """
    Return a list of completed output run directories with available files.
    """
    runs = []

    # Scan output directory for run_YYYYMMDD_HHMMSS folders
    for entry in sorted(output_dir.iterdir()):
        if entry.is_dir() and entry.name.startswith("run_"):
            run_info = {
                "id":          entry.name,
                "article_md":  (entry / "article.md").exists(),
                "article_docx": (entry / "article.docx").exists(),
                "logs":        (entry / "logs.txt").exists(),
                "report":      (entry / "run_report.json").exists(),
            }
            runs.append(run_info)

    return JSONResponse(runs)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)
