"""
Standalone test for the chat_driver.py (Claude.ai / ChatGPT browser automation).

PREREQUISITE: Chrome running with --remote-debugging-port=9222, chat site logged in.

Usage:
    python test_chat_driver.py
"""

import time
import config
from chat_driver import send_to_chat_ui, wait_for_chat_response, check_rate_limit, RateLimitDetected, _get_response_text
from playwright.sync_api import sync_playwright


def main():
    print("=" * 50)
    print("  Chat Driver Test (CDP)")
    print("=" * 50)

    print(f"\n  Chat site:  {config.CHAT_SITE_URL}")
    print(f"  CDP URL:    {config.CHROME_CDP_URL}")

    print("\nConnecting to Chrome via CDP...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(config.CHROME_CDP_URL)
        except Exception as e:
            print(f"\nFAILED to connect: {e}")
            print(
                "\nMake sure Chrome is running with:\n"
                '  chrome.exe --remote-debugging-port=9222\n'
                "Close ALL other Chrome windows first, then relaunch with that flag."
            )
            return

        # Find the Claude tab
        page = None
        for ctx in browser.contexts:
            for pg in ctx.pages:
                if "claude.ai" in pg.url or "chatgpt.com" in pg.url:
                    page = pg
                    break

        if not page:
            print("\nNo chat tab found. Opening new tab...")
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            page = ctx.new_page()
            page.goto(config.CHAT_SITE_URL, wait_until="domcontentloaded")

        print(f"Using tab: {page.url}")
        input("\n>> Press Enter when the chat page is loaded and ready...")

        # Step 1: Check input box
        print("\n[Test] Step 1: Checking input box...")
        input_sel = config.CHAT_SELECTORS["input_box"]
        count = page.locator(input_sel).count()
        print(f"  input_box ({input_sel}): {'OK' if count > 0 else 'NOT FOUND'} ({count} matches)")

        # Step 2: Try reading existing response
        print("\n[Test] Step 2: Reading existing response (if any)...")
        existing = _get_response_text(page)
        if existing:
            print(f"  Got {len(existing)} chars: {existing[:200]}...")
        else:
            print("  No existing response found (expected on a new chat page).")

        # Step 3: Check rate limits
        print("\n[Test] Step 3: Checking rate limits...")
        try:
            check_rate_limit(page)
            print("  No rate limit. OK")
        except RateLimitDetected as e:
            print(f"  !! Rate limit: {e.phrase}")

        # Step 4: Send test message
        print("\n" + "-" * 50)
        ans = input("[Test] Send a test message? (y/n): ").strip().lower()

        if ans == "y":
            test_msg = "Reply with exactly one word: WORKING"

            print(f"\n[Test] Step 4: Sending: '{test_msg}'")
            try:
                send_to_chat_ui(page, test_msg)
                print("\n[Test] Step 5: Waiting for response...")
                response = wait_for_chat_response(page)
                print(f"\n  Response ({len(response)} chars):")
                print(f"  {response[:500]}")
            except RateLimitDetected as e:
                print(f"  !! Rate limit hit: {e.phrase}")
            except Exception as e:
                print(f"  FAILED: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("\nSkipped send test.")

        print("\n" + "=" * 50)
        print("  Chat driver test complete!")
        print("=" * 50)


if __name__ == "__main__":
    main()
