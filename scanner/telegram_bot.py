"""Telegram Bot notifier using the Telegram Bot HTTP API."""

import logging
import time
from typing import Optional
import requests

logger = logging.getLogger(__name__)


def send_telegram_message(
    bot_token: Optional[str],
    chat_id: Optional[str],
    html_text: str,
    dry_run: bool = False,
) -> bool:
    """Dispatches formatted HTML message to Telegram.

    If dry_run is True or tokens are missing, logs to stdout.
    """
    if dry_run or not bot_token or not chat_id:
        print("\n" + "=" * 50)
        print(" [DRY RUN / NO TELEGRAM CREDS] Rendered Output:")
        print("=" * 50)
        try:
            print(html_text)
        except UnicodeEncodeError:
            safe_text = html_text.encode(
                sys.stdout.encoding or "utf-8", errors="replace"
            ).decode(sys.stdout.encoding or "utf-8")
            print(safe_text)
        print("=" * 50 + "\n")
        logger.info("Message printed to console (dry run or credentials not set).")
        return True

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": html_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "AVWAP-Scanner-Bot/1.0",
    }

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)

            if resp.status_code == 200:
                logger.info(f"Telegram message sent successfully to {chat_id}.")
                return True

            if resp.status_code == 429:
                # Rate limited: check retry_after
                retry_after = resp.json().get("parameters", {}).get("retry_after", 3)
                logger.warning(
                    f"Telegram rate limited. Waiting {retry_after}s before retry..."
                )
                time.sleep(retry_after)
                continue

            logger.error(
                f"Telegram API error {resp.status_code} on attempt {attempt}: {resp.text}"
            )
            time.sleep(2 * attempt)

        except Exception as e:
            logger.error(
                f"Exception sending Telegram message (attempt {attempt}): {e}"
            )
            time.sleep(2 * attempt)

    return False
