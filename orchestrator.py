import requests
import json
import config
from notifier import notify_phone
from bridge_logger import bprint as print, binput as input

ORCHESTRATOR_SYSTEM = config.load_prompt("orchestrator_system.md")

def analyze_message(text: str, system: str = ORCHESTRATOR_SYSTEM) -> dict:
    """
    POSTs to OLLAMA_URL to analyze the text for DONE or ERROR signals.
    Returns a dictionary with 'is_done', 'is_error', and 'phase_tag'.
    """
    # Truncate text if it's too long to save processing time
    truncated_text = text if len(text) < 4000 else text[:2000] + "\n...[truncated]...\n" + text[-2000:]
    
    payload = {
        "model": config.OLLAMA_MODELS["orchestrator"],
        "prompt": f"Analyze this message:\n\n{truncated_text}",
        "system": system,
        "stream": False,
        "format": "json" # Force JSON output if supported by model
    }
    
    default_result = {"is_done": False, "is_error": False, "phase_tag": "Unknown"}
    
    try:
        print(f"[Orchestrator] Analyzing message via {config.OLLAMA_MODELS['orchestrator']}...")
        response = requests.post(config.OLLAMA_URL, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        raw_output = result.get("response", "").strip()
        
        # Clean up in case model wrapped in markdown
        if raw_output.startswith("```json"):
            raw_output = raw_output[7:]
        if raw_output.endswith("```"):
            raw_output = raw_output[:-3]
            
        parsed = json.loads(raw_output.strip())
        print(f"[Orchestrator] Analysis result: {parsed}")
        
        # We explicitly override the LLM's is_done guess with a strict codeword check
        actual_is_done = "[BRIDGE_TERMINATE]" in text
        
        # Safeguard against the LLM's false positive error detection
        actual_is_error = bool(parsed.get("is_error", False))
        if actual_is_error:
            if "Traceback" not in text and "Error:" not in text and "Exception:" not in text and "ERR!" not in text:
                actual_is_error = False

        # Ensure fallback fields
        # Detect if the AI is asking a question instead of giving a command
        is_question = bool(parsed.get("is_question", False))
        # Heuristic fallback: catch common question patterns the LLM might miss
        question_patterns = [
            "which do you prefer", "would you like", "should i", "do you want",
            "continue or start", "option 1", "option 2", "select one",
            "choose from", "pick one", "what would you", "shall i",
            "before i proceed", "before we begin", "quick check",
            "is this task a continuation"
        ]
        text_lower = text.lower()
        if any(pat in text_lower for pat in question_patterns):
            is_question = True

        return {
            "is_done": actual_is_done,
            "is_error": actual_is_error,
            "is_question": is_question,
            "phase_tag": str(parsed.get("phase_tag", "Unknown"))
        }
        
    except json.JSONDecodeError as e:
        print(f"[Orchestrator] Failed to parse JSON from model: {e}")
        return default_result
    except Exception as e:
        # We don't want to crash the whole bridge if analysis fails, just return defaults
        if "Connection" in str(e) or "404" in str(e):
             # Silently degrade if Ollama is not running to avoid spamming the console
             pass
        else:
             print(f"[Orchestrator] Error calling Ollama: {e}")
        return default_result

def summarize_error(error_text: str) -> str:
    """Uses the coder model to produce a concise, actionable error summary."""
    # Truncate to avoid blowing up context, but keep the ends where tracebacks live
    truncated_text = error_text if len(error_text) < 4000 else error_text[:1000] + "\n...[truncated]...\n" + error_text[-3000:]
    
    payload = {
        "model": config.OLLAMA_MODELS["code_analyzer"],
        "prompt": f"Here is the error output:\n\n{truncated_text}",
        "system": config.load_prompt("error_summarizer.md"),
        "stream": False,
        "format": "json"
    }
    
    try:
        print(f"[Orchestrator] Summarizing error via {config.OLLAMA_MODELS['code_analyzer']}...")
        response = requests.post(config.OLLAMA_URL, json=payload, timeout=90)
        response.raise_for_status()
        
        result = response.json()
        raw_output = result.get("response", "").strip()
        
        if raw_output.startswith("```json"):
            raw_output = raw_output[7:]
        if raw_output.endswith("```"):
            raw_output = raw_output[:-3]
            
        parsed = json.loads(raw_output.strip())
        summary = f"Error detected: {parsed.get('root_cause', 'Unknown Error')}\nFix: {parsed.get('fix', 'Unknown fix')}"
        print(f"[Orchestrator] Summary generated:\n{summary}")
        return summary
    except Exception as e:
        if "Connection" in str(e) or "404" in str(e):
            return f"Error detected, but couldn't summarize because Ollama is down.\n\nRaw error snippet:\n{truncated_text[-500:]}"
        print(f"[Orchestrator] Error summarizing error trace: {e}")
        return f"Error detected, but failed to summarize: {e}\n\nRaw error snippet:\n{truncated_text[-500:]}"

def compress_history(history: str) -> str:
    """Uses the orchestrator model to compress conversation history and prevent context bloat."""
    if len(history) < 2000:
        return history # Don't bother compressing short histories
        
    prompt = config.load_prompt("compression.md", history=history)
    
    payload = {
        "model": config.OLLAMA_MODELS["orchestrator"],
        "prompt": prompt,
        "stream": False
    }
    
    try:
        print(f"[Orchestrator] Compressing history (current size: {len(history)} chars)...")
        response = requests.post(config.OLLAMA_URL, json=payload, timeout=90)
        response.raise_for_status()
        
        result = response.json()
        compressed = result.get("response", "").strip()
        print(f"[Orchestrator] History compressed to {len(compressed)} chars.")
        return compressed
    except Exception as e:
        if "Connection" in str(e) or "404" in str(e):
            pass
        else:
            print(f"[Orchestrator] Error compressing history: {e}")
        return history # Return original on failure
