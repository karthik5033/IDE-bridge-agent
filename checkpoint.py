import json
import os
import config

def save_checkpoint(turn: int, history_summary: str, phase: int = 1, current_payload: str = "", next_recipient: str = "chat", **kwargs):
    """Saves the current turn, phase, and history summary to the checkpoint file."""
    try:
        data = {
            "turn": turn,
            "phase": phase,
            "history_summary": history_summary,
            "current_payload": current_payload,
            "next_recipient": next_recipient
        }
        data.update(kwargs)
        with open(config.CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[Warning] Failed to save checkpoint: {e}")

def load_checkpoint() -> dict | None:
    """Loads the checkpoint from disk if it exists, otherwise returns None."""
    if not os.path.exists(config.CHECKPOINT_FILE):
        return None
    
    try:
        with open(config.CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[Warning] Failed to load checkpoint: {e}")
        return None

def clear_checkpoint():
    """Deletes the checkpoint file if it exists."""
    if os.path.exists(config.CHECKPOINT_FILE):
        try:
            os.remove(config.CHECKPOINT_FILE)
        except Exception as e:
            print(f"[Warning] Failed to clear checkpoint: {e}")
