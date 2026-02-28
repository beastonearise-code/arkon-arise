import os
import threading
import time
import asyncio
import gc
import socket
from typing import Optional
from dotenv import load_dotenv
import requests
from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from urllib3.exceptions import NameResolutionError

# నీ సొంత ఫైల్స్ నుంచి ఇంపోర్ట్స్
try:
    from arkon_healer import propose_selector, florence2_describe_image_url
except ImportError as e:
    print(f"🔱 Warning: arkon_healer.py missing: {e}")

# .env లోడ్ చేయడం
load_dotenv()

app = FastAPI(title="Arkon Sovereign API", version="2.0.0")

# --- టోకెన్ వెరిఫికేషన్ (Secret Name Match) ---
# నీ HF సెట్టింగ్స్ లో ఉన్న 'TELEGRAM_TOKENS' కి ఇది మ్యాచ్ అవుతుంది
BOT_TOKEN: Optional[str] = (
    os.getenv("TELEGRAM_TOKENS", "").strip() or 
    os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or 
    None
)
CHAT_IDS_RAW: Optional[str] = (os.getenv("TELEGRAM_CHAT_IDS", "").strip() or None)

# --- Sovereign Async Reactor: single event loop for background tasks ---
_bg_loop = None
_bg_thread = None

def _start_bg_loop():
    """🔱 Sovereign Reactor: spins a dedicated asyncio loop in a daemon thread."""
    global _bg_loop, _bg_thread
    if _bg_loop and _bg_thread and _bg_thread.is_alive():
        return
    _bg_loop = asyncio.new_event_loop()
    def _runner():
        asyncio.set_event_loop(_bg_loop)
        _bg_loop.run_forever()
    _bg_thread = threading.Thread(target=_runner, daemon=True)
    _bg_thread.start()

def _run_async(coro, timeout: float = 60.0):
    """🔱 Gatekeeper: submit coroutine to Sovereign reactor and wait for result."""
    _start_bg_loop()
    fut = asyncio.run_coroutine_threadsafe(coro, _bg_loop)
    return fut.result(timeout=timeout)

def _retry_request(method: str, url: str, *, params=None, json=None, timeout=60, max_attempts=6, base_delay=1.5):
    """🔱 Tenacity-lite: resilient HTTP for NameResolution/DNS hiccups."""
    delay = base_delay
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.request(method, url, params=params, json=json, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as e:
            if attempt == max_attempts:
                raise
            time.sleep(delay)
            delay = min(delay * 1.8, 20.0)

def _chat_ids() -> list[str]:
    raw = (CHAT_IDS_RAW or "").strip().strip("\"' ")
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts

def _telegram_loop():
    """టెలిగ్రామ్ బాట్ పోలింగ్ లూప్"""
    if not BOT_TOKEN:
        print("🔱 Error: TELEGRAM_TOKENS not found in Secrets! Please check HF Settings.")
        return
    
    base = f"https://api.telegram.org/bot{BOT_TOKEN}"
    offset = 0
    print(f"🔱 Arkon Bot is Online! Polling with Token: {BOT_TOKEN[:5]}***")
    
    while True:
        try:
            data = _get_json_with_retry(f"{base}/getUpdates", params={"timeout": 50, "offset": offset}, timeout=60)
            
            for upd in data.get("result", []):
                offset = max(offset, upd.get("update_id", 0) + 1)
                msg = upd.get("message") or {}
                chat_id = msg.get("chat", {}).get("id")
                if not chat_id:
                    continue
                
                text = msg.get("text")
                photos = msg.get("photo") or []
                
                if text:
                    print(f"🔱 Received Text: {text}")
                    try:
                        answer = _safe_ddgs_answer(text.strip())
                    except Exception as e:
                        answer = f"🔱 The Sovereign senses static in the ether: {e}"
                    _post_json_with_retry(f"{base}/sendMessage", json={"chat_id": chat_id, "text": answer}, timeout=30)
                
                elif photos:
                    print("🔱 Received Photo")
                    try:
                        fid = sorted(photos, key=lambda p: p.get("file_size", 0))[-1]["file_id"]
                        f = _get_json_with_retry(f"{base}/getFile", params={"file_id": fid}, timeout=30)
                        fp = f.get("result", {}).get("file_path")
                        if fp:
                            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{fp}"
                            vr = _safe_vision_url(file_url)
                            txt = _format_vision(vr)
                            _post_json_with_retry(f"{base}/sendMessage", json={"chat_id": chat_id, "text": txt}, timeout=30)
                    except Exception as e:
                        _post_json_with_retry(f"{base}/sendMessage", json={"chat_id": chat_id, "text": f"🔱 Vision faltered: {e}"}, timeout=30)
        except Exception as e:
            print(f"🔱 Bot Loop Error: {e}")
            if isinstance(e, (requests.exceptions.ConnectionError, NameResolutionError)):
                print("🔱 Arkon is in Network Stealth Mode. Retrying DNS...")
            time.sleep(5)

def _safe_ddgs_answer(prompt: str) -> str:
    goal = "Answer concisely using web search"
    try:
        return _run_async(propose_selector(goal, prompt), timeout=45)
    except Exception as e:
        return f"🔱 Sovereign Whisper: network winds are restless — {str(e)}"

def _safe_vision_url(url: str) -> dict:
    try:
        v = _run_async(florence2_describe_image_url(url), timeout=90)
        gc.collect()
        return v
    except Exception as e:
        return {"error": str(e)}

def _format_vision(v: dict) -> str:
    if not v or "error" in v: return "🔱 Vision Error."
    cap = v.get("caption", {}).get("result", {}).get("<CAPTION>", "No caption.")
    od = v.get("objects", {}).get("result", {}).get("<OD>", "No objects.")
    return f"🔱 **Arkon Vision Report**\n\n**Caption:** {cap}\n**Objects:** {od}"

@app.get("/")
@app.get("/health")
def health():
    return {
        "status": "Arkon is Alive",
        "bot_online": BOT_TOKEN is not None,
        "token_key_used": "TELEGRAM_TOKENS" if os.getenv("TELEGRAM_TOKENS") else "TELEGRAM_BOT_TOKEN"
    }

@app.on_event("startup")
def on_startup():
    if BOT_TOKEN:
        def warm_up_dns(hostname: str = "api.telegram.org", retries: int = 10, max_seconds: int = 5) -> None:
            start = time.time()
            for _ in range(max(1, retries)):
                try:
                    socket.gethostbyname(hostname)
                    return
                except Exception:
                    if time.time() - start >= max_seconds:
                        break
                    time.sleep(5)
        try:
            warm_up_dns()
        except Exception:
            pass
        def _supervisor():
            time.sleep(20)
            backoff = 2.0
            while True:
                try:
                    _telegram_loop()
                except Exception as e:
                    print(f"🔱 Loop crashed, Sovereign revives it: {e}")
                    time.sleep(backoff)
                    backoff = min(backoff * 1.8, 20.0)
        threading.Thread(target=_supervisor, daemon=True).start()
        print("🔱 Background Telegram Thread Supervisor Started.")
        try:
            base = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            salute = "🔱 Arkon Sovereign is Online! System: 100% Operational."
            for cid in _chat_ids():
                try:
                    _post_json_with_retry(base, json={"chat_id": cid, "text": salute, "parse_mode": "HTML"}, timeout=20)
                except Exception:
                    continue
        except Exception:
            pass

@retry(wait=wait_exponential(multiplier=1, min=1, max=20), stop=stop_after_attempt(20), retry=retry_if_exception_type((requests.exceptions.ConnectionError, NameResolutionError)))
def _get_json_with_retry(url: str, *, params=None, timeout: int = 60) -> dict:
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

@retry(wait=wait_exponential(multiplier=1, min=1, max=20), stop=stop_after_attempt(20), retry=retry_if_exception_type((requests.exceptions.ConnectionError, NameResolutionError)))
def _post_json_with_retry(url: str, *, json=None, timeout: int = 30) -> dict:
    r = requests.post(url, json=json, timeout=timeout)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return {}

if __name__ == "__main__":
    import uvicorn
    # హగ్గింగ్ ఫేస్ కోసం పోర్ట్ 7860
    uvicorn.run(app, host="0.0.0.0", port=7860)
