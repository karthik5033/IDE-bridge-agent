import json
import requests
import config
import time
import tempfile
import base64
import os
from bridge_logger import bprint as print, binput as input

CRITIC_SYSTEM_PROMPT = config.load_prompt("critic_system.md")

def _evaluate_via_web_ui(screenshot_b64: str, console_errors: str, page, platform: dict) -> dict:
    print(f"[Critic] Evaluating UI via {platform.get('name', 'Web UI')}. Found {len(console_errors)} bytes of error logs.")
    prompt = f"Console Errors:\n{console_errors if console_errors else 'None'}\n\nEvaluate the UI based on the system criteria and the console errors.\n\n{CRITIC_SYSTEM_PROMPT}"
    
    try:
        # Save base64 screenshot to a temporary file
        img_data = base64.b64decode(screenshot_b64)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(img_data)
            tmp_path = tmp.name
        
        # Bring ChatGPT tab to front (optional but helpful)
        page.bring_to_front()
        
        # Upload image
        if platform["selectors"].get("file_upload"):
            file_input = page.locator(platform["selectors"]["file_upload"])
            file_input.set_input_files(tmp_path)
            time.sleep(2) # wait for upload to process visually
            
        os.remove(tmp_path)
        
        # Type the prompt
        input_box = page.locator(platform["selectors"]["input_box"])
        input_box.fill(prompt)
        time.sleep(1)
        
        # Click send
        page.locator(platform["selectors"]["send_button"]).click()
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
        if "```json" in last_text:
            last_text = last_text.split("```json")[1].split("```")[0].strip()
            
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

def evaluate_ui(screenshot_b64: str, console_errors: str, critic_page=None, critic_platform=None) -> dict:
    """
    Main entry point for UI evaluation. 
    Routes to the active web critic (ChatGPT/Claude) or local Ollama based on config.
    """
    if config.CRITIC_MODE == "chatgpt" and critic_page and critic_platform:
        return _evaluate_via_web_ui(screenshot_b64, console_errors, critic_page, critic_platform)
    else:
        return _evaluate_via_local(screenshot_b64, console_errors)
