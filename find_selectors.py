"""
Quick diagnostic: dumps the DOM of the Claude.ai page to find correct CSS selectors.

PREREQUISITE: Chrome running with --remote-debugging-port=9222, Claude.ai logged in.

Usage:
    python find_selectors.py
"""

from playwright.sync_api import sync_playwright
import config


def main():
    print("Connecting to Chrome via CDP...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(config.CHROME_CDP_URL)
        except Exception as e:
            print(f"Failed: {e}")
            return

        # Find the Claude tab
        page = None
        for ctx in browser.contexts:
            for pg in ctx.pages:
                if "claude.ai" in pg.url:
                    page = pg
                    break

        if not page:
            print("No Claude.ai tab found! Open Claude.ai first.")
            return

        print(f"Found Claude tab: {page.url}")
        input("\nMake sure the chat page is fully loaded. Press Enter...")

        print("\n" + "=" * 60)
        print("  Searching for input, send button, and response elements")
        print("=" * 60)

        # Common selectors to try for the INPUT BOX
        input_candidates = [
            'div[data-testid="chat-input"]',
            '[contenteditable="true"]',
            'div[contenteditable="true"][data-placeholder]',
            'fieldset div[contenteditable]',
            'div.ProseMirror',
            '[role="textbox"]',
            'textarea',
            'div[enterkeyhint="enter"]',
        ]

        print("\n--- INPUT BOX candidates ---")
        for sel in input_candidates:
            try:
                count = page.locator(sel).count()
                if count > 0:
                    text = page.locator(sel).first.inner_text()[:50]
                    print(f"  FOUND ({count}x): {sel}")
                    print(f"         text: '{text}'")
            except Exception:
                pass

        # Common selectors to try for the SEND BUTTON
        send_candidates = [
            'button[aria-label="Send"]',
            'button[aria-label="Send message"]',
            'button[aria-label*="Send"]',
            'button[data-testid="send-button"]',
            'button[data-testid*="send"]',
            'button[type="submit"]',
            'button:has(svg[viewBox])',
            'fieldset button',
            'form button',
        ]

        print("\n--- SEND BUTTON candidates ---")
        for sel in send_candidates:
            try:
                count = page.locator(sel).count()
                if count > 0:
                    label = page.locator(sel).first.get_attribute("aria-label") or ""
                    print(f"  FOUND ({count}x): {sel}")
                    if label:
                        print(f"         aria-label: '{label}'")
            except Exception:
                pass

        # Common selectors for the RESPONSE container
        response_candidates = [
            '[data-testid="assistant-message"]',
            '[data-testid="chat-message-text"]',
            '[data-testid*="message"]',
            '[data-testid*="response"]',
            '.font-claude-message',
            '[data-is-streaming]',
            '.prose',
            '.markdown',
            '[class*="message"]',
            '[class*="response"]',
            '[class*="assistant"]',
        ]

        print("\n--- RESPONSE CONTAINER candidates ---")
        for sel in response_candidates:
            try:
                count = page.locator(sel).count()
                if count > 0:
                    text = page.locator(sel).last.inner_text()[:80]
                    print(f"  FOUND ({count}x): {sel}")
                    print(f"         last text: '{text}'")
            except Exception:
                pass

        # Dump all data-testid attributes on the page
        print("\n--- All data-testid values on page ---")
        try:
            testids = page.evaluate("""
                () => {
                    const els = document.querySelectorAll('[data-testid]');
                    return [...els].map(e => ({
                        testid: e.getAttribute('data-testid'),
                        tag: e.tagName.toLowerCase(),
                        text: (e.textContent || '').slice(0, 40).trim()
                    }));
                }
            """)
            seen = set()
            for item in testids:
                key = item['testid']
                if key not in seen:
                    seen.add(key)
                    print(f"  {item['tag']}[data-testid=\"{key}\"]  text: '{item['text']}'")
        except Exception as e:
            print(f"  Error: {e}")

        print("\n" + "=" * 60)
        print("Copy the working selectors into config.py CHAT_SELECTORS")
        print("=" * 60)


if __name__ == "__main__":
    main()
