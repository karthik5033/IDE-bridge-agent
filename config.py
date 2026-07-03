import os

STOP_REQUESTED = False

OLLAMA_MODELS = {
    "orchestrator": "qwen2.5",         # signal detection, phase tagging
    "code_analyzer": "qwen2.5-coder:latest",  # error analysis, code review
    "local_critic": "qwen3-vl:8b",        # fallback vision critic (when ChatGPT unavailable)
}
OLLAMA_URL = "http://localhost:11434/api/generate"
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
CRITIC_MODE = "chatgpt"  # "local" or "chatgpt"
CRITIC_MODEL = "qwen3-vl:8b"
CRITIC_RETRY_CAP = 3
CRITIC_TRIGGER = "error_or_bad_ui"

CLAUDE_SELECTORS = {
    "input_box": 'div[data-testid="chat-input"]',
    "send_button": None,
    "file_upload": 'input[type="file"]',
    "latest_response": 'div.font-claude-message',
}

CHATGPT_SELECTORS = {
    "input_box": 'div[id="prompt-textarea"]',
    "send_button": 'button[data-testid="send-button"]',
    "file_upload": 'input#upload-files',
    "latest_response": 'div[data-message-author-role="assistant"]',
}

CHAT_PLATFORMS = {
    "claude": {
        "url": "https://claude.ai/new",
        "selectors": CLAUDE_SELECTORS,
        "stop_indicator": 'button[aria-label="Stop Response"]',
        "noise": [
            "Sonnet 5 Medium", "Sonnet 4 Medium", "Haiku 3.5",
            "Claude is AI and can make mistakes. Please double-check responses.",
            "Claude can make mistakes. Please double-check responses.",
            "Share", "Quick answer", "Want to be notified when Claude responds?",
            "Notify", "Show less"
        ]
    },
    "chatgpt": {
        "url": "https://chatgpt.com",
        "selectors": CHATGPT_SELECTORS,
        "stop_indicator": 'button[aria-label="Stop generating"]',
        "noise": ["ChatGPT can make mistakes. Check important info."]
    }
}

def load_prompt(filename: str, **kwargs) -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", filename)
    with open(prompt_path, "r", encoding="utf-8") as f:
        content = f.read()
    return content.format(**kwargs) if kwargs else content
