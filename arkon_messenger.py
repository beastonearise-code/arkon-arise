import os
import time
import logging
import requests
import socket
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# 🔱 Sovereign Dependencies
try:
    import cloudinary
    import cloudinary.uploader
    from arkon_memory import meta_log, save_failure_trace
except ImportError:
    print("🔱 Warning: Some dependencies or arkon_memory missing. Running in limited mode.")

load_dotenv()
logger = logging.getLogger("arkon_messenger")

# --- 🔱 Credentials & Keys ---
# Telegram
_telegram_tokens: Optional[str] = os.getenv("TELEGRAM_TOKENS", "").strip() or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
_telegram_chat_ids: Optional[str] = os.getenv("TELEGRAM_CHAT_IDS", "").strip()

# Meta/Instagram
_meta_token: Optional[str] = os.getenv("META_ACCESS_TOKEN", "").strip()
_ig_id: Optional[str] = os.getenv("INSTAGRAM_BUSINESS_ID", "").strip()

# Cloudinary Setup
cloudinary_url = os.getenv("CLOUDINARY_URL", "")
if cloudinary_url:
    # URL format: cloudinary://api_key:api_secret@cloud_name
    try:
        from urllib.parse import urlparse
        parsed = urlparse(cloudinary_url)
        cloudinary.config(
            cloud_name=parsed.hostname,
            api_key=parsed.username,
            api_secret=parsed.password,
            secure=True
        )
    except:
        logger.error("🔱 [Messenger]: Cloudinary config failed.")

# Gmail
_gmail_user: Optional[str] = os.getenv("GMAIL_USER", "").strip()
_gmail_app_pass: Optional[str] = os.getenv("GMAIL_APP_PASS", "").strip()
_recipient_email: Optional[str] = os.getenv("RECIPIENT_EMAIL", "").strip()

# --- 🔱 Internal Helpers ---
def _get_chat_ids() -> List[str]:
    if not _telegram_chat_ids: return []
    return [cid.strip() for cid in _telegram_chat_ids.split(",") if cid.strip()]

# --- 🔱 [VOICE 1]: Telegram Protocol ---
def send_telegram_message(message: str) -> bool:
    """🔱 Sends a broadcast to all authorized Telegram Chat IDs."""
    if not _telegram_tokens or not _telegram_chat_ids:
        logger.warning("🔱 Telegram credentials missing.")
        return False
    
    url = f"https://api.telegram.org/bot{_telegram_tokens}/sendMessage"
    success = True
    
    for chat_id in _get_chat_ids():
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        try:
            r = requests.post(url, json=payload, timeout=15)
            r.raise_for_status()
            logger.info(f"🔱 Broadcast sent to {chat_id}")
        except Exception as e:
            logger.error(f"🔱 Failed broadcast to {chat_id}: {e}")
            success = False
    return success

# --- 🔱 [VOICE 2]: Cloudinary Bridge ---
def upload_to_cloudinary(file_source: str, folder: str = "arkon_sovereign") -> Optional[str]:
    """🔱 Uploads a local file or dynamic URL to Cloudinary and returns a static secure URL."""
    try:
        response = cloudinary.uploader.upload(file_source, folder=folder)
        secure_url = response.get("secure_url")
        logger.info(f"🔱 Asset synced to Cloudinary: {secure_url}")
        return secure_url
    except Exception as e:
        logger.error(f"🔱 Cloudinary sync failed: {e}")
        return None

# --- 🔱 [VOICE 3]: Instagram Meta Empire ---
def instagram_post_image(image_source: str, caption: str) -> bool:
    """🔱 Posts an image to Instagram Feed. Handles dynamic Pollinations URLs via Cloudinary Bridge."""
    if not _meta_token or not _ig_id:
        logger.error("🔱 Meta credentials missing.")
        return False

    final_image_url = image_source
    
    # If image is dynamic (Pollinations) or local, bridge it through Cloudinary for Instagram compatibility
    if "pollinations.ai" in image_source or not image_source.startswith("http"):
        print("🔱 Bridging image through Cloudinary for Instagram compatibility...")
        final_image_url = upload_to_cloudinary(image_source)
        if not final_image_url:
            return False

    try:
        # Phase 1: Create Container
        logger.info("🔱 Phase 1: Creating Instagram Media Container...")
        container_url = f"https://graph.facebook.com/v19.0/{_ig_id}/media"
        payload = {'image_url': final_image_url, 'caption': caption, 'access_token': _meta_token}
        
        r = requests.post(container_url, data=payload)
        res = r.json()
        
        if 'id' in res:
            creation_id = res['id']
            logger.info(f"🔱 Container Ready (ID: {creation_id}). Processing...")
            time.sleep(20) # Grace period for Meta servers
            
            # Phase 2: Publish
            logger.info("🔱 Phase 2: Publishing to Instagram Feed...")
            pub_url = f"https://graph.facebook.com/v19.0/{_ig_id}/media_publish"
            r_pub = requests.post(pub_url, data={'creation_id': creation_id, 'access_token': _meta_token})
            
            if 'id' in r_pub.json():
                logger.info(f"🔱 Success! Arkon is Live on Instagram: {r_pub.json()['id']}")
                try: meta_log("Instagram_Post", "Success", 1.0, {"post_id": r_pub.json()['id']})
                except: pass
                return True
        
        logger.error(f"🔱 Meta API Error: {res}")
        return False
    except Exception as e:
        logger.error(f"🔱 Instagram execution failed: {e}")
        try: save_failure_trace("Instagram_Post", str(e))
        except: pass
        return False

# --- 🔱 [VOICE 4]: Gmail Formal Dispatch ---
def send_gmail_email(subject: str, body: str) -> bool:
    """🔱 Sends a formal dispatch via Gmail SMTP."""
    if not _gmail_user or not _gmail_app_pass or not _recipient_email:
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
        return True
    except Exception as e:
        logger.error(f"🔱 Gmail failed: {e}")
        return False

# --- 🔱 [VOICE 5]: Sentinel Alerts ---
def send_sentinel_alert(message: str) -> None:
    """🔱 Immediate high-priority warning in logs and Telegram."""
    alert = f"🚨 🔱 **SENTINEL ALERT** 🔱 🚨\n\n{message}"
    logger.warning(f"🔱 [Sentinel]: {message}")
    send_telegram_message(alert)

if __name__ == "__main__":
    print("🔱 Arkon Messenger Protocol Test Initiated...")
    # Example: send_telegram_message("🔱 System Test: Sovereign Voice is Online.")