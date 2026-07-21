import sys
import traceback
import config
import time
import webbrowser
from bridge_logger import bprint as print, binput as input
from checkpoint import save_checkpoint, load_checkpoint, clear_checkpoint, git_commit_state, git_rollback_state
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


def _load_builder_memory():
    """Loads the accumulated lessons learned from previous critic rejections."""
    memory_path = os.path.join(os.path.dirname(__file__), "builder_memory.txt")
    if os.path.exists(memory_path):
        with open(memory_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "No previous mistakes recorded yet. Keep up the good work!"

def _save_builder_memory(reason: str, instruction: str):
    """Appends a critic rejection to the builder's long-term memory."""
    memory_path = os.path.join(os.path.dirname(__file__), "builder_memory.txt")
    
    # Read existing
    lines = []
    if os.path.exists(memory_path):
        with open(memory_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
    # Append new lesson
    new_lesson = f"- REJECTED: {reason} -> FIX: {instruction}\n"
    lines.append(new_lesson)
    
    # Keep only the last 10 lessons to prevent context bloat
    if len(lines) > 10:
        lines = lines[-10:]
        
    with open(memory_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def _send_to_chat_with_retry(page, text, platform="gemini"):
    """Helper to send a message to Chat UI and get response, handling rate limits."""
    while True:
        try:
            send_to_chat_ui(page, text, platform=platform)
            return wait_for_chat_response(page, text, platform=platform)
        except RateLimitDetected as e:
            notify_phone(f"Rate limit hit: {e.phrase}", "Bridge Paused")
            print(f"\n!! Rate limit detected: {e.phrase}")
            input(
                "Switch accounts or wait for the limit to reset, "
                "then press Enter to retry sending..."
            )
            page.reload(wait_until="domcontentloaded")
            continue


def run_bridge(initial_task: str, resume_override: bool = None):
    """Main bridge loop: Brief → Build → Critic fix loop.
    
    Phase 1: Claude produces a comprehensive project brief (one shot).
    Phase 2: Antigravity builds the entire app from the brief (one shot).
    Phase 3: Critic evaluates → fixes go directly to Antigravity (no Claude).
             Claude only re-enters if critic escalates after repeated failures.
    """
    # CRITICAL: When called from a worker thread (dashboard's threading.Thread),
    # the thread starts on the process's default non-interactive desktop.
    # Switch to the interactive input desktop so we can find and control windows.
    import ctypes
    _u32 = ctypes.windll.user32
    _hd = _u32.OpenInputDesktop(0, False, 0x10000000)  # GENERIC_ALL
    if _hd:
        _u32.SetThreadDesktop(_hd)

    print("=" * 50)
    print("  Bridge Agent Starting")
    print("=" * 50)

    config.STOP_REQUESTED = False
    config.check_config()
    start_fresh = False
    chk = load_checkpoint()
    if chk:
        print(f"\nFound checkpoint from turn {chk.get('turn', 0)}, phase {chk.get('phase', 1)}.")
        if resume_override is not None:
            ans = "y" if resume_override else "n"
        else:
            ans = input("Resume from checkpoint? (y/n): ").strip().lower()
            
        if ans in ("y", "yes"):
            turn = chk.get("turn", 0)
            phase = chk.get("phase", 1)
            history_summary = chk.get("history_summary", "")
            current_payload = chk.get("current_payload", "")
            project_brief = chk.get("project_brief", "")
            print("Resuming from checkpoint...")
        else:
            print("Starting fresh...")
            start_fresh = True
    else:
        start_fresh = True

    if start_fresh:
        turn = 0
        phase = 1
        history_summary = ""
        current_payload = ""
        project_brief = ""

    print("\nStarting Dev Server Manager...")
    dev_server = DevServerManager(config.DEV_SERVER_CMD, config.DEV_SERVER_CWD, config.DEV_SERVER_PORT)
    dev_server.start()

    print("\nConnecting to Chrome via CDP...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(config.CHROME_CDP_URL)
        except Exception as e:
            print(f"\nFailed to connect to Chrome: {e}")
            return

        # Find the Claude tab
        page = None
        for ctx in browser.contexts:
            for pg in ctx.pages:
                if "claude.ai" in pg.url:
                    page = pg
                    break
            if page:
                break

        if page:
            print(f"Connected to chat tab: {page.url}")
            if start_fresh:
                print("Starting fresh... Navigating to New Chat for Claude.")
                page.goto(config.CHAT_PLATFORMS["claude"]["url"], wait_until="domcontentloaded")
        else:
            print(f"No chat tab found. Opening {config.CHAT_PLATFORMS['claude']['url']}...")
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            page = ctx.new_page()
            page.goto(config.CHAT_PLATFORMS["claude"]["url"], wait_until="domcontentloaded")

        chatgpt_page = None
        if getattr(config, "CRITIC_MODE", "local") == "chatgpt":
            print("Finding or opening ChatGPT Critic tab...")
            for ctx in browser.contexts:
                for pg in ctx.pages:
                    if "chatgpt.com" in pg.url and pg != page:
                        chatgpt_page = pg
                        break
                if chatgpt_page:
                    break
            
            needs_init = False
            if chatgpt_page:
                if start_fresh:
                    print("Starting fresh... Navigating to New Chat for ChatGPT.")
                    chatgpt_page.goto(config.CHAT_PLATFORMS["chatgpt"]["url"], wait_until="domcontentloaded")
                    needs_init = True
            else:
                ctx = browser.contexts[0] if browser.contexts else browser.new_context()
                chatgpt_page = ctx.new_page()
                chatgpt_page.goto(config.CHAT_PLATFORMS["chatgpt"]["url"], wait_until="domcontentloaded")
                needs_init = True

            # Initialize ChatGPT with design system and critic rules
            if needs_init:
                print("[Critic] Initializing ChatGPT with design system and critic rules...")
                design_system = _load_design_library()
                critic_init_prompt = config.load_prompt("chatgpt_critic_init.md", design_system=design_system)
                try:
                    time.sleep(3)  # Wait for ChatGPT page to fully load
                    init_response = _send_to_chat_with_retry(chatgpt_page, critic_init_prompt, platform=config.CHAT_PLATFORMS["chatgpt"])
                    print(f"[Critic] ChatGPT initialized. Response: {init_response[:200]}")
                except Exception as e:
                    print(f"[Critic] Warning: ChatGPT init failed ({e}). Will still attempt evaluations.")

        pages = {"claude": page, "chatgpt": chatgpt_page}
        architect_name = "claude"
        critic_name = "chatgpt"

        print("Setting up local dev server page in background tab...")
        dev_page = ctx.new_page()
        
        # Capture browser console errors
        browser_console_errors = []
        dev_page.on("console", lambda msg: browser_console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ["error", "warning"] else None)
        dev_page.on("pageerror", lambda err: browser_console_errors.append(f"[PageError] {err}"))
        
        try:
            dev_page.goto(f"http://localhost:{config.DEV_SERVER_PORT}", timeout=10000, wait_until="commit")
            if not chk:
                webbrowser.open(f"http://localhost:{config.DEV_SERVER_PORT}")
                print("Opened Dev Server in default browser.")
        except Exception as e:
            print(f"Warning: Could not navigate to dev server initially: {e}")

        exited_cleanly = False
        
        # Connect to Antigravity IDE
        print("Connecting to Antigravity IDE...")
        ag_win = get_antigravity_window()

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
            critic_retry_count = 0
            escalation_count = 0
            
            while turn < config.MAX_TURNS:
                try:
                    if getattr(config, "STOP_REQUESTED", False):
                        print("\n[System] Stop requested! Gracefully pausing bridge...")
                        config.STOP_REQUESTED = False
                        save_checkpoint(turn, history_summary, phase, current_payload, "critic", project_brief=project_brief)
                        print("[System] Agent gracefully stopped.")
                        break
                        
                    # Robustly recover any closed Playwright tabs (Karthik override: fix the issue)
                    try:
                        if pages["claude"] and pages["claude"].is_closed():
                            print("[System] Claude tab was closed. Recreating it...")
                            pages["claude"] = ctx.new_page()
                            pages["claude"].goto(config.CHAT_PLATFORMS["claude"]["url"], wait_until="domcontentloaded")
                            page = pages["claude"]

                        if pages.get("chatgpt") and pages["chatgpt"].is_closed():
                            print("[System] ChatGPT tab was closed. Recreating it...")
                            pages["chatgpt"] = ctx.new_page()
                            pages["chatgpt"].goto(config.CHAT_PLATFORMS["chatgpt"]["url"], wait_until="domcontentloaded")
                            chatgpt_page = pages["chatgpt"]

                        if dev_page and dev_page.is_closed():
                            print("[System] Dev Server tab was closed. Recreating it...")
                            dev_page = ctx.new_page()
                            dev_page.on("console", lambda msg: browser_console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ["error", "warning"] else None)
                            dev_page.on("pageerror", lambda err: browser_console_errors.append(f"[PageError] {err}"))
                    except Exception as e:
                        print(f"[System] Warning: Could not recover browser tabs: {e}")

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
                        
                        design_system = _load_design_library()
                        lessons_learned = _load_builder_memory()
                        phase2_prompt = config.load_prompt("phase2_builder.md", master_plan=project_brief, brief=chat_response, design_system=design_system, lessons_learned=lessons_learned)
                        
                        print("Sending step to Antigravity...")
                        ag_win.set_focus()
                        send_to_antigravity(ag_win, phase2_prompt)
                        ag_response = wait_for_antigravity_response(ag_win)
                        
                        print(f"\n--- Antigravity Build Report ({len(ag_response)} chars) ---")
                        
                        current_payload = ag_response
                        history_summary += f"\n--- Turn {turn} (Execution) ---\n{ag_response[:500]}\n"
                        
                        phase = 3
                        save_checkpoint(turn, history_summary, phase, current_payload, "critic", project_brief=project_brief)

                    # Phase 3: Critic Evaluation
                    if phase == 3:
                        print(f"\n{'='*50}")
                        print(f"  Phase 3: Critic Evaluation (Turn {turn})")
                        print(f"{'='*50}")
                        
                        screenshot_bytes = None
                        min_critic_turn = getattr(config, "MIN_CRITIC_TURN", 1)
                        if turn < min_critic_turn:
                            print(f"[Critic] Skipping evaluation (Turn {turn} < {min_critic_turn}).")
                            critic_result = {"verdict": "pass"}
                        else:
                            # Fast-Fail Local Build Check
                            print("[Critic] Running fast-fail local build check (npm run build)...")
                            import subprocess
                            build_failed = False
                            build_error_msg = ""
                            try:
                                res = subprocess.run('npm run build', shell=True, cwd=config.DEV_SERVER_CWD, capture_output=True, text=True)
                                if res.returncode != 0:
                                    build_failed = True
                                    build_error_msg = res.stderr if res.stderr else res.stdout
                            except Exception as e:
                                build_failed = True
                                build_error_msg = str(e)

                            if build_failed:
                                print("[Critic] Fast-fail build check failed! Bypassing UI evaluation.")
                                critic_result = {
                                    "verdict": "fix_needed",
                                    "reason": "The project failed to build (TypeScript or compilation error).",
                                    "instruction": f"Fix the following build errors:\n```\n{build_error_msg[:1500]}\n```"
                                }
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
                                        design_system = _load_design_library()
                                        
                                        # Load previous screenshot if it exists
                                        prev_screenshot_path = os.path.join(config.DEV_SERVER_CWD, "_previous_screenshot.jpg")
                                        prev_screenshot_bytes = None
                                        if os.path.exists(prev_screenshot_path):
                                            try:
                                                with open(prev_screenshot_path, "rb") as f:
                                                    prev_screenshot_bytes = f.read()
                                            except Exception as e:
                                                print(f"[Critic] Could not read previous screenshot: {e}")

                                        critic_result = evaluate_ui(
                                            screenshot_b64, screenshot_bytes, dom_summary, combined_errors,
                                            critic_page=pages[critic_name],
                                            critic_platform=config.CHAT_PLATFORMS[critic_name],
                                            design_system=design_system,
                                            prev_screenshot_bytes=prev_screenshot_bytes
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
                                    
                                print("[Critic] Escalating to Architect and rolling back to last stable state...")
                                git_rollback_state()
                                
                                escalation_msg = (
                                    f"The UI Critic failed {config.CRITIC_RETRY_CAP} times and the workspace was rolled back to the last stable state.\n"
                                    f"The last critic feedback before rollback was:\n"
                                    f"Reason: {critic_result.get('reason')}\n"
                                    f"Instruction: {critic_result.get('instruction')}\n\n"
                                    f"Based on this feedback, provide a DIFFERENT approach or a single fix instruction for Antigravity."
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
                                _save_builder_memory(reason, instruction)
                                
                                # Save the critic screenshot so Antigravity can SEE what's wrong
                                screenshot_hint = ""
                                if screenshot_bytes:
                                    try:
                                        screenshot_path = os.path.join(config.DEV_SERVER_CWD, "_critic_screenshot.jpg")
                                        with open(screenshot_path, "wb") as f:
                                            f.write(screenshot_bytes)
                                        screenshot_hint = (
                                            f"\n\nA screenshot of the current state has been saved to: {screenshot_path}\n"
                                            f"Use the view_file tool on this image to see exactly what the critic saw before making changes."
                                        )
                                        print(f"[Critic] Screenshot saved to {screenshot_path}")
                                    except Exception as ss_err:
                                        print(f"[Critic] Could not save screenshot: {ss_err}")
                                
                                fix_prompt = f"UI Critic Feedback:\nReason: {reason}\nInstruction: {instruction}{screenshot_hint}\nFix this issue."
                                
                                ag_win.set_focus()
                                send_to_antigravity(ag_win, fix_prompt)
                                ag_response = wait_for_antigravity_response(ag_win)
                                current_payload = ag_response
                                history_summary += f"\n--- Turn {turn} (Critic Fix) ---\n{ag_response[:500]}\n"
                        else:
                            print("[Critic] Verdict: PASS. Step complete! Requesting next step...")
                            git_commit_state(turn)
                            
                            if screenshot_bytes:
                                try:
                                    prev_screenshot_path = os.path.join(config.DEV_SERVER_CWD, "_previous_screenshot.jpg")
                                    with open(prev_screenshot_path, "wb") as f:
                                        f.write(screenshot_bytes)
                                except Exception as e:
                                    print(f"[Critic] Could not save previous screenshot: {e}")
                                    
                            phase = 2  # Go back to Claude for the next step!
                            
                        turn += 1
                        if turn % 5 == 0:
                            history_summary = compress_history(history_summary)

                except KeyboardInterrupt:
                    raise  # Let the outer block catch this to save checkpoint and exit
                except Exception as loop_err:
                    print(f"\n[System] Recoverable error in loop at turn {turn}: {loop_err}")
                    traceback.print_exc()
                    print("[System] The bridge will attempt to self-heal and resume in 5 seconds...")
                    time.sleep(5)
                    continue  # Resume the loop

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
