from playwright.sync_api import sync_playwright
import time
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    for ctx in browser.contexts:
        for page in ctx.pages:
            if 'claude.ai' in page.url:
                page.goto('https://claude.ai/new', wait_until='domcontentloaded')
                time.sleep(2)
                input_selector = 'div[data-testid="chat-input"]'
                input_locator = page.locator(input_selector)
                input_locator.click(timeout=10000)
                
                page.keyboard.type('Hello this is a test prompt')
                time.sleep(1)
                
                buttons = page.locator('button').all()
                for b in buttons:
                    try:
                        html = b.evaluate('el => el.outerHTML')
                        if 'aria-label' in html.lower() and ('send' in html.lower() or 'svg' in html.lower()):
                            print('FOUND SEND BUTTON:', html)
                    except Exception:
                        pass
