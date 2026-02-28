import os
import logging
from dotenv import load_dotenv
from typing import Optional
import argparse

load_dotenv()

logger = logging.getLogger("arkon")

# Telegram Bot API
_telegram_bot_token: Optional[str] = (os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or None)
_telegram_chat_id: Optional[str] = (os.getenv("TELEGRAM_CHAT_ID", "").strip() or None)

# Gmail SMTP
_gmail_user: Optional[str] = (os.getenv("GMAIL_USER", "").strip() or None)
_gmail_app_pass: Optional[str] = (os.getenv("GMAIL_APP_PASS", "").strip() or None)
_recipient_email: Optional[str] = (os.getenv("RECIPIENT_EMAIL", "").strip() or None)

def send_telegram_message(message: str) -> bool:
    if not _telegram_bot_token or not _telegram_chat_id:
        logger.warning("🔱 [Messenger]: Telegram BOT_TOKEN or CHAT_ID not found. Cannot send message.")
        return False
    
    import requests
    url = f"https://api.telegram.org/bot{_telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": _telegram_chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"🔱 [Messenger]: Telegram message sent: {message}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"🔱 [Messenger]: Failed to send Telegram message: {e}")
        return False

def send_gmail_email(subject: str, body: str) -> bool:
    if not _gmail_user or not _gmail_app_pass or not _recipient_email:
        logger.warning("🔱 [Messenger]: Gmail credentials or recipient email not found. Cannot send email.")
        return False
    
    import smtplib
    from email.mime.text import MIMEText

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = _gmail_user
        msg["To"] = _recipient_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(_gmail_user, _gmail_app_pass)
            smtp.send_message(msg)
        logger.info(f"🔱 [Messenger]: Gmail email sent to {_recipient_email} with subject: {subject}")
        return True
    except Exception as e:
        logger.error(f"🔱 [Messenger]: Failed to send Gmail email: {e}")
        return False

def send_sentinel_alert(message: str) -> None:
    logger.warning(f"🔱 [Sentinel Alert]: {message}")

# Example usage (for testing purposes, can be removed later)
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send a Telegram message.")
    parser.add_argument("message", type=str, help="The message to send to Telegram.")
    args = parser.parse_args()

    print(f"Sending Telegram message: {args.message}")
    send_telegram_message(args.message)
