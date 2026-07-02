OLLAMA_MODEL = "qwen2.5-coder:latest"
OLLAMA_URL = "http://localhost:11434/api/generate"

CHAT_SITE_URL = "https://claude.ai/new"   # or "https://chatgpt.com"
CHROME_CDP_URL = "http://localhost:9222"   # Chrome remote debugging port

# CSS selectors for Claude.ai (found via find_selectors.py)
CHAT_SELECTORS = {
    "input_box": 'div[data-testid="chat-input"]',
    "send_button": None,  # No button selector — we press Enter to send
    "user_message": 'div[data-testid="user-message"]',  # for tracking conversation
}

# --- Antigravity window ---
# Found via pywinauto inspector (run: python inspect_antigravity.py)
ANTIGRAVITY_WINDOW_TITLE = r".*Antigravity IDE.*"
# UIA auto_id for the conversation panel (used to read response text)
CONVERSATION_AUTO_ID = "conversation"

# Timing
IDLE_STABLE_SECONDS = 2.5   # how long output must stop changing to count as "done"
POLL_INTERVAL = 0.5          # seconds between each poll
HUMAN_DELAY_MIN = 1.0        # minimum random delay before sending (anti-bot)
HUMAN_DELAY_MAX = 3.0        # maximum random delay before sending (anti-bot)

MAX_TURNS = 40
STOP_TOKEN = "DONE"

# --- FILL THIS IN ---
# Pick an unguessable random string, subscribe to it on the ntfy app on your phone
NTFY_TOPIC = "bridge_kp_x7f92m"
CHECKPOINT_FILE = "bridge_checkpoint.json"

RATE_LIMIT_PHRASES = [
    "you've reached your message limit",
    "you have reached your message limit",
    "too many requests",
    "rate limit exceeded",
    "please try again later",
    "usage limit",
    "you're out of free messages",
    "upgrade to continue",
]


def check_config():
    """Validates that all placeholders have been replaced before running."""
    placeholders = [
        ("CHAT_SELECTORS['input_box']", CHAT_SELECTORS["input_box"]),
        ("ANTIGRAVITY_WINDOW_TITLE", ANTIGRAVITY_WINDOW_TITLE),
        ("NTFY_TOPIC", NTFY_TOPIC),
    ]

    missing = [name for name, val in placeholders if val and "PLACEHOLDER" in val]
    if missing:
        raise ValueError(
            "Configuration incomplete! Fill these in config.py:\n  - "
            + "\n  - ".join(missing)
        )

# --- Dev Server & UI Critic Config ---
DEV_SERVER_CMD = "npm run dev"
DEV_SERVER_CWD = r"d:\coding_files\kpautomate\portfolio-app"
DEV_SERVER_PORT = 3000
CRITIC_MODEL = "qwen3-vl:8b"
CRITIC_RETRY_CAP = 3
CRITIC_TRIGGER = "error_or_bad_ui"
