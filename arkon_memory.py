import base64
import json
import os
import time
import re
import sqlite3
import concurrent.futures
import uuid
import platform
import hashlib as _hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# 🔱 Encryption Check
try:
    from Crypto.Cipher import AES  # type: ignore
    from Crypto.Util.Padding import pad, unpad  # type: ignore
    _HAS_AES = True
except Exception:
    _HAS_AES = False

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    _HAS_GCM = True
except Exception:
    _HAS_GCM = False

# --- Paths & DB Setup ---
def _db_path() -> str:
    base = "/tmp" if (os.getenv("HF_SPACE") or os.getenv("HUGGINGFACE_SPACE")) else os.path.dirname(__file__)
    return os.path.join(base, "arkon_memory.db")

_CONN: Optional[sqlite3.Connection] = None
_ADAPTER: Optional["DataAdapter"] = None
_EXEC: Optional[concurrent.futures.ThreadPoolExecutor] = None

def _conn() -> sqlite3.Connection:
    global _CONN
    if _CONN is None:
        _CONN = sqlite3.connect(_db_path(), check_same_thread=False, timeout=30)
        _CONN.row_factory = sqlite3.Row
        _init_db(_CONN)
    return _CONN

# --- 🔱 Sovereign Data Adapters (Cloud Sync) ---
class _SupabaseSource:
    def __init__(self):
        self.url = (os.getenv("SUPABASE_URL", "") or "").strip()
        self.key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    def ok(self) -> bool: return bool(self.url and self.key)
    def put_doc(self, doc: Dict[str, Any]):
        if not self.ok(): return
        try:
            import urllib.request
            body = json.dumps(doc).encode("utf-8")
            req = urllib.request.Request(f"{self.url}/rest/v1/docs", data=body, method="POST", 
                                         headers={"apikey": self.key, "Content-Type": "application/json", "Prefer": "return=minimal"})
            urllib.request.urlopen(req, timeout=8)
        except: pass

class DataAdapter:
    def __init__(self):
        self.sb = _SupabaseSource()
        global _EXEC
        if _EXEC is None: _EXEC = concurrent.futures.ThreadPoolExecutor(max_workers=6)
    
    def write_doc(self, doc: Dict[str, Any]):
        def _sqlite():
            try:
                c = _conn()
                c.execute("INSERT INTO docs(ts,text,meta) VALUES(?,?,?)", 
                          (doc.get("ts"), doc.get("text"), json.dumps(doc.get("meta", {}))))
                c.commit()
            except: _conn().rollback()
        
        if _EXEC: _EXEC.submit(_sqlite)
        if self.sb.ok(): _EXEC.submit(self.sb.put_doc, doc)

# --- 🔱 Encryption Engine ---
def _dna_key() -> bytes:
    try:
        raw_id = str(uuid.getnode()) + platform.node() + (platform.processor() or "arkon")
        return _hashlib.sha256(raw_id.encode()).digest()
    except: return _hashlib.sha256(b"arkon-sovereign").digest()

def _gcm_enc(b: bytes) -> bytes:
    if not _HAS_GCM: return b
    try:
        nonce = os.urandom(12)
        ct = AESGCM(_dna_key()).encrypt(nonce, b, None)
        return base64.b64encode(nonce + ct)
    except: return b

# --- 🔱 Core Memory Functions ---
_WORKING: List[Dict[str, Any]] = []
_WORKING_LIMIT = 200

def working_memory_store(key: str, value: Any):
    """Store ephemeral session data."""
    try:
        rec = {"ts": int(time.time() * 1000), "key": key, "val": value}
        _WORKING.append(rec)
        if len(_WORKING) > _WORKING_LIMIT: _WORKING.pop(0)
    except: pass

def working_memory_recall(key: str) -> Optional[Any]:
    for r in reversed(_WORKING):
        if r['key'] == key: return r['val']
    return None

def ingest_document(text: str, meta: Optional[Dict[str, Any]] = None):
    """Securely store a document in the brain."""
    try:
        payload = (text or "").encode("utf-8")
        enc = _gcm_enc(payload)
        _adapter().write_doc({
            "ts": int(time.time() * 1000), 
            "text": enc.decode("utf-8") if isinstance(enc, bytes) else enc, 
            "meta": meta or {}
        })
    except: pass

def save_failure_trace(task_name: str, error_msg: str):
    """🔱 Combined Failure Learning: Saves to DB and local JSON shard."""
    try:
        # 1. Store in Database for RAG and Evolution Score
        ingest_document(f"failure|task:{task_name}\nerror:{error_msg}", {"type": "failure", "status": "learned"})
        
        # 2. Store in Local JSON for quick inspection
        trace_data = {
            "ts": datetime.now().isoformat(),
            "task": task_name,
            "error": str(error_msg),
            "verdict": "FAILED_LEARNED"
        }
        
        shard_path = os.path.join(os.path.dirname(_db_path()), "arkon_failures.json")
        with open(shard_path, "a") as f:
            f.write(json.dumps(trace_data) + "\n")
            
        print(f"🔱 Arkon Memory: Failure in '{task_name}' recorded in Sovereign Vault.")
    except Exception as e:
        print(f"❌ Memory Error: {e}")

def meta_log_entry(action: str, confidence: float, outcome: str, meta: Optional[Dict] = None):
    """Track self-awareness and performance metrics."""
    try:
        entry = f"Action: {action} | Confidence: {confidence} | Outcome: {outcome}"
        ingest_document(entry, {"type": "meta", "confidence": confidence, **(meta or {})})
        working_memory_store("last_action", action)
    except: pass

def _adapter() -> DataAdapter:
    global _ADAPTER
    if _ADAPTER is None: _ADAPTER = DataAdapter()
    return _ADAPTER

def _init_db(c: sqlite3.Connection):
    try:
        c.execute("CREATE TABLE IF NOT EXISTS docs (ts INTEGER, text TEXT, meta TEXT)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_docs_ts ON docs(ts)")
        c.commit()
    except: c.rollback()

print("🔱 Arkon Sovereign Memory System Initialized.")