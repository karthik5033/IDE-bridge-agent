import base64
import os
import tempfile
import time
from playwright.sync_api import sync_playwright
import config

def extract_dom_summary(page, max_depth=5):
    """Extracts a simplified summary of the DOM to help the critic understand structure."""
    return page.evaluate(f"""() => {{
        function summarizeElement(el, depth, maxDepth) {{
            if (depth > maxDepth) return "...";
            if (!el) return null;
            
            // Skip hidden elements, scripts, styles
            const style = window.getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return null;
            if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'SVG', 'PATH', 'IFRAME'].includes(el.tagName)) return null;

            let summary = `<${{el.tagName.toLowerCase()}}`;
            if (el.id) summary += ` id="${{el.id}}"`;
            if (el.className && typeof el.className === 'string') {{
                const cls = el.className.trim().replace(/\s+/g, ' ');
                if (cls) summary += ` class="${{cls}}"`;
            }}
            
            // Add important attributes
            const attrs = ['role', 'aria-label', 'placeholder', 'type', 'href', 'src'];
            for (let attr of attrs) {{
                if (el.hasAttribute(attr)) {{
                    summary += ` ${{attr}}="${{el.getAttribute(attr)}}"`;
                }}
            }}
            summary += ">";

            // Process children
            let hasValidChildren = false;
            let textContent = "";
            for (let child of el.childNodes) {{
                if (child.nodeType === Node.TEXT_NODE) {{
                    const text = child.textContent.trim();
                    if (text) textContent += text + " ";
                }} else if (child.nodeType === Node.ELEMENT_NODE) {{
                    const childSummary = summarizeElement(child, depth + 1, maxDepth);
                    if (childSummary) {{
                        hasValidChildren = true;
                        summary += `\\n${{'  '.repeat(depth + 1)}}${{childSummary}}`;
                    }}
                }}
            }}
            
            if (textContent) {{
                // Truncate long text
                const text = textContent.trim();
                summary += text.length > 50 ? text.substring(0, 50) + "..." : text;
            }}
            
            if (hasValidChildren) {{
                summary += `\\n${{'  '.repeat(depth)}}</${{el.tagName.toLowerCase()}}>`;
            }} else if (!textContent) {{
                 // if empty tag and no children, self-close
                 summary = summary.replace(">", " />");
            }} else {{
                summary += `</${{el.tagName.toLowerCase()}}>`;
            }}

            return summary;
        }}
        
        return summarizeElement(document.body, 0, {max_depth});
    }}""")

def test_upload():
    with sync_playwright() as p:
        print("Connecting to Chrome...")
        browser = p.chromium.connect_over_cdp(config.CHROME_CDP_URL)
        
        # 1. Find ChatGPT page
        chatgpt_page = None
        for ctx in browser.contexts:
            for pg in ctx.pages:
                if "chatgpt.com" in pg.url:
                    chatgpt_page = pg
                    break
            if chatgpt_page:
                break
                
        if not chatgpt_page:
            print("No ChatGPT tab found!")
            return
            
        print(f"ChatGPT tab: {chatgpt_page.url}")
        chatgpt_page.bring_to_front()
        
        # 2. Get local dev page
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        dev_page = ctx.new_page()
        dev_page.goto("http://localhost:3000", wait_until="networkidle")
        dev_page.bring_to_front()
        time.sleep(2)
        
        # 3. Extract DOM & Screenshot
        print("Extracting DOM...")
        dom_summary = extract_dom_summary(dev_page, max_depth=5)
        print(f"DOM Summary ({len(dom_summary)} chars):")
        print(dom_summary[:500] + "..." if len(dom_summary) > 500 else dom_summary)
        
        print("Taking screenshot...")
        screenshot_bytes = dev_page.screenshot(type="jpeg", quality=60)
        
        # 4. Try upload via file input
        chatgpt_page.bring_to_front()
        time.sleep(1)
        
        print("Attempting to upload to ChatGPT...")
        input_selector = config.CHATGPT_SELECTORS["input_box"]
        input_locator = chatgpt_page.locator(input_selector)
        input_locator.click(timeout=5000)
        time.sleep(1)
        
        try:
            # Try multiple selectors for the hidden file input
            selectors = ['input[type="file"]', 'input#upload-files']
            uploaded = False
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(screenshot_bytes)
                tmp_path = tmp.name
                
            for sel in selectors:
                if chatgpt_page.locator(sel).count() > 0:
                    print(f"Found file input: {sel}")
                    chatgpt_page.locator(sel).first.set_input_files(tmp_path)
                    uploaded = True
                    break
                    
            if not uploaded:
                print("Could not find file input. The DOM might have changed.")
                
            os.remove(tmp_path)
            
            if uploaded:
                # wait for image thumbnail
                print("Waiting for thumbnail to appear...")
                time.sleep(4)
                
                print("Filling prompt...")
                chatgpt_page.keyboard.insert_text(f"Here is a test screenshot. And the DOM:\\n```html\\n{dom_summary}\\n```\\nTell me what you see.")
                time.sleep(1)
                
                print("Sending...")
                chatgpt_page.keyboard.press("Enter")
                
                print("Done sending test message. Check ChatGPT window.")
        except Exception as e:
            print(f"Upload failed: {e}")
            
if __name__ == "__main__":
    test_upload()
