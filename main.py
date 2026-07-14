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


def run_bridge(initial_task: str):
    """Main bridge loop: Brief → Build → Critic fix loop.
    
    Phase 1: Claude produces a comprehensive project brief (one shot).
    Phase 2: Antigravity builds the entire app from the brief (one shot).
    Phase 3: Critic evaluates → fixes go directly to Antigravity (no Claude).
             Claude only re-enters if critic escalates after repeated failures.
    """
    print("=" * 50)
    print("  Bridge Agent Starting")
    print("=" * 50)

    config.STOP_REQUESTED = False
    config.check_config()

    try:
        ag_win = get_antigravity_window()
    except Exception as e:
        print(f"Fatal: Could not resolve Antigravity window. {e}")
        notify_phone(f"Startup failed: {e}", "Bridge Error")
        return

    # Checkpoint variables
    turn = 0
    phase = 1
    history_summary = f"Initial Task: {initial_task}\n"
    current_payload = ""
    project_brief = ""  # Stored separately for re-use

    chk = load_checkpoint()
    start_fresh = False
    if chk:
        print(f"\nFound checkpoint from turn {chk.get('turn', 0)}, phase {chk.get('phase', 1)}.")
        ans = input("Resume from checkpoint? (y/n): ").strip().lower()
        if ans == "y":
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
                if "claude.ai" in pg.url or "chatgpt.com" in pg.url:
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
            dev_page.goto(f"http://localhost:{config.DEV_SERVER_PORT}")
            if not chk:
                webbrowser.open(f"http://localhost:{config.DEV_SERVER_PORT}")
                print("Opened Dev Server in default browser.")
        except Exception as e:
            print(f"Warning: Could not navigate to dev server initially: {e}")

        exited_cleanly = False

        try:
            # ============================================================
            # PHASE 1: Get comprehensive project brief from Claude (ONE SHOT)
            # ============================================================
            if phase == 1:
                print("\n" + "="*50)
                print("  Phase 1: Get Project Brief from Claude (ONE SHOT)")
                print("="*50)
                
                design_system = _load_design_library()
                phase1_prompt = config.load_prompt("phase1_architect.md", design_system=design_system, initial_task=initial_task)
                
                print("Sending task to Claude for comprehensive project brief...")
                chat_response = _send_to_chat_with_retry(pages[architect_name], phase1_prompt, platform=config.CHAT_PLATFORMS[architect_name])
                
                print(f"\n--- Project Brief Received ({len(chat_response)} chars) ---")
                print(chat_response[:500] + "..." if len(chat_response) > 500 else chat_response)
                print("---------------------------------------------------\n")
                
                # Analyze for error just in case
                analysis = analyze_message(chat_response)
                if analysis.get("is_error"):
                    print("Error detected in Claude Phase 1 response.")
                    notify_phone("Phase 1 Claude Error", "Bridge Paused")
                    input("Resolve error and press Enter to exit/retry...")
                    return
                
                # If Claude is asking questions instead of giving a brief, force it forward
                max_clarifications = 3
                for _ in range(max_clarifications):
                    if not _is_question_response(chat_response, analysis):
                        break
                    
                    print("[Orchestrator] Claude is asking questions instead of producing a brief.")
                    print("[Orchestrator] Auto-replying to force a complete brief...")
                    auto_reply = (
                        "Do NOT ask questions. You are in a fully automated pipeline with no human to answer. "
                        "Make your best senior-dev decision on ALL open questions and produce the COMPLETE "
                        "project brief NOW. Include every detail the coding agent needs to build the entire "
                        "application in one pass."
                    )
                    chat_response = _send_to_chat_with_retry(pages[architect_name], auto_reply, platform=config.CHAT_PLATFORMS[architect_name])
                    print(f"[Orchestrator] Got follow-up response ({len(chat_response)} chars).")
                    analysis = analyze_message(chat_response)
                
                project_brief = chat_response
                current_payload = chat_response
                phase = 2
                save_checkpoint(turn, history_summary, phase, current_payload, "antigravity", project_brief=project_brief)

            # ============================================================
            # PHASE 2: Send full brief to Antigravity to build (ONE SHOT)
            # ============================================================
            if phase == 2:
                print("\n" + "="*50)
                print("  Phase 2: Antigravity Builds from Brief (ONE SHOT)")
                print("="*50)
                
                phase2_prompt = config.load_prompt("phase2_builder.md", brief=project_brief or current_payload)
                
                print("Sending full project brief to Antigravity...")
                ag_win.set_focus()
                send_to_antigravity(ag_win, phase2_prompt)
                ag_response = wait_for_antigravity_response(ag_win)
                
                print(f"\n--- Antigravity Build Report ({len(ag_response)} chars) ---")
                print(ag_response[:500] + "..." if len(ag_response) > 500 else ag_response)
                print("-----------------------------------------------------\n")
                
                analysis = analyze_message(ag_response)
                if analysis.get("is_error"):
                    print("Error detected in Antigravity Phase 2 response.")
                    notify_phone("Phase 2 Antigravity Error", "Bridge Paused")
                    input("Resolve error and press Enter to exit/retry...")
                    return

                current_payload = ag_response
                history_summary += f"\n--- Phase 2 (Antigravity Build) ---\n{ag_response[:500]}\n"
                phase = 3
                turn = 1  # Start critic loop at turn 1
                save_checkpoint(turn, history_summary, phase, current_payload, "critic", project_brief=project_brief)

            # ============================================================
            # PHASE 3: Critic evaluation + fix loop (Antigravity ↔ Critic)
            # Claude only re-enters if critic escalates.
            # ============================================================
            if phase == 3:
                critic_retry_count = 0
                escalation_count = 0
                
                while turn < config.MAX_TURNS:
                    if getattr(config, "STOP_REQUESTED", False):
                        print("\n[System] Stop requested! Gracefully pausing bridge...")
                        config.STOP_REQUESTED = False
                        save_checkpoint(turn, history_summary, phase, current_payload, "critic", project_brief=project_brief)
                        print("[System] Agent gracefully stopped.")
                        break

                    print(f"\n{'='*50}")
                    print(f"  Phase 3: Critic Evaluation (Turn {turn})")
                    print(f"{'='*50}")
                    
                    save_checkpoint(turn, history_summary, phase, current_payload, "critic", project_brief=project_brief)
                    
                    # --- Run UI Critic ---
                    min_critic_turn = getattr(config, "MIN_CRITIC_TURN", 1)
                    if turn < min_critic_turn:
                        print(f"[Critic] Skipping evaluation (Turn {turn} < {min_critic_turn}).")
                        critic_result = {"verdict": "pass"}
                    else:
                        # Refresh dev page and check errors — navigate to
                        # the base URL to re-establish a valid execution context
                        # (explore_page may have left it on a different route
                        # or in a destroyed state after navigations).
                        try:
                            dev_page.goto(
                                f"http://localhost:{config.DEV_SERVER_PORT}",
                                wait_until="networkidle",
                                timeout=15000,
                            )
                        except Exception:
                            # Fallback: try a plain reload
                            try:
                                dev_page.reload(wait_until="networkidle", timeout=10000)
                            except Exception:
                                pass
                            
                        new_dev_errors = dev_server.get_new_errors()
                        
                        # Get browser console errors and clear the buffer
                        browser_errs_str = "\n".join(browser_console_errors)
                        browser_console_errors.clear()
                        
                        combined_errors = ""
                        if new_dev_errors: combined_errors += f"Dev Server Errors:\n{new_dev_errors}\n"
                        if browser_errs_str: combined_errors += f"Browser Console Errors:\n{browser_errs_str}\n"
                        
                        # Check if the page is literally an error page
                        try:
                            page_title = dev_page.title()
                        except Exception:
                            page_title = ""
                        if "error" in page_title.lower() or "refused" in page_title.lower():
                            combined_errors += f"Browser says: {page_title}\n"
                            
                        # Capture page context (screenshot + DOM)
                        # This can throw if the dev server is down or the page
                        # execution context was destroyed during exploration.
                        try:
                            screenshot_b64, screenshot_bytes, dom_summary = capture_page_context(dev_page)
                        except Exception as ctx_err:
                            print(f"[Critic] capture_page_context failed: {ctx_err}")
                            print("[Critic] Skipping this evaluation turn — will retry next turn.")
                            screenshot_b64, screenshot_bytes, dom_summary = "", None, ""
                            
                        if config.CRITIC_TRIGGER == "error_or_bad_ui":
                            try:
                                critic_result = evaluate_ui(
                                    screenshot_b64, screenshot_bytes, dom_summary, combined_errors,
                                    critic_page=pages[critic_name],
                                    critic_platform=config.CHAT_PLATFORMS[critic_name]
                                )
                            except Exception as eval_err:
                                print(f"[Critic] evaluate_ui failed: {eval_err}")
                                print("[Critic] Falling back to PASS for this turn.")
                                critic_result = {"verdict": "pass", "reason": f"Critic error: {eval_err}"}
                        else:
                            critic_result = {"verdict": "pass"}
                    
                    # --- Handle Critic Result ---
                    if critic_result.get("verdict") == "fix_needed":
                        critic_retry_count += 1
                        
                        if critic_retry_count >= config.CRITIC_RETRY_CAP:
                            # Escalate to Claude
                            escalation_count += 1
                            print(f"[Critic] Max retries ({config.CRITIC_RETRY_CAP}) reached. Escalating to Claude (Escalation #{escalation_count}).")
                            
                            if escalation_count >= 2:
                                print("[Critic] Multiple escalations. Accepting current state and terminating.")
                                exited_cleanly = True
                                break
                            
                            escalation_msg = (
                                f"The UI Critic has failed {config.CRITIC_RETRY_CAP} consecutive times to get a passing result. "
                                f"Last reason: {critic_result.get('reason')}\n\n"
                                f"Original task: {initial_task}\n\n"
                                f"Antigravity's last report:\n{current_payload[:2000]}\n\n"
                                f"Provide a SINGLE comprehensive fix instruction that addresses ALL remaining issues. "
                                f"Do NOT break it into steps."
                            )
                            
                            chat_response = _send_to_chat_with_retry(pages[architect_name], escalation_msg, platform=config.CHAT_PLATFORMS[architect_name])
                            current_payload = chat_response
                            critic_retry_count = 0
                            
                            # Send Claude's fix instruction to Antigravity
                            print("Forwarding Claude's fix instruction to Antigravity...")
                            ag_win.set_focus()
                            send_to_antigravity(ag_win, current_payload)
                            ag_response = wait_for_antigravity_response(ag_win)
                            current_payload = ag_response
                            print(f"Antigravity fix response received ({len(ag_response)} chars).")
                            
                            history_summary += f"\n--- Turn {turn} (Escalation #{escalation_count}) ---\n{ag_response[:500]}\n"
                        else:
                            # Send fix directly to Antigravity (no Claude involved)
                            print(f"[Critic] Fix needed. Routing directly to Antigravity (Attempt {critic_retry_count}/{config.CRITIC_RETRY_CAP})")
                            instruction = critic_result.get('instruction', 'Fix the visual issues.')
                            reason = critic_result.get('reason', '')
                            
                            fix_prompt = (
                                f"UI Critic Feedback (fix attempt {critic_retry_count}/{config.CRITIC_RETRY_CAP}):\n"
                                f"Reason: {reason}\n"
                                f"Instruction: {instruction}\n\n"
                                f"Fix this issue and verify the dev server runs cleanly."
                            )
                            
                            ag_win.set_focus()
                            send_to_antigravity(ag_win, fix_prompt)
                            ag_response = wait_for_antigravity_response(ag_win)
                            current_payload = ag_response
                            print(f"Antigravity fix response received ({len(ag_response)} chars).")
                            
                            history_summary += f"\n--- Turn {turn} (Critic Fix #{critic_retry_count}) ---\n{ag_response[:500]}\n"
                    else:
                        # Critic passed!
                        print("[Critic] Verdict: PASS. Application looks good!")
                        exited_cleanly = True
                        break
                    
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
