import requests
import config

def notify_phone(message: str, title: str = "Bridge agent"):
    """
    POSTs a message to the user-specific ntfy.sh topic.
    Wrapped in try/except so it never crashes the main loop on network failure.
    """
    if "PLACEHOLDER" in config.NTFY_TOPIC:
        print(f"[Notifier] Skipped sending notification (topic not configured): {title} - {message}")
        return

    url = f"https://ntfy.sh/{config.NTFY_TOPIC}"
    headers = {
        "Title": title,
        "Priority": "high"
    }
    
    try:
        response = requests.post(url, data=message.encode('utf-8'), headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"[Notifier] Warning: Failed to send notification (status {response.status_code}): {response.text}")
    except Exception as e:
        print(f"[Notifier] Error: Could not reach ntfy.sh: {e}")
