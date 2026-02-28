import os
import logging
import time
from dotenv import load_dotenv
from typing import Optional, List
import requests

load_dotenv()

logger = logging.getLogger("arkon")

# 🔱 Sovereign Identity: Variable names matched with app.py
_telegram_tokens: Optional[str] = (os.getenv("TELEGRAM_TOKENS", "").strip() or None)
_telegram_chat_ids: Optional[str] = (os.getenv("TELEGRAM_CHAT_IDS", "").strip() or None)

# Gmail SMTP
_gmail_user: Optional[str] = (os.getenv("GMAIL_USER", "").strip() or None)
_gmail_app_pass: Optional[str] = (os.getenv("GMAIL_APP_PASS", "").strip() or None)
_recipient_email: Optional[str] = (os.getenv("RECIPIENT_EMAIL", "").strip() or None)

def _get_chat_ids() -> List[str]:
    """Extracts multiple chat IDs from environment."""
    if not _telegram_chat_ids: return []
    return [cid.strip() for cid in _telegram_chat_ids.split(",") if cid.strip()]

def send_telegram_message(message: str) -> bool:
    """🔱 Arkon's Voice: Sends a secure message via Telegram."""
    if not _telegram_tokens or not _telegram_chat_ids:
        logger.warning("🔱 [Messenger]: TELEGRAM_TOKENS or CHAT_IDS missing. Voice is silenced.")
        return False
    
    url = f"https://api.telegram.org/bot{_telegram_tokens}/sendMessage"
    success = True
    
    for chat_id in _get_chat_ids():
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        # Simple retry logic for reliability
        for attempt in range(3):
            try:
                response = requests.post(url, json=payload, timeout=15)
                response.raise_for_status()
                logger.info(f"🔱 [Messenger]: Telegram broadcast sent to {chat_id}")
                break
            except Exception as e:
                if attempt == 2:
                    logger.error(f"🔱 [Messenger]: Failed broadcast to {chat_id}: {e}")
                    success = False
                time.sleep(2)
    return success

def send_gmail_email(subject: str, body: str) -> bool:
    """🔱 Arkon's Official Dispatch: Sends a formal report via Gmail."""
    if not _gmail_user or not _gmail_app_pass or not _recipient_email:
        logger.warning("🔱 [Messenger]: Gmail credentials missing. Dispatch aborted.")
        return False
    
    import smtplib
    from email.mime.text import MIMEText

    try:
        msg = MIMEText(body)
        msg["Subject"] = f"🔱 Arkon Sovereign: {subject}"
        msg["From"] = _gmail_user
        msg["To"] = _recipient_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(_gmail_user, _gmail_app_pass)
            smtp.send_message(msg)
        logger.info(f"🔱 [Messenger]: Gmail dispatch sent to {_recipient_email}")
        return True
    except Exception as e:
        logger.error(f"🔱 [Messenger]: Gmail dispatch failed: {e}")
        return False

def send_sentinel_alert(message: str) -> None:
    """Immediate warning in logs for critical state changes."""
    logger.warning(f"🔱 [Sentinel Alert]: {message}")

if __name__ == "__main__":
    # Testing mode
    import argparse
    parser = argparse.ArgumentParser(description="Arkon Messenger CLI")
    parser.add_argument("message", type=str, help="Test message for Telegram")
    args = parser.parse_args()

    print(f"🔱 Initiating Telegram Protocol: {args.message}")
    send_telegram_message(args.message)