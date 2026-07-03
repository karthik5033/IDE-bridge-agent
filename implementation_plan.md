# Bridge Agent V2 — Full Upgrade Plan

> **Context**: The bridge agent currently automates a Claude ↔ Antigravity loop via Playwright + pywinauto. It works, but the output apps are "noob level", the terminal interface is boring, and the UI critic (8B local vision model) can't judge real design quality. This plan fixes all of that.

---

## Phase 1: Design System Injection (Prompt Engineering Overhaul)

**Goal**: Stop saying "premium" and start injecting *specific, opinionated design constraints* into every build.

### What to build

Create a `design_library/` folder at `d:\coding_files\kpautomate\bridge_agent\design_library\`:

```
design_library/
├── tokens.json
├── typography.md
├── color_palettes/
│   ├── light_neutral.md      # Apple-style: whites, grays, one accent
│   ├── dark_refined.md       # Linear-style: not generic dark, actual dark palette
│   └── warm_editorial.md     # Stripe-style: warm whites, deep blues
├── patterns/
│   ├── navigation.md         # Real code: sticky nav, mobile hamburger, breadcrumbs
│   ├── hero_sections.md      # 3-4 non-generic hero patterns with actual CSS
│   ├── cards.md              # Card grids, feature cards, pricing cards
│   ├── layouts.md            # Grid systems, sidebar layouts, dashboard grids
│   ├── forms.md              # Input styles, validation states, button variants
│   └── footers.md            # Minimal footer, mega footer, CTA footer
├── anti_patterns.md           # The "NEVER do this" list (expanded from current critic)
└── references.md              # URLs of real sites to study per category
```

#### `tokens.json` — Concrete design tokens

```json
{
  "spacing": {
    "unit": "4px",
    "scale": [4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128],
    "note": "All spacing MUST come from this scale. No arbitrary values."
  },
  "border_radius": {
    "none": "0px",
    "sm": "4px",
    "md": "8px",
    "lg": "12px",
    "xl": "16px",
    "full": "9999px",
    "note": "Pick ONE radius personality for the whole app. Don't mix rounded and sharp."
  },
  "shadows": {
    "sm": "0 1px 2px rgba(0,0,0,0.05)",
    "md": "0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1)",
    "lg": "0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.1)",
    "note": "Use shadows sparingly. Max 2 shadow levels in any single app."
  },
  "transitions": {
    "fast": "150ms ease",
    "normal": "200ms ease",
    "slow": "300ms ease",
    "note": "ONLY use opacity and transform for animations. No animating width/height/margin."
  }
}
```

#### `typography.md` — Font pairing rules

```markdown
## Approved Font Pairings (pick ONE pair per project)

### Pair 1: Clean Modern (shadcn-style)
- Display: Inter 600/700
- Body: Inter 400/500
- Mono: JetBrains Mono 400

### Pair 2: Editorial Premium (Stripe-style)
- Display: Instrument Serif 400
- Body: Inter 400/500
- Mono: IBM Plex Mono 400

### Pair 3: Geometric Sharp (Linear-style)
- Display: Outfit 600/700
- Body: Inter 400/500
- Mono: Fira Code 400

## Type Scale (use rem, base 16px)
- xs: 0.75rem / 1rem line-height
- sm: 0.875rem / 1.25rem
- base: 1rem / 1.5rem
- lg: 1.125rem / 1.75rem
- xl: 1.25rem / 1.75rem
- 2xl: 1.5rem / 2rem
- 3xl: 1.875rem / 2.25rem
- 4xl: 2.25rem / 2.5rem
- 5xl: 3rem / 1.1 (tight for display text)

## Rules
- NEVER use more than 2 font families in one project
- NEVER use font-weight below 400 or above 700
- Body text: always 400 or 500 weight, never bold
- Headings: always 600 or 700, never 400
- Letter-spacing: -0.02em on display text (2xl+), 0 on body
```

#### `anti_patterns.md` — Expanded rejection criteria

```markdown
## HARD REJECT — if ANY of these appear, the design has failed:

### Color
- Warm cream (#F4F1EA) + terracotta (#D97757) — the 2024 AI default palette
- Pure black (#000) background + single neon accent (lime, cyan, hot pink)
- Rainbow gradients or more than 3 colors used prominently
- Using opacity/transparency as a substitute for actual color choices

### Layout
- Centered hero with "big number + small label + gradient blob" when the content doesn't call for it
- Numbered section markers (01/ 02/ 03/) as decoration on non-sequential content
- Newspaper-column layout when the content isn't editorial
- Everything centered with no left-alignment anywhere

### Typography
- Default system fonts (no Google Fonts loaded)
- More than 2 font families
- Display text and body text using the same weight
- Inconsistent heading sizes (h2 larger than h1, etc.)

### Animation
- More than 3 distinct animation types on one page
- Animations longer than 500ms
- Parallax scrolling when the content doesn't benefit from depth
- Scroll-triggered animations on every single element
- "Floating" decorative shapes/blobs

### Components
- Bootstrap or Tailwind with zero customization (visible defaults)
- Unstyled focus states (browser default blue outline)
- Buttons with no hover/active state transitions
- Cards that all look identical with no visual hierarchy
- Generic placeholder images (gradient squares, stock photos)

## PASS CRITERIA — the design must show:
- A specific point of view tied to what the app actually IS
- Type pairing that looks intentional (not just "whatever sans-serif")
- Consistent spacing rhythm (eyeball test: could you overlay a 8px grid and it aligns?)
- Color restraint (2-3 colors max, used with purpose)
- Motion only where it serves UX (hover feedback, page transitions, loading states)
- The whole thing reads like a real product, not a demo/template
```

### How to wire it into the prompt

Modify `main.py` Phase 1 prompt construction:

```python
def _load_design_library():
    """Loads all design library files and concatenates them into a prompt section."""
    library_dir = os.path.join(os.path.dirname(__file__), "design_library")
    sections = []
    for root, dirs, files in os.walk(library_dir):
        for fname in sorted(files):
            filepath = os.path.join(root, fname)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            relative = os.path.relpath(filepath, library_dir)
            sections.append(f"### {relative}\n{content}")
    return "\n\n---\n\n".join(sections)
```

Then inject into Phase 1:
```python
design_system = _load_design_library()
phase1_prompt = f"""You are an expert architect. You MUST follow the design system below exactly.
Do not deviate. Do not add your own aesthetic opinions. The design system IS the aesthetic.

=== DESIGN SYSTEM (MANDATORY) ===
{design_system}
=== END DESIGN SYSTEM ===

Now, given the task below, create a detailed implementation plan.

Task: {initial_task}"""
```

> [!IMPORTANT]
> This is the single highest-impact change. Everything else is secondary to this. Bad prompts → bad output, regardless of how many agents or critics you throw at it.

---

## Phase 2: ChatGPT Go as the UI Critic (Your Idea)

**Goal**: Replace the local 8B vision model with ChatGPT Go (GPT-4o vision) for design criticism. Doesn't run out, actually good at judging UI.

### Architecture

```
Current flow:
  Antigravity finishes step → screenshot → qwen3-vl:8b (local) → pass/fail

New flow:
  Antigravity finishes step → screenshot → ChatGPT Go tab (Playwright) → pass/fail
```

### How it works

You already have Playwright connected to Chrome via CDP. You already know how to:
- Find/open tabs
- Type into chat inputs
- Wait for responses
- Upload images

The plan:

1. **On startup**, open a second Playwright tab to `https://chatgpt.com` (alongside the Claude tab)
2. **On critic trigger**, instead of calling Ollama:
   - Take screenshot of dev server (already done in current code)
   - Save screenshot to a temp file
   - Switch to the ChatGPT tab
   - Upload the screenshot as an image attachment
   - Type the critic prompt (same system criteria from `anti_patterns.md`)
   - Wait for ChatGPT's response
   - Parse the JSON verdict
   - Route back into the existing critic loop

### Files to modify

#### `config.py` — Add ChatGPT config

```python
# --- UI Critic Config (V2: ChatGPT Go) ---
CRITIC_MODE = "chatgpt"  # "local" (old qwen3-vl) or "chatgpt" (new)
CHATGPT_URL = "https://chatgpt.com"
CHATGPT_SELECTORS = {
    "input_box": 'div[id="prompt-textarea"]',     # ChatGPT's input area
    "send_button": 'button[data-testid="send-button"]',
    "file_upload": 'input[type="file"]',           # hidden file input for image upload
    "latest_response": 'div[data-message-author-role="assistant"]:last-child',
}
```

#### `ui_critic.py` — Dual-mode critic

```python
def evaluate_ui(screenshot_b64, console_errors, chatgpt_page=None):
    if config.CRITIC_MODE == "chatgpt" and chatgpt_page:
        return _evaluate_via_chatgpt(screenshot_b64, console_errors, chatgpt_page)
    else:
        return _evaluate_via_local(screenshot_b64, console_errors)
```

The `_evaluate_via_chatgpt` function:
1. Saves screenshot bytes to a temp `.jpg` file
2. Uses the hidden `<input type="file">` element to upload it (Playwright's `set_input_files()`)
3. Types the critic prompt into the chat input
4. Waits for response (same stability-based polling as `chat_driver.py`)
5. Parses JSON from the response text
6. Returns `{"verdict": "pass" | "fix_needed", "reason": ..., "instruction": ...}`

#### `main.py` — Pass chatgpt_page to critic

In the startup section, after finding/opening the Claude tab:
```python
# Find or open ChatGPT tab for UI criticism
chatgpt_page = None
if config.CRITIC_MODE == "chatgpt":
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if "chatgpt.com" in pg.url:
                chatgpt_page = pg
                break
    if not chatgpt_page:
        chatgpt_page = ctx.new_page()
        chatgpt_page.goto(config.CHATGPT_URL, wait_until="domcontentloaded")
    print(f"ChatGPT critic tab ready: {chatgpt_page.url}")
```

Then in the Phase 3 loop, pass it:
```python
critic_result = evaluate_ui(screenshot_b64, new_errors, chatgpt_page=chatgpt_page)
```

### Advantages

| | Local 8B Model | ChatGPT Go |
|---|---|---|
| Vision quality | Mediocre | GPT-4o level |
| Rate limits | None | "Unlimited" with Go plan |
| Speed | ~10-15s per eval | ~5-10s per eval |
| Cost | Free (local GPU) | Free (included in Go) |
| Can judge shadcn-level design | ❌ No | ✅ Yes |

### Risk: ChatGPT Go rate limits

Even "unlimited" plans can have soft throttling. Mitigate by:
- Only triggering the critic when frontend files were touched (current behavior)
- Adding a cooldown: don't critique more than once every 3 turns
- Falling back to local model if ChatGPT returns an error/rate-limit

> [!TIP]
> Keep the local `qwen3-vl:8b` as a fallback. If ChatGPT is slow or throttled, the system should gracefully degrade to local evaluation rather than blocking.

---

## Phase 3: Multi-Model Local Orchestration

**Goal**: Use the right local model for the right job instead of one model for everything.

### Current state
- `config.OLLAMA_MODEL = "qwen2.5-coder:latest"` — used for ALL orchestrator calls

### New state

```python
# config.py
OLLAMA_MODELS = {
    "orchestrator": "qwen3.5:9b",         # signal detection, phase tagging
    "code_analyzer": "qwen2.5-coder:latest",  # error analysis, code review
    "local_critic": "qwen3-vl:8b",        # fallback vision critic (when ChatGPT unavailable)
}
```

### Where each model is used

| Function | Current Model | New Model | Why |
|---|---|---|---|
| `orchestrator.analyze_message()` | qwen2.5-coder | **qwen3.5:9b** | Better at reasoning about "is this done?" vs "is this an error?" — fewer false positives |
| Error trace analysis (NEW) | N/A | **qwen2.5-coder** | When an error IS detected, ask the coder model to summarize the fix needed before forwarding |
| UI Critic (fallback) | qwen3-vl:8b | **qwen3-vl:8b** (unchanged) | Only used when ChatGPT is unavailable |

### New capability: Error Summarizer

When `analyze_message()` detects `is_error: true`, instead of just forwarding the raw error, run it through `qwen2.5-coder` with a specialized prompt:

```python
def summarize_error(error_text: str) -> str:
    """Uses the coder model to produce a concise, actionable error summary."""
    payload = {
        "model": config.OLLAMA_MODELS["code_analyzer"],
        "prompt": error_text,
        "system": "Extract the root cause and suggest a one-line fix. Output: {\"root_cause\": str, \"fix\": str}",
        "stream": False,
        "format": "json"
    }
    # ... same Ollama call pattern
```

This means instead of forwarding a 200-line traceback to Claude, you forward:
```
Error detected: TypeError in App.jsx:42 — cannot read property 'map' of undefined.
Fix: Add null check before mapping over `data.items`.
```

Much better use of Claude's rate-limited turns.

---

## Phase 4: Web Dashboard + Mobile Control

**Goal**: Replace the terminal with a real-time web dashboard that works from your phone too.

### Tech Stack

| Layer | Tech | Why |
|---|---|---|
| Backend | **FastAPI** (Python) | You already have Python everywhere, WebSocket support built in |
| Real-time | **WebSocket** | Live streaming of agent conversations, turn updates |
| Frontend | **Next.js + shadcn/ui** | Since you want shadcn-level UI, use shadcn itself. Mobile responsive by default |
| Mobile | **PWA** (Progressive Web App) | Install on phone home screen, works offline for viewing history, push notifications |
| Notifications | **ntfy** (keep existing) + **Web Push** | ntfy as backup, native browser push for the dashboard |

### Dashboard Features

#### Main View (Desktop)
```
┌──────────────────────────────────────────────────────────┐
│  Bridge Agent Dashboard                    ● Running      │
├──────────┬───────────────────────────────────────────────┤
│          │                                               │
│ Sidebar  │  Main Panel                                   │
│          │                                               │
│ ● Status │  ┌─────────────┐  ┌─────────────────────────┐│
│ ○ History│  │ Dev Preview  │  │ Agent Conversation      ││
│ ○ Config │  │ (live iframe │  │                         ││
│ ○ Design │  │  or auto-    │  │ Claude: "Next, build    ││
│   Library│  │  refreshing  │  │ the sidebar component..." ││
│ ○ Logs   │  │  screenshot) │  │                         ││
│          │  │              │  │ Antigravity: "Done.     ││
│          │  └─────────────┘  │ Created Sidebar.jsx..." ││
│          │                    │                         ││
│          │  ┌─────────────┐  │ [Critic]: Pass ✅       ││
│          │  │ Console Logs │  │                         ││
│          │  │ (streaming)  │  └─────────────────────────┘│
│          │  └─────────────┘                              │
│          │                                               │
│          │  [⏸ Pause] [▶ Resume] [⏹ Stop] [💬 Inject]  │
├──────────┴───────────────────────────────────────────────┤
│ Turn 7/40 │ Phase: Review Loop │ Current: Claude → AG    │
└──────────────────────────────────────────────────────────┘
```

#### Mobile View (Responsive / PWA)
```
┌─────────────────────┐
│ Bridge Agent    ● ▶  │
├─────────────────────┤
│ Turn 7/40  Phase 3  │
│ Claude is thinking… │
├─────────────────────┤
│ ┌─────────────────┐ │
│ │  Dev Preview    │ │
│ │  (screenshot)   │ │
│ └─────────────────┘ │
│                     │
│ Latest:             │
│ Claude: "Build the  │
│ nav component with  │
│ the Inter font..."  │
│                     │
│ Critic: ✅ Pass     │
│                     │
│ [⏸] [▶] [⏹] [💬]  │
├─────────────────────┤
│ ⚡ Console: No errs │
└─────────────────────┘
```

### Backend Architecture

```
bridge_agent/
├── main.py                    # MODIFIED: now starts FastAPI server alongside bridge loop
├── dashboard/
│   ├── server.py              # FastAPI app, WebSocket endpoints, REST API
│   ├── ws_manager.py          # WebSocket connection manager (broadcast to all clients)
│   ├── models.py              # Pydantic models for turn data, status, etc.
│   └── static/                # Built Next.js output (or served separately in dev)
├── dashboard_frontend/        # Next.js project
│   ├── app/
│   │   ├── page.tsx           # Main dashboard page
│   │   ├── layout.tsx         # Root layout with sidebar
│   │   └── history/page.tsx   # Turn history view
│   ├── components/
│   │   ├── DevPreview.tsx     # Auto-refreshing screenshot/iframe
│   │   ├── ConversationPanel.tsx  # Streaming agent messages
│   │   ├── ConsolePanel.tsx   # Dev server logs
│   │   ├── ControlBar.tsx     # Pause/Resume/Stop/Inject buttons
│   │   ├── StatusBar.tsx      # Turn counter, phase, active agent
│   │   └── CriticBadge.tsx    # Pass/fail indicator with reason tooltip
│   ├── lib/
│   │   └── ws.ts              # WebSocket client hook
│   └── public/
│       └── manifest.json      # PWA manifest
```

### WebSocket Events

```python
# Server → Client (broadcast)
{
    "type": "turn_update",
    "data": {
        "turn": 7,
        "phase": 3,
        "active_agent": "claude",  # or "antigravity" or "critic"
        "status": "running"        # or "paused", "waiting", "done", "error"
    }
}

{
    "type": "message",
    "data": {
        "source": "claude",        # or "antigravity", "critic", "system"
        "content": "Next, implement the sidebar...",
        "timestamp": "2026-07-04T01:30:00Z",
        "turn": 7
    }
}

{
    "type": "screenshot",
    "data": {
        "image_b64": "...",        # base64 JPEG of dev server
        "timestamp": "..."
    }
}

{
    "type": "console",
    "data": {
        "level": "error",          # or "info", "warn"
        "message": "TypeError: ...",
        "timestamp": "..."
    }
}

# Client → Server
{
    "type": "command",
    "data": {
        "action": "pause" | "resume" | "stop" | "inject",
        "payload": "optional instruction text for inject"
    }
}
```

### How the bridge loop changes

The bridge loop in `main.py` currently runs synchronously. To support the dashboard:

1. **Run the bridge loop in a background thread** (or asyncio task)
2. **FastAPI serves the dashboard on a separate port** (e.g., `localhost:8080`)
3. **Every time the bridge does something** (sends message, receives response, critic runs), it emits a WebSocket event
4. **Dashboard controls** (pause/resume/stop/inject) set flags that the bridge loop checks between turns

```python
# Simplified integration
from dashboard.server import app, broadcast, check_commands

# In the bridge loop, after every significant action:
await broadcast({"type": "message", "data": {"source": "claude", "content": response}})

# Before each turn:
cmd = check_commands()  # non-blocking check for pause/stop/inject
if cmd == "pause":
    await broadcast({"type": "turn_update", "data": {"status": "paused"}})
    wait_for_resume()
elif cmd == "inject":
    current_payload = cmd.payload  # override the next message
```

### Running it

```bash
# Terminal 1: Start the dashboard server
python -m dashboard.server  # FastAPI on port 8080

# Terminal 2: Start the bridge (or integrate into one process)
python main.py "build a portfolio app"

# Phone: Open http://<local-ip>:8080 in browser, add to home screen as PWA
```

> [!IMPORTANT]
> For mobile access over your local network, the dashboard server needs to bind to `0.0.0.0:8080` (not just localhost), and your phone must be on the same WiFi. Alternatively, use a tunnel like `ngrok` or `cloudflared` for access from anywhere.

---

## Phase 5: Additional Ideas

### 5.1 Component Cache (Reuse Good Work)

Once the agent builds a component that passes the critic, save it:

```
component_cache/
├── navbars/
│   ├── sticky_glassmorphism.jsx
│   └── minimal_underline.jsx
├── heroes/
│   ├── split_image_text.jsx
│   └── centered_cta.jsx
└── index.json   # metadata: which project used it, critic score, etc.
```

When a new project needs a similar component, inject the cached version as a reference:
*"Here's a navbar component that passed our design critic before. Use it as a starting point, adapt the colors and content."*

### 5.2 Conversation Compression

Currently `history_summary` grows unbounded and gets bloated. Add a compression step:

Every 5 turns, run the history through `qwen3.5:9b` with:
*"Compress this conversation history to under 500 words. Keep only: decisions made, files created, current state of the project, and what's left to do."*

This keeps Claude's context window clean and focused.

### 5.3 Prompt Template Library

Instead of hardcoding prompts in `main.py`, create a `prompts/` folder:

```
prompts/
├── phase1_architect.md        # The planning prompt template
├── phase2_handoff.md          # Handing the plan to Antigravity
├── phase3_review.md           # Review loop template
├── critic_chatgpt.md          # ChatGPT critic prompt
├── error_summarizer.md        # Error summarization prompt
└── compression.md             # History compression prompt
```

Each file uses `{variable}` placeholders that get `.format()`-ed at runtime. Makes it easy to tweak prompts without touching Python code.

### 5.4 Auto-Deploy Preview

After each major milestone (every N turns), auto-deploy a static build to a free host:

```python
# After critic passes:
subprocess.run(["npm", "run", "build"], cwd=dev_server_cwd)
subprocess.run(["npx", "netlify-cli", "deploy", "--dir=dist", "--json"], ...)
# Parse the deploy URL, send it to your phone via ntfy
```

Then you can view the actual app on your phone, not just a screenshot.

### 5.5 Multi-Chat Rotation

Since you have both Claude and ChatGPT:

```
Turn 1-10:  Claude as architect
Turn 11-20: If Claude hits rate limit → swap to ChatGPT as architect
Turn 21+:   Back to Claude (cooldown passed)
```

Config:
```python
CHAT_SITES = [
    {"url": "https://claude.ai/new", "selectors": CLAUDE_SELECTORS, "name": "Claude"},
    {"url": "https://chatgpt.com", "selectors": CHATGPT_SELECTORS, "name": "ChatGPT"},
]
ACTIVE_ARCHITECT = 0  # index into CHAT_SITES
ACTIVE_CRITIC = 1     # use the OTHER one as critic
```

This means you NEVER hit a rate limit wall — just swap. And the critic is always the model that ISN'T currently architecting.

### 5.6 Quality Metrics Tracking

Track metrics across runs to see if your prompt changes are actually improving output:

```json
{
  "run_id": "2026-07-04-portfolio",
  "task": "portfolio web app",
  "turns_used": 14,
  "critic_fails": 3,
  "critic_passes": 11,
  "errors_detected": 2,
  "design_system_used": "light_neutral",
  "font_pair": "Inter + Instrument Serif",
  "final_verdict": "pass",
  "notes": "Hero section needed 2 critic retries"
}
```

Store in `metrics/` folder or a SQLite database. The dashboard can show trends over time.

---

## Implementation Order

| Priority | Phase | Effort | Impact |
|---|---|---|---|
| 🔴 P0 | **Phase 1: Design Library + Prompt Overhaul** | ~2-3 hours | Massive — fixes the root cause of "noob level" output |
| 🔴 P0 | **Phase 3: Swap orchestrator to qwen3.5:9b** | ~10 minutes | Easy win — one config change |
| 🟠 P1 | **Phase 2: ChatGPT Go as UI Critic** | ~3-4 hours | High — replaces the weakest link (8B vision model) |
| 🟠 P1 | **Phase 5.3: Prompt Template Library** | ~1 hour | Medium — makes future prompt tuning much easier |
| 🟡 P2 | **Phase 5.2: Conversation Compression** | ~1 hour | Medium — prevents context bloat on long runs |
| 🟡 P2 | **Phase 5.5: Multi-Chat Rotation** | ~2-3 hours | High — eliminates rate limit as a blocker entirely |
| 🔵 P3 | **Phase 4: Web Dashboard + Mobile** | ~1-2 days | Transformative UX, but the biggest build |
| 🔵 P3 | **Phase 5.1: Component Cache** | ~2-3 hours | Compounds over time |
| ⚪ P4 | **Phase 5.4: Auto-Deploy Preview** | ~1 hour | Nice to have |
| ⚪ P4 | **Phase 5.6: Quality Metrics** | ~2 hours | Nice to have |

---

## Open Questions

> [!IMPORTANT]
> **ChatGPT Go Selectors**: The CSS selectors for ChatGPT's input box, send button, and file upload will need to be verified via DevTools, just like you did for Claude. They change periodically. Do you want to build a `find_selectors_chatgpt.py` similar to your existing `find_selectors.py`?

> [!IMPORTANT]
> **Dashboard Tech Choice**: I suggested Next.js + shadcn/ui for the frontend. But since this is a local tool, a simpler option like a single HTML file with vanilla JS + WebSocket might be faster to build and maintain. Which do you prefer — premium dashboard UI, or "get it working fast"?

> [!IMPORTANT]
> **Design Library Curation**: The design tokens and patterns I listed above are a starting point. Do you want me to pre-populate them with real, production-quality CSS/component code, or do you want to curate them yourself based on sites you personally like?

> [!WARNING]
> **ChatGPT Image Upload via Playwright**: Uploading images to ChatGPT via the hidden file input works, but ChatGPT sometimes uses a drag-and-drop zone instead. This needs testing — if `set_input_files()` doesn't work, we'll need to use Playwright's drag-and-drop API or paste from clipboard. Build the fallback path from the start.
