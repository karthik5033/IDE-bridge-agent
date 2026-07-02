from playwright.sync_api import sync_playwright

def inspect_claude():
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
        
        # Dump the body text to see what it looks like
        body_text = page.locator("body").inner_text()
        print("\n--- Body Text Snippet ---")
        print(body_text[-1000:].encode('cp1252', 'replace').decode('cp1252'))
        
        # Let's see what data-testids exist
        testids = page.evaluate("""
            () => {
                const els = document.querySelectorAll('[data-testid]');
                const ids = new Set();
                els.forEach(el => ids.add(el.getAttribute('data-testid')));
                return Array.from(ids);
            }
        """)
        print("\n--- Data Test IDs ---")
        for tid in testids:
            print(tid)
            
        # Also grab any class names containing 'message'
        message_classes = page.evaluate("""
            () => {
                const classes = new Set();
                document.querySelectorAll('*').forEach(el => {
                    el.classList.forEach(c => {
                        if (c.toLowerCase().includes('message')) {
                            classes.add(c);
                        }
                    });
                });
                return Array.from(classes);
            }
        """)
        print("\n--- Classes containing 'message' ---")
        for cls in message_classes:
            print(cls)
            
if __name__ == "__main__":
    inspect_claude()
