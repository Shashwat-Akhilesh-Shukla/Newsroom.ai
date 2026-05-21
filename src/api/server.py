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
import subprocess
import threading
import json as _json

_workflow_thread = None
_workflow_running = False

@app.post("/api/run")
async def trigger_run():
    global _workflow_thread, _workflow_running

    if _workflow_running:
        return JSONResponse(
            status_code=409,
            content={"status": "error", "message": "A workflow is already running."}
        )

    root = Path(__file__).parent.parent.parent
    python = sys.executable

    def run_in_thread():
        global _workflow_running
        _workflow_running = True
        try:
            proc = subprocess.Popen(
                [python, "-m", "src.main"],
                cwd=str(root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    if line.startswith("__EVENT__:"):
                        payload = line[10:]
                    else:
                        payload = _json.dumps({"type": "log", "message": line})
                    # Schedule broadcast on the event loop from this thread
                    asyncio.run_coroutine_threadsafe(manager.broadcast(payload), loop)
            proc.wait()
            done = _json.dumps({"type": "log", "message": f">>> Workflow process exited (code {proc.returncode})"})
            asyncio.run_coroutine_threadsafe(manager.broadcast(done), loop)
        except Exception as e:
            err = _json.dumps({"type": "log", "message": f">>> Subprocess error: {e}"})
            asyncio.run_coroutine_threadsafe(manager.broadcast(err), loop)
        finally:
            _workflow_running = False

    # Grab the running event loop so the thread can schedule broadcasts
    loop = asyncio.get_event_loop()

    _workflow_thread = threading.Thread(target=run_in_thread, daemon=True)
    _workflow_thread.start()

    logger.info("Workflow thread started")
    return JSONResponse({"status": "started"})



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

# ─── Frontend Static Mount ────────────────────────────
# Must be mounted last so it doesn't shadow /api or /ws routes
frontend_dir = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
else:
    logger.warning("Frontend dist directory not found. Please run 'npm run build' in the frontend folder.")

if __name__ == "__main__":
    import uvicorn
    # Use PORT env variable if available, defaults to 8000
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=port, reload=True)
