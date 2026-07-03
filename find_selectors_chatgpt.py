"""
Utility script to help find and test CSS selectors for ChatGPT.
Run this when ChatGPT updates its DOM to fix the bridge agent.
"""
from playwright.sync_api import sync_playwright
import config

def test_chatgpt_selectors():
    with sync_playwright() as p:
        try:
            print(f"Connecting to Chrome CDP at {config.CHROME_CDP_URL}...")
            browser = p.chromium.connect_over_cdp(config.CHROME_CDP_URL)
        except Exception as e:
            print(f"Failed to connect to Chrome. Did you launch it with --remote-debugging-port=9222?\n{e}")
            return

        chatgpt_page = None
        for ctx in browser.contexts:
            for pg in ctx.pages:
                if "chatgpt.com" in pg.url:
                    chatgpt_page = pg
                    break
            if chatgpt_page:
                break
                
        if not chatgpt_page:
            print("No ChatGPT tab found. Please open https://chatgpt.com in your debug browser.")
            return
            
        print(f"Found ChatGPT tab: {chatgpt_page.url}")
        
        # Test input box
        input_sel = config.CHATGPT_SELECTORS["input_box"]
        if chatgpt_page.locator(input_sel).count() > 0:
            print(f"[OK] Input box found using: {input_sel}")
        else:
            print(f"[FAIL] Input box NOT found using: {input_sel}")
            
        # Test file upload (hidden)
        file_sel = config.CHATGPT_SELECTORS["file_upload"]
        if chatgpt_page.locator(file_sel).count() > 0:
            print(f"[OK] File upload input found using: {file_sel}")
        else:
            print(f"[FAIL] File upload input NOT found using: {file_sel}")
            
        # Test latest response (might need an actual response on the page)
        resp_sel = config.CHATGPT_SELECTORS["latest_response"]
        count = chatgpt_page.locator(resp_sel).count()
        print(f"Found {count} assistant responses using: {resp_sel}")

if __name__ == "__main__":
    test_chatgpt_selectors()
