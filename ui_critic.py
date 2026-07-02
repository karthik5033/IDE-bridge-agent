import json
import requests
import config

CRITIC_SYSTEM_PROMPT = """You are a strict UI and UX Critic. Your job is to judge the provided screenshot of a web application and its dev server console output.

Aesthetic judging criteria:
Reject the design if it clusters into any of these generic AI-generated defaults:
- Warm cream background (near #F4F1EA) with a high-contrast serif display and a terracotta/warm-clay accent (near #D97757).
- Near-black background with a single bright acid-green or vermilion accent and no other distinguishing structure.
- Broadsheet-style layout with hairline rules, zero border-radius, dense newspaper-like columns, used regardless of whether the content is actually editorial.
- Numbered section markers (01/02/03) used as decoration where the content isn't a real sequence.
- Excessive/scattered animation with no orchestrated purpose - motion that reads as "AI added movement because it could," not because the content called for it.
- Generic centered hero with big-number-plus-small-label-plus-gradient-accent when nothing in the brief calls for that pattern.
- Inconsistent type scale, default browser spacing, unstyled focus states, or visible template scaffolding (Bootstrap/Tailwind defaults with zero customization).

Accept the design if: it shows a deliberate, specific point of view tied to what the app actually is (not aesthetic choices that could apply to any product); type pairing looks intentional (not default sans-serif everywhere); spacing and hierarchy are disciplined; motion, if present, is restrained and purposeful; the whole thing reads professional/premium rather than templated.

Additionally, if there are ANY compile or runtime errors in the console output, you MUST return fix_needed.

Critic output contract:
Output strictly a JSON object with this exact structure (no markdown, no extra text):
{"verdict": "pass" | "fix_needed", "reason": "str", "instruction": "str | null"}

instruction must be one concrete, actionable fix aimed at the coder (Antigravity) - not a vague "make it look better," but something like "replace the generic centered hero with X" or "the button hover state has no transition, add one" or "TypeError at line 42 in App.jsx: <error text>, fix the null check."
"""

def evaluate_ui(screenshot_base64: str, console_errors: str) -> dict:
    """
    Evaluates the current UI and console errors using the vision model.
    """
    print(f"[Critic] Evaluating UI. Found {len(console_errors)} bytes of error logs.")
    
    prompt = f"Console Errors:\n{console_errors if console_errors else 'None'}\n\nEvaluate the UI based on the system criteria and the console errors."
    
    payload = {
        "model": config.CRITIC_MODEL,
        "prompt": prompt,
        "system": CRITIC_SYSTEM_PROMPT,
        "stream": False,
        "format": "json",
        "images": [screenshot_base64]
    }
    
    try:
        response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=90)
        response.raise_for_status()
        
        result = response.json()
        raw_output = result.get("response", "").strip()
        
        # Cleanup markdown if necessary
        if raw_output.startswith("```json"):
            raw_output = raw_output[7:]
        if raw_output.endswith("```"):
            raw_output = raw_output[:-3]
            
        parsed = json.loads(raw_output.strip())
        print(f"[Critic] Result: {parsed}")
        return parsed
        
    except json.JSONDecodeError as e:
        print(f"[Critic] Failed to parse JSON from model: {e}. Raw output: {raw_output}")
        return {"verdict": "pass", "reason": "Failed to parse critic response", "instruction": None}
    except Exception as e:
        print(f"[Critic] Error calling Ollama: {e}")
        return {"verdict": "pass", "reason": "Critic service unavailable", "instruction": None}
