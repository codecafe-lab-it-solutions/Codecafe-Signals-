"""Telegram alerts (free). Set TELEGRAM_BOT_TOKEN (from @BotFather) and TELEGRAM_CHAT_ID; without them alerts are off."""
import json
import os
import urllib.request

import config  # noqa: F401  loads .env


def send(text: str) -> bool:
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN", ""), os.getenv("TELEGRAM_CHAT_ID", "")
    if not (token and chat):
        return False
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                 data=json.dumps({"chat_id": chat, "text": text}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10):
            return True
    except Exception as e:  # an alert must never break trading
        print(f"Telegram alert failed: {e}")
        return False
