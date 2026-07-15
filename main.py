import sys
import traceback
import config
import time
import webbrowser
from bridge_logger import bprint as print, binput as input
from checkpoint import save_checkpoint, load_checkpoint, clear_checkpoint
from notifier import notify_phone
from orchestrator import analyze_message, summarize_error, compress_history
from antigravity_driver import (
    get_antigravity_window,
    send_to_antigravity,
    wait_for_antigravity_response,
)
from chat_driver import send_to_chat_ui, wait_for_chat_response, RateLimitDetected
from playwright.sync_api import sync_playwright
import base64
import os
from dev_server import DevServerManager
from ui_critic import evaluate_ui, capture_page_context
from functional_qa import run_functional_qa, FunctionalQAError


def _is_question_response(text: str, analysis: dict = None) -> bool:
    """Detects if a chat response is asking a question instead of giving a command."""
    # Check orchestrator signal first
    if analysis and analysis.get("is_question"):
        return True
    
    # Rely purely on the orchestrator's LLM analysis (which uses chain-of-thought).
    # Brittle regex/substring fallbacks here were causing major false positives on project briefs.
    return False


def _load_design_library():
    """Loads all design library files and concatenates them into a prompt section."""
    library_dir = os.path.join(os.path.dirname(__file__), "design_library")
    sections = []
    if os.path.exists(library_dir):
        for root, dirs, files in os.walk(library_dir):
            for fname in sorted(files):
                filepath = os.path.join(root, fname)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                relative = os.path.relpath(filepath, library_dir)
                sections.append(f"### {relative}\n{content}")
    return "\n\n---\n\n".join(sections)


def _send_to_chat_with_retry(page, text: str, platform: dict = None) -> str:
    """Helper to send a message to Chat UI and get response, handling rate limits."""
    while True:
        try:
            # ============================================================
            # PHASE 1: Architect Master Plan (Claude)
            # ============================================================
            if phase == 1:
                print("\n" + "="*50)
                print("  Phase 1: Architect Master Plan (Claude)")
                print("="*50)
                
                design_system = _load_design_library()
                phase1_prompt = config.load_prompt("phase1_architect.md", design_system=design_system, initial_task=initial_task)
                
                print("Asking Claude to generate master plan...")
                chat_response = _send_to_chat_with_retry(pages[architect_name], phase1_prompt, platform=config.CHAT_PLATFORMS[architect_name])
                
                project_brief = chat_response
                print(f"\n--- Master Plan Received ({len(project_brief)} chars) ---")
                print(project_brief[:500] + "..." if len(project_brief) > 500 else project_brief)
                print("---------------------------------------------------\n")
                
                phase = 2
                current_payload = chat_response
                save_checkpoint(turn, history_summary, phase, current_payload, "architect", project_brief=project_brief)

            # ============================================================
            # CONTINUOUS ITERATIVE LOOP (Phases 2 & 3)
            # ============================================================
            while turn < config.MAX_TURNS:
                if getattr(config, "STOP_REQUESTED", False):
                    print("\n[System] Stop requested! Gracefully pausing bridge...")
                    config.STOP_REQUESTED = False
                    save_checkpoint(turn, history_summary, phase, current_payload, "critic", project_brief=project_brief)
                    print("[System] Agent gracefully stopped.")
                    break
                    
                # Phase 2: Claude provides step, Antigravity executes
                if phase == 2:
                    print("\n" + "="*50)
                    print(f"  Phase 2: Generating Next Step (Turn {turn})")
                    print("="*50)
                    
                    next_step_prompt = config.load_prompt("architect_next_step.md", context=history_summary)
                    chat_response = _send_to_chat_with_retry(pages[architect_name], next_step_prompt, platform=config.CHAT_PLATFORMS[architect_name])
                    
                    if "PROJECT_COMPLETE" in chat_response:
                        print("\n[Orchestrator] Claude declared PROJECT_COMPLETE! Application is fully built.")
                        exited_cleanly = True
                        break
                        
                    print(f"\n--- Next Step Instruction ({len(chat_response)} chars) ---")
                    print(chat_response[:500] + "..." if len(chat_response) > 500 else chat_response)
                    
                    phase2_prompt = config.load_prompt("phase2_builder.md", master_plan=project_brief, brief=chat_response)
                    
                    print("Sending step to Antigravity...")
                    ag_win.set_focus()
                    send_to_antigravity(ag_win, phase2_prompt)
                    ag_response = wait_for_antigravity_response(ag_win)
                    
                    print(f"\n--- Antigravity Build Report ({len(ag_response)} chars) ---")
                    
                    current_payload = ag_response
                    history_summary += f"\n--- Turn {turn} (Execution) ---\n{ag_response[:500]}\n"
                    
                    phase = 3
                    critic_retry_count = 0
                    escalation_count = 0
                    save_checkpoint(turn, history_summary, phase, current_payload, "critic", project_brief=project_brief)

                # Phase 3: Critic Evaluation
                if phase == 3:
                    print(f"\n{'='*50}")
                    print(f"  Phase 3: Critic Evaluation (Turn {turn})")
                    print(f"{'='*50}")
                    
                    min_critic_turn = getattr(config, "MIN_CRITIC_TURN", 1)
                    if turn < min_critic_turn:
                        print(f"[Critic] Skipping evaluation (Turn {turn} < {min_critic_turn}).")
                        critic_result = {"verdict": "pass"}
                    else:
                        # Functional QA
                        qa_failed = False
                        qa_error_msg = ""
                        try:
                            run_functional_qa(dev_page, f"http://localhost:{config.DEV_SERVER_PORT}")
                        except Exception as qa_err:
                            qa_failed = True
                            qa_error_msg = str(qa_err)
                            
                        # Browser + Dev Server Errors
                        new_dev_errors = dev_server.get_new_errors()
                        browser_errs_str = "\n".join(browser_console_errors)
                        browser_console_errors.clear()
                        
                        combined_errors = ""
                        if new_dev_errors: combined_errors += f"Dev Server Errors:\n{new_dev_errors}\n"
                        if browser_errs_str: combined_errors += f"Browser Console Errors:\n{browser_errs_str}\n"
                        
                        try:
                            screenshot_b64, screenshot_bytes, dom_summary = capture_page_context(dev_page)
                        except Exception as ctx_err:
                            screenshot_b64, screenshot_bytes, dom_summary = "", None, ""
                            
                        if qa_failed:
                            critic_result = {
                                "verdict": "fix_needed", 
                                "reason": "Functional QA failed.", 
                                "instruction": f"Fix the following errors:\n{qa_error_msg}"
                            }
                        elif config.CRITIC_TRIGGER == "error_or_bad_ui":
                            try:
                                critic_result = evaluate_ui(
                                    screenshot_b64, screenshot_bytes, dom_summary, combined_errors,
                                    critic_page=pages[critic_name],
                                    critic_platform=config.CHAT_PLATFORMS[critic_name]
                                )
                            except Exception as eval_err:
                                critic_result = {"verdict": "pass", "reason": f"Critic error: {eval_err}"}
                        else:
                            critic_result = {"verdict": "pass"}
                    
                    if critic_result.get("verdict") == "fix_needed":
                        critic_retry_count += 1
                        if critic_retry_count >= config.CRITIC_RETRY_CAP:
                            escalation_count += 1
                            if escalation_count >= 2:
                                print("[Critic] Multiple escalations. Terminating loop.")
                                exited_cleanly = True
                                break
                                
                            escalation_msg = (
                                f"The UI Critic failed {config.CRITIC_RETRY_CAP} times.\n"
                                f"Provide a single fix instruction for Antigravity."
                            )
                            chat_response = _send_to_chat_with_retry(pages[architect_name], escalation_msg, platform=config.CHAT_PLATFORMS[architect_name])
                            current_payload = chat_response
                            critic_retry_count = 0
                            
                            ag_win.set_focus()
                            send_to_antigravity(ag_win, current_payload)
                            ag_response = wait_for_antigravity_response(ag_win)
                            current_payload = ag_response
                            history_summary += f"\n--- Turn {turn} (Escalation) ---\n{ag_response[:500]}\n"
                        else:
                            instruction = critic_result.get('instruction', 'Fix visual issues.')
                            reason = critic_result.get('reason', '')
                            fix_prompt = f"UI Critic Feedback:\nReason: {reason}\nInstruction: {instruction}\nFix this issue."
                            
                            ag_win.set_focus()
                            send_to_antigravity(ag_win, fix_prompt)
                            ag_response = wait_for_antigravity_response(ag_win)
                            current_payload = ag_response
                            history_summary += f"\n--- Turn {turn} (Critic Fix) ---\n{ag_response[:500]}\n"
                    else:
                        print("[Critic] Verdict: PASS. Step complete! Requesting next step...")
                        phase = 2  # Go back to Claude for the next step!
                        
                    turn += 1
                    if turn % 5 == 0:
                        history_summary = compress_history(history_summary)

        except KeyboardInterrupt:
            print("\n\nInterrupted by user (Ctrl+C). Saving checkpoint...")
            save_checkpoint(turn, history_summary, phase, current_payload, "critic", project_brief=project_brief)
            notify_phone("User interrupted the bridge loop.", "Bridge Stopped")

        except Exception as e:
            print(f"\nFatal error in main loop: {e}")
            traceback.print_exc()
            notify_phone(f"Unhandled exception: {e}", "Bridge Error")

        finally:
            print("Stopping Dev Server...")
            dev_server.stop()
            print("Disconnecting from Chrome...")
            browser.close()

            if exited_cleanly:
                clear_checkpoint()
                notify_phone("Loop finished cleanly.", "Bridge Finished")
                print("Task finished cleanly.")
            else:
                print("Task did not finish cleanly. Checkpoint preserved for resume.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        task = input("Enter the initial task for the agent: ").strip()

    if not task:
        print("No task provided. Exiting.")
        sys.exit(1)

    try:
        run_bridge(task)
    except KeyboardInterrupt:
        print("\nAborted.")
    except Exception as main_e:
        print(f"Script aborted: {main_e}")
        traceback.print_exc()
