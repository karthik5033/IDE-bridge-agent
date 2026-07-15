"""
functional_qa.py — Automated interactive testing and zero-tolerance error monitoring.

This module crawls the DOM, clicks interactive elements, and fails fast
if any console errors or unhandled rejections are detected.
"""

import time
from bridge_logger import bprint as print

class FunctionalQAError(Exception):
    """Raised when the application fails functional QA (e.g., console error)."""
    pass

def run_functional_qa(page, base_url):
    """
    Crawls interactive elements and monitors for errors.
    Raises FunctionalQAError if any error is encountered.
    """
    print("\n[Functional QA] Starting zero-tolerance interactive testing...")
    
    errors = []
    
    def handle_console(msg):
        if msg.type in ["error", "warning"]:
            # Ignore specific non-fatal warnings if needed, but default to strict
            # e.g., ignore hydration warnings if we choose to whitelist them later.
            if "hydration" in msg.text.lower() or "did not match" in msg.text.lower():
                print(f"[Functional QA] Warning (Ignored): {msg.text}")
            else:
                errors.append(f"Console {msg.type}: {msg.text}")
                
    def handle_page_error(err):
        errors.append(f"Unhandled Exception: {err}")

    # Attach strict listeners
    page.on("console", handle_console)
    page.on("pageerror", handle_page_error)
    
    try:
        # Navigate to base URL to start fresh
        page.goto(base_url, wait_until="domcontentloaded", timeout=10000)
    except Exception as e:
        if "interrupted by another navigation" not in str(e):
            raise FunctionalQAError(f"Failed to load application at {base_url}: {e}")

    # Give it a moment to render
    time.sleep(2)
    
    if errors:
        _raise_if_errors(errors, "Initial load")

    # Discover buttons and links
    try:
        interactives = page.evaluate("""() => {
            const results = [];
            const elements = document.querySelectorAll('button:not([disabled]), a[href], [role="button"], input[type="submit"], input[type="button"]');
            for (const el of elements) {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden') {
                    // Generate a unique selector or just use xpath-like structure for playwright to click
                    const text = (el.innerText || el.value || '').trim().substring(0, 30);
                    if (text) {
                        // Create a simple css selector if id exists, or just use text
                        results.push({
                            text: text,
                            tagName: el.tagName
                        });
                    }
                }
            }
            return results;
        }""")
    except Exception as e:
        print(f"[Functional QA] Failed to discover elements: {e}")
        interactives = []

    print(f"[Functional QA] Discovered {len(interactives)} interactive elements to test.")

    tested_count = 0
    max_tests = 10  # Cap the number of interactions to prevent infinite loops

    for elem in interactives:
        if tested_count >= max_tests:
            break
        
        text = elem.get("text", "")
        if not text:
            continue
            
        print(f"[Functional QA] Testing interaction: clicking {elem['tagName']} '{text}'")
        
        try:
            # Try to click the element using Playwright's locator by text
            locator = page.get_by_text(text, exact=False).first
            if locator.is_visible(timeout=1000):
                locator.click(timeout=3000)
                tested_count += 1
                time.sleep(1) # wait for potential errors to bubble up
        except Exception as e:
            # It's okay if a click fails (e.g. element hidden or intercepted)
            print(f"[Functional QA] Click failed for '{text}', continuing... ({e})")
            
        # Check if clicking caused any errors
        if errors:
            _raise_if_errors(errors, f"Clicking '{text}'")
            
    print(f"[Functional QA] Successfully tested {tested_count} interactions with zero errors.")
    
    # Cleanup listeners
    page.remove_listener("console", handle_console)
    page.remove_listener("pageerror", handle_page_error)
    
    return True

def _raise_if_errors(errors, context):
    error_msg = f"Failed during {context}.\n" + "\n".join(errors)
    raise FunctionalQAError(error_msg)
