"""
page_explorer.py — Smart page exploration for the UI Critic.

Instead of taking one static screenshot, this module:
1. Takes a full-page screenshot (scrolling the entire page height)
2. Discovers internal routes from <a> tags and navigates to each
3. Finds interactive elements (buttons, tabs, accordions) and clicks them
4. Captures a labeled screenshot after each action
5. Stitches everything into one composite image for the critic
"""

import time
import io
import base64
from urllib.parse import urlparse, urljoin
from PIL import Image, ImageDraw, ImageFont
from bridge_logger import bprint as print, binput as input
import config


def _get_limits():
    """Read exploration limits from config."""
    return (
        getattr(config, 'EXPLORER_MAX_SCREENSHOTS', 8),
        getattr(config, 'EXPLORER_MAX_ROUTES', 4),
        getattr(config, 'EXPLORER_MAX_INTERACTIONS', 3),
    )


def _safe_screenshot(page, full_page=False, label=""):
    """Takes a screenshot, returns (label, PIL.Image) or None on failure."""
    try:
        raw = page.screenshot(type="jpeg", quality=70, full_page=full_page)
        img = Image.open(io.BytesIO(raw))
        return (label, img)
    except Exception as e:
        print(f"[Explorer] Screenshot failed ({label}): {e}")
        return None


def _discover_routes(page, base_url):
    """Finds internal navigation links on the page."""
    try:
        links = page.evaluate("""() => {
            const anchors = document.querySelectorAll('a[href]');
            const results = [];
            const seen = new Set();
            for (const a of anchors) {
                const href = a.getAttribute('href');
                const text = a.innerText.trim().substring(0, 40);
                if (!href) continue;
                // Skip external links, anchors, javascript, mailto
                if (href.startsWith('http') && !href.startsWith(window.location.origin)) continue;
                if (href.startsWith('#') || href.startsWith('javascript:') || href.startsWith('mailto:')) continue;
                // Normalize
                const full = new URL(href, window.location.origin).pathname;
                if (seen.has(full) || full === window.location.pathname) continue;
                seen.add(full);
                results.push({href: full, text: text || full});
            }
            return results;
        }""")
        return links or []
    except Exception as e:
        print(f"[Explorer] Route discovery failed: {e}")
        return []


def _discover_interactive_elements(page):
    """Finds clickable elements worth testing (buttons, tabs, dropdowns)."""
    try:
        elements = page.evaluate("""() => {
            const results = [];
            const seen = new Set();
            
            // Buttons (not submit, not hidden)
            const buttons = document.querySelectorAll('button:not([type="submit"]):not([disabled])');
            for (const btn of buttons) {
                const rect = btn.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;
                const style = window.getComputedStyle(btn);
                if (style.display === 'none' || style.visibility === 'hidden') continue;
                const text = btn.innerText.trim().substring(0, 30);
                if (!text || seen.has(text)) continue;
                // Skip navigation-like buttons (they're handled by route discovery)
                if (btn.closest('nav') || btn.closest('header')) continue;
                seen.add(text);
                results.push({
                    selector: `button:has-text("${text}")`,
                    text: text,
                    type: 'button'
                });
            }
            
            // Tabs (role="tab")
            const tabs = document.querySelectorAll('[role="tab"]:not([aria-selected="true"])');
            for (const tab of tabs) {
                const rect = tab.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;
                const text = tab.innerText.trim().substring(0, 30);
                if (!text || seen.has(text)) continue;
                seen.add(text);
                results.push({
                    selector: `[role="tab"]:has-text("${text}")`,
                    text: text,
                    type: 'tab'
                });
            }
            
            // Accordion / details elements
            const details = document.querySelectorAll('details:not([open]) > summary');
            for (const summary of details) {
                const text = summary.innerText.trim().substring(0, 30);
                if (!text || seen.has(text)) continue;
                seen.add(text);
                results.push({
                    selector: `summary:has-text("${text}")`,
                    text: text,
                    type: 'accordion'
                });
            }
            
            return results;
        }""")
        return elements or []
    except Exception as e:
        print(f"[Explorer] Interactive element discovery failed: {e}")
        return []


def _add_label_to_image(img, label):
    """Adds a labeled banner at the top of an image."""
    banner_height = 32
    new_img = Image.new("RGB", (img.width, img.height + banner_height), (30, 30, 30))
    draw = ImageDraw.Draw(new_img)
    
    # Use default font (always available)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
    
    draw.text((10, 6), label, fill=(255, 255, 100), font=font)
    new_img.paste(img, (0, banner_height))
    return new_img


def stitch_screenshots(screenshots):
    """
    Stitches a list of (label, PIL.Image) into one tall composite image.
    Returns (composite_b64, composite_bytes).
    """
    if not screenshots:
        return "", None

    labeled = []
    for label, img in screenshots:
        labeled.append(_add_label_to_image(img, label))

    # Calculate total dimensions
    max_width = max(img.width for img in labeled)
    total_height = sum(img.height for img in labeled)

    # Create composite
    composite = Image.new("RGB", (max_width, total_height), (20, 20, 20))
    y_offset = 0
    for img in labeled:
        composite.paste(img, (0, y_offset))
        y_offset += img.height

    # Scale down if too large (ChatGPT has limits)
    max_dim = 4000
    if composite.height > max_dim:
        ratio = max_dim / composite.height
        new_w = int(composite.width * ratio)
        composite = composite.resize((new_w, max_dim), Image.LANCZOS)

    # Export
    buf = io.BytesIO()
    composite.save(buf, format="JPEG", quality=75)
    composite_bytes = buf.getvalue()
    composite_b64 = base64.b64encode(composite_bytes).decode("utf-8")
    
    return composite_b64, composite_bytes


def explore_page(dev_page, base_url="http://localhost:3000"):
    """
    Smart page exploration. Scrolls, navigates routes, clicks interactive
    elements, and collects labeled screenshots.
    
    Returns: list of (label, PIL.Image)
    """
    MAX_SCREENSHOTS, MAX_ROUTES, MAX_INTERACTIONS = _get_limits()
    screenshots = []
    starting_url = dev_page.url
    
    print(f"[Explorer] Starting smart exploration of {starting_url}")
    
    # --- Step 1: Full-page screenshot of current view ---
    result = _safe_screenshot(dev_page, full_page=True, label=f"Full Page: {dev_page.url}")
    if result:
        screenshots.append(result)
        print(f"[Explorer] Captured full-page screenshot ({result[1].width}x{result[1].height})")
    
    # --- Step 2: Discover and visit internal routes ---
    routes = _discover_routes(dev_page, base_url)
    print(f"[Explorer] Found {len(routes)} internal routes")
    
    visited = 0
    for route in routes[:MAX_ROUTES]:
        if len(screenshots) >= MAX_SCREENSHOTS:
            break
        try:
            target_url = urljoin(base_url, route["href"])
            print(f"[Explorer] Navigating to: {route['href']} ({route['text']})")
            dev_page.goto(target_url, wait_until="networkidle", timeout=8000)
            time.sleep(1)
            
            result = _safe_screenshot(
                dev_page, full_page=True,
                label=f"Route: {route['href']} ({route['text']})"
            )
            if result:
                screenshots.append(result)
                visited += 1
        except Exception as e:
            print(f"[Explorer] Failed to visit {route['href']}: {e}")
    
    print(f"[Explorer] Visited {visited} routes")
    
    # --- Step 3: Go back to starting page for interactions ---
    try:
        dev_page.goto(starting_url, wait_until="networkidle", timeout=8000)
        time.sleep(1)
    except Exception as e:
        print(f"[Explorer] Failed to return to starting page: {e}")
        # Try one more time with domcontentloaded (less strict)
        try:
            dev_page.goto(starting_url, wait_until="domcontentloaded", timeout=8000)
            time.sleep(1)
        except Exception:
            print(f"[Explorer] Could not recover starting page. Returning collected screenshots.")
            return screenshots
    
    # --- Step 4: Click interactive elements and capture results ---
    interactives = _discover_interactive_elements(dev_page)
    print(f"[Explorer] Found {len(interactives)} interactive elements")
    
    clicked = 0
    for elem in interactives[:MAX_INTERACTIONS]:
        if len(screenshots) >= MAX_SCREENSHOTS:
            break
        try:
            locator = dev_page.locator(elem["selector"]).first
            if locator.is_visible():
                print(f"[Explorer] Clicking: {elem['text']} ({elem['type']})")
                locator.click(timeout=3000)
                time.sleep(1.5)  # wait for animation/state change
                
                result = _safe_screenshot(
                    dev_page, full_page=False,
                    label=f"After clicking {elem['type']}: '{elem['text']}'"
                )
                if result:
                    screenshots.append(result)
                    clicked += 1
        except Exception as e:
            print(f"[Explorer] Failed to click {elem['text']}: {e}")
    
    print(f"[Explorer] Clicked {clicked} interactive elements")
    
    # --- Step 5: Go back to starting page to leave it clean ---
    try:
        dev_page.goto(starting_url, wait_until="networkidle", timeout=8000)
    except Exception:
        # Fallback with less strict wait
        try:
            dev_page.goto(starting_url, wait_until="domcontentloaded", timeout=8000)
        except Exception:
            print(f"[Explorer] Warning: Could not return to starting page after exploration.")
    
    print(f"[Explorer] Exploration complete. Captured {len(screenshots)} screenshots total.")
    return screenshots
