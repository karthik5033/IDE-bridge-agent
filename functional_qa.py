"""
functional_qa.py — Automated interactive testing with intelligent error classification.

This module crawls the DOM, clicks interactive elements, and classifies
console messages as fatal (crash/block) vs. non-fatal (warnings/noise).
Only fatal errors trigger a fix cycle — non-fatal warnings are logged but tolerated.
"""

import time
import config
from bridge_logger import bprint as print

class FunctionalQAError(Exception):
    """Raised when the application fails functional QA (e.g., fatal console error)."""
    pass


def _classify_console_message(text: str) -> str:
    """Classifies a console message as 'fatal', 'warning', or 'ignore'.
    
    Priority: fatal patterns > ignore patterns > default to warning.
    """
    text_lower = text.lower()
    
    # Check fatal patterns first (these always trigger a fix)
    fatal_patterns = getattr(config, "QA_FATAL_PATTERNS", [])
    for pattern in fatal_patterns:
        if pattern.lower() in text_lower:
            return "fatal"
    
    # Check ignore patterns (these are silently swallowed)
    ignore_patterns = getattr(config, "QA_IGNORE_PATTERNS", [])
    for pattern in ignore_patterns:
        if pattern.lower() in text_lower:
            return "ignore"
    
    # Default: treat as a warning (logged but not fatal)
    return "warning"


def run_functional_qa(page, base_url):
    """
    Crawls interactive elements and monitors for errors.
    
    Error classification:
    - Fatal errors (TypeError, ReferenceError, etc.) → raise FunctionalQAError
    - Warnings (non-fatal console messages) → logged but tolerated
    - Ignored (hydration, HMR, favicon, etc.) → silently skipped
    
    Raises FunctionalQAError only if FATAL errors are encountered.
    """
    print("\n[Functional QA] Starting intelligent interactive testing...")
    
    fatal_errors = []
    warnings = []
    ignored_count = 0
    
    def handle_console(msg):
        nonlocal ignored_count
        if msg.type in ["error", "warning"]:
            classification = _classify_console_message(msg.text)
            if classification == "fatal":
                fatal_errors.append(f"Console {msg.type}: {msg.text}")
            elif classification == "warning":
                warnings.append(f"Console {msg.type}: {msg.text}")
            else:
                ignored_count += 1
                
    def handle_page_error(err):
        # Page errors (unhandled exceptions) are always fatal
        fatal_errors.append(f"Unhandled Exception: {err}")

    # Attach listeners
    page.on("console", handle_console)
    page.on("pageerror", handle_page_error)
    
    try:
        # Navigate to base URL (30s timeout for Next.js compilation)
        page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        if "interrupted by another navigation" not in str(e):
            raise FunctionalQAError(f"Failed to load application at {base_url}: {e}")

    # Give it a moment to render and fire initial errors
    time.sleep(2)
    
    if fatal_errors:
        _raise_with_context(fatal_errors, warnings, ignored_count, "Initial page load")

    # Discover interactive elements
    try:
        interactives = page.evaluate("""() => {
            const results = [];
            const elements = document.querySelectorAll('button:not([disabled]), a[href], [role="button"], input[type="submit"], input[type="button"]');
            for (const el of elements) {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden') {
                    const text = (el.innerText || el.value || '').trim().substring(0, 30);
                    if (text) {
                        results.push({
                            text: text,
                            tagName: el.tagName,
                            id: el.id || null,
                            className: (el.className || '').toString().substring(0, 50)
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
    max_tests = 10

    for elem in interactives:
        if tested_count >= max_tests:
            break
        
        text = elem.get("text", "")
        if not text:
            continue
        
        elem_id = f"{elem['tagName']}"
        if elem.get("id"):
            elem_id += f"#{elem['id']}"
        elif elem.get("className"):
            elem_id += f".{elem['className'].split()[0]}" if elem['className'] else ""
            
        print(f"[Functional QA] Testing: click {elem_id} '{text}'")
        
        try:
            locator = page.get_by_text(text, exact=False).first
            if locator.is_visible(timeout=1000):
                locator.click(timeout=3000)
                tested_count += 1
                time.sleep(1)  # Wait for potential errors to bubble up
        except Exception as e:
            print(f"[Functional QA] Click failed for '{text}', continuing... ({type(e).__name__})")
            
        # Check if clicking caused fatal errors
        if fatal_errors:
            _raise_with_context(
                fatal_errors, warnings, ignored_count,
                f"After clicking {elem_id} '{text}'"
            )

    # Final summary
    summary_parts = [f"✅ Tested {tested_count} interactions"]
    if warnings:
        summary_parts.append(f"⚠️  {len(warnings)} non-fatal warnings (tolerated)")
        for w in warnings[:3]:
            print(f"[Functional QA] Warning (tolerated): {w}")
    if ignored_count > 0:
        summary_parts.append(f"🔇 {ignored_count} messages ignored (noise)")
    
    print(f"[Functional QA] {' | '.join(summary_parts)}")
    
    # Cleanup listeners
    page.remove_listener("console", handle_console)
    page.remove_listener("pageerror", handle_page_error)
    
    return True


def _raise_with_context(fatal_errors, warnings, ignored_count, context):
    """Raises FunctionalQAError with rich context about what happened."""
    parts = [f"FATAL errors during: {context}"]
    parts.append(f"\n--- Fatal Errors ({len(fatal_errors)}) ---")
    for err in fatal_errors:
        parts.append(f"  ❌ {err}")
    
    if warnings:
        parts.append(f"\n--- Non-Fatal Warnings ({len(warnings)}) ---")
        for w in warnings[:5]:
            parts.append(f"  ⚠️  {w}")
        if len(warnings) > 5:
            parts.append(f"  ... and {len(warnings) - 5} more warnings")
    
    if ignored_count > 0:
        parts.append(f"\n(Also ignored {ignored_count} noise messages)")
    
    raise FunctionalQAError("\n".join(parts))
