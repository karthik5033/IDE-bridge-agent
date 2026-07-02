# PRD: Antigravity <-> Chat UI Bridge Agent

Zero-cost, local, unattended automation that replaces manual copy-paste
between the Antigravity IDE and a browser-based AI chat (Claude.ai or
ChatGPT), using a local LLM as the orchestrator. No paid API usage anywhere.

Hand this file to the IDE agent as the spec. It should be able to build the
whole thing from this document plus the setup values the user fills in.

---

## 1. Problem

Manual workflow today: user reads Antigravity's output, decides the next
prompt, pastes it into a chat AI, reads the reply, pastes it back into
Antigravity, repeat. The user is the transport layer and has to babysit
every turn.

## 2. Goal

A single long-running local process that:
- Decides what to do next (local LLM orchestrator).
- Drives Antigravity's desktop UI directly (OS-level automation).
- Drives a real, logged-in browser chat session (Claude.ai or ChatGPT free
  tier) directly (browser automation).
- Detects when either side is rate-limited and pauses safely instead of
  crashing or silently failing.
- Notifies the user's phone when it needs manual intervention.
- Checkpoints progress so a paused/killed run can resume without repeating
  work.
- Requires zero manual copy-paste and zero paid API calls.

## 3. Non-goals

- Not a general-purpose coding agent — Antigravity and the chat UI still do
  the actual thinking; this system is purely the transport/orchestration
  layer between them.
- Not cloud-hosted — runs on the user's local Windows laptop only.
- Not resilient to chat-site redesigns — selectors will need periodic
  maintenance; this is accepted, not solved, in v1.
- Not guaranteed safe from account flags on the chat provider's side —
  documented as a known risk, mitigated with randomized timing, not
  eliminated.
- Does not sandbox filesystem access — Antigravity operates with whatever
  permissions it already has on the user's machine.

## 4. Users

Single user (local dev machine, Windows 11, i7 CPU, RTX 4060 8GB GPU,
Ollama installed locally).

---

## 5. Architecture

```
                    ┌─────────────────────┐
                    │   Orchestrator       │
                    │  (local Qwen3 via    │
                    │   Ollama, free)      │
                    └──────────┬───────────┘
                               │ decides next instruction /
                               │ judges completion / stop condition
              ┌────────────────┴────────────────┐
              ▼                                  ▼
    ┌───────────────────┐              ┌───────────────────────┐
    │ Antigravity driver │              │  Chat UI driver         │
    │ (pywinauto / UIA)  │◄────output──►│  (Playwright / Chromium)│
    │ desktop automation │   forwarded  │  browser automation     │
    └───────────────────┘              └───────────────────────┘
              │                                  │
              ▼                                  ▼
     Antigravity.exe window            claude.ai or chatgpt.com
     (native desktop app)              (real logged-in browser tab)

    Cross-cutting:
    - Checkpoint store (JSON file on disk) — turn number + running history
    - Rate-limit detector — scans chat page text for known limit phrases
    - Phone notifier — ntfy.sh HTTP push, free, no account
```

### Component responsibilities

| Component | Responsibility | Tech |
|---|---|---|
| Orchestrator | Given running history, produce next instruction for Antigravity; detect task completion; emit `DONE` | Ollama local API, `qwen3:8b` |
| Antigravity driver | Type/paste instruction into Antigravity's input control, trigger send, poll output control until stable, return text | `pywinauto`, UIA backend |
| Chat UI driver | Type/paste Antigravity's output into chat input, trigger send, poll response container until stable, return text | `playwright` (sync API), Chromium, persistent browser profile |
| Rate-limit detector | Scan page body text against a phrase list before/during each chat turn; raise on match | Plain string matching on `page.locator("body").inner_text()` |
| Checkpoint store | Persist `{turn, history_summary}` to disk after every turn; load on startup and offer resume | JSON file, local disk |
| Phone notifier | POST message to a user-specific ntfy.sh topic on pause/completion/error | `requests`, HTTP POST, no auth |

---

## 6. Repo / file structure

```
bridge_agent/
├── main.py                  # CLI entrypoint, argument parsing, run_bridge() orchestration
├── config.py                 # all constants: selectors, window titles, model name, topic, timeouts
├── orchestrator.py           # ask_qwen(), ORCHESTRATOR_SYSTEM prompt
├── antigravity_driver.py     # get_antigravity_window(), send_to_antigravity(), wait_for_antigravity_response()
├── chat_driver.py            # send_to_chat_ui(), wait_for_chat_response(), check_rate_limit(), RateLimitDetected
├── checkpoint.py             # save_checkpoint(), load_checkpoint(), clear_checkpoint()
├── notifier.py                # notify_phone()
├── requirements.txt
├── browser_profile/          # gitignored - Playwright persistent context (holds login session)
├── bridge_checkpoint.json    # gitignored - runtime state
└── README.md                 # setup steps (see section 10)
```

Rationale for splitting into modules: each side (Antigravity vs chat UI)
has independently volatile selectors/config that will need editing without
touching orchestration logic. Keep `main.py` as pure control flow with no
selector/window-title literals in it.

---

## 7. Configuration (`config.py`)

```python
OLLAMA_MODEL = "qwen3:8b"
OLLAMA_URL = "http://localhost:11434/api/generate"

CHAT_SITE_URL = "https://claude.ai/new"   # or "https://chatgpt.com"
PERSISTENT_CONTEXT_DIR = "./browser_profile"

CHAT_SELECTORS = {
    "input_box": str,       # CSS selector, verified via devtools by user
    "send_button": str,
    "latest_response": str,
}

ANTIGRAVITY_WINDOW_TITLE = str      # regex
INPUT_CTRL_AUTO_ID = str            # from pywinauto inspector
SEND_CTRL_AUTO_ID = str
OUTPUT_CTRL_AUTO_ID = str

IDLE_STABLE_SECONDS = 2.5   # how long output must stop changing to count as "done"
MAX_TURNS = 40
STOP_TOKEN = "DONE"

NTFY_TOPIC = str            # unguessable random string, user-provided
CHECKPOINT_FILE = "bridge_checkpoint.json"

RATE_LIMIT_PHRASES = list[str]   # tunable after observing real UI behavior
```

All of the above except numeric timeouts are placeholders the user fills in
after the one-time inspection steps (section 10). The agent building this
should treat missing values as required CLI/config errors at startup, not
silent failures — fail fast with a clear message naming which value is
unset.

---

## 8. Functional requirements

### 8.1 Orchestrator (`orchestrator.py`)

- `ask_qwen(prompt: str, system: str = "") -> str`
  - POSTs to `OLLAMA_URL` with `{"model", "prompt", "system", "stream": false}`.
  - Raises on non-200 response (`raise_for_status`).
  - Returns the `response` field of the JSON body.
- System prompt instructs the model to:
  - Produce short, concrete instructions for Antigravity based on history.
  - Emit exactly `DONE` when the task is complete — no other content in
    that message when signaling completion.
- Timeout: 120s per call (local generation, no external rate limit, but
  slow models can genuinely take a while).

### 8.2 Antigravity driver (`antigravity_driver.py`)

- `get_antigravity_window()` — locates the window via `Desktop(backend="uia").window(title_re=...)`.
- `send_to_antigravity(win, text: str)` — clicks the input control, sets
  text, clicks send. Must clear any existing text first.
- `wait_for_antigravity_response(win) -> str` — polls the output control's
  `window_text()` every 0.5s; considers it complete once text is unchanged
  for `IDLE_STABLE_SECONDS`. No hard timeout in v1 — acceptable because
  Antigravity is not rate-limited, only network/compute-bound. (Flag as a
  known gap: if Antigravity errors out silently, this polls forever.)

### 8.3 Chat UI driver (`chat_driver.py`)

- `send_to_chat_ui(page, text: str)` — calls `check_rate_limit(page)`
  first, then fills the input locator and clicks send.
- `wait_for_chat_response(page) -> str` — polls `check_rate_limit(page)`
  and the response locator's `inner_text()` every 0.5s, same
  stability-based completion detection as Antigravity.
- `check_rate_limit(page)` — reads full page body text (lowercased),
  checks against `RATE_LIMIT_PHRASES`; raises `RateLimitDetected(phrase)`
  on first match.
- `RateLimitDetected` is a custom exception carrying the matched phrase for
  logging.

### 8.4 Checkpointing (`checkpoint.py`)

- `save_checkpoint(turn: int, history_summary: str)` — overwrites
  `CHECKPOINT_FILE` with `{"turn": turn, "history_summary": history_summary}`.
  Called at the start of every turn (not just on pause) so a hard crash
  loses at most one turn.
- `load_checkpoint() -> dict | None` — returns parsed JSON or `None` if the
  file doesn't exist.
- `clear_checkpoint()` — deletes the file. Called only on clean completion
  (`DONE` reached), not on pause.

### 8.5 Notifier (`notifier.py`)

- `notify_phone(message: str, title: str = "Bridge agent")` — `POST` to
  `https://ntfy.sh/{NTFY_TOPIC}` with the message as the body and `Title` /
  `Priority: high` headers. Wrapped in try/except — a failed notification
  must never crash the main loop; log to console instead.
- Called on: rate-limit pause, clean completion, and (recommended addition
  for the build) any unhandled exception in the main loop, so the user
  isn't left wondering why the terminal went quiet.

### 8.6 Main loop (`main.py`)

1. Parse initial task from CLI arg or interactive prompt.
2. Resolve Antigravity window; focus it.
3. Attempt checkpoint load; if found, ask user (input prompt) whether to
   resume from saved turn/history or start fresh.
4. Launch Playwright persistent context, navigate to `CHAT_SITE_URL`, block
   on `input()` for the user to confirm login/page readiness (first run
   only — persistent profile means subsequent runs may not need this, but
   don't assume; always prompt).
5. Loop while `turn < MAX_TURNS`:
   a. `save_checkpoint(turn, history_summary)`.
   b. Get next instruction from orchestrator; if it contains `STOP_TOKEN`, break.
   c. Send to Antigravity, wait for response.
   d. Try: send Antigravity's output to chat UI, wait for reply.
      Except `RateLimitDetected`: notify phone, block on `input()` for
      manual account switch, `page.reload()`, `continue` (retry same turn,
      do not increment `turn`).
   e. Append both outputs to `history_summary`; increment `turn`.
   f. If chat reply contains `STOP_TOKEN`, break.
6. On loop exit: close Playwright context, `clear_checkpoint()` only if
   exited via `DONE` (not via `MAX_TURNS` exhaustion — that should keep the
   checkpoint so the user can inspect/resume), `notify_phone("Loop
   finished")`.

---

## 9. Error handling requirements (must implement, not optional)

- Every external call (Ollama HTTP, Playwright locator actions, pywinauto
  control lookups) must be wrapped so a transient failure doesn't kill the
  whole process silently — log the exception, notify the phone, and either
  retry once or pause for manual intervention, not a bare crash.
- Missing/placeholder config values (e.g. `NTFY_TOPIC` still set to a
  template default) must cause a startup error, not a runtime failure deep
  in the loop.
- If Antigravity's window can't be found at startup, fail immediately with
  a clear message — don't proceed into the loop.

## 10. Setup steps required from the user before this can run (document in README.md)

1. `ollama pull qwen3:8b`
2. `pip install playwright pywinauto pyperclip requests` then
   `playwright install chromium`
3. Run the `pywinauto` inspector against a live Antigravity window to get
   real `auto_id` values for input box, send button, output panel.
4. Open the target chat site in a real browser, use devtools to find CSS
   selectors for input box, send button, and latest-response container.
5. Pick an unguessable `NTFY_TOPIC` string, install the ntfy app on phone,
   subscribe to that topic.
6. Fill all placeholders in `config.py`.
7. First run: manually complete login in the Playwright-launched browser
   window when prompted, so the persistent profile has a valid session.

## 11. Acceptance criteria

- Running `python main.py "<task>"` with valid config completes a
  multi-turn Antigravity/chat exchange with zero manual copy-paste.
- Killing the process mid-run and re-running with the same checkpoint
  present resumes from the correct turn rather than restarting.
- Simulated rate-limit text on the chat page triggers a phone notification
  and a clean pause (not a crash) within one polling interval.
- No API keys, billing config, or paid endpoints anywhere in the codebase.

## 12. Known risks (carried from prior discussion, unchanged)

| Risk | Mitigation status |
|---|---|
| Antigravity chat panel has no accessible UIA tree | Unmitigated in v1 — fallback would be OCR/pixel coords, out of scope |
| Streaming output causes false "stable" detection | Partially mitigated via `IDLE_STABLE_SECONDS` tuning; not solved structurally |
| Free-tier rate limits interrupt long runs | Mitigated via detection + notify + checkpoint/resume |
| Chat site DOM selectors change over time | Unmitigated — requires manual re-verification, documented as maintenance burden |
| Bot-like usage pattern flags account | Partially mitigated — recommend the build add randomized delay jitter (e.g. `time.sleep(random.uniform(1, 3))` before each send) on top of this spec |
| No filesystem sandboxing | Unmitigated, accepted risk per non-goals |

## 13. Build order (suggested phases for the IDE agent)

1. `checkpoint.py` + `notifier.py` — no external dependencies besides
   `requests`, easiest to get right and test in isolation first.
2. `antigravity_driver.py` — test against the real Antigravity window with
   placeholder-free config before touching the browser side.
3. `chat_driver.py` including `check_rate_limit` — test against the real
   chat site manually before wiring into the loop.
4. `orchestrator.py` — test `ask_qwen` standalone against a running Ollama
   instance.
5. `main.py` — wire everything together per section 8.6.
6. Manual end-to-end run with a trivial task (e.g. "say hello") to verify
   the full loop before trusting it with real work.
