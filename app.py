import os
import threading
import time
import asyncio
from typing import Optional
from dotenv import load_dotenv
import requests
from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse

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
            # టెలిగ్రామ్ నుంచి అప్‌డేట్స్ తెచ్చుకోవడం
            resp = requests.get(f"{base}/getUpdates", params={"timeout": 50, "offset": offset}, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            
            for upd in data.get("result", []):
                offset = max(offset, upd.get("update_id", 0) + 1)
                msg = upd.get("message") or {}
                chat_id = msg.get("chat", {}).get("id")
                if not chat_id: continue
                
                text = msg.get("text")
                photos = msg.get("photo") or []
                
                if text:
                    print(f"🔱 Received Text: {text}")
                    answer = _safe_ddgs_answer(text.strip())
                    requests.post(f"{base}/sendMessage", json={"chat_id": chat_id, "text": answer}, timeout=30)
                
                elif photos:
                    print("🔱 Received Photo")
                    fid = sorted(photos, key=lambda p: p.get("file_size", 0))[-1]["file_id"]
                    f = requests.get(f"{base}/getFile", params={"file_id": fid}, timeout=30).json()
                    fp = f.get("result", {}).get("file_path")
                    if fp:
                        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{fp}"
                        vr = _safe_vision_url(file_url)
                        txt = _format_vision(vr)
                        requests.post(f"{base}/sendMessage", json={"chat_id": chat_id, "text": txt}, timeout=30)
                        
        except Exception as e:
            print(f"🔱 Bot Loop Error: {e}")
            time.sleep(5)

def _safe_ddgs_answer(prompt: str) -> str:
    goal = "Answer concisely using web search"
    try:
        try:
            return asyncio.run(propose_selector(goal, prompt))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            return loop.run_until_complete(propose_selector(goal, prompt))
    except Exception as e:
        return f"Arkon Search Error: {str(e)}"

def _safe_vision_url(url: str) -> dict:
    try:
        try:
            return asyncio.run(florence2_describe_image_url(url))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            return loop.run_until_complete(florence2_describe_image_url(url))
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
        threading.Thread(target=_telegram_loop, daemon=True).start()
        print("🔱 Background Telegram Thread Started.")

if __name__ == "__main__":
    import uvicorn
    # హగ్గింగ్ ఫేస్ కోసం పోర్ట్ 7860
    uvicorn.run(app, host="0.0.0.0", port=7860)