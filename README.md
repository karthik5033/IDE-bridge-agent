<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/Playwright-Browser%20Automation-45BA63?style=for-the-badge&logo=playwright&logoColor=white" alt="Playwright"/>
  <img src="https://img.shields.io/badge/Windows-11-0078D4?style=for-the-badge&logo=windows&logoColor=white" alt="Windows 11"/>
  <img src="https://img.shields.io/badge/Ollama-Local%20LLM-000000?style=for-the-badge" alt="Ollama"/>
  <img src="https://img.shields.io/badge/Cost-$0-28a745?style=for-the-badge" alt="Zero Cost"/>
</p>

<h1 align="center">🌉 Bridge Agent</h1>

<p align="center">
  <b>Fully autonomous, zero-cost local automation that bridges AI coding agents with browser-based AI assistants — no manual copy-paste, no paid APIs, no babysitting.</b>
</p>

<p align="center">
  <i>Give it a task. Walk away. Come back to a finished, production-quality web application.</i>
</p>

---

## 📖 Table of Contents

- [What Is Bridge Agent?](#-what-is-bridge-agent)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Phase Pipeline](#-phase-pipeline-how-it-builds-an-app)
- [Module Reference](#-module-reference)
- [Project Structure](#-project-structure)
- [Prompt Engineering System](#-prompt-engineering-system)
- [Design Library](#-design-library)
- [Dashboard (Web UI)](#-dashboard-web-ui)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#%EF%B8%8F-configuration)
- [Usage](#-usage)
- [Checkpoint & Resume](#-checkpoint--resume)
- [Known Risks & Mitigations](#-known-risks--mitigations)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🤔 What Is Bridge Agent?

Bridge Agent is a **local orchestration system** that connects two AI systems — the [Antigravity IDE](https://antigravity.dev) (a desktop AI coding agent) and a browser-based AI chat (Claude.ai or ChatGPT) — into a single, fully autonomous pipeline.

**The problem it solves:** Without Bridge Agent, building an app with these tools requires a human to manually copy-paste between the two AI systems, deciding what to send where, every single turn. The human becomes nothing more than a transport layer.

**Bridge Agent replaces the human transport layer entirely.** It drives both UIs at the OS level, uses local LLMs (via Ollama) for decision-making, and runs the full architect → build → critique → fix loop unattended.

```
┌──────────────────────────────────────────────────────────────────┐
│                     THE OLD WAY (MANUAL)                        │
│                                                                  │
│   You ──read──> Antigravity ──copy──> You ──paste──> Claude     │
│   Claude ──read──> You ──copy──> Antigravity ──read──> You ...  │
│                                                                  │
│   ⏱️ Hours of babysitting. Hundreds of copy-pastes.              │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                     THE NEW WAY (BRIDGE AGENT)                  │
│                                                                  │
│   You ──task──> Bridge Agent ──────────────────> Finished App   │
│                                                                  │
│   ☕ Go get coffee. Or sleep. It handles everything.             │
└──────────────────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

| Feature | Description |
|---|---|
| **🤖 Fully Autonomous** | No human intervention required after starting. Three-phase pipeline runs to completion. |
| **💰 Zero Cost** | Uses Ollama local LLMs, free-tier Claude/ChatGPT, and ntfy.sh for notifications. No API keys or billing anywhere. |
| **🖥️ Desktop + Browser Automation** | Drives Antigravity via Win32 API / pywinauto, and Claude/ChatGPT via Playwright CDP. |
| **👁️ AI-Powered UI Critic** | Automatically screenshots the built app, explores pages/routes, and evaluates design quality against anti-pattern rules. |
| **🔄 Self-Healing Loop** | Critic failures route fixes directly back to Antigravity. Persistent failures escalate to Claude for architectural guidance. |
| **💾 Checkpoint & Resume** | Every turn is checkpointed to disk. Kill it mid-run, resume exactly where you left off. |
| **📱 Phone Notifications** | Pushes real-time alerts to your phone via ntfy.sh on rate limits, errors, and completion. |
| **🛡️ Rate Limit Detection** | Scans chat pages for rate-limit phrases, pauses gracefully, and waits for manual account switch. |
| **🌐 Web Dashboard** | Real-time monitoring via a Next.js dashboard connected over WebSocket to the FastAPI backend. |
| **🎨 Design Library** | Ships with design tokens, typography rules, and anti-pattern guidelines baked into every prompt. |

---

## 🏗 System Architecture

### High-Level Overview

```
                          ┌─────────────────────────────┐
                          │      Bridge Agent (main.py)  │
                          │    ┌─────────────────────┐   │
                          │    │   Phase Controller   │   │
                          │    │  (3-phase pipeline)  │   │
                          │    └────────┬────────────┘   │
                          │             │                 │
                          │    ┌────────┴────────────┐   │
                          │    │    Orchestrator      │   │
                          │    │  (Ollama / Qwen2.5)  │   │
                          │    │  Signal detection,   │   │
                          │    │  error analysis,     │   │
                          │    │  history compression  │   │
                          │    └────────┬────────────┘   │
                          └─────────────┼─────────────────┘
                     ┌──────────────────┼──────────────────┐
                     ▼                  ▼                   ▼
          ┌─────────────────┐ ┌──────────────────┐ ┌──────────────────┐
          │  Antigravity     │ │  Chat UI Driver   │ │  UI Critic       │
          │  Driver          │ │  (Playwright CDP) │ │  (Vision LLM /   │
          │  (Win32 / UIA)   │ │                    │ │   ChatGPT)       │
          └────────┬─────────┘ └────────┬──────────┘ └────────┬─────────┘
                   │                    │                      │
                   ▼                    ▼                      ▼
          ┌─────────────────┐ ┌──────────────────┐ ┌──────────────────┐
          │  Antigravity IDE │ │  Claude.ai /      │ │  Dev Server      │
          │  (Desktop App)   │ │  ChatGPT.com      │ │  (localhost:3000) │
          └──────────────────┘ └──────────────────┘ └──────────────────┘

    Cross-cutting concerns:
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐
    │ Checkpoint   │  │ Notifier     │  │ Bridge Logger│  │ Dev Server    │
    │ (JSON file)  │  │ (ntfy.sh)    │  │ (dual-mode)  │  │ Manager       │
    └──────────────┘  └──────────────┘  └──────────────┘  └───────────────┘
```

### Component Interaction Map

```
                    ┌──────────────────────────┐
                    │       User's Phone       │
                    │     (ntfy.sh alerts)     │
                    └────────────▲─────────────┘
                                 │ HTTP POST
                    ┌────────────┴─────────────┐
                    │       notifier.py         │
                    └────────────▲─────────────┘
                                 │
    ┌────────────────────────────┼────────────────────────────┐
    │                        main.py                          │
    │                   (Phase Controller)                     │
    │                                                          │
    │  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
    │  │ Phase 1:    │  │ Phase 2:     │  │ Phase 3:      │  │
    │  │ Architect   │──│ Build        │──│ Critic Loop   │  │
    │  │ (Claude)    │  │ (Antigravity)│  │ (Fix ↔ Judge) │  │
    │  └──────┬──────┘  └──────┬───────┘  └──┬─────┬──────┘  │
    │         │                │              │     │          │
    │         ▼                ▼              ▼     ▼          │
    │  ┌────────────┐  ┌────────────┐  ┌────────┐┌─────────┐ │
    │  │chat_driver │  │antigravity │  │ui_critic││page_    │ │
    │  │   .py      │  │_driver.py  │  │  .py   ││explorer │ │
    │  └────────────┘  └────────────┘  └────────┘│  .py    │ │
    │                                             └─────────┘ │
    │  ┌────────────┐  ┌────────────┐  ┌──────────────────┐  │
    │  │checkpoint  │  │orchestrator│  │  dev_server.py   │  │
    │  │   .py      │  │   .py      │  │  (subprocess     │  │
    │  └────────────┘  └────────────┘  │   manager)       │  │
    │                                   └──────────────────┘  │
    └─────────────────────────────────────────────────────────┘
```

---

## 🔄 Phase Pipeline: How It Builds an App

Bridge Agent operates in a strict **three-phase pipeline**. Each phase has a single responsibility and a clean handoff to the next.

```
 ┌───────────────────────────────────────────────────────────────────┐
 │                    BRIDGE AGENT PIPELINE                          │
 │                                                                   │
 │  ┌─────────┐      ┌─────────┐      ┌─────────────────────────┐  │
 │  │ PHASE 1 │─────▶│ PHASE 2 │─────▶│        PHASE 3          │  │
 │  │Architect│      │ Builder │      │     Critic Loop          │  │
 │  └─────────┘      └─────────┘      │                          │  │
 │                                      │  ┌───────┐    ┌──────┐ │  │
 │  Claude produces   Antigravity      │  │Critic │───▶│ Fix  │ │  │
 │  a project brief   builds the       │  │judges │    │(AG)  │ │  │
 │  from user task    entire app       │  └───┬───┘    └──┬───┘ │  │
 │  (ONE SHOT)        (ONE SHOT)       │      │           │      │  │
 │                                      │      └───pass?───┘      │  │
 │                                      │           │ yes          │  │
 │                                      │           ▼              │  │
 │                                      │        ✅ DONE           │  │
 │                                      └─────────────────────────┘  │
 └───────────────────────────────────────────────────────────────────┘
```

### Phase 1: Architect (Claude)

```
User Task ──▶ Phase 1 Prompt + Design Library ──▶ Claude.ai ──▶ Project Brief
```

- The user's raw task (e.g., *"Build a premium e-commerce site for headphones"*) is wrapped with the **Phase 1 Architect prompt** and the **Design Library**.
- Claude acts as a visionary product manager: it produces a comprehensive project brief covering concept, features, user flows, and design direction.
- If Claude asks questions instead of producing a brief, the system auto-replies up to 3 times forcing a decision.
- **Output:** A complete project brief (typically 2,000–8,000 chars).

### Phase 2: Builder (Antigravity)

```
Project Brief ──▶ Phase 2 Prompt ──▶ Antigravity IDE ──▶ Complete Application
```

- The project brief is wrapped with the **Phase 2 Builder prompt** and sent to Antigravity via OS-level automation.
- Antigravity builds the **entire application in a single pass** — scaffolding, components, styling, mock data, routing, everything.
- The system waits for Antigravity to write its response to `bridge_response.txt` (file-based IPC — far more reliable than UI scraping).
- **Output:** A running web application on `localhost:3000`.

### Phase 3: Critic Loop (UI Critic ↔ Antigravity)

```
┌──────────────────────────────────────────────────────────────┐
│                     CRITIC LOOP DETAIL                       │
│                                                              │
│  ┌──────────────┐    ┌───────────────┐    ┌──────────────┐  │
│  │ Capture Page │───▶│  UI Critic    │───▶│  Verdict?    │  │
│  │ Context      │    │  Evaluates    │    │              │  │
│  │ • Screenshot │    │  • Layout     │    │ PASS ──▶ ✅  │  │
│  │ • DOM summary│    │  • Typography │    │              │  │
│  │ • Console    │    │  • Color      │    │ FIX_NEEDED:  │  │
│  │   errors     │    │  • Components │    │  ├─ retry<3  │  │
│  │ • Routes     │    │  • Errors     │    │  │  send fix │  │
│  │ • Interactions    │  • Anti-      │    │  │  to AG ───┤  │
│  └──────────────┘    │    patterns   │    │  │           │  │
│         ▲            └───────────────┘    │  └─ retry≥3  │  │
│         │                                 │     escalate │  │
│         │                                 │     to Claude│  │
│         └─────────── loop back ◀──────────┘              │  │
│                                                           │  │
│  After 2 escalations: accept current state & terminate.  │  │
└──────────────────────────────────────────────────────────────┘
```

- The **Page Explorer** smartly captures the app: full-page screenshots, internal route navigation, interactive element clicking (buttons, tabs, accordions), all stitched into a labeled composite image.
- The **UI Critic** (ChatGPT or local Ollama vision model) evaluates against strict aesthetic and functional criteria, including anti-pattern detection for generic AI-generated designs.
- Fix instructions are routed **directly to Antigravity** without Claude involvement (faster, no context needed).
- If fixes fail 3 times (`CRITIC_RETRY_CAP`), the system **escalates to Claude** for architectural guidance, then feeds Claude's fix back to Antigravity.
- After 2 escalations without resolution, the system accepts the current state and terminates cleanly.

---

## 📦 Module Reference

### Core Modules

| Module | Responsibility | Key Functions |
|---|---|---|
| [`main.py`](main.py) | Phase controller, main loop, pipeline orchestration | `run_bridge()`, `_load_design_library()`, `_send_to_chat_with_retry()` |
| [`config.py`](config.py) | All configuration: selectors, models, timeouts, platform configs | `check_config()`, `load_prompt()` |
| [`orchestrator.py`](orchestrator.py) | LLM-powered signal detection, error summarization, history compression | `analyze_message()`, `summarize_error()`, `compress_history()` |

### Driver Modules

| Module | Responsibility | Key Functions |
|---|---|---|
| [`antigravity_driver.py`](antigravity_driver.py) | Win32 window automation for the Antigravity IDE desktop app | `get_antigravity_window()`, `send_to_antigravity()`, `wait_for_antigravity_response()` |
| [`chat_driver.py`](chat_driver.py) | Browser automation for Claude.ai / ChatGPT via Playwright CDP | `send_to_chat_ui()`, `wait_for_chat_response()`, `check_rate_limit()` |

### Critic & Exploration Modules

| Module | Responsibility | Key Functions |
|---|---|---|
| [`ui_critic.py`](ui_critic.py) | UI quality evaluation via vision LLMs or web-based AI chat | `evaluate_ui()`, `capture_page_context()`, `extract_dom_summary()` |
| [`page_explorer.py`](page_explorer.py) | Smart page exploration: scrolling, route discovery, interaction testing | `explore_page()`, `stitch_screenshots()` |

### Infrastructure Modules

| Module | Responsibility | Key Functions |
|---|---|---|
| [`checkpoint.py`](checkpoint.py) | JSON-based state persistence for crash recovery | `save_checkpoint()`, `load_checkpoint()`, `clear_checkpoint()` |
| [`notifier.py`](notifier.py) | Phone push notifications via ntfy.sh | `notify_phone()` |
| [`dev_server.py`](dev_server.py) | Subprocess manager for the project's dev server | `DevServerManager.start()`, `.stop()`, `.get_new_errors()` |
| [`bridge_logger.py`](bridge_logger.py) | Dual-mode logger (CLI + WebSocket) with input queue | `bprint()`, `binput()`, `emit()` |
| [`text_utils.py`](text_utils.py) | Fuzzy text extraction and whitespace normalization | `fuzzy_extract_after()`, `normalize_whitespace()` |
| [`api_server.py`](api_server.py) | FastAPI backend for the web dashboard | WebSocket `/ws/stream`, REST `/api/start`, `/api/stop` |

### Utility & Debug Scripts

| Script | Purpose |
|---|---|
| [`find_selectors.py`](find_selectors.py) | Discovers CSS selectors from live Claude/ChatGPT pages |
| [`inspect_antigravity.py`](inspect_antigravity.py) | Dumps the UIA accessibility tree of the Antigravity window |
| [`debug_claude.py`](debug_claude.py) | Tests the Claude chat driver in isolation |
| [`test_chat_driver.py`](test_chat_driver.py) | Integration tests for `chat_driver.py` |
| [`test_dom_and_upload.py`](test_dom_and_upload.py) | Tests DOM extraction and screenshot upload to ChatGPT |
| [`calculator.py`](calculator.py) | Standalone test utility |

---

## 📁 Project Structure

```
bridge_agent/
├── main.py                      # 🎯 CLI entrypoint & phase controller
├── config.py                    # ⚙️  All configuration constants
├── orchestrator.py              # 🧠 LLM-based signal detection & analysis
├── antigravity_driver.py        # 🖥️  Win32/UIA desktop automation
├── chat_driver.py               # 🌐 Playwright browser automation
├── ui_critic.py                 # 👁️  Vision-based UI quality evaluation
├── page_explorer.py             # 🔍 Smart multi-page screenshot exploration
├── checkpoint.py                # 💾 JSON checkpoint save/load/clear
├── notifier.py                  # 📱 ntfy.sh phone notifications
├── dev_server.py                # 🖧  Dev server subprocess manager
├── bridge_logger.py             # 📝 Dual-mode logger (CLI + WebSocket)
├── text_utils.py                # 🔤 Fuzzy text extraction utilities
├── api_server.py                # 🚀 FastAPI backend for web dashboard
│
├── prompts/                     # 📄 LLM prompt templates
│   ├── phase1_architect.md      #    Phase 1: Claude architect prompt
│   ├── phase2_builder.md        #    Phase 2: Antigravity builder prompt
│   ├── critic_system.md         #    UI critic evaluation criteria
│   ├── chatgpt_critic_init.md   #    ChatGPT critic initialization
│   ├── orchestrator_system.md   #    Orchestrator signal detection prompt
│   ├── error_summarizer.md      #    Error analysis prompt
│   └── compression.md           #    History compression prompt
│
├── design_library/              # 🎨 Design system & guardrails
│   ├── tokens.json              #    Design tokens (colors, spacing, etc.)
│   ├── typography.md            #    Typography rules & scale
│   └── anti_patterns.md         #    AI design anti-patterns to avoid
│
├── bridge_web/                  # 🌐 Next.js monitoring dashboard
│   ├── src/                     #    React components & pages
│   ├── package.json             #    Dependencies (Next.js 16, React 19)
│   └── ...
│
├── browser_profile/             # 🔒 Playwright persistent context (gitignored)
├── bridge_checkpoint.json       # 💾 Runtime state file (gitignored)
├── requirements.txt             # 📦 Python dependencies
├── start_dashboard.ps1          # ⚡ One-click dashboard launcher
├── prd.md                       # 📋 Original product requirements document
├── running.md                   # 📋 Operational notes
└── .gitignore
```

---

## 🎯 Prompt Engineering System

Bridge Agent uses a sophisticated multi-prompt architecture. Each prompt is a Markdown template stored in `prompts/` and loaded at runtime via `config.load_prompt()`.

```
                        ┌─────────────────────┐
                        │    User's Task       │
                        │ "Build a headphone   │
                        │  e-commerce site"    │
                        └──────────┬──────────┘
                                   │
                                   ▼
 ┌─────────────────────────────────────────────────────────────┐
 │              phase1_architect.md                             │
 │  ┌─────────────────┐  ┌──────────────────────────────────┐ │
 │  │ Architect Rules  │  │ Design Library (injected)        │ │
 │  │ • Never ask      │  │ • tokens.json                    │ │
 │  │   questions      │  │ • typography.md                  │ │
 │  │ • Make decisions  │  │ • anti_patterns.md               │ │
 │  │ • Vision, not    │  │                                   │ │
 │  │   implementation │  └──────────────────────────────────┘ │
 │  └─────────────────┘                                        │
 └──────────────────────────────────┬──────────────────────────┘
                                    │
                                    ▼
 ┌─────────────────────────────────────────────────────────────┐
 │              phase2_builder.md                               │
 │  Wraps the project brief with builder instructions:         │
 │  • Build EVERYTHING in one pass                              │
 │  • Verify dev server runs cleanly                            │
 │  • Make UI look PREMIUM                                      │
 └──────────────────────────────────┬──────────────────────────┘
                                    │
                                    ▼
 ┌─────────────────────────────────────────────────────────────┐
 │              critic_system.md                                │
 │  Strict evaluation criteria:                                 │
 │  • Layout, Typography, Color, Components, DOM, Errors       │
 │  • Anti-pattern rejection rules (cream+terracotta, etc.)    │
 │  • Returns structured JSON verdict                           │
 └─────────────────────────────────────────────────────────────┘
```

### Supporting Prompts

| Prompt | Used By | Purpose |
|---|---|---|
| `orchestrator_system.md` | `orchestrator.py` | Instructs Qwen2.5 to detect signals: `is_done`, `is_error`, `is_question`, `phase_tag` |
| `error_summarizer.md` | `orchestrator.py` | Instructs Qwen2.5-Coder to produce root cause + fix from error traces |
| `compression.md` | `orchestrator.py` | Compresses growing conversation history to prevent context bloat |
| `chatgpt_critic_init.md` | `main.py` | Initializes the ChatGPT critic tab with the design system and evaluation rules |

---

## 🎨 Design Library

The Design Library is a curated set of design constraints injected into every architect prompt. It ensures Claude's project briefs produce **distinctive, premium-looking apps** instead of generic AI-generated designs.

```
design_library/
├── tokens.json          # Color palettes, spacing scale, border radii, shadows
├── typography.md        # Font families, type scale, line heights
└── anti_patterns.md     # Explicit patterns to REJECT (cream+terracotta, etc.)
```

The anti-patterns file is particularly important — it catalogues the most common "AI default" design traps and instructs both the architect and the critic to **reject them on sight**.

---

## 🖥️ Dashboard (Web UI)

Bridge Agent includes a real-time monitoring dashboard built with **Next.js 16**, **React 19**, **Tailwind CSS 4**, and **Framer Motion**.

### Architecture

```
┌──────────────────────┐         ┌──────────────────────┐
│   Next.js Frontend   │◀──ws──▶│  FastAPI Backend     │
│   (localhost:4000)   │         │  (localhost:8000)    │
│                       │         │                      │
│  • Real-time logs    │         │  • /ws/stream        │
│  • Phase indicators  │         │  • /api/start        │
│  • Input prompts     │         │  • /api/stop         │
│  • Start/Stop        │         │                      │
└──────────────────────┘         └──────────┬───────────┘
                                             │
                                    ┌────────┴────────┐
                                    │   bridge_logger  │
                                    │   (ui_queue +    │
                                    │    cmd_queue)    │
                                    └─────────────────┘
```

### Launch

```powershell
# One-click launcher
.\start_dashboard.ps1

# Or manually:
python -m uvicorn api_server:app --host 127.0.0.1 --port 8000  # Terminal 1
cd bridge_web && npm run dev                                     # Terminal 2
# Open http://localhost:4000
```

---

## 📋 Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| **Windows** | 10/11 | OS-level automation requires Win32 APIs |
| **Python** | 3.10+ | Required for type hint syntax |
| **Node.js** | 18+ | For the web dashboard and project dev servers |
| **Chrome** | Any recent | Must be launched with remote debugging enabled |
| **Ollama** | Latest | Local LLM inference engine |
| **Antigravity IDE** | Latest | The desktop AI coding agent being automated |

### Required Ollama Models

```bash
ollama pull qwen2.5           # Orchestrator (signal detection, phase tagging)
ollama pull qwen2.5-coder     # Code analyzer (error analysis)
ollama pull qwen3-vl:8b       # UI critic fallback (vision model, optional)
```

---

## 🚀 Installation

### 1. Clone & Install Python Dependencies

```bash
cd bridge_agent
pip install -r requirements.txt
pip install fastapi uvicorn pydantic Pillow  # For dashboard & page explorer
playwright install chromium
```

### 2. Install Dashboard Dependencies (Optional)

```bash
cd bridge_web
npm install
```

### 3. Launch Chrome with Remote Debugging

```powershell
# Close all Chrome instances first, then:
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
```

> **Important:** You must be logged into Claude.ai and/or ChatGPT in this Chrome instance before running Bridge Agent.

### 4. Configure ntfy.sh Notifications

1. Install the [ntfy app](https://ntfy.sh) on your phone.
2. Subscribe to a topic with an unguessable name (e.g., `bridge_kp_x7f92m`).
3. Set `NTFY_TOPIC` in `config.py` to match.

### 5. Inspect & Configure Selectors

```bash
# Inspect Antigravity's UIA tree (with Antigravity open)
python inspect_antigravity.py

# Discover Claude/ChatGPT CSS selectors (with Chrome running)
python find_selectors.py
```

Update `config.py` with the discovered values if they differ from the defaults.

---

## ⚙️ Configuration

All configuration lives in [`config.py`](config.py). Key settings:

### LLM Configuration

```python
OLLAMA_MODELS = {
    "orchestrator": "qwen2.5",              # Signal detection
    "code_analyzer": "qwen2.5-coder:latest", # Error analysis
    "ui_critic": "qwen3-vl:8b",             # Vision-based UI critic (fallback)
}
OLLAMA_URL = "http://localhost:11434/api/generate"
```

### Connection

```python
CHROME_CDP_URL = "http://localhost:9222"     # Chrome DevTools Protocol
```

### Timing & Limits

```python
IDLE_STABLE_SECONDS = 2.5    # Output must be unchanged for this long = "done"
POLL_INTERVAL = 0.5          # Seconds between polls
HUMAN_DELAY_MIN = 1.0        # Anti-bot: min random delay before sending
HUMAN_DELAY_MAX = 3.0        # Anti-bot: max random delay before sending
MAX_TURNS = 40               # Maximum critic loop iterations
CRITIC_RETRY_CAP = 3         # Max direct fixes before escalating to Claude
MIN_CRITIC_TURN = 1          # Start evaluating from this turn
```

### Critic Configuration

```python
CRITIC_MODE = "chatgpt"      # "local" (Ollama vision) or "chatgpt" (web UI)
CRITIC_TRIGGER = "error_or_bad_ui"
```

### Dev Server

```python
DEV_SERVER_CMD = "npm run dev"
DEV_SERVER_CWD = r"d:\coding_files\kpautomate\meridian"
DEV_SERVER_PORT = 3000
```

### Platform Selectors

The system supports both Claude and ChatGPT with platform-specific selector configs:

```python
CHAT_PLATFORMS = {
    "claude": {
        "url": "https://claude.ai/new",
        "selectors": { ... },
        "stop_indicator": 'button[aria-label="Stop Response"]',
        "noise": [ ... ]  # UI text to strip from responses
    },
    "chatgpt": {
        "url": "https://chatgpt.com",
        "selectors": { ... },
        "stop_indicator": 'button[aria-label="Stop generating"]',
        "noise": [ ... ]
    }
}
```

---

## ▶️ Usage

### CLI Mode (Headless)

```bash
# With inline task
python main.py "Build a premium e-commerce site for artisan headphones"

# Interactive prompt
python main.py
# > Enter the initial task for the agent: _
```

### Dashboard Mode

```powershell
.\start_dashboard.ps1
# Opens http://localhost:4000 with real-time monitoring
```

### What Happens After Launch

1. **Startup**: Locates the Antigravity window, connects to Chrome via CDP, finds Claude/ChatGPT tabs, starts the dev server.
2. **Phase 1**: Sends the task + design library to Claude → receives a project brief.
3. **Phase 2**: Wraps the brief in builder instructions → sends to Antigravity → waits for the full app to be built.
4. **Phase 3**: Critic loop begins — screenshots, evaluates, fixes, repeats until the app passes or max turns exhausted.
5. **Completion**: Phone notification sent, checkpoint cleared, browser disconnected.

---

## 💾 Checkpoint & Resume

Bridge Agent saves state after **every turn** to `bridge_checkpoint.json`:

```json
{
  "turn": 3,
  "phase": 3,
  "history_summary": "Initial Task: Build a headphone store\n...",
  "current_payload": "...",
  "next_recipient": "critic",
  "project_brief": "..."
}
```

### Resume Flow

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│ Process dies │────▶│ Restart main.py  │────▶│ Checkpoint   │
│ (crash/kill/ │     │                  │     │ detected!    │
│  Ctrl+C)     │     │                  │     │ Resume? y/n  │
└──────────────┘     └──────────────────┘     └──────┬───────┘
                                                      │
                                               ┌──────┴───────┐
                                               │ y: Restore   │
                                               │    turn,     │
                                               │    phase,    │
                                               │    history   │
                                               │              │
                                               │ n: Start     │
                                               │    fresh     │
                                               └──────────────┘
```

- **Ctrl+C**: Saves checkpoint before exiting.
- **Fatal error**: Checkpoint preserved; phone notified.
- **Clean completion**: Checkpoint file **deleted** (no stale resume).
- **MAX_TURNS exhausted**: Checkpoint **kept** for manual inspection.

---

## ⚠️ Known Risks & Mitigations

| Risk | Status | Mitigation |
|---|---|---|
| Antigravity chat panel has no accessible UIA tree | ⚠️ Partially mitigated | File-based IPC (`bridge_response.txt`) bypasses UI scraping entirely |
| Streaming output causes false "stable" detection | ✅ Mitigated | `IDLE_STABLE_SECONDS` tuning + streaming indicator checks |
| Free-tier rate limits interrupt long runs | ✅ Mitigated | Detection + phone notification + checkpoint/resume |
| Chat site DOM selectors change over time | ⚠️ Unmitigated | `find_selectors.py` helper + manual re-verification |
| Bot-like usage triggers account flags | ⚠️ Partially mitigated | Randomized delays (`HUMAN_DELAY_MIN/MAX`), but not eliminated |
| No filesystem sandboxing | ❌ Accepted risk | Antigravity operates with user's full permissions |
| Local LLM false positives (error/question detection) | ✅ Mitigated | Strict codeword checks override LLM guesses; chain-of-thought reasoning |

---

## 🤝 Contributing

1. **Selectors will break.** When Claude.ai or ChatGPT updates their UI, run `find_selectors.py` and update `config.py`.
2. **Prompts are the product.** The quality of the output depends heavily on the prompts in `prompts/` and `design_library/`. Iterate on these with care.
3. **Test in isolation.** Each driver module (`chat_driver.py`, `antigravity_driver.py`) can be tested independently before wiring into the main loop.

---

## 📄 License

This project is for personal use. No license is currently specified.

---

<p align="center">
  <i>Built by <a href="https://github.com/karthikkp">Karthik K P</a> — because life's too short to copy-paste between AI agents.</i>
</p>
