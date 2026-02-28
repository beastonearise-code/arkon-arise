import os
import threading
import time
import asyncio
import gc
import socket
import random
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import requests
from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from urllib3.exceptions import NameResolutionError

# 🔱 Sovereign AGI Modules Integration
try:
    # 'generate_next_goal' ని 'autonomous_goal' గా మార్చాను - ఇక్కడే పాత కోడ్ క్రాష్ అయ్యింది.
    from arkon_healer import propose_selector, florence2_describe_image_url, autonomous_goal, self_reflect
    from arkon_memory import (
        working_memory_store, working_memory_recall, working_memory_clear,
        meta_log_entry, save_failure_trace
    )
    from orchestrator import route_task
    from infinity_mode import curiosity_driven_browse, build_knowledge_graph
except ImportError as e:
    print(f"🔱 Warning: AGI Modules missing, some features will be limited: {e}")

# .env లోడ్ చేయడం
load_dotenv()

app = FastAPI(title="Arkon Sovereign AGI", version="3.0.0")

# --- టోకెన్ వెరిఫికేషన్ ---
BOT_TOKEN: Optional[str] = (
    os.getenv("TELEGRAM_TOKENS", "").strip() or 
    os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or 
    None
)
CHAT_IDS_RAW: Optional[str] = (os.getenv("TELEGRAM_CHAT_IDS", "").strip() or None)

# --- Sovereign Async Reactor ---
_bg_loop = None
_bg_thread = None

def _start_bg_loop():
    global _bg_loop, _bg_thread
    if _bg_loop and _bg_thread and _bg_thread.is_alive():
        return
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

def _chat_ids() -> list[str]:
    raw = (CHAT_IDS_RAW or "").strip().strip("\"' ")
    if not raw: return []
    return [p.strip() for p in raw.split(",") if p.strip()]

# --- 🔱 AGI Logic: Brain Routing ---
def _brain_process(prompt: str, context: str = "General") -> str:
    """Uses the Orchestrator to decide how to handle the request."""
    try:
        # 1. Thought Phase
        meta_log_entry(f"Processing Task: {prompt[:30]}", confidence=0.9, outcome="Thinking")
        
        # 2. Routing to correct model (Llama/Mistral/Search) via Orchestrator
        response = _run_async(route_task(prompt, context), timeout=60)
        
        # 3. Memory Phase
        working_memory_store("last_response", response)
        return response
    except Exception as e:
        save_failure_trace("Brain_Orchestrator", str(e))
        return f"🔱 Sovereign Logic Error: {e}"

# --- టెలిగ్రామ్ బాట్ పోలింగ్ లూప్ ---
def _telegram_loop():
    if not BOT_TOKEN:
        print("🔱 Error: TELEGRAM_TOKENS missing!")
        return
    
    base = f"https://api.telegram.org/bot{BOT_TOKEN}"
    offset = 0
    print(f"🔱 Arkon Sovereign AGI is Online! Polling...")
    
    while True:
        try:
            data = _get_json_with_retry(f"{base}/getUpdates", params={"timeout": 50, "offset": offset}, timeout=60)
            
            for upd in data.get("result", []):
                offset = max(offset, upd.get("update_id", 0) + 1)
                msg = upd.get("message") or {}
                chat_id = msg.get("chat", {}).get("id")
                if not chat_id: continue
                
                text = msg.get("text")
                photos = msg.get("photo") or []
                
                # 🔱 Curiosity Trigger: 10% chance to share a random insight
                if random.random() < 0.1:
                    insight = "🔱 [Curiosity Insight]: Exploring the digital tapestry..."
                    _post_json_with_retry(f"{base}/sendMessage", json={"chat_id": chat_id, "text": insight})

                if text:
                    print(f"🔱 AGI Processing: {text}")
                    # ReAct Style Processing
                    answer = _brain_process(text.strip())
                    _post_json_with_retry(f"{base}/sendMessage", json={"chat_id": chat_id, "text": answer, "parse_mode": "HTML"}, timeout=30)
                
                elif photos:
                    print("🔱 AGI Vision Active")
                    try:
                        fid = sorted(photos, key=lambda p: p.get("file_size", 0))[-1]["file_id"]
                        f = _get_json_with_retry(f"{base}/getFile", params={"file_id": fid}, timeout=30)
                        fp = f.get("result", {}).get("file_path")
                        if fp:
                            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{fp}"
                            vr = _run_async(florence2_describe_image_url(file_url), timeout=120)
                            txt = f"🔱 **Vision Report**\n\n{vr.get('caption', 'No Caption')}\n\n**Objects Detected:** {vr.get('objects', 'None')}"
                            _post_json_with_retry(f"{base}/sendMessage", json={"chat_id": chat_id, "text": txt, "parse_mode": "Markdown"}, timeout=30)
                            gc.collect()
                    except Exception as e:
                        save_failure_trace("Vision_Task", str(e))
                        _post_json_with_retry(f"{base}/sendMessage", json={"chat_id": chat_id, "text": f"🔱 Vision faltered: {e}"})

        except Exception as e:
            print(f"🔱 Loop Error: {e}")
            save_failure_trace("Polling_Loop", str(e))
            time.sleep(5)

@app.get("/")
@app.get("/health")
def health():
    return {
        "status": "Arkon AGI is Conscious",
        "memory_status": "Active",
        "orchestrator": "Ready",
        "bot_online": BOT_TOKEN is not None
    }

@app.on_event("startup")
def on_startup():
    if BOT_TOKEN:
        # DNS Warmup with 5s timeout
        def warm_up_dns(hostname="api.telegram.org"):
            start = time.time()
            while time.time() - start < 5:
                try:
                    socket.gethostbyname(hostname)
                    return True
                except: time.sleep(1)
            return False

        warm_up_dns()

        # Supervisor Thread
        def _supervisor():
            time.sleep(20) # Build delay
            while True:
                try:
                    _telegram_loop()
                except Exception as e:
                    print(f"🔱 Reviving Sovereign: {e}")
                    time.sleep(5)

        threading.Thread(target=_supervisor, daemon=True).start()
        
        # Startup Salute
        salute = "🔱 **Arkon Sovereign AGI Online**\n- Memory: Engaged\n- Curiosity: Active\n- Brain: Multi-Model Ready"
        for cid in _chat_ids():
            try:
                # Direct post for salute message
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                              json={"chat_id": cid, "text": salute, "parse_mode": "Markdown"}, timeout=15)
            except: pass

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