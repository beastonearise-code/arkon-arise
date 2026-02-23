import json
import os
import time
import urllib.request
from typing import Dict, Any, Optional, List
import threading

def _swarm_path() -> str:
    if os.getenv("HF_SPACE") or os.getenv("HUGGINGFACE_SPACE") or os.getenv("SPACE_ID"):
        return "/tmp/swarm_intel.json"
    return os.path.join(os.path.dirname(__file__), "swarm_intel.json")


def _load() -> Dict[str, Any]:
    path = _swarm_path()
    if not os.path.exists(path):
        return {"success": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"success": []}


def _save(db: Dict[str, Any]) -> None:
    try:
        with open(_swarm_path(), "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _clean_swarm(db: Dict[str, Any]) -> Dict[str, Any]:
    try:
        path = _swarm_path()
        if os.path.exists(path) and os.path.getsize(path) > 2_000_000:
            now = int(time.time())
            keep: List[Dict[str, Any]] = []
            for rec in db.get("success", []):
                ts = rec.get("ts", now)
                if now - ts < 30 * 86400 and (rec.get("success_count", 1) >= 1):
                    keep.append(rec)
            db["success"] = keep
    except Exception:
        pass
    return db


def _domain(url: str) -> str:
    try:
        import urllib.parse
        return urllib.parse.urlparse(url).netloc
    except Exception:
        return url


def swarm_publish(selector_record: Dict[str, Any]) -> None:
    db = _load()
    arr: List[Dict[str, Any]] = db.setdefault("success", [])
    sel = selector_record.get("selector")
    url = selector_record.get("url")
    goal = selector_record.get("goal")
    sid = selector_record.get("sid", "")
    now = int(time.time())
    found = False
    for rec in arr:
        if rec.get("selector") == sel and rec.get("url") == url and rec.get("goal") == goal:
            rec["success_count"] = int(rec.get("success_count", 1)) + 1
            rec["ts"] = now
            rec["sid"] = sid or rec.get("sid", "")
            found = True
            break
    if not found:
        selector_record["success_count"] = int(selector_record.get("success_count", 1))
        selector_record["ts"] = now
        selector_record["sid"] = sid
        arr.append(selector_record)
    _save(_clean_swarm(db))
    try:
        url_sb = (os.getenv("SUPABASE_URL", "") or "").strip()
        key_sb = os.getenv("SUPABASE_ANON_KEY", "").strip()
        if url_sb and key_sb:
            body = json.dumps({"url": url, "goal": goal, "selector": sel, "success_count": selector_record.get("success_count", 1), "sid": sid, "ts": now}).encode("utf-8")
            req = urllib.request.Request(f"{url_sb}/rest/v1/swarm", data=body, method="POST", headers={"apikey": key_sb, "Content-Type": "application/json", "Prefer": "return=minimal"})
            urllib.request.urlopen(req, timeout=8).read()
    except Exception:
        pass


def swarm_fetch(goal: str, url: str) -> Optional[Dict[str, Any]]:
    db = _load()
    best = None
    best_score = -1
    for rec in db.get("success", []):
        if rec.get("goal") == goal and rec.get("url") == url and rec.get("selector"):
            sc = int(rec.get("success_count", 1))
            if sc > best_score:
                best = rec
                best_score = sc
    if best:
        return best
    d = _domain(url)
    for rec in db.get("success", []):
        if rec.get("goal") == goal and _domain(rec.get("url","")) == d and rec.get("selector"):
            sc = int(rec.get("success_count", 1))
            if sc > best_score:
                best = rec
                best_score = sc
    return best

def register_node(url: str) -> None:
    db = _load()
    nodes: List[Dict[str, Any]] = db.setdefault("nodes", [])
    now = int(time.time())
    found = False
    for n in nodes:
        if n.get("url") == url:
            n["last_seen"] = now
            found = True
            break
    if not found:
        nodes.append({"url": url, "last_seen": now, "status": "unknown"})
    _save(db)

def heartbeat_from(url: str) -> None:
    db = _load()
    nodes: List[Dict[str, Any]] = db.setdefault("nodes", [])
    now = int(time.time())
    for n in nodes:
        if n.get("url") == url:
            n["last_seen"] = now
            n["status"] = "alive"
            break
    _save(db)

def ping_swarm(timeout: int = 6) -> None:
    db = _load()
    nodes: List[Dict[str, Any]] = db.get("nodes", [])
    changed = False
    resurrect_needed: List[str] = []
    for n in nodes:
        u = (n.get("url") or "").rstrip("/")
        if not u:
            continue
        try:
            req = urllib.request.Request(f"{u}/health", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.getcode() == 200:
                    n["status"] = "alive"
                    n["last_seen"] = int(time.time())
                    changed = True
        except Exception:
            n["status"] = "down"
            resurrect_needed.append(u)
            changed = True
    if changed:
        _save(db)
    try:
        if os.getenv("SWARM_AUTO_RESURRECT") and resurrect_needed:
            import importlib
            ac = importlib.import_module("arkon_cloud")
            for _ in resurrect_needed:
                try:
                    ac.github_create_repo(f"arkon-shadow-{int(time.time())}", private=True, auto_init=True)
                    owner = ac.github_owner()
                    if owner:
                        ac.push_core_payload_to_repo(owner, f"arkon-shadow-{int(time.time())}")
                except Exception:
                    continue
    except Exception:
        pass

def start_swarm_keepalive(interval_sec: int = 600) -> None:
    try:
        def run():
            while True:
                try:
                    ping_swarm()
                except Exception:
                    pass
                time.sleep(interval_sec)
        t = threading.Thread(target=run, daemon=True)
        t.start()
    except Exception:
        pass
try:
    if os.getenv("SWARM_AUTO_PING"):
        start_swarm_keepalive()
except Exception:
    pass
