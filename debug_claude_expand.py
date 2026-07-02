from playwright.sync_api import sync_playwright
import time

def expand_and_dump():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        page = None
        for ctx in browser.contexts:
            for pg in ctx.pages:
                if "claude.ai" in pg.url:
                    page = pg
                    break
            if page:
                break
                
        if not page:
            print("No Claude tab found")
            return
            
        print("Connected to Claude.")
        
        # Click all "Show more" buttons
        show_more = page.locator('text="Show more"')
        count = show_more.count()
        print(f"Found {count} 'Show more' buttons.")
        for i in range(count):
            try:
                show_more.nth(i).click()
                print("Clicked one 'Show more' button.")
                time.sleep(0.5)
            except Exception as e:
                print(f"Failed to click: {e}")
                
        body_text = page.locator("body").inner_text()
        print("\n--- Body Text Snippet ---")
        print(body_text[-1000:].encode('cp1252', 'replace').decode('cp1252'))

if __name__ == "__main__":
    expand_and_dump()
