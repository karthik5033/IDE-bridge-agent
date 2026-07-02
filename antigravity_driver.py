"""
Antigravity driver — sends instructions and reads responses from the
Antigravity IDE chat panel.

Uses Win32 API (ctypes) for reliable window activation, and pywinauto's
UIA backend only for locating the window handle. All keystrokes are sent
via win32 SendInput through pyautogui AFTER verifying the correct window
is in the foreground.
"""

import time
import ctypes
import ctypes.wintypes
import pyperclip
import pyautogui
from pywinauto import Desktop
import config
from notifier import notify_phone

# Win32 constants
SW_RESTORE = 9
SW_SHOW = 5
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001

user32 = ctypes.windll.user32


def _force_foreground(hwnd):
    """Forces a window to the foreground using multiple Win32 tricks.

    Windows restricts SetForegroundWindow to processes that already own the
    foreground. We work around this by:
    1. Attaching our thread's input to the foreground thread.
    2. Using SetForegroundWindow.
    3. Temporarily setting the window as topmost and then removing topmost.
    """
    # Restore if minimised
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.3)

    # Attach our thread to the foreground window's thread input
    foreground_hwnd = user32.GetForegroundWindow()
    foreground_thread = user32.GetWindowThreadProcessId(foreground_hwnd, None)
    our_thread = ctypes.windll.kernel32.GetCurrentThreadId()

    attached = False
    if foreground_thread != our_thread:
        attached = user32.AttachThreadInput(our_thread, foreground_thread, True)

    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)

        # Topmost trick: set as topmost, then remove topmost flag
        user32.SetWindowPos(
            hwnd, HWND_TOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE
        )
        user32.SetWindowPos(
            hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE
        )
    finally:
        if attached:
            user32.AttachThreadInput(our_thread, foreground_thread, False)

    time.sleep(0.3)


def _verify_foreground(hwnd) -> bool:
    """Checks that the given hwnd is actually the foreground window."""
    return user32.GetForegroundWindow() == hwnd


def _get_hwnd(win):
    """Extracts the raw Win32 HWND from a pywinauto window wrapper."""
    return win.handle


def get_antigravity_window():
    """Locates the Antigravity window using the configured title regex.
    Returns the window wrapper. Raises RuntimeError if not found."""
    print("[Antigravity] Locating window...")
    try:
        desktop = Desktop(backend="uia")
        win = desktop.window(title_re=config.ANTIGRAVITY_WINDOW_TITLE)
        # .exists() actually queries the OS — if False, the window isn't there
        if not win.exists():
            raise RuntimeError(
                f"No window matching regex: {config.ANTIGRAVITY_WINDOW_TITLE}"
            )
        print("[Antigravity] Window found.")
        return win
    except Exception as e:
        print(f"[Antigravity] Error locating window: {e}")
        notify_phone(f"Failed to find Antigravity window: {e}", "Bridge Error")
        raise


def _activate_window(win):
    """Brings the Antigravity window to the foreground reliably.
    Raises RuntimeError if the window could not be activated."""
    hwnd = _get_hwnd(win)
    _force_foreground(hwnd)

    # Verify with retries
    for attempt in range(3):
        if _verify_foreground(hwnd):
            return
        time.sleep(0.3)
        _force_foreground(hwnd)

    # One last check
    if not _verify_foreground(hwnd):
        print(
            "\n[Warning] Could not bring Antigravity to the foreground automatically. "
            "Please click on the Antigravity window to give it focus."
        )
        while not _verify_foreground(hwnd):
            time.sleep(0.5)


def _read_conversation_text(win) -> str:
    """Reads the conversation panel text via the accessibility tree.

    First tries UIA's get_value/texts patterns on the conversation control.
    Falls back to clipboard-based copy if those don't return useful content.
    """
    try:
        conv_ctrl = win.child_window(auto_id=config.CONVERSATION_AUTO_ID)

        # Try the legacy_properties or iface approach for text
        try:
            props = conv_ctrl.legacy_properties()
            val = props.get("Value", "")
            if val and val.strip() and val.strip() != "Agent Conversation":
                return val.strip()
        except Exception:
            pass

        # Try getting all text from descendants
        try:
            texts = []
            for child in conv_ctrl.descendants():
                try:
                    t = child.window_text()
                    if t and t.strip():
                        texts.append(t.strip())
                except Exception:
                    pass
            if texts:
                combined = "\n".join(texts)
                if combined.strip() and combined.strip() != "Agent Conversation":
                    return combined.strip()
        except Exception:
            pass

        # Fallback: clipboard-based reading
        # Activate window first
        _activate_window(win)

        # Click in the middle of the conversation area
        rect = conv_ctrl.rectangle()
        click_x = rect.left + (rect.width() // 2)
        click_y = rect.top + min(100, rect.height() // 3)

        pyautogui.click(click_x, click_y)
        time.sleep(0.2)

        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.2)
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(0.2)

        # Click again to deselect
        pyautogui.press('escape')
        time.sleep(0.1)

        return pyperclip.paste().strip()

    except Exception as e:
        print(f"[Antigravity] Read failed: {e}")
        return ""


from text_utils import fuzzy_extract_after

# Module-level state to track the last instruction sent, used for response extraction
_last_sent_instruction = ""

def _extract_latest_response(full_text: str, sent_instruction: str) -> str:
    """Extracts the agent's latest response from the full conversation text."""
    return fuzzy_extract_after(full_text, sent_instruction)


def send_to_antigravity(win, text: str):
    """Sends text to the Antigravity chat input by focusing it with Ctrl+L.

    Approach:
    1. Force the Antigravity window to the foreground (Win32 API).
    2. Verify it is actually focused.
    3. Press Ctrl+L to focus the chat input.
    4. Paste the text.
    5. Enter to submit.
    """
    global _last_sent_instruction
    try:
        print("[Antigravity] Sending instruction...")

        # Reliably bring the window to the front
        _activate_window(win)
        print("[Antigravity] Window activated and verified in foreground.")

        # Since Ctrl+L clears the integrated terminal if it has focus, we must click.
        # UIA auto_ids are flaky in Electron and sometimes return the full window.
        # Instead, we click relative to the bottom-right of the whole window, 
        # which is where the Antigravity chat input is permanently docked.
        rect = win.rectangle()
        
        # Click 150px from the right edge, and 80px from the bottom (above status bar)
        input_x = rect.right - 150
        input_y = rect.bottom - 80

        print(f"[Antigravity] Clicking chat input at ({input_x}, {input_y})...")
        pyautogui.click(input_x, input_y)
        time.sleep(0.4)

        # Select all existing text in the input and replace with our text
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.2)

        # Paste via clipboard
        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.3)

        # Send the message
        pyautogui.press('enter')

        _last_sent_instruction = text
        print("[Antigravity] Instruction sent.")

    except Exception as e:
        print(f"[Antigravity] Error sending instruction: {e}")
        notify_phone(f"Failed to send to Antigravity: {e}", "Bridge Error")
        raise


def wait_for_antigravity_response(win) -> str:
    """Polls the conversation panel text every POLL_INTERVAL seconds.
    Returns the response text once it hasn't changed for IDLE_STABLE_SECONDS.

    Reads text from the UIA accessibility tree of the conversation panel
    (descendants' window_text()), falling back to clipboard if needed.
    """
    try:
        print("[Antigravity] Waiting for response...")

        # Take a baseline snapshot before Antigravity starts responding
        time.sleep(1.5)  # brief pause to let Antigravity start processing
        baseline_text = _read_conversation_text(win)

        last_text = baseline_text
        stable_time = 0.0

        while True:
            time.sleep(config.POLL_INTERVAL)
            current_text = _read_conversation_text(win)

            if current_text != last_text:
                last_text = current_text
                stable_time = 0.0
            else:
                # Only count as stable if text has actually changed from baseline
                if current_text and current_text != baseline_text:
                    stable_time += config.POLL_INTERVAL
                    if stable_time >= config.IDLE_STABLE_SECONDS:
                        print(
                            f"[Antigravity] Response stable for "
                            f"{config.IDLE_STABLE_SECONDS}s."
                        )
                        break

        # Extract just the latest response from the full conversation
        response = _extract_latest_response(last_text, _last_sent_instruction)
        print(f"[Antigravity] Extracted response ({len(response)} chars).")
        return response

    except Exception as e:
        print(f"[Antigravity] Error waiting for response: {e}")
        notify_phone(f"Failed to read Antigravity output: {e}", "Bridge Error")
        raise
