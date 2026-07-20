import os
import sys
import threading
import asyncio
import requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure bridge_agent directory is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import bridge_logger
import config
import checkpoint
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
    resume: bool = False

@app.get("/api/models")
def get_models():
    try:
        session = requests.Session()
        session.mount('http://', requests.adapters.HTTPAdapter(max_retries=0))
        resp = session.get("http://localhost:11434/api/tags", timeout=1)
        resp.raise_for_status()
        data = resp.json()
        models = [m["name"] for m in data.get("models", [])]
        return {"models": models, "active": config.OLLAMA_MODELS["orchestrator"]}
    except Exception as e:
        fallback_models = [config.OLLAMA_MODELS["orchestrator"], "llama3.1:8b", "mistral:7b"]
        # Ensure unique in case orchestrator is one of the fallback models
        fallback_models = list(dict.fromkeys(fallback_models))
        return {"models": fallback_models, "active": config.OLLAMA_MODELS["orchestrator"], "error": str(e)}

class ModelRequest(BaseModel):
    model_name: str

@app.post("/api/models/active")
def set_active_model(req: ModelRequest):
    config.OLLAMA_MODELS["orchestrator"] = req.model_name
    return {"status": "success", "active": req.model_name}

active_thread = None

@app.get("/api/checkpoint")
def check_checkpoint():
    chk = checkpoint.load_checkpoint()
    return {"has_checkpoint": chk is not None}

@app.post("/api/start")
async def start_bridge(req: StartRequest):
    global active_thread
    
    if active_thread and active_thread.is_alive():
        return {"status": "error", "message": "Bridge is already running. Please stop it before starting a new session."}
        
    config.STOP_REQUESTED = False
    
    # Spawn a background thread to run the synchronous bridge engine
    t = threading.Thread(target=run_bridge, args=(req.task, req.resume), daemon=True)
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
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
