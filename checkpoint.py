import json
import os
import config
import subprocess

def git_commit_state(turn: int):
    """Commits the current state of the workspace to Git."""
    cwd = config.DEV_SERVER_CWD
    try:
        # Ensure git is initialized
        if not os.path.exists(os.path.join(cwd, '.git')):
            subprocess.run(['git', 'init'], cwd=cwd, check=True, capture_output=True)
            
        subprocess.run(['git', 'add', '.'], cwd=cwd, check=True, capture_output=True)
        # We allow empty commits in case nothing changed but we still want a marker, though git commit -m might fail without --allow-empty
        res = subprocess.run(['git', 'commit', '--allow-empty', '-m', f'Checkpoint: Turn {turn} (Critic PASS)'], cwd=cwd, capture_output=True)
        if res.returncode == 0:
            print(f"[Git] Checkpoint saved for turn {turn}.")
        else:
            # If there's nothing to commit, that's fine
            print(f"[Git] No new changes to commit for turn {turn}.")
    except Exception as e:
        print(f"[Warning] Failed to git commit checkpoint: {e}")

def git_rollback_state():
    """Rolls back the workspace to the last Git commit."""
    cwd = config.DEV_SERVER_CWD
    try:
        subprocess.run(['git', 'reset', '--hard', 'HEAD'], cwd=cwd, check=True, capture_output=True)
        subprocess.run(['git', 'clean', '-fd'], cwd=cwd, check=True, capture_output=True)
        print(f"[Git] Workspace rolled back to last stable checkpoint.")
    except Exception as e:
        print(f"[Warning] Failed to git rollback: {e}")

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
