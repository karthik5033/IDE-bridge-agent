import queue
import builtins

ui_queue = queue.Queue()
cmd_queue = queue.Queue()

# Set to False when running via the FastAPI server
CLI_MODE = True

def emit(event_type: str, data: dict):
    """Emit an event to the UI queue."""
    if CLI_MODE:
        if event_type == "log":
            builtins.print(data.get("message", ""))
    ui_queue.put({"type": event_type, "data": data})

def wait_for_user(prompt: str) -> str:
    """Block execution until the user provides input (via CLI or Web UI)."""
    emit("input_required", {"prompt": prompt})
    if CLI_MODE:
        return builtins.input(prompt)
    else:
        # Block until API receives input
        return cmd_queue.get()

def bprint(*args, **kwargs):
    """Drop-in replacement for built-in print."""
    msg = " ".join(str(a) for a in args)
    emit("log", {"message": msg})

def binput(prompt: str) -> str:
    """Drop-in replacement for built-in input."""
    return wait_for_user(prompt)
