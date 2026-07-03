import os
import sys
import threading
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure bridge_agent directory is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import bridge_logger
import config
from main import run_bridge

app = FastAPI(title="Bridge Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_connections = []

async def broadcast_event(event_dict):
    disconnected = []
    for ws in active_connections:
        try:
            await ws.send_json(event_dict)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        active_connections.remove(ws)

async def monitor_ui_queue():
    """Polls bridge_logger.ui_queue and broadcasts events."""
    while True:
        while not bridge_logger.ui_queue.empty():
            event = bridge_logger.ui_queue.get()
            await broadcast_event(event)
        await asyncio.sleep(0.1)

@app.on_event("startup")
async def startup_event():
    # Set logger to API mode so it won't block the server trying to read from CLI
    bridge_logger.CLI_MODE = False
    asyncio.create_task(monitor_ui_queue())

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # Receive commands from the dashboard UI
            data = await websocket.receive_json()
            if data.get("type") == "input_response":
                bridge_logger.cmd_queue.put(data.get("value"))
    except WebSocketDisconnect:
        active_connections.remove(websocket)

class StartRequest(BaseModel):
    task: str

active_thread = None

@app.post("/api/start")
async def start_bridge(req: StartRequest):
    global active_thread
    # Spawn a background thread to run the synchronous bridge engine
    t = threading.Thread(target=run_bridge, args=(req.task,), daemon=True)
    t.start()
    active_thread = t
    return {"status": "started", "message": "Bridge thread launched in background."}

@app.post("/api/stop")
async def stop_bridge():
    global active_thread
    config.STOP_REQUESTED = True
    # If the thread has already crashed/exited, emit the stopped signal immediately
    if active_thread is None or not active_thread.is_alive():
        bridge_logger.bprint("[System] Agent gracefully stopped.")
        active_thread = None
        return {"status": "stopped", "message": "Agent was already stopped."}
    return {"status": "stopping", "message": "Stop signal sent to bridge engine."}

if __name__ == "__main__":
    import uvicorn
    # Make sure to run this file via `python api_server.py`
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=True)
