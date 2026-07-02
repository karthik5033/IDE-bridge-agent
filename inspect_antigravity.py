"""
Helper script: Inspects the Antigravity (VS Code) window to find UIA auto_ids.

How to use:
1. Make sure the Antigravity IDE window is open and visible.
2. Run:  python inspect_antigravity.py
3. It will print all child controls it can find, along with their auto_id,
   control_type, and window_text (truncated).
4. Look through the output for:
   - The TEXT INPUT box (where you type prompts)
   - The SEND BUTTON
   - The OUTPUT PANEL (where responses appear)
5. Copy those auto_id values into config.py.
"""

from pywinauto import Desktop
import re

print("=" * 60)
print("  Antigravity Window Inspector")
print("=" * 60)

# Step 1: List all top-level windows so user can pick the right one
print("\nListing all visible windows:\n")
desktop = Desktop(backend="uia")
windows = desktop.windows()

for i, w in enumerate(windows):
    try:
        title = w.window_text()
        if title.strip():
            print(f"  [{i}] {title}")
    except Exception:
        pass

print("\n" + "-" * 60)
choice = input(
    "Enter the number of the Antigravity window from the list above "
    "(or type part of the title): "
).strip()

# Find the window
target_win = None
if choice.isdigit():
    target_win = windows[int(choice)]
else:
    for w in windows:
        try:
            if choice.lower() in w.window_text().lower():
                target_win = w
                break
        except Exception:
            pass

if target_win is None:
    print("Could not find that window. Exiting.")
    exit(1)

print(f"\nInspecting: {target_win.window_text()}")
print("=" * 60)
print(f"\nWindow title regex to use in config.py:")
print(f'  ANTIGRAVITY_WINDOW_TITLE = "{re.escape(target_win.window_text())}"')

# Step 2: Print all child controls
print(f"\n{'='*60}")
print("  Child Controls (auto_id | control_type | text preview)")
print(f"{'='*60}\n")

try:
    descendants = target_win.descendants()
    for ctrl in descendants:
        try:
            auto_id = ctrl.element_info.automation_id or "(none)"
            ctrl_type = ctrl.element_info.control_type or "(unknown)"
            text = ctrl.window_text()[:80].replace("\n", " ") if ctrl.window_text() else "(empty)"
            # Only print controls that have an auto_id (the useful ones)
            if auto_id != "(none)":
                print(f"  auto_id: {auto_id}")
                print(f"    type:  {ctrl_type}")
                print(f"    text:  {text}")
                print()
        except Exception:
            pass
except Exception as e:
    print(f"Error enumerating children: {e}")
    print("The window may not expose a UIA tree (known risk from PRD).")

print(f"\n{'='*60}")
print("Key auto_id for config.py:")
print("  CONVERSATION_AUTO_ID = 'conversation'  (if present above)")
print()
print("NOTE: The chat input, send button, and response text are inside")
print("a WebView and NOT visible as individual UIA controls. The bridge")
print("agent uses keyboard shortcuts (Ctrl+L, Enter) instead of auto_ids")
print("to interact with the chat. See config.py -> ANTIGRAVITY_KEYS.")
print(f"{'='*60}")
