"""Send the dashboard screenshot (and optional error alerts) to Telegram."""
from __future__ import annotations

import logging
from pathlib import Path

import requests

from src.config import TelegramConfig

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"


def send_photo(telegram_cfg: TelegramConfig, image_path: str | Path, caption: str) -> None:
    token = telegram_cfg.bot_token()
    chat_id = telegram_cfg.chat_id()

    url = f"{API_BASE}/bot{token}/sendPhoto"
    with open(image_path, "rb") as fh:
        response = requests.post(
            url,
            data={"chat_id": chat_id, "caption": caption},
            files={"photo": fh},
            timeout=30,
        )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram sendPhoto failed: {payload}")

    logger.info("Sent dashboard screenshot to Telegram chat %s", chat_id)


def send_message(telegram_cfg: TelegramConfig, text: str) -> None:
    token = telegram_cfg.bot_token()
    chat_id = telegram_cfg.chat_id()

    url = f"{API_BASE}/bot{token}/sendMessage"
    response = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram sendMessage failed: {payload}")

    logger.info("Sent text message to Telegram chat %s", chat_id)
