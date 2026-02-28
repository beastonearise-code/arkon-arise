import base64
import json
import os
import time
import re
import sqlite3
import concurrent.futures
from typing import Any, Dict, List, Optional, Tuple
try:
    from Crypto.Cipher import AES  # type: ignore
    from Crypto.Util.Padding import pad, unpad  # type: ignore
    import hashlib as _hashlib
    _HAS_AES = True
except Exception:
    _HAS_AES = False
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    _HAS_GCM = True
except Exception:
    _HAS_GCM = False
import uuid
import hashlib as _hashlib2
import platform

def _memory_path() -> str:
    tmp = "/tmp/arkon_memory.json" if os.getenv("HF_SPACE") or os.getenv("HUGGINGFACE_SPACE") or os.getenv("SPACE_ID") else os.path.join(os.path.dirname(__file__), "arkon_memory.json")
    return tmp

def _db_path() -> str:
    base = "/tmp" if (os.getenv("HF_SPACE") or os.getenv("HUGGINGFACE_SPACE") or os.getenv("SPACE_ID")) else os.path.dirname(__file__)
    return os.path.join(base, "arkon_memory.db")

_CONN: Optional[sqlite3.Connection] = None
_ADAPTER: Optional["DataAdapter"] = None
_EXEC: Optional[concurrent.futures.ThreadPoolExecutor] = None

def _conn() -> sqlite3.Connection:
    global _CONN
    if _CONN is None:
        _CONN = sqlite3.connect(_db_path(), check_same_thread=False)
        _CONN.row_factory = sqlite3.Row
        _init_db(_CONN)
    return _CONN

class _SupabaseSource:
    def __init__(self):
        self.url = (os.getenv("SUPABASE_URL", "") or "").strip()
        self.key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    def ok(self) -> bool:
        return bool(self.url and self.key)
    def put_event(self, ev: Dict[str, Any]) -> None:
        if not self.ok():
            return
        try:
            body = json.dumps(ev).encode("utf-8")
            import urllib.request
            req = urllib.request.Request(f"{self.url}/rest/v1/events", data=body, method="POST", headers={"apikey": self.key, "Content-Type": "application/json", "Prefer": "return=minimal"})
            urllib.request.urlopen(req, timeout=8).read()
        except Exception:
            pass
    def put_doc(self, doc: Dict[str, Any]) -> None:
        if not self.ok():
            return
        try:
            body = json.dumps(doc).encode("utf-8")
            import urllib.request
            req = urllib.request.Request(f"{self.url}/rest/v1/docs", data=body, method="POST", headers={"apikey": self.key, "Content-Type": "application/json", "Prefer": "return=minimal"})
            urllib.request.urlopen(req, timeout=8).read()
        except Exception:
            pass
    def fetch_events(self, limit: int = 1000) -> List[Dict[str, Any]]:
        if not self.ok():
            return []
        try:
            import urllib.request, urllib.parse
            url = f"{self.url}/rest/v1/events?select=*&order=ts.asc&limit={limit}"
            req = urllib.request.Request(url, headers={"apikey": self.key})
            with urllib.request.urlopen(req, timeout=8) as resp:
                arr = json.loads(resp.read().decode("utf-8"))
            out: List[Dict[str, Any]] = []
            for e in arr:
                out.append({
                    "ts": int(e.get("ts", 0)),
                    "url": e.get("url",""),
                    "goal": e.get("goal",""),
                    "selector": e.get("selector",""),
                    "hint": e.get("hint",""),
                    "action": e.get("action",""),
                    "result": e.get("result",""),
                    "notes": e.get("notes",""),
                    "sid": e.get("sid",""),
                })
            return out
        except Exception:
            return []
    def fetch_docs(self, limit: int = 1000) -> List[Dict[str, Any]]:
        if not self.ok():
            return []
        try:
            import urllib.request
            url = f"{self.url}/rest/v1/docs?select=*&order=ts.asc&limit={limit}"
            req = urllib.request.Request(url, headers={"apikey": self.key})
            with urllib.request.urlopen(req, timeout=8) as resp:
                arr = json.loads(resp.read().decode("utf-8"))
            out: List[Dict[str, Any]] = []
            for d in arr:
                m = {}
                try:
                    m = json.loads(d.get("meta","") or "{}")
                except Exception:
                    m = {}
                out.append({"ts": int(d.get("ts", 0)), "text": d.get("text",""), "meta": m})
            return out
        except Exception:
            return []

class _SheetsSource:
    def __init__(self):
        self.web_ev = (os.getenv("SHEETS_WEBHOOK_EVENTS","") or "").strip()
        self.web_doc = (os.getenv("SHEETS_WEBHOOK_DOCS","") or "").strip()
    def ok(self) -> bool:
        return bool(self.web_ev or self.web_doc)
    def put_event(self, ev: Dict[str, Any]) -> None:
        if not self.web_ev:
            return
        try:
            import urllib.request
            body = json.dumps(ev).encode("utf-8")
            req = urllib.request.Request(self.web_ev, data=body, method="POST", headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=8).read()
        except Exception:
            pass
    def put_doc(self, doc: Dict[str, Any]) -> None:
        if not self.web_doc:
            return
        try:
            import urllib.request
            body = json.dumps(doc).encode("utf-8")
            req = urllib.request.Request(self.web_doc, data=body, method="POST", headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=8).read()
        except Exception:
            pass

class _PineconeSource:
    def __init__(self):
        self.host = (os.getenv("PINECONE_HOST","") or "").strip()
        self.key = os.getenv("PINECONE_API_KEY","").strip()
        self.index = (os.getenv("PINECONE_INDEX","arkon") or "arkon").strip()
    def ok(self) -> bool:
        return bool(self.host and self.key)
    def _vec(self, text: str) -> List[float]:
        toks = re.findall(r"[a-zA-Z0-9]+", (text or "").lower())
        d = 8
        v = [0]*d
        for t in toks:
            h = sum(ord(c) for c in t)
            v[h % d] += 1.0
        s = sum(v) or 1.0
        return [x/s for x in v]
    def put_doc(self, doc: Dict[str, Any]) -> None:
        if not self.ok():
            return
        try:
            import urllib.request, urllib.parse
            idv = str(doc.get("ts") or int(time.time()*1000))
            vec = self._vec(doc.get("text",""))
            payload = json.dumps({"vectors":[{"id":idv,"values":vec,"metadata":{"ts":doc.get("ts"),"meta":doc.get("meta","")}}],"namespace": self.index}).encode("utf-8")
            req = urllib.request.Request(f"{self.host}/vectors/upsert", data=payload, method="POST", headers={"Api-Key": self.key, "Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=8).read()
        except Exception:
            pass
    def put_event(self, ev: Dict[str, Any]) -> None:
        return

class _PluginSource:
    def __init__(self):
        self.mod = (os.getenv("DATA_PLUGIN_MODULE","") or "").strip()
        self.obj = None
        if self.mod:
            try:
                import importlib
                m = importlib.import_module(self.mod)
                self.obj = getattr(m, "get_source")() if hasattr(m, "get_source") else None
            except Exception:
                self.obj = None
    def ok(self) -> bool:
        return bool(self.obj)
    def put_event(self, ev: Dict[str, Any]) -> None:
        try:
            if self.obj and hasattr(self.obj, "put_event"):
                self.obj.put_event(ev)
        except Exception:
            pass
    def put_doc(self, doc: Dict[str, Any]) -> None:
        try:
            if self.obj and hasattr(self.obj, "put_doc"):
                self.obj.put_doc(doc)
        except Exception:
            pass

class DataAdapter:
    def __init__(self):
        self.sb = _SupabaseSource()
        self.sh = _SheetsSource()
        self.pc = _PineconeSource()
        self.pl = _PluginSource()
        global _EXEC
        if _EXEC is None:
            try:
                _EXEC = concurrent.futures.ThreadPoolExecutor(max_workers=6)
            except Exception:
                _EXEC = None
    def write_event(self, ev: Dict[str, Any]) -> None:
        def _sqlite():
            try:
                c = _conn()
                c.execute("INSERT INTO events(ts,url,goal,selector,hint,action,result,notes,sid) VALUES(?,?,?,?,?,?,?,?,?)", (ev.get("ts"), ev.get("url"), ev.get("goal"), ev.get("selector"), ev.get("hint"), ev.get("action"), ev.get("result"), ev.get("notes"), ev.get("sid")))
                c.commit()
            except Exception:
                try:
                    _conn().rollback()
                except Exception:
                    pass
        def _sb():
            try: self.sb.put_event(ev)
            except Exception: pass
        def _sh():
            try: self.sh.put_event(ev)
            except Exception: pass
        def _pl():
            try: self.pl.put_event(ev)
            except Exception: pass
        tasks = [_sqlite, _sb, _sh, _pl]
        try:
            if _EXEC:
                futs = [ _EXEC.submit(t) for t in tasks ]
                for f in futs: 
                    try: f.result(timeout=3)
                    except Exception: pass
            else:
                for t in tasks: 
                    try: t()
                    except Exception: pass
        except Exception:
            pass
    def write_doc(self, doc: Dict[str, Any]) -> None:
        def _sqlite():
            try:
                c = _conn()
                c.execute("INSERT INTO docs(ts,text,meta) VALUES(?,?,?)", (doc.get("ts"), doc.get("text"), json.dumps(doc.get("meta", {}), ensure_ascii=False)))
                c.commit()
            except Exception:
                try:
                    _conn().rollback()
                except Exception:
                    pass
        def _sb():
            try: self.sb.put_doc(doc)
            except Exception: pass
        def _sh():
            try: self.sh.put_doc(doc)
            except Exception: pass
        def _pc():
            try: self.pc.put_doc(doc)
            except Exception: pass
        def _pl():
            try: self.pl.put_doc(doc)
            except Exception: pass
        tasks = [_sqlite, _sb, _sh, _pc, _pl]
        try:
            if _EXEC:
                futs = [ _EXEC.submit(t) for t in tasks ]
                for f in futs:
                    try: f.result(timeout=3)
                    except Exception: pass
            else:
                for t in tasks:
                    try: t()
                    except Exception: pass
        except Exception:
            pass
    def read_events(self, limit: int = 1000) -> List[Dict[str, Any]]:
        try:
            c = _conn()
            out: List[Dict[str, Any]] = []
            for r in c.execute("SELECT ts,url,goal,selector,hint,action,result,notes,sid FROM events ORDER BY ts ASC LIMIT ?", (limit,)):
                out.append({k: r[k] for k in r.keys()})
            if out:
                return out
        except Exception:
            pass
        sb = self.sb.fetch_events(limit)
        return sb
    def read_docs(self, limit: int = 1000) -> List[Dict[str, Any]]:
        try:
            c = _conn()
            out: List[Dict[str, Any]] = []
            for r in c.execute("SELECT ts,text,meta FROM docs ORDER BY ts ASC LIMIT ?", (limit,)):
                m = {}
                try:
                    m = json.loads(r["meta"]) if r["meta"] else {}
                except Exception:
                    m = {}
                out.append({"ts": r["ts"], "text": r["text"], "meta": m})
            if out:
                return out
        except Exception:
            pass
        return self.sb.fetch_docs(limit)

def _adapter() -> DataAdapter:
    global _ADAPTER
    if _ADAPTER is None:
        _ADAPTER = DataAdapter()
    return _ADAPTER

def _adapter_reload() -> None:
    try:
        # Reinitialize plugin and sources without process restart
        global _ADAPTER
        _ADAPTER = DataAdapter()
    except Exception:
        pass

def _init_db(c: sqlite3.Connection) -> None:
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS events (
            ts INTEGER,
            url TEXT,
            goal TEXT,
            selector TEXT,
            hint TEXT,
            action TEXT,
            result TEXT,
            notes TEXT,
            sid TEXT
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_events_goal ON events(goal)")
        c.execute("""CREATE TABLE IF NOT EXISTS docs (
            ts INTEGER,
            text TEXT,
            meta TEXT
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_docs_ts ON docs(ts)")
        c.commit()
    except Exception:
        try:
            c.rollback()
        except Exception:
            pass

def _aes_key() -> bytes:
    raw = (os.getenv("ARKON_AES_KEY", "") or os.getenv("ARKON_VAULT_KEY", "") or "leviathan-vault").encode("utf-8")
    try:
        return _hashlib.sha256(raw).digest()
    except Exception:
        return (raw + b"\x00" * 32)[:32]

def _aes_enc(b: bytes) -> bytes:
    if not _HAS_AES:
        return b
    try:
        import os as _os
        iv = _os.urandom(16)
        cipher = AES.new(_aes_key(), AES.MODE_CBC, iv)
        ct = cipher.encrypt(pad(b, AES.block_size))
        return base64.b64encode(iv + ct)
    except Exception:
        return b

def _aes_dec(b: bytes) -> bytes:
    if not _HAS_AES:
        return b
    try:
        raw = base64.b64decode(b)
        iv, ct = raw[:16], raw[16:]
        cipher = AES.new(_aes_key(), AES.MODE_CBC, iv)
        pt = unpad(cipher.decrypt(ct), AES.block_size)
        return pt
    except Exception:
        return b

def _dna_key() -> bytes:
    try:
        raw_id = str(uuid.getnode()) + platform.node() + (platform.processor() or "")
        return _hashlib2.sha256(raw_id.encode()).digest()
    except Exception:
        return _hashlib2.sha256(b"arkon").digest()

def _gcm_enc(b: bytes) -> bytes:
    if not _HAS_GCM:
        return b
    try:
        nonce = os.urandom(12)
        ct = AESGCM(_dna_key()).encrypt(nonce, b, None)
        return base64.b64encode(nonce + ct)
    except Exception:
        return b

def _gcm_dec(b: bytes) -> bytes:
    if not _HAS_GCM:
        return b
    try:
        raw = base64.b64decode(b)
        nonce, ct = raw[:12], raw[12:]
        pt = AESGCM(_dna_key()).decrypt(nonce, ct, None)
        return pt
    except Exception:
        return b


def _key_bytes() -> bytes:
    k = os.getenv("ARKON_VAULT_KEY", "").encode("utf-8")
    if not k:
        k = b"leviathan-vault"
    return k


def _xor(data: bytes, key: bytes) -> bytes:
    kb = key
    out = bytearray()
    for i, b in enumerate(data):
        out.append(b ^ kb[i % len(kb)])
    return bytes(out)


def _load() -> Dict[str, Any]:
    try:
        evs = _adapter().read_events(5000)
        docs = _adapter().read_docs(5000)
        return {"events": evs, "docs": docs}
    except Exception:
        return {"events": []}


def _save(db: Dict[str, Any]) -> None:
    try:
        c = _conn()
        if "events" in db:
            try:
                c.execute("DELETE FROM events")
                for e in db.get("events", []):
                    c.execute(
                        "INSERT INTO events(ts,url,goal,selector,hint,action,result,notes,sid) VALUES(?,?,?,?,?,?,?,?,?)",
                        (e.get("ts"), e.get("url"), e.get("goal"), e.get("selector"), e.get("hint"), e.get("action"), e.get("result"), e.get("notes"), e.get("sid")),
                    )
            except Exception:
                pass
        if "docs" in db:
            try:
                c.execute("DELETE FROM docs")
                for d in db.get("docs", []):
                    c.execute(
                        "INSERT INTO docs(ts,text,meta) VALUES(?,?,?)",
                        (d.get("ts"), d.get("text"), json.dumps(d.get("meta", {}), ensure_ascii=False)),
                    )
            except Exception:
                pass
        c.commit()
    except Exception:
        try:
            _conn().rollback()
        except Exception:
            pass


def _compress_failures(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    i = 0
    while i < len(events):
        ev = events[i]
        if ev.get("result") == "failure":
            j = i + 1
            same = 1
            while j < len(events):
                nxt = events[j]
                if nxt.get("result") == "failure" and nxt.get("url") == ev.get("url") and nxt.get("goal") == ev.get("goal") and nxt.get("selector") == ev.get("selector"):
                    same += 1
                    j += 1
                else:
                    break
            if same > 3:
                out.append({
                    "ts": ev.get("ts"),
                    "url": ev.get("url"),
                    "goal": ev.get("goal"),
                    "selector": ev.get("selector"),
                    "hint": ev.get("hint"),
                    "action": "click",
                    "result": "failure",
                    "notes": f"Repeated-Failure x{same}",
                    "sid": ev.get("sid", ""),
                })
                i = j
                continue
        out.append(ev)
        i += 1
    return out


def _prune_memory(db: Dict[str, Any]) -> Dict[str, Any]:
    evs: List[Dict[str, Any]] = db.get("events", [])
    if len(evs) > 500:
        oldest = evs[:100]
        keep = evs[100:]
        successes = sum(1 for e in oldest if e.get("result") == "success")
        failures = sum(1 for e in oldest if e.get("result") == "failure")
        goals: Dict[str, int] = {}
        for e in oldest:
            g = (e.get("goal") or "").strip()
            if g:
                goals[g] = goals.get(g, 0) + 1
        top_goals = sorted(goals.items(), key=lambda x: x[1], reverse=True)[:3]
        domains: Dict[str, int] = {}
        for e in oldest:
            try:
                import urllib.parse
                d = urllib.parse.urlparse(e.get("url", "")).netloc
                if d:
                    domains[d] = domains.get(d, 0) + 1
            except Exception:
                pass
        top_domains = sorted(domains.items(), key=lambda x: x[1], reverse=True)[:2]
        lines = [
            f"Compressed {len(oldest)} events",
            f"Successes {successes}, Failures {failures}",
            f"Top Goals: {', '.join([f'{g}:{c}' for g,c in top_goals])}" if top_goals else "Top Goals: none",
            f"Domains: {', '.join([f'{d}:{c}' for d,c in top_domains])}" if top_domains else "Domains: none",
            "Retention optimized",
        ]
        summary = {
            "ts": int(time.time() * 1000),
            "url": "summary",
            "goal": "compressed",
            "selector": "",
            "hint": "",
            "action": "compress",
            "result": "summary",
            "notes": "\n".join(lines),
            "sid": "",
        }
        db["events"] = _compress_failures(keep + [summary])
    else:
        db["events"] = _compress_failures(evs)
    return db


def record_event(url: str, goal: str, selector: str, hint: str, action: str, result: str, notes: str = "", sid: Optional[str] = None) -> None:
    try:
        _adapter().write_event({"ts": int(time.time() * 1000), "url": url, "goal": goal, "selector": selector, "hint": hint, "action": action, "result": result, "notes": notes, "sid": sid or ""})
    except Exception:
        pass


def consult_selector(url: str, goal: str) -> Optional[Tuple[str, str]]:
    try:
        c = _conn()
        for r in c.execute("SELECT selector,hint FROM events WHERE url=? AND goal=? AND result='success' ORDER BY ts DESC LIMIT 1", (url, goal)):
            sel = (r["selector"] or "").strip()
            hint = (r["hint"] or "").strip()
            if sel:
                return sel, hint
        return None
    except Exception:
        return None


def record_failure(url: str, goal: str, selector: str, hint: str, notes: str = "", sid: Optional[str] = None) -> None:
    record_event(url, goal, selector, hint, "click", "failure", notes=notes, sid=sid)


def record_success(url: str, goal: str, selector: str, hint: str, notes: str = "", sid: Optional[str] = None) -> None:
    record_event(url, goal, selector, hint, "click", "success", notes=notes, sid=sid)


def record_hostile(url: str, notes: str = "", sid: Optional[str] = None) -> None:
    record_event(url, "hostile-site", "", "", "defense", "hostile", notes=notes, sid=sid)
 
def ingest_document(text: str, meta: Optional[Dict[str, Any]] = None) -> None:
    try:
        payload = (text or "")[:200000].encode("utf-8")
        enc = _gcm_enc(payload) if _HAS_GCM else _aes_enc(payload)
        _adapter().write_doc({"ts": int(time.time() * 1000), "text": enc.decode("utf-8") if isinstance(enc, (bytes, bytearray)) else enc, "meta": meta or {}})
    except Exception:
        pass
 
def _tok(s: str) -> List[str]:
    try:
        arr = re.findall(r"[a-zA-Z0-9]+", (s or "").lower())
        return [a for a in arr if a]
    except Exception:
        return []
 
def rag_query(question: str, top_k: int = 3) -> List[Dict[str, Any]]:
    try:
        c = _conn()
        docs: List[Dict[str, Any]] = []
        for r in c.execute("SELECT ts,text,meta FROM docs ORDER BY ts DESC"):
            m = {}
            try:
                m = json.loads(r["meta"]) if r["meta"] else {}
            except Exception:
                m = {}
            txt = r["text"] or ""
            try:
                txt_b = _gcm_dec(txt.encode("utf-8")) if _HAS_GCM else _aes_dec(txt.encode("utf-8"))
                txt = txt_b.decode("utf-8", "ignore")
            except Exception:
                pass
            docs.append({"ts": r["ts"], "text": txt, "meta": m})
        q = set(_tok(question))
        scored: List[Tuple[int, Dict[str, Any]]] = []
        for d in docs:
            t = set(_tok(d.get("text", "")))
            score = len(q & t)
            if score > 0:
                scored.append((score, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:max(1, top_k)]]
    except Exception:
        return []

def intent_normalize(text: str) -> Dict[str, Any]:
    s = (text or "").strip().lower()
    toks = _tok(s)
    mode = "balanced"
    if "stealth" in toks:
        mode = "stealth"
    if "aggressive" in toks:
        mode = "aggressive"
    action = "unknown"
    if any(w in toks for w in ["ingest","upload","learn","store"]):
        action = "ingest"
    elif any(w in toks for w in ["spawn","clone","deploy"]):
        action = "spawn"
    elif any(w in toks for w in ["test","probe","sandbox"]):
        action = "test"
    elif any(w in toks for w in ["commit","push","rewrite"]):
        action = "commit"
    elif any(w in toks for w in ["key","apikey","token"]):
        action = "key"
    return {"text": s, "tokens": toks, "mode": mode, "action": action}

def get_evolution_score(window: int = 200) -> Dict[str, Any]:
    try:
        c = _conn()
        evs: List[Dict[str, Any]] = []
        for r in c.execute("SELECT result FROM events ORDER BY ts DESC LIMIT ?", (window,)):
            evs.append({"result": r["result"]})
        succ = sum(1 for e in evs if e.get("result") == "success")
        fail = sum(1 for e in evs if e.get("result") == "failure")
        total = max(1, len(evs))
        score = int(100 * succ / total)
        return {"score": score, "success": succ, "failure": fail, "total": total}
    except Exception:
        return {"score": 0, "success": 0, "failure": 0, "total": 0}

def save_failure_trace(task: str, error: str, meta: Optional[Dict[str, Any]] = None) -> None:
    try:
        ingest_document(f"failure|task:{task}\nerror:{error}", {"type": "failure", **(meta or {})})
        record_failure("local", task, "", "", error)
    except Exception as e:
        try:
            print(f"❌ Memory Error: Could not save trace: {e}")
        except Exception:
            pass
def save_failure_trace(task_name, error_msg):
    """అల్ట్రాన్ చేసిన తప్పులను భవిష్యత్తు కోసం గుర్తు పెట్టుకునే మెదడు భాగం"""
    import json
    from datetime import datetime
    
    trace_data = {
        "timestamp": datetime.now().isoformat(),
        "task": task_name,
        "error": str(error_msg),
        "status": "FAILED_LEARNED"
    }
    
    # దీనిని ఒక 'Failure Shard' లాగా సేవ్ చేస్తున్నాం
    try:
        with open("arkon_failures.json", "a") as f:
            f.write(json.dumps(trace_data) + "\n")
        print(f"🔱 Arkon Memory: Learned from failure in {task_name}")
    except Exception as e:
        print(f"❌ Memory Error: Could not save trace: {e}")
