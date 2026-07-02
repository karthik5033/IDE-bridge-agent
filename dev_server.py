import subprocess
import threading
import queue
import time
import os

class DevServerManager:
    def __init__(self, cmd: str, cwd: str, port: int):
        self.cmd = cmd
        self.cwd = cwd
        self.port = port
        self.process = None
        self.log_queue = queue.Queue()
        self.error_buffer = []
        self._stop_event = threading.Event()
        self._thread = None
        
        # We consider these keywords as indicative of a crash or compilation error
        self.error_keywords = ["error", "exception", "failed to compile", "traceback"]

    def start(self):
        import urllib.request
        import urllib.error
        try:
            # Check if server is already running on this port
            urllib.request.urlopen(f"http://localhost:{self.port}", timeout=2)
            print(f"[DevServer] Server is already running on port {self.port}. Skipping startup.")
            return
        except urllib.error.URLError:
            pass # Port is free, proceed to start

        print(f"[DevServer] Starting manager for: {self.cmd} in {self.cwd}")
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()

    def _run_server(self):
        # Wait for directory to exist
        while not self._stop_event.is_set():
            if os.path.exists(self.cwd) and os.path.isdir(self.cwd):
                break
            time.sleep(2)
            
        if self._stop_event.is_set():
            return
            
        print(f"[DevServer] Directory found. Starting: {self.cmd}")
        try:
            self.process = subprocess.Popen(
                self.cmd,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=True,
                bufsize=1
            )
        except Exception as e:
            print(f"[DevServer] Failed to start subprocess: {e}")
            return
            
        # Read logs loop
        while not self._stop_event.is_set() and self.process.poll() is None:
            line = self.process.stdout.readline()
            if line:
                self.log_queue.put(line)
                
                # Check for errors
                line_lower = line.lower()
                if any(kw in line_lower for kw in self.error_keywords):
                    self.error_buffer.append(line.strip())

    def get_new_errors(self) -> str:
        """Returns collected errors and clears the buffer."""
        if not self.error_buffer:
            return ""
        
        errors = "\n".join(self.error_buffer)
        self.error_buffer.clear()
        return errors

    def stop(self):
        self._stop_event.set()
        if self.process:
            print("[DevServer] Stopping server...")
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
        if self._thread:
            self._thread.join(timeout=1)
