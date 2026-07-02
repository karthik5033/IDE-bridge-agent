# 🏃‍♂️ Running the Bridge Agent

This guide provides step-by-step instructions on how to spin up all the necessary components to run the Bridge Agent. You need to start three main things before running the Python script: the local LLM, the browser, and the Antigravity IDE.

---

## Step 1: Start the Local LLM (Ollama)
The Bridge Agent uses a local LLM as an orchestrator to analyze messages. 

1. Ensure [Ollama](https://ollama.com/) is installed and running in your system tray.
2. Open a terminal and run the model specified in your `config.py` (default is `qwen2.5-coder:latest`):
   ```bash
   ollama run qwen2.5-coder:latest
   ```
   *Note: You don't necessarily have to leave this terminal open if Ollama is running as a background service, but running it once ensures the model is pulled and loaded.*

---

## Step 2: Start Chrome with Remote Debugging
The agent uses Playwright to connect to an existing Chrome instance so it doesn't have to log in to Claude every time.

1. Close all currently open Chrome windows. (This is important, as remote debugging won't attach to a new window if Chrome is already running without the flag).
2. Open a PowerShell window and run:
   ```powershell
   Start-Process "chrome.exe" -ArgumentList "--remote-debugging-port=9222"
   ```
3. In this new Chrome window, navigate to [claude.ai/new](https://claude.ai/new) (or your chosen chat UI).
4. **Log in** to your account and make sure you are sitting on the new chat screen.

---

## Step 3: Start the Antigravity IDE
The agent uses `pywinauto` to send keyboard shortcuts to the Antigravity IDE.

1. Open your Antigravity IDE.
2. Ensure the window title matches the regex in your `config.py` (`ANTIGRAVITY_WINDOW_TITLE`). If you aren't sure, run `python inspect_antigravity.py` to check the title.
3. Bring the IDE window to the foreground at least once so Windows registers it.

---

## Step 4: Run the Bridge Agent
Now that all dependencies are running, you can start the automation loop.

1. Open a new terminal in the `bridge_agent` directory.
2. Ensure your virtual environment is activated (if you are using one).
3. Run the main script and provide your initial task:
   ```bash
   python main.py "Create a beautiful React dashboard with a dark mode toggle"
   ```
   *(Alternatively, if you run `python main.py` without arguments, it will prompt you to type the task).*

4. The script will automatically connect to Chrome, grab the architect's plan from Claude, and start driving the Antigravity IDE. Sit back and watch!

---

### 🛑 How to Stop
If you need to pause or stop the agent at any time, press **`Ctrl + C`** in the terminal running `main.py`. 
The agent will gracefully save a checkpoint so you can resume later.
