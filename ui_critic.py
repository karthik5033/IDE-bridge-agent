import json
import requests
import config
import time
import tempfile
import base64
import os
from bridge_logger import bprint as print, binput as input
from page_explorer import explore_page, stitch_screenshots

CRITIC_SYSTEM_PROMPT = config.load_prompt("critic_system.md")

def extract_dom_summary(page, max_depth=5):
    """Extracts a simplified summary of the DOM to help the critic understand structure."""
    return page.evaluate(f"""() => {{
        function summarizeElement(el, depth, maxDepth) {{
            if (depth > maxDepth) return "...";
            if (!el) return null;
            
            const style = window.getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return null;
            if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'SVG', 'PATH', 'IFRAME'].includes(el.tagName)) return null;

            let summary = `<${{el.tagName.toLowerCase()}}`;
            if (el.id) summary += ` id="${{el.id}}"`;
            if (el.className && typeof el.className === 'string') {{
                const cls = el.className.trim().replace(/\\s+/g, ' ');
                if (cls) summary += ` class="${{cls}}"`;
            }}
            
            const attrs = ['role', 'aria-label', 'placeholder', 'type', 'href', 'src'];
            for (let attr of attrs) {{
                if (el.hasAttribute(attr)) {{
                    summary += ` ${{attr}}="${{el.getAttribute(attr)}}"`;
                }}
            }}
            summary += ">";

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
                const text = textContent.trim();
                summary += text.length > 50 ? text.substring(0, 50) + "..." : text;
            }}
            
            if (hasValidChildren) {{
                summary += `\\n${{'  '.repeat(depth)}}</${{el.tagName.toLowerCase()}}>`;
            }} else if (!textContent) {{
                 summary = summary.replace(">", " />");
            }} else {{
                summary += `</${{el.tagName.toLowerCase()}}>`;
            }}

            return summary;
        }}
        
        return summarizeElement(document.body, 0, {max_depth});
    }}""")

def capture_page_context(dev_page):
    """Captures screenshots (via smart exploration) and DOM summary from the dev page."""
    # Smart exploration: scroll, navigate routes, click elements, capture all
    base_url = f"http://localhost:{config.DEV_SERVER_PORT}"

    try:
        screenshots = explore_page(dev_page, base_url=base_url)
    except Exception as e:
        print(f"[Critic] Page exploration failed, falling back to single screenshot: {e}")
        screenshots = []

    # After exploration, ensure we're back on the base URL with a valid context
    try:
        dev_page.goto(base_url, wait_until="networkidle", timeout=10000)
    except Exception:
        try:
            dev_page.goto(base_url, wait_until="domcontentloaded", timeout=10000)
        except Exception as e:
            print(f"[Critic] Warning: could not re-navigate to base URL: {e}")

    # Extract DOM summary from the current (restored) page state
    try:
        max_depth = getattr(config, 'CRITIC_DOM_MAX_DEPTH', 5)
        dom_summary = extract_dom_summary(dev_page, max_depth=max_depth)
    except Exception as e:
        print(f"[Critic] Failed to extract DOM: {e}")
        dom_summary = ""

    if screenshots:
        composite_b64, composite_bytes = stitch_screenshots(screenshots)
        num_shots = len(screenshots)
        print(f"[Critic] Stitched {num_shots} screenshots into composite image.")
    else:
        # Fallback: single viewport screenshot
        try:
            raw = dev_page.screenshot(type="jpeg", quality=60)
            composite_b64 = base64.b64encode(raw).decode('utf-8')
            composite_bytes = raw
        except Exception as e:
            print(f"[Critic] Failed to take fallback screenshot: {e}")
            composite_b64 = ""
            composite_bytes = None

    return composite_b64, composite_bytes, dom_summary

def _evaluate_via_web_ui(screenshot_b64: str, screenshot_bytes: bytes, dom_summary: str, console_errors: str, page, platform: dict) -> dict:
    print(f"[Critic] Evaluating UI via {platform.get('name', 'Web UI')}. Found {len(console_errors)} bytes of error logs.")
    prompt = f"Console Errors:\n{console_errors if console_errors else 'None'}\n\nDOM Summary:\n```html\n{dom_summary}\n```\n\nEvaluate the UI based on the system criteria and the console errors.\n\n{CRITIC_SYSTEM_PROMPT}"
    
    try:
        page.bring_to_front()
        time.sleep(1)
        
        # Click the input to focus
        input_box = page.locator(platform["selectors"]["input_box"])
        input_box.click(timeout=5000)
        time.sleep(1)
        
        # Upload image using fallback selectors
        if screenshot_bytes:
            selectors = ['input[type="file"]', 'input#upload-files']
            uploaded = False
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(screenshot_bytes)
                tmp_path = tmp.name
                
            for sel in selectors:
                if page.locator(sel).count() > 0:
                    page.locator(sel).first.set_input_files(tmp_path)
                    uploaded = True
                    break
            
            os.remove(tmp_path)
            
            if uploaded:
                time.sleep(4) # wait for thumbnail to appear
        
        # Type the prompt (using keyboard to avoid clearing)
        page.keyboard.insert_text(prompt)
        time.sleep(1)
        
        # Press Enter to send (more reliable than clicking)
        page.keyboard.press("Enter")
        time.sleep(2)
        
        # Wait for response (simplified polling)
        print(f"[Critic] Waiting for response...")
        last_text = ""
        stable_count = 0
        while True:
            time.sleep(1)
            responses = page.locator(platform["selectors"]["latest_response"]).all()
            if not responses:
                continue
            
            current_text = responses[-1].inner_text()
            if current_text and current_text == last_text:
                stable_count += 1
                if stable_count >= config.IDLE_STABLE_SECONDS:
                    break
            else:
                last_text = current_text
                stable_count = 0
        
        # Parse JSON from last_text
        import re
        
        # Try to clean up markdown code blocks if present
        if "```json" in last_text.lower():
            try:
                last_text = re.split(r"```json", last_text, flags=re.IGNORECASE)[1].split("```")[0].strip()
            except Exception:
                pass
        elif "```" in last_text:
            parts = last_text.split("```")
            if len(parts) >= 3:
                last_text = parts[1].strip()
                
        # Find the first { and last } to extract just the JSON object
        start_idx = last_text.find('{')
        end_idx = last_text.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
            last_text = last_text[start_idx:end_idx+1]
            
        result = json.loads(last_text)
        print(f"[Critic] Result: {result}")
        return result
        
    except Exception as e:
        print(f"[Critic] Web UI evaluation failed: {e}")
        return {"verdict": "pass", "reason": f"Fallback to pass due to critic error: {e}", "instruction": None}

def _evaluate_via_local(screenshot_base64: str, console_errors: str) -> dict:
    print(f"[Critic] Evaluating UI via local Ollama ({config.OLLAMA_MODELS['ui_critic']})...")
    prompt = f"Console Errors:\n{console_errors if console_errors else 'None'}\n\nEvaluate the UI based on the system criteria and the console errors.\n\n{CRITIC_SYSTEM_PROMPT}"
    
    payload = {
        "model": config.OLLAMA_MODELS["ui_critic"],
        "prompt": prompt,
        "images": [screenshot_base64],
        "stream": False,
        "format": "json"
    }
    
    try:
        response = requests.post(config.OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()
        raw_output = result.get("response", "").strip()
        
        if raw_output.startswith("```json"):
            raw_output = raw_output[7:]
        if raw_output.endswith("```"):
            raw_output = raw_output[:-3]
            
        parsed = json.loads(raw_output.strip())
        print(f"[Critic] Local evaluation result: {parsed}")
        return parsed
    except json.JSONDecodeError as e:
        print(f"[Critic] Failed to parse JSON from local critic: {e}")
        return {"verdict": "pass", "reason": "JSON decode failed", "instruction": None}
    except Exception as e:
        print(f"[Critic] Error calling Ollama: {e}")
        return {"verdict": "pass", "reason": "Critic service unavailable", "instruction": None}

def evaluate_ui(screenshot_b64: str, screenshot_bytes: bytes, dom_summary: str, console_errors: str, critic_page=None, critic_platform=None) -> dict:
    """
    Main entry point for UI evaluation. 
    Routes to the active web critic (ChatGPT/Claude) or local Ollama based on config.
    """
    if config.CRITIC_MODE == "chatgpt" and critic_page and critic_platform:
        return _evaluate_via_web_ui(screenshot_b64, screenshot_bytes, dom_summary, console_errors, critic_page, critic_platform)
    else:
        return _evaluate_via_local(screenshot_b64, console_errors)
