import os
import threading
import time
import asyncio
import gc
import socket
import random
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import requests
from fastapi import FastAPI
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from urllib3.exceptions import NameResolutionError

# 🔱 AGI Modules Integration - Corrected Names based on your files
try:
    from arkon_healer import propose_selector, florence2_describe_image_url, autonomous_goal, self_reflect
    from arkon_memory import (
        working_memory_add, working_memory_snapshot, 
        meta_log, save_failure_trace, record_failure
    )
    # Note: ensure orchestrator.py has route_task or update name here
    from orchestrator import route_task
except ImportError as e:
    print(f"🔱 Warning: AGI Modules missing or Name Mismatch: {e}")

load_dotenv()
app = FastAPI(title="Arkon Sovereign AGI", version="3.2.0")

# --- Token Handling ---
BOT_TOKEN = os.getenv("TELEGRAM_TOKENS", "").strip() or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_IDS_RAW = os.getenv("TELEGRAM_CHAT_IDS", "").strip()

def _chat_ids() -> List[str]:
    raw = (CHAT_IDS_RAW or "").strip().strip("\"' ")
    return [p.strip() for p in raw.split(",") if p.strip()]

# --- Sovereign Reactor ---
_bg_loop = None
_bg_thread = None

def _start_bg_loop():
    global _bg_loop, _bg_thread
    if _bg_loop and _bg_thread and _bg_thread.is_alive(): return
    _bg_loop = asyncio.new_event_loop()
    def _runner():
        asyncio.set_event_loop(_bg_loop)
        _bg_loop.run_forever()
    _bg_thread = threading.Thread(target=_runner, daemon=True)
    _bg_thread.start()

def _run_async(coro, timeout: float = 90.0):
    _start_bg_loop()
    fut = asyncio.run_coroutine_threadsafe(coro, _bg_loop)
    return fut.result(timeout=timeout)

# --- 🔱 AGI Reasoning Logic ---
def _brain_process(prompt: str, context: str = "General") -> str:
    try:
        try: meta_log(f"Thinking: {prompt[:30]}", 0.8, "Initiated")
        except: pass
        
        # Routing to AGI Brain
        response = _run_async(route_task(prompt, context), timeout=60)
        
        try: working_memory_add("last_response", "success", 0.9, {"val": response})
        except: pass
        return response
    except Exception as e:
        try: save_failure_trace("Brain_Orchestrator", str(e))
        except: pass
        return f"🔱 Sovereign Logic Error: {e}"

# --- Telegram Polling Loop ---
def _telegram_loop():
    if not BOT_TOKEN: return
    base = f"https://api.telegram.org/bot{BOT_TOKEN}"
    offset = 0
    print(f"🔱 Arkon Sovereign AGI is Online! Listening...")
    
    while True:
        try:
            data = _get_json_with_retry(f"{base}/getUpdates", params={"timeout": 50, "offset": offset}, timeout=60)
            for upd in data.get("result", []):
                offset = max(offset, upd.get("update_id", 0) + 1)
                msg = upd.get("message") or {}
                chat_id = msg.get("chat", {}).get("id")
                if not chat_id: continue
                
                text = msg.get("text")
                if text:
                    answer = _brain_process(text.strip())
                    _post_json_with_retry(f"{base}/sendMessage", json={"chat_id": chat_id, "text": answer}, timeout=30)
                
                # ... (Photo logic if needed)
        except Exception as e:
            time.sleep(5)

@app.on_event("startup")
def on_startup():
    if BOT_TOKEN:
        def warm_up_dns():
            start = time.time()
            while time.time() - start < 5:
                try: socket.gethostbyname("api.telegram.org"); return True
                except: time.sleep(1)
            return False
        warm_up_dns()

        def _supervisor():
            time.sleep(20) # Build delay
            while True:
                try: _telegram_loop()
                except: time.sleep(5)

        threading.Thread(target=_supervisor, daemon=True).start()
        
        # Salute
        salute = "🔱 **Arkon Sovereign AGI Online**\nStatus: Namespaces Synchronized."
        for cid in _chat_ids():
            try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                               json={"chat_id": cid, "text": salute, "parse_mode": "Markdown"}, timeout=15)
            except: pass

@retry(wait=wait_exponential(multiplier=1, min=1, max=20), stop=stop_after_attempt(10), 
       retry=retry_if_exception_type((requests.exceptions.ConnectionError, NameResolutionError)))
def _get_json_with_retry(url, params=None, timeout=60):
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status(); return r.json()

@retry(wait=wait_exponential(multiplier=1, min=1, max=20), stop=stop_after_attempt(10), 
       retry=retry_if_exception_type((requests.exceptions.ConnectionError, NameResolutionError)))
def _post_json_with_retry(url, json=None, timeout=30):
    r = requests.post(url, json=json, timeout=timeout)
    r.raise_for_status(); return r.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)