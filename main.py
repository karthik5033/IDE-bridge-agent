import sys
import traceback
import config
import time
from checkpoint import save_checkpoint, load_checkpoint, clear_checkpoint
from notifier import notify_phone
from orchestrator import analyze_message
from antigravity_driver import (
    get_antigravity_window,
    send_to_antigravity,
    wait_for_antigravity_response,
)
from chat_driver import send_to_chat_ui, wait_for_chat_response, RateLimitDetected
from playwright.sync_api import sync_playwright


def _send_to_chat_with_retry(page, text: str) -> str:
    """Helper to send a message to Chat UI and get response, handling rate limits."""
    while True:
        try:
            send_to_chat_ui(page, text)
            return wait_for_chat_response(page, text)
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
        else:
            print(f"No chat tab found. Opening {config.CHAT_SITE_URL}...")
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            page = ctx.new_page()
            page.goto(config.CHAT_SITE_URL, wait_until="domcontentloaded")

        input(
            "\n>> Please ensure you are logged in to the chat UI.\n"
            ">> Press Enter when the page is ready..."
        )

        exited_cleanly = False

        try:
            # === Phase 1: Planning (Chat UI) ===
            if phase == 1:
                print("\n" + "="*40 + "\n  Phase 1: Planning (Chat UI)\n" + "="*40)
                phase1_prompt = (
                    "You are an expert software architect and product manager. Your goal is to guide a coding agent to build a PREMIUM, state-of-the-art application. "
                    "We do NOT want simple or basic apps. Focus heavily on high-end aesthetics, robust architecture, and premium 'vibecode' UI/UX. "
                    "Given the task below, write a detailed brief and step-by-step implementation plan. "
                    "Break the plan into multiple clear, logical phases. "
                    "CRITICAL RULES FOR YOU: "
                    "1. Have a rich, high-quality architectural conversation with the agent. Discuss design patterns, UI layout, and edge cases. "
                    "2. DO NOT demand full file contents or massive code dumps from the agent in its responses. The agent will write code to disk. Trust its confirmation. "
                    "3. ALWAYS end your response by guiding the agent on the next logical step, but do it collaboratively rather than acting like a dictator. "
                    "4. Output only the brief, architecture discussion, and the first step's goal.\n\n"
                    f"Task:\n{initial_task}"
                )
                
                print("Sending initial task to Chat UI to generate brief...")
                chat_response = _send_to_chat_with_retry(page, phase1_prompt)
                
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
                    print(f"\n{'='*40}\n  Phase 3 (Turn {turn})\n{'='*40}")
                    
                    save_checkpoint(turn, history_summary, phase, current_payload, next_recipient)
                    
                    if next_recipient == "chat":
                        print("Forwarding payload to Chat UI...")
                        chat_response = _send_to_chat_with_retry(page, current_payload)
                        print(f"Chat UI response received ({len(chat_response)} chars).")
                        
                        analysis = analyze_message(chat_response)
                        history_summary += f"\n--- Turn {turn} (Chat) [{analysis.get('phase_tag', '')}] ---\n"
                        history_summary += f"{chat_response[:500]}\n"
                        
                        if analysis.get("is_error"):
                            notify_phone("Error trace from Chat UI", "Bridge Paused")
                            print("!! Error detected in Chat UI output. Pausing.")
                            print(f"Qwen Analysis: {analysis}")
                            input("Press Enter to continue loop anyway, or Ctrl+C to abort...")
                        
                        if config.STOP_TOKEN in chat_response:
                            print("Task signaled DONE by Chat UI.")
                            exited_cleanly = True
                            break
                        
                        current_payload = chat_response
                        next_recipient = "antigravity"
                        
                    elif next_recipient == "antigravity":
                        print("Forwarding payload to Antigravity...")
                        ag_win.set_focus()
                        send_to_antigravity(ag_win, current_payload)
                        ag_response = wait_for_antigravity_response(ag_win)
                        print(f"Antigravity response received ({len(ag_response)} chars).")
                        
                        analysis = analyze_message(ag_response)
                        history_summary += f"\n--- Turn {turn} (Antigravity) [{analysis.get('phase_tag', '')}] ---\n"
                        history_summary += f"{ag_response[:500]}\n"
                        
                        if analysis.get("is_error"):
                            notify_phone("Error trace from Antigravity", "Bridge Paused")
                            print("!! Error detected in Antigravity output. Pausing.")
                            print(f"Qwen Analysis: {analysis}")
                            input("Press Enter to continue loop anyway, or Ctrl+C to abort...")
                        
                        if config.STOP_TOKEN in ag_response:
                            print("Task signaled DONE by Antigravity.")
                            exited_cleanly = True
                            break
                            
                        current_payload = ag_response
                        next_recipient = "chat"
                        turn += 1

        except KeyboardInterrupt:
            print("\n\nInterrupted by user (Ctrl+C). Saving checkpoint...")
            save_checkpoint(turn, history_summary, phase, current_payload, next_recipient)
            notify_phone("User interrupted the bridge loop.", "Bridge Stopped")

        except Exception as e:
            print(f"\nFatal error in main loop: {e}")
            traceback.print_exc()
            notify_phone(f"Unhandled exception: {e}", "Bridge Error")

        finally:
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
