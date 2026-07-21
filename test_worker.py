import threading
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bridge_logger
bridge_logger.CLI_MODE = False

import main
import config
from antigravity_driver import get_antigravity_window

def worker():
    try:
        print("Worker starting...")
        main.run_bridge("test") # wait, run_bridge calls input()!
    except Exception as e:
        print(f"Worker failed: {e}")

# instead of run_bridge, just call get_antigravity_window directly as if it was run_bridge
def worker_sim():
    # simulate run_bridge desktop switch
    import ctypes
    _u32 = ctypes.windll.user32
    _hd = _u32.OpenInputDesktop(0, False, 0x10000000)  # GENERIC_ALL
    if _hd:
        res = _u32.SetThreadDesktop(_hd)
        print(f"SetThreadDesktop in worker thread: {res}, hdesk: {_hd}")
    
    try:
        ag = get_antigravity_window()
        print(f"WORKER FOUND WINDOW: {ag.handle}")
    except Exception as e:
        print(f"WORKER FAILED: {e}")

t = threading.Thread(target=worker_sim)
t.start()
t.join()
