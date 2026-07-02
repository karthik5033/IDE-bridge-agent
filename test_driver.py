"""
Standalone test for the antigravity_driver.py.

Run this with the Antigravity IDE window open:
    python test_driver.py

It will:
1. Find the Antigravity window.
2. Force it to the foreground and verify focus.
3. Try to read the conversation panel text.
4. Optionally send a test message.
"""

import time
from antigravity_driver import (
    get_antigravity_window,
    send_to_antigravity,
    wait_for_antigravity_response,
    _read_conversation_text,
    _activate_window,
    _verify_foreground,
    _get_hwnd,
)


def main():
    print("=" * 50)
    print("  Antigravity Driver Test")
    print("=" * 50)

    # Step 1: Find the window
    print("\n[Test] Step 1: Finding Antigravity window...")
    try:
        win = get_antigravity_window()
    except Exception as e:
        print(f"FAILED: Could not find Antigravity window: {e}")
        return

    # Step 2: Force window to foreground
    print("\n[Test] Step 2: Activating Antigravity window...")
    try:
        _activate_window(win)
        hwnd = _get_hwnd(win)
        if _verify_foreground(hwnd):
            print("  SUCCESS: Antigravity is now the foreground window!")
        else:
            print("  WARNING: Could not verify foreground status.")
    except RuntimeError as e:
        print(f"  FAILED: {e}")
        return

    # Step 3: Read conversation text
    print("\n[Test] Step 3: Reading conversation panel text...")
    text = _read_conversation_text(win)
    if text:
        preview = text[:300].replace('\n', '\n    ')
        print(f"  Got {len(text)} chars. Preview:")
        print(f"    {preview}...")
    else:
        print("  WARNING: Got empty text from conversation panel.")

    # Step 4: Ask if user wants to send a test message
    print("\n" + "-" * 50)
    ans = input("[Test] Do you want to send a test message? (y/n): ").strip().lower()
    if ans != "y":
        print("\nTest complete (skipped send).")
        return

    test_msg = "hello, this is a test from the bridge agent driver"
    print(f"\n[Test] Step 4: Sending: '{test_msg}'")
    print("  (The Antigravity window will be brought to the front)")
    time.sleep(1)

    try:
        send_to_antigravity(win, test_msg)
        print("  Message sent successfully!")
    except Exception as e:
        print(f"  FAILED to send: {e}")
        return

    # Step 5: Wait for response
    print("\n[Test] Step 5: Waiting for Antigravity response...")
    try:
        response = wait_for_antigravity_response(win)
        preview = response[:500].replace('\n', '\n    ')
        print(f"\n  Response ({len(response)} chars):")
        print(f"    {preview}")
    except Exception as e:
        print(f"  FAILED to get response: {e}")
        return

    print("\n" + "=" * 50)
    print("  Test complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
