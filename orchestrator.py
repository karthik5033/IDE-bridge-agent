import requests
import json
import config
from notifier import notify_phone
from bridge_logger import bprint as print, binput as input

import os

ORCHESTRATOR_SYSTEM = config.load_prompt("orchestrator_system.md")
KNOWLEDGE_FILE = "qwen_knowledge.txt"

# --- Verification prompt for dual-pass ---
VERIFICATION_PROMPT = """You previously classified a message with these results:
{classification}

The original message excerpt:
{excerpt}

VERIFY: Is this classification correct? Specifically:
- If is_error=true: Is there a REAL traceback/crash in the message, or was it a false positive?
- If is_question=true: Is the AI genuinely BLOCKED and waiting for human input, or is it just describing features?

Output a JSON object with:
1. "verified": true if the original classification is correct, false if it was a mistake
2. "corrected_is_error": the corrected value (true/false)
3. "corrected_is_question": the corrected value (true/false)  
4. "reasoning": brief explanation of your verification

Output ONLY valid JSON. No markdown. No ```json blocks.
"""


def _call_ollama(model: str, prompt: str, system: str = "", format_json: bool = True) -> dict | None:
    """Low-level Ollama call with JSON retry logic.
    
    Returns the parsed JSON dict, or None if all retries fail.
    """
    max_retries = getattr(config, "ORCHESTRATOR_MAX_JSON_RETRIES", 2)
    temperature = getattr(config, "ORCHESTRATOR_TEMPERATURE", 0.1)
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if system:
        payload["system"] = system
    if format_json:
        payload["format"] = "json"
    
    for attempt in range(1 + max_retries):
        try:
            response = requests.post(config.OLLAMA_URL, json=payload, timeout=90)
            response.raise_for_status()
            
            result = response.json()
            raw_output = result.get("response", "").strip()
            
            # Clean markdown wrappers
            if raw_output.startswith("```json"):
                raw_output = raw_output[7:]
            if raw_output.startswith("```"):
                raw_output = raw_output[3:]
            if raw_output.endswith("```"):
                raw_output = raw_output[:-3]
            raw_output = raw_output.strip()
            
            # Find JSON object boundaries
            start_idx = raw_output.find("{")
            end_idx = raw_output.rfind("}")
            if start_idx != -1 and end_idx > start_idx:
                raw_output = raw_output[start_idx:end_idx + 1]
            
            parsed = json.loads(raw_output)
            return parsed
            
        except json.JSONDecodeError as e:
            if attempt < max_retries:
                print(f"[Orchestrator] JSON parse failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                # Nudge the model to fix its JSON
                payload["prompt"] = (
                    f"Your previous response was not valid JSON. The error was: {e}\n"
                    f"Your raw output was: {raw_output[:500]}\n\n"
                    f"Please output ONLY a valid JSON object. No markdown, no extra text.\n\n"
                    f"Original request: {prompt[:1000]}"
                )
            else:
                print(f"[Orchestrator] JSON parse failed after {max_retries + 1} attempts: {e}")
                return None
                
        except requests.exceptions.ConnectionError:
            # Ollama not running — silently degrade
            return None
        except Exception as e:
            if "Connection" in str(e) or "404" in str(e):
                return None
            print(f"[Orchestrator] Error calling Ollama: {e}")
            return None
    
    return None


def _load_knowledge() -> str:
    """Loads Qwen's accumulated knowledge base."""
    if os.path.exists(KNOWLEDGE_FILE):
        with open(KNOWLEDGE_FILE, "r") as f:
            lines = f.readlines()
        # Return only the last 20 entries to keep context manageable
        recent = lines[-20:] if len(lines) > 20 else lines
        return "".join(recent)
    return ""


def _save_knowledge(update: str):
    """Appends a new fact to Qwen's knowledge base."""
    if update and update.strip():
        with open(KNOWLEDGE_FILE, "a") as f:
            f.write(f"- {update.strip()}\n")


def _verify_classification(classification: dict, original_text: str) -> dict:
    """Dual-pass verification: asks Qwen to re-check a high-stakes classification.
    
    Only called when is_error=true or is_question=true to reduce false positives.
    Returns the (potentially corrected) classification dict.
    """
    if not getattr(config, "ORCHESTRATOR_VERIFICATION_ENABLED", True):
        return classification
    
    # Only verify high-stakes signals
    if not classification.get("is_error") and not classification.get("is_question"):
        return classification
    
    excerpt = original_text[:2000] if len(original_text) > 2000 else original_text
    verification_prompt = VERIFICATION_PROMPT.format(
        classification=json.dumps({
            "is_error": classification.get("is_error"),
            "is_question": classification.get("is_question"),
            "error_evidence": classification.get("error_evidence"),
            "question_evidence": classification.get("question_evidence"),
        }, indent=2),
        excerpt=excerpt
    )
    
    print("[Orchestrator] Running dual-pass verification on high-stakes signal...")
    verified = _call_ollama(
        config.OLLAMA_MODELS["orchestrator"],
        verification_prompt,
        system="You are a careful signal verification agent. Check if a previous classification was correct.",
    )
    
    if verified and not verified.get("verified", True):
        print(f"[Orchestrator] Verification OVERRODE classification: {verified.get('reasoning', 'no reason given')}")
        classification["is_error"] = bool(verified.get("corrected_is_error", False))
        classification["is_question"] = bool(verified.get("corrected_is_question", False))
        # If we corrected a false positive, record it
        _save_knowledge(f"False positive corrected: {verified.get('reasoning', '')[:100]}")
    elif verified:
        print("[Orchestrator] Verification CONFIRMED classification.")
    else:
        print("[Orchestrator] Verification call failed; keeping original classification.")
    
    return classification


def analyze_message(text: str, system: str = ORCHESTRATOR_SYSTEM) -> dict:
    """
    POSTs to OLLAMA_URL to analyze the text for DONE, ERROR, or QUESTION signals.
    Returns a dictionary with 'is_done', 'is_error', 'is_question', and 'phase_tag'.
    
    Features:
    - Confidence gating: Only trusts flags when Qwen's confidence >= threshold
    - JSON retry: Retries malformed JSON up to N times
    - Dual-pass verification: Re-verifies error/question signals to prevent false positives
    - Knowledge integration: Passes accumulated knowledge to improve future classifications
    """
    # Truncate text if it's too long to save processing time
    truncated_text = text if len(text) < 4000 else text[:2000] + "\n...[truncated]...\n" + text[-2000:]
    
    # Load Qwen's accumulated knowledge
    knowledge = _load_knowledge()
    
    prompt = f"Analyze this message:\n\n{truncated_text}"
    if knowledge:
        prompt += f"\n\n--- YOUR KNOWLEDGE BASE (facts you've previously learned) ---\n{knowledge}"
    
    default_result = {"is_done": False, "is_error": False, "is_question": False, "phase_tag": "Unknown"}
    
    print(f"[Orchestrator] Analyzing message via {config.OLLAMA_MODELS['orchestrator']}...")
    parsed = _call_ollama(
        config.OLLAMA_MODELS["orchestrator"],
        prompt,
        system=system,
    )
    
    if parsed is None:
        return default_result
    
    print(f"[Orchestrator] Raw analysis: {json.dumps(parsed, indent=2)[:500]}")
    
    # --- Save knowledge updates ---
    knowledge_update = parsed.get("knowledge_update")
    if knowledge_update:
        print(f"[Orchestrator] Qwen learned: {knowledge_update}")
        _save_knowledge(knowledge_update)
    
    # --- Apply confidence gating ---
    threshold = getattr(config, "ORCHESTRATOR_CONFIDENCE_THRESHOLD", 0.7)
    
    # is_done: strictly codeword-based, never trust the LLM
    actual_is_done = "[BRIDGE_TERMINATE]" in text
    
    # is_error: must pass confidence gate AND have evidence
    raw_is_error = bool(parsed.get("is_error", False))
    error_confidence = float(parsed.get("error_confidence", 0.5))
    error_evidence = parsed.get("error_evidence")
    
    if raw_is_error:
        if error_confidence < threshold:
            print(f"[Orchestrator] is_error=true REJECTED (confidence {error_confidence:.2f} < {threshold})")
            raw_is_error = False
        elif not error_evidence:
            print(f"[Orchestrator] is_error=true REJECTED (no evidence provided)")
            raw_is_error = False
    
    # is_question: must pass confidence gate AND have evidence
    raw_is_question = bool(parsed.get("is_question", False))
    question_confidence = float(parsed.get("question_confidence", 0.5))
    question_evidence = parsed.get("question_evidence")
    
    if raw_is_question:
        if question_confidence < threshold:
            print(f"[Orchestrator] is_question=true REJECTED (confidence {question_confidence:.2f} < {threshold})")
            raw_is_question = False
        elif not question_evidence:
            print(f"[Orchestrator] is_question=true REJECTED (no evidence provided)")
            raw_is_question = False
    
    result = {
        "is_done": actual_is_done,
        "is_error": raw_is_error,
        "is_question": raw_is_question,
        "phase_tag": str(parsed.get("phase_tag", "Unknown")),
        "auto_answer": parsed.get("auto_answer"),
        "error_evidence": error_evidence if raw_is_error else None,
        "question_evidence": question_evidence if raw_is_question else None,
    }
    
    # --- Dual-pass verification for high-stakes signals ---
    if raw_is_error or raw_is_question:
        result = _verify_classification(result, text)
    
    print(f"[Orchestrator] Final result: is_done={result['is_done']}, is_error={result['is_error']}, "
          f"is_question={result['is_question']}, phase={result['phase_tag']}")
    
    return result


def summarize_error(error_text: str) -> str:
    """Uses the coder model to produce a structured, actionable error diagnosis.
    
    Returns a formatted fix instruction targeting only the root cause,
    with cascading errors identified for deduplication.
    """
    # Truncate to avoid blowing up context, but keep the ends where tracebacks live
    truncated_text = (
        error_text if len(error_text) < 4000
        else error_text[:1000] + "\n...[truncated]...\n" + error_text[-3000:]
    )
    
    system_prompt = config.load_prompt("error_summarizer.md")
    prompt = f"Here is the error output:\n\n{truncated_text}"
    
    print(f"[Orchestrator] Diagnosing error via {config.OLLAMA_MODELS['code_analyzer']}...")
    parsed = _call_ollama(
        config.OLLAMA_MODELS["code_analyzer"],
        prompt,
        system=system_prompt,
    )
    
    if parsed is None:
        return (
            f"Error detected, but couldn't diagnose (Ollama unavailable).\n\n"
            f"Raw error snippet:\n{truncated_text[-500:]}"
        )
    
    # Build a structured fix instruction
    error_type = parsed.get("error_type", "unknown")
    file_loc = parsed.get("file", "unknown file")
    line_loc = parsed.get("line", "?")
    root_cause = parsed.get("root_cause", "Unknown error")
    fix = parsed.get("fix", "Investigate and fix the error")
    cascading = parsed.get("cascading_errors", [])
    confidence = parsed.get("confidence", 0.5)
    prevention = parsed.get("prevention_hint")
    
    summary_parts = [
        f"🔍 Error Diagnosis (confidence: {confidence:.0%})",
        f"   Type: {error_type}",
        f"   Location: {file_loc}:{line_loc}",
        f"   Root Cause: {root_cause}",
        f"",
        f"🔧 Fix Instruction:",
        f"   {fix}",
    ]
    
    if cascading:
        summary_parts.append(f"")
        summary_parts.append(f"⚡ Cascading errors (will auto-resolve with root fix):")
        for ce in cascading[:5]:
            summary_parts.append(f"   - {ce}")
    
    if prevention:
        summary_parts.append(f"")
        summary_parts.append(f"💡 Prevention: {prevention}")
    
    summary = "\n".join(summary_parts)
    print(f"[Orchestrator] Diagnosis:\n{summary}")
    
    # Record the error pattern in knowledge for future reference
    _save_knowledge(f"Error pattern: {error_type} in {file_loc} — {root_cause[:80]}")
    
    return summary


def compress_history(history: str) -> str:
    """Uses the orchestrator model to compress conversation history into a structured summary.
    
    Preserves critical context: file names, error resolutions, and remaining work.
    """
    if len(history) < 2000:
        return history  # Don't bother compressing short histories
        
    prompt = config.load_prompt("compression.md", history=history)
    
    print(f"[Orchestrator] Compressing history (current size: {len(history)} chars)...")
    # Use plain text format, not JSON
    parsed = _call_ollama(
        config.OLLAMA_MODELS["orchestrator"],
        prompt,
        format_json=False,
    )
    
    if parsed is None:
        # _call_ollama returns None on failure; for non-JSON mode, let's call directly
        try:
            payload = {
                "model": config.OLLAMA_MODELS["orchestrator"],
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1},
            }
            response = requests.post(config.OLLAMA_URL, json=payload, timeout=90)
            response.raise_for_status()
            result = response.json()
            compressed = result.get("response", "").strip()
            print(f"[Orchestrator] History compressed: {len(history)} → {len(compressed)} chars.")
            return compressed
        except Exception as e:
            if "Connection" not in str(e) and "404" not in str(e):
                print(f"[Orchestrator] Error compressing history: {e}")
            return history
    
    # If _call_ollama somehow returned a dict (shouldn't for non-JSON), stringify it
    if isinstance(parsed, dict):
        compressed = json.dumps(parsed)
    else:
        compressed = str(parsed)
    
    print(f"[Orchestrator] History compressed: {len(history)} → {len(compressed)} chars.")
    return compressed
