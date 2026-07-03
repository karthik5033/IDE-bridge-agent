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
from ui_critic import evaluate_ui


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
    """Main bridge loop implementing Phase 1, Phase 2, and Phase 3 state machine."""
    print("=" * 50)
    print("  Bridge Agent Starting")
    print("=" * 50)

    config.check_config()

    try:
        ag_win = get_antigravity_window()
        ag_win.set_focus()
    except Exception as e:
        print(f"Fatal: Could not resolve Antigravity window. {e}")
        notify_phone(f"Startup failed: {e}", "Bridge Error")
        return

    # Checkpoint variables
    turn = 0
    phase = 1
    history_summary = f"Initial Task: {initial_task}\n"
    current_payload = ""
    next_recipient = "chat" # or "antigravity"

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
            next_recipient = chk.get("next_recipient", "chat")
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
            
            if chatgpt_page:
                if start_fresh:
                    print("Starting fresh... Navigating to New Chat for ChatGPT.")
                    chatgpt_page.goto(config.CHAT_PLATFORMS["chatgpt"]["url"], wait_until="domcontentloaded")
            else:
                ctx = browser.contexts[0] if browser.contexts else browser.new_context()
                chatgpt_page = ctx.new_page()
                chatgpt_page.goto(config.CHAT_PLATFORMS["chatgpt"]["url"], wait_until="domcontentloaded")
            print(f"ChatGPT critic tab ready: {chatgpt_page.url}")

            # Initialize ChatGPT with design system and critic rules
            if start_fresh:
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
        try:
            dev_page.goto(f"http://localhost:{config.DEV_SERVER_PORT}")
            if not chk:
                webbrowser.open(f"http://localhost:{config.DEV_SERVER_PORT}")
                print("Opened Dev Server in default browser.")
        except Exception as e:
            print(f"Warning: Could not navigate to dev server initially: {e}")


        exited_cleanly = False

        try:
            # === Phase 1: Planning (Chat UI) ===
            if phase == 1:
                print("\n" + "="*40 + "\n  Phase 1: Planning (Chat UI)\n" + "="*40)
                design_system = _load_design_library()
                phase1_prompt = config.load_prompt("phase1_architect.md", design_system=design_system, initial_task=initial_task)
                
                print("Sending initial task to Chat UI to generate brief...")
                chat_response = _send_to_chat_with_retry(pages[architect_name], phase1_prompt, platform=config.CHAT_PLATFORMS[architect_name])
                
                print("\n--- Message Received from Chat UI ---")
                print(chat_response)
                print("-------------------------------------\n")
                
                # Analyze for error just in case
                analysis = analyze_message(chat_response)
                if analysis.get("is_error"):
                    print("Error detected in Chat UI Phase 1 response.")
                    print(f"Qwen Analysis: {analysis}")
                    notify_phone("Phase 1 Chat UI Error", "Bridge Paused")
                    input("Resolve error and press Enter to exit/retry...")
                    return
                
                current_payload = chat_response
                
                # Check if Claude is asking a question instead of giving an executable command.
                # If so, auto-reply to keep the flow moving and avoid a deadlock.
                max_clarifications = 3
                for _ in range(max_clarifications):
                    lower = current_payload.lower()
                    ends_with_question = lower.rstrip().endswith("?")
                    question_phrases = ["sound good", "do you want", "what do you think", 
                                       "should we", "do you prefer", "what's your", "before we start",
                                       "worth confirming", "happy to go with", "before scaffolding",
                                       "or do you want to", "one open question"]
                    is_discussion = ends_with_question and any(p in lower for p in question_phrases)
                    
                    if not is_discussion:
                        break
                    
                    print("[Orchestrator] Claude is asking a clarification question, not giving a command.")
                    print("[Orchestrator] Auto-replying with 'proceed' to keep the flow moving...")
                    auto_reply = "Proceed with your best judgment on the open questions. Give me the first concrete, executable command."
                    chat_response = _send_to_chat_with_retry(pages[architect_name], auto_reply, platform=config.CHAT_PLATFORMS[architect_name])
                    print(f"[Orchestrator] Got follow-up response ({len(chat_response)} chars).")
                    current_payload = chat_response
                
                phase = 2
                next_recipient = "antigravity"
                save_checkpoint(turn, history_summary, phase, current_payload, next_recipient)

            # === Phase 2: Plan first, not code (Antigravity) ===
            if phase == 2:
                print("\n" + "="*40 + "\n  Phase 2: Plan first (Antigravity)\n" + "="*40)
                phase2_prompt = (
                    "You are a coding agent. An expert architect has produced the following project brief and your first command. "
                    "Read the brief carefully to understand the vision, then execute ONLY the specific command given at the end. "
                    "When you have finished the step, report your progress clearly so the architect can give you the next step.\n\n"
                    "IMPORTANT: To hand control back to the orchestrator, you MUST write your final response report to a file named "
                    r"`d:\coding_files\kpautomate\bridge_response.txt`. You MUST use the `write_to_file` tool to create this file. DO NOT merely reply in the chat UI, or the automation loop will hang indefinitely. CREATE THE FILE!\n\n"
                    f"Architect's Instructions:\n{current_payload}"
                )
                
                print("Sending brief to Antigravity...")
                ag_win.set_focus()
                send_to_antigravity(ag_win, phase2_prompt)
                ag_response = wait_for_antigravity_response(ag_win)
                
                print("\n--- Message Received from Antigravity ---")
                print(ag_response)
                print("-----------------------------------------\n")
                
                analysis = analyze_message(ag_response)
                if analysis.get("is_error"):
                    print("Error detected in Antigravity Phase 2 response.")
                    print(f"Qwen Analysis: {analysis}")
                    notify_phone("Phase 2 Antigravity Error", "Bridge Paused")
                    input("Resolve error and press Enter to exit/retry...")
                    return

                current_payload = ag_response
                phase = 3
                next_recipient = "chat"
                save_checkpoint(turn, history_summary, phase, current_payload, next_recipient)


            # === Phase 3: Review loop ===
            if phase == 3:
                while turn < config.MAX_TURNS:
                    if getattr(config, "STOP_REQUESTED", False):
                        print("\n[System] Stop requested! Gracefully pausing bridge...")
                        config.STOP_REQUESTED = False
                        save_checkpoint(turn, history_summary, phase, current_payload, next_recipient)
                        print("[System] Agent gracefully stopped.")
                        break

                    print(f"\n{'='*40}\n  Phase 3 (Turn {turn})\n{'='*40}")
                    
                    save_checkpoint(turn, history_summary, phase, current_payload, next_recipient)
                    
                    if next_recipient == "chat":
                        if turn > 0 and turn % 10 == 0:
                            architect_name, critic_name = critic_name, architect_name
                            print(f"\n[Rotation] Swapped roles! Architect is now {architect_name.upper()}, Critic is {critic_name.upper()}.")
                            
                        print("Antigravity finished step. Running UI Critic check...")
                        
                        critic_retry_count = chk.get("critic_retry_count", 0) if chk else 0
                        
                        # Refresh dev page and check errors
                        try:
                            dev_page.reload(wait_until="networkidle", timeout=10000)
                        except Exception:
                            pass
                            
                        new_errors = dev_server.get_new_errors()
                        
                        # Take screenshot
                        try:
                            screenshot_bytes = dev_page.screenshot(type="jpeg", quality=60)
                            screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                        except Exception as e:
                            print(f"[Critic] Failed to take screenshot: {e}")
                            screenshot_b64 = ""
                            
                        if config.CRITIC_TRIGGER == "error_or_bad_ui":
                            critic_result = evaluate_ui(screenshot_b64, new_errors, critic_page=pages[critic_name], critic_platform=config.CHAT_PLATFORMS[critic_name])
                        else:
                            critic_result = {"verdict": "pass"}
                        
                        if critic_result.get("verdict") == "fix_needed":
                            critic_retry_count += 1
                            if critic_retry_count >= config.CRITIC_RETRY_CAP:
                                print(f"[Critic] Max retries ({config.CRITIC_RETRY_CAP}) reached. Escalating to Chat UI.")
                                current_payload = f"The UI Critic failed {config.CRITIC_RETRY_CAP} times. Last reason: {critic_result.get('reason')}\n\nAntigravity's last report:\n{current_payload}"
                                save_checkpoint(turn, history_summary, phase, current_payload, next_recipient, critic_retry_count=0)
                            else:
                                print(f"[Critic] Fix needed. Routing back to Antigravity (Attempt {critic_retry_count})")
                                instruction = critic_result.get('instruction', 'Fix the visual issues.')
                                current_payload = f"UI Critic Feedback:\nReason: {critic_result.get('reason')}\nInstruction: {instruction}"
                                next_recipient = "antigravity"
                                save_checkpoint(turn, history_summary, phase, current_payload, next_recipient, critic_retry_count=critic_retry_count)
                                continue # Skip Chat UI, go back to top of loop
                        else:
                            print("[Critic] Verdict: pass. Forwarding to Chat UI.")
                            critic_retry_count = 0
                            save_checkpoint(turn, history_summary, phase, current_payload, next_recipient, critic_retry_count=0)

                        print("Forwarding payload to Chat UI...")
                        chat_response = _send_to_chat_with_retry(pages[architect_name], current_payload, platform=config.CHAT_PLATFORMS[architect_name])
                        print(f"Chat UI response received ({len(chat_response)} chars).")
                        
                        analysis = analyze_message(chat_response)
                        history_summary += f"\n--- Turn {turn} (Chat) [{analysis.get('phase_tag', '')}] ---\n"
                        history_summary += f"{chat_response[:500]}\n"
                        
                        if analysis.get("is_error"):
                            notify_phone("Error trace from Chat UI", "Bridge Paused")
                            print("!! Error detected in Chat UI output. Pausing.")
                            print(f"Qwen Analysis: {analysis}")
                            input("Press Enter to continue loop anyway, or Ctrl+C to abort...")
                        
                        if analysis.get("is_done"):
                            print("Task signaled DONE by Chat UI.")
                            exited_cleanly = True
                            break
                        
                        current_payload = chat_response
                        
                        # Check if Claude is asking a question instead of giving a command
                        for _ in range(3):
                            lower = current_payload.lower()
                            ends_with_question = lower.rstrip().endswith("?")
                            question_phrases = ["sound good", "do you want", "what do you think", 
                                               "should we", "do you prefer", "what's your",
                                               "worth confirming", "or do you want to", "one open question",
                                               "before we proceed", "before moving on"]
                            is_discussion = ends_with_question and any(p in lower for p in question_phrases)
                            
                            if not is_discussion:
                                break
                            
                            print("[Orchestrator] Claude asked a question mid-loop. Auto-replying to keep flow moving...")
                            auto_reply = "Proceed with your best judgment. Give the next concrete, executable command for the coding agent."
                            chat_response = _send_to_chat_with_retry(pages[architect_name], auto_reply, platform=config.CHAT_PLATFORMS[architect_name])
                            current_payload = chat_response
                        
                        next_recipient = "antigravity"
                        
                    elif next_recipient == "antigravity":
                        print("Forwarding payload to Antigravity...")
                        ag_win.set_focus()
                        
                        # Wrap the payload with the instruction to write the response file
                        ag_prompt = (
                            f"{current_payload}\n\n"
                            "IMPORTANT: To hand control back to the orchestrator, you MUST write your final response report to a file named "
                            r"`d:\coding_files\kpautomate\bridge_response.txt`. You MUST use the `write_to_file` tool to create this file. DO NOT merely reply in the chat UI, or the automation loop will hang indefinitely. CREATE THE FILE!"
                        )
                        
                        send_to_antigravity(ag_win, ag_prompt)
                        ag_response = wait_for_antigravity_response(ag_win)
                        print(f"Antigravity response received ({len(ag_response)} chars).")
                        
                        analysis = analyze_message(ag_response)
                        history_summary += f"\n--- Turn {turn} (Antigravity) [{analysis.get('phase_tag', '')}] ---\n"
                        history_summary += f"{ag_response[:500]}\n"
                        
                        current_payload = ag_response

                        if analysis.get("is_error"):
                            print("!! Error detected in Antigravity output. Summarizing...")
                            summarized_err = summarize_error(ag_response)
                            notify_phone("Error trace from Antigravity", "Bridge Paused")
                            print(f"Qwen Analysis: {analysis}")
                            print(f"Summary:\n{summarized_err}")
                            input("Press Enter to forward this summary to Chat UI, or Ctrl+C to abort...")
                            current_payload = summarized_err
                        
                        if analysis.get("is_done"):
                            print("Task signaled DONE by Antigravity.")
                            exited_cleanly = True
                            break
                        next_recipient = "chat"
                        turn += 1
                        
                        if turn % 5 == 0:
                            history_summary = compress_history(history_summary)

        except KeyboardInterrupt:
            print("\n\nInterrupted by user (Ctrl+C). Saving checkpoint...")
            save_checkpoint(turn, history_summary, phase, current_payload, next_recipient)
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
