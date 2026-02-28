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

# 🔱 Sovereign AGI Modules Integration - Strictly Synced with your memory/healer files
try:
    # arkon_healer.py లోని ఫంక్షన్లు
    from arkon_healer import propose_selector, florence2_describe_image_url, autonomous_goal, self_reflect
    # arkon_memory.py లోని ఫంక్షన్లు (Restored functions)
    from arkon_memory import (
        working_memory_add, working_memory_snapshot, 
        meta_log, save_failure_trace, record_failure
    )
    # orchestrator.py లోని ఫంక్షన్లు
    from orchestrator import route_task
except ImportError as e:
    print(f"🔱 Warning: AGI Modules missing or Name Mismatch: {e}")

load_dotenv()
app = FastAPI(title="Arkon Sovereign AGI", version="4.0.0")

# --- Token & Chat Handling ---
# Hugging Face Secrets లో 'TELEGRAM_TOKENS' గా ఉండాలి
BOT_TOKEN = os.getenv("TELEGRAM_TOKENS", "").strip() or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_IDS_RAW = os.getenv("TELEGRAM_CHAT_IDS", "").strip()

def _chat_ids() -> List[str]:
    raw = (CHAT_IDS_RAW or "").strip().strip("\"' ")
    if not raw: return []
    return [p.strip() for p in raw.split(",") if p.strip()]

# --- Sovereign Async Reactor ---
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

# --- 🔱 AGI Logic: Brain Routing ---
def _brain_process(prompt: str, context: str = "General") -> str:
    try:
        # Cognition Logging
        try: meta_log("Thinking", "Initiated", 0.8, {"task": prompt[:30]})
        except Exception as e: print(f"Logging error: {e}")
        
        # Routing to AGI Brain (orchestrator.py)
        response = _run_async(route_task(prompt, context), timeout=60)
        
        # Working Memory Storage
        try: working_memory_add("response", "success", 0.9, {"val": response})
        except: pass
        return response
    except Exception as e:
        try: save_failure_trace("Brain_Orchestrator", str(e))
        except: pass
        return f"🔱 Sovereign Logic Error: {e}"

# --- Telegram Polling Loop ---
def _telegram_loop():
    if not BOT_TOKEN:
        print("🔱 Critical: BOT_TOKEN is missing!")
        return
    
    base = f"https://api.telegram.org/bot{BOT_TOKEN}"
    offset = 0
    print(f"🔱 Arkon Sovereign AGI is Online! Listening...")
    
    while True:
        try:
            # Resilient long-polling with retry logic
            data = _get_json_with_retry(f"{base}/getUpdates", params={"timeout": 50, "offset": offset}, timeout=60)
            
            for upd in data.get("result", []):
                offset = max(offset, upd.get("update_id", 0) + 1)
                msg = upd.get("message") or {}
                chat_id = msg.get("chat", {}).get("id")
                if not chat_id: continue
                
                text = msg.get("text")
                if text:
                    print(f"🔱 Input detected: {text[:20]}...")
                    answer = _brain_process(text.strip())
                    _post_json_with_retry(f"{base}/sendMessage", json={"chat_id": chat_id, "text": answer}, timeout=30)
                    
        except Exception as e:
            # 🔱 Network errors are handled by @retry, but we catch top-level for continuity
            time.sleep(5)

@app.get("/")
@app.get("/health")
def health():
    return {
        "status": "Arkon AGI is Conscious",
        "bot_online": BOT_TOKEN is not None,
        "active_brain": "Sovereign-Orchestrator-v4"
    }

@app.on_event("startup")
def on_startup():
    if BOT_TOKEN:
        # 🔱 Phase 1: DNS Warm-up for Hugging Face connectivity
        def warm_up_dns():
            print("🔱 Arkon DNS Warmup: Resolving Telegram API...")
            start = time.time()
            while time.time() - start < 10:
                try:
                    socket.gethostbyname("api.telegram.org")
                    print("🔱 DNS Secured. Connectivity confirmed.")
                    return True
                except:
                    time.sleep(2)
            return False

        # 🔱 Phase 2: Background Supervisor
        def _supervisor():
            if warm_up_dns():
                time.sleep(10) # Wait for network stability
                
                # Arkon Awakening Salute
                salute = "🔱 **Arkon Sovereign AGI Online**\n- Namespaces: Synchronized\n- Memory Vault: Locked & Secure\n- System: 100% Operational."
                for cid in _chat_ids():
                    try:
                        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                                       json={"chat_id": cid, "text": salute, "parse_mode": "Markdown"}, timeout=15)
                    except Exception as e:
                        print(f"🔱 Salute failed for {cid}: {e}")
                
                # Start the core polling loop
                while True:
                    try:
                        _telegram_loop()
                    except Exception as e:
                        print(f"🔱 Bot loop crashed, reviving in 5s: {e}")
                        time.sleep(5)
            else:
                print("🔱 Critical failure: Network not available on startup.")

        threading.Thread(target=_supervisor, daemon=True).start()
        print("🔱 Background Telegram Thread Supervisor Initialized.")

# --- 🔱 Resilience Layer: Retries for Network Flakes ---
@retry(wait=wait_exponential(multiplier=1, min=1, max=20), stop=stop_after_attempt(10), 
       retry=retry_if_exception_type((requests.exceptions.ConnectionError, NameResolutionError)))
def _get_json_with_retry(url, params=None, timeout=60):
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

@retry(wait=wait_exponential(multiplier=1, min=1, max=20), stop=stop_after_attempt(10), 
       retry=retry_if_exception_type((requests.exceptions.ConnectionError, NameResolutionError)))
def _post_json_with_retry(url, json=None, timeout=30):
    r = requests.post(url, json=json, timeout=timeout)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)