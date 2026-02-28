import os
import subprocess
import socket
import importlib
import json
import time
import requests
from dotenv import load_dotenv

def mask_token(t: str) -> str:
    if not t:
        return ""
    s = t.strip()
    return (s[:3] + "..." + s[-3:]) if len(s) > 6 else s

def print_env():
    load_dotenv()
    tok = os.getenv("TELEGRAM_TOKENS", "") or os.getenv("TELEGRAM_BOT_TOKEN", "")
    cids = os.getenv("TELEGRAM_CHAT_IDS", "") or os.getenv("TELEGRAM_CHAT_ID", "")
    print(json.dumps({"TELEGRAM_TOKENS": mask_token(tok), "TELEGRAM_CHAT_IDS": cids}, ensure_ascii=False))
    return tok, cids

def check_imports():
    errors = []
    try:
        m = importlib.import_module("arkon_memory")
        for name in ["record_failure", "record_success", "meta_log", "working_memory_add", "ingest_document"]:
            if not hasattr(m, name):
                errors.append(f"arkon_memory missing: {name}")
    except Exception as e:
        errors.append(f"arkon_memory import error: {e}")
    try:
        h = importlib.import_module("arkon_healer")
        for name in ["propose_selector", "florence2_describe_image_url", "autonomous_goal", "causal_reasoning", "self_reflect"]:
            if not hasattr(h, name):
                errors.append(f"arkon_healer missing: {name}")
    except Exception as e:
        errors.append(f"arkon_healer import error: {e}")
    try:
        o = importlib.import_module("orchestrator")
        for name in ["react", "route_reasoning"]:
            if not hasattr(o, name):
                errors.append(f"orchestrator missing: {name}")
    except Exception as e:
        errors.append(f"orchestrator import error: {e}")
    print(json.dumps({"imports": "ok" if not errors else "errors", "details": errors}, ensure_ascii=False))
    return errors

def ping_host(host="api.telegram.org"):
    try:
        socket.gethostbyname(host)
        if os.name == "nt":
            cmd = ["ping", "-n", "1", host]
        else:
            cmd = ["ping", "-c", "1", host]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        ok = r.returncode == 0
        print(json.dumps({"ping": "ok" if ok else "fail"}))
        return ok
    except Exception as e:
        print(json.dumps({"ping": "error", "detail": str(e)}))
        return False

def direct_message(token: str, chat_ids: str):
    try:
        base = f"https://api.telegram.org/bot{token}/sendMessage"
        ids = [x.strip() for x in (chat_ids or "").split(",") if x.strip()]
        status = []
        for cid in ids[:1] if ids else []:
            try:
                r = requests.post(base, json={"chat_id": cid, "text": "🔱 Arkon Local Test: Connection Successful!"}, timeout=10)
                r.raise_for_status()
                status.append("ok")
            except Exception as e:
                status.append(f"error:{e}")
        print(json.dumps({"direct_message": status or ["no_chat_ids"]}))
        return not any(s.startswith("error") for s in status) if status else False
    except Exception as e:
        print(json.dumps({"direct_message": f"error:{e}"}))
        return False

def auto_fix(errors):
    changed = False
    if any("arkon_memory missing" in e for e in errors):
        try:
            p = os.path.join(os.path.dirname(__file__), "arkon_memory.py")
            with open(p, "a", encoding="utf-8") as f:
                f.write("\n\ndef record_failure(url, goal, selector, hint, notes='', sid=None):\n")
                f.write("    try:\n")
                f.write("        ingest_document(json.dumps({'url': url, 'goal': goal, 'selector': selector, 'hint': hint, 'notes': notes, 'sid': sid or '', 'result': 'failure'}, ensure_ascii=False), {'type': 'event'})\n")
                f.write("    except: pass\n")
                f.write("\n\ndef record_success(url, goal, selector, hint, notes='', sid=None):\n")
                f.write("    try:\n")
                f.write("        ingest_document(json.dumps({'url': url, 'goal': goal, 'selector': selector, 'hint': hint, 'notes': notes, 'sid': sid or '', 'result': 'success'}, ensure_ascii=False), {'type': 'event'})\n")
                f.write("    except: pass\n")
            changed = True
        except Exception:
            pass
    print(json.dumps({"auto_fix": "changed" if changed else "no_change"}))
    return changed

def main():
    tok, cids = print_env()
    errs = check_imports()
    if errs:
        auto_fix(errs)
    ping_host()
    direct_message(tok, cids)

if __name__ == "__main__":
    main()
