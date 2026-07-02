"""
Chat UI driver — sends text to and reads responses from a browser-based
AI chat (Claude.ai or ChatGPT) via Playwright CDP connection.

Uses the Playwright page object connected to the user's real Chrome browser.
"""

import time
import random
import config
from notifier import notify_phone


class RateLimitDetected(Exception):
    """Raised when a rate-limit message is detected on the chat page."""
    def __init__(self, phrase: str):
        self.phrase = phrase
        super().__init__(f"Rate limit detected: matched phrase '{phrase}'")


def check_rate_limit(page):
    """Scans the full page body text for any known rate-limit phrases.
    Raises RateLimitDetected on first match."""
    try:
        body_text = page.locator("body").inner_text(timeout=5000).lower()
        for phrase in config.RATE_LIMIT_PHRASES:
            if phrase.lower() in body_text:
                raise RateLimitDetected(phrase)
    except RateLimitDetected:
        raise
    except Exception as e:
        if "Target page, context or browser has been closed" in str(e):
            raise
        # Don't crash the loop if the body text read fails for some reason
        print(f"[Chat UI] Warning: Could not check rate limit: {e}")


def send_to_chat_ui(page, text: str):
    """Checks rate limit, fills the chat input, and presses Enter to send.
    Adds a randomized human-like delay before sending (anti-bot)."""
    try:
        print("[Chat UI] Checking rate limits before sending...")
        check_rate_limit(page)

        # Anti-bot: randomized delay before typing
        delay = random.uniform(config.HUMAN_DELAY_MIN, config.HUMAN_DELAY_MAX)
        print(f"[Chat UI] Waiting {delay:.1f}s before sending (anti-bot)...")
        time.sleep(delay)

        print("[Chat UI] Sending output to chat...")
        input_selector = config.CHAT_SELECTORS["input_box"]

        # Click the input to focus it
        input_locator = page.locator(input_selector)
        input_locator.click(timeout=10000)
        time.sleep(0.3)

        # Type the text using the keyboard (more reliable than fill for
        # contenteditable divs like Claude.ai uses)
        # First, select all existing text and delete it
        page.keyboard.press("Control+a")
        time.sleep(0.1)
        page.keyboard.press("Backspace")
        time.sleep(0.1)

        # Paste via clipboard (fastest and handles special characters)
        page.evaluate(f"navigator.clipboard.writeText({repr(text)})")
        page.keyboard.press("Control+v")
        time.sleep(0.3)

        # Press Enter to send
        page.keyboard.press("Enter")
        time.sleep(0.5)

        # Always try to click the send button just in case Enter didn't work
        try:
            # Try finding by aria-label first
            send_btn = page.locator('button[aria-label="Send Message"]')
            if send_btn.count() > 0 and send_btn.first.is_visible():
                send_btn.first.click(timeout=1000)
                print("[Chat UI] Clicked 'Send Message' button.")
            else:
                # Fallback to the last SVG button in the input container
                send_btn = page.locator('button:has(svg)')
                # We specifically want the button near the input
                input_parent = page.locator('div:has(> [data-testid="chat-input"])')
                if input_parent.count() > 0:
                    send_btn_fallback = input_parent.locator('button:has(svg)')
                    if send_btn_fallback.count() > 0 and send_btn_fallback.last.is_visible():
                        send_btn_fallback.last.click(timeout=1000)
                        print("[Chat UI] Clicked fallback send button.")
        except Exception as click_err:
            pass

        print("[Chat UI] Message sent.")

    except RateLimitDetected:
        raise
    except Exception as e:
        print(f"[Chat UI] Error sending to chat: {e}")
        notify_phone(f"Failed to send to Chat UI: {e}", "Bridge Error")
        raise


# UI noise patterns to strip from Claude's response
_UI_NOISE = [
    "Sonnet 5 Medium",
    "Sonnet 4 Medium",
    "Haiku 3.5",
    "Claude is AI and can make mistakes. Please double-check responses.",
    "Claude can make mistakes. Please double-check responses.",
    "Share",
    "Quick answer",
    "Want to be notified when Claude responds?",
    "Notify",
    "Show less",
]


def _clean_response(text: str) -> str:
    """Strips known UI noise from the extracted response text."""
    if not text:
        return ""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip empty lines, timestamps (e.g. '5:52 pm'), and known UI noise
        if not stripped:
            continue
        if stripped.lower().endswith(('am', 'pm')) and len(stripped) < 10:
            continue  # timestamp like '5:52 pm'
        is_noise = False
        for noise in _UI_NOISE:
            if len(noise) < 15:
                # Exact match for short UI buttons (case insensitive)
                if stripped.lower() == noise.lower():
                    is_noise = True
                    break
            else:
                # Substring match for long disclaimers (case insensitive)
                if noise.lower() in stripped.lower():
                    is_noise = True
                    break
        if is_noise:
            continue
        cleaned.append(stripped)
    return "\n".join(cleaned).strip()


from text_utils import fuzzy_extract_after

def _get_full_page_text(page) -> str:
    """Extracts all text from the page."""
    try:
        # Get all text inside the main conversation container if possible
        # Otherwise fallback to body
        return page.locator("body").inner_text(timeout=2000)
    except Exception as e:
        if "Target page, context or browser has been closed" in str(e):
            raise
        print(f"[Chat UI] Warning: full text extraction failed: {e}")
        return ""


def _is_streaming(page) -> bool:
    """Checks if Claude is still generating a response (streaming indicator visible)."""
    try:
        # Claude shows a stop button while streaming
        stop_btn = page.locator('button[aria-label="Stop Response"]')
        if stop_btn.count() > 0 and stop_btn.is_visible():
            return True

        # Also check for any element with data-is-streaming
        streaming = page.locator('[data-is-streaming="true"]')
        if streaming.count() > 0:
            return True

        return False
    except Exception:
        return False


def wait_for_chat_response(page, sent_text: str) -> str:
    """Polls the chat page for the assistant's response.
    Returns the text once it hasn't changed for IDLE_STABLE_SECONDS.
    Also checks for rate-limit messages during polling."""
    try:
        print("[Chat UI] Waiting for response...")

        time.sleep(2.0)

        last_text = ""
        stable_time = 0.0

        while True:
            check_rate_limit(page)

            # Expand any 'Show more' buttons that might be hiding the prompt
            try:
                show_more = page.locator('text="Show more"')
                count = show_more.count()
                for i in range(count):
                    try:
                        show_more.nth(i).click(timeout=1000)
                        time.sleep(0.3)
                    except Exception:
                        pass
            except Exception:
                pass

            # Get full text
            full_text = _get_full_page_text(page)
            
            # Extract just the response after our prompt
            current_text = fuzzy_extract_after(full_text, sent_text)
            current_text = _clean_response(current_text)

            if current_text != last_text:
                last_text = current_text
                stable_time = 0.0
            else:
                if current_text and not _is_streaming(page):
                    stable_time += config.POLL_INTERVAL
                    if stable_time >= config.IDLE_STABLE_SECONDS:
                        print(
                            f"[Chat UI] Response stable for "
                            f"{config.IDLE_STABLE_SECONDS}s."
                        )
                        break

            time.sleep(config.POLL_INTERVAL)

        return last_text

    except RateLimitDetected:
        raise
    except Exception as e:
        print(f"[Chat UI] Error waiting for response: {e}")
        notify_phone(f"Failed to read Chat UI output: {e}", "Bridge Error")
        raise
