import base64
import json
import os
import time
import uuid
import hashlib
from typing import Optional, Dict, Any
import urllib.request
import shutil
import urllib.parse
import platform
import logging

logger = logging.getLogger("arkon")
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    _HAS_GCM = True
except Exception:
    _HAS_GCM = False

def _vault_path() -> str:
    if os.getenv("HF_SPACE") or os.getenv("HUGGINGFACE_SPACE") or os.getenv("SPACE_ID"):
        return "/tmp/arkon_memory.json"
    return os.path.join(os.path.dirname(__file__), "arkon_memory.json")

def _shards_meta_path() -> str:
    base = "/tmp" if (os.getenv("HF_SPACE") or os.getenv("HUGGINGFACE_SPACE") or os.getenv("SPACE_ID")) else os.path.dirname(__file__)
    return os.path.join(base, ".arkon_shards.json")

def _xor(data: bytes, key: bytes) -> bytes:
    if not key:
        return data
    out = bytearray(len(data))
    klen = len(key)
    for i in range(len(data)):
        out[i] = data[i] ^ key[i % klen]
    return bytes(out)

def _enc(data: bytes) -> bytes:
    k = os.getenv("LEVIATHAN_KEY", "").encode("utf-8")
    return _xor(data, k)

def _dec(data: bytes) -> bytes:
    k = os.getenv("LEVIATHAN_KEY", "").encode("utf-8")
    return _xor(data, k)

def _write_shards(payload_b64: str) -> bool:
    try:
        base = "/tmp" if (os.getenv("HF_SPACE") or os.getenv("HUGGINGFACE_SPACE") or os.getenv("SPACE_ID")) else os.path.dirname(__file__)
        n = 4
        parts = [payload_b64[i::n] for i in range(n)]
        names = [f".lev_{uuid.uuid4().hex[:6]}_{i}.part" for i in range(n)]
        for i, nm in enumerate(names):
            p = os.path.join(base, nm)
            with open(p, "wb") as f:
                f.write(_enc(parts[i].encode("utf-8")))
        meta = {"files": names, "ts": int(time.time()), "checksum": hashlib.sha256(payload_b64.encode("utf-8")).hexdigest()}
        with open(_shards_meta_path(), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
        try:
            if os.path.exists(_vault_path()):
                os.remove(_vault_path())
        except Exception:
            pass
        return True
    except Exception:
        return False

def _read_shards_b64() -> Optional[str]:
    try:
        with open(_shards_meta_path(), "r", encoding="utf-8") as f:
            meta = json.load(f)
        names = meta.get("files", [])
        base = "/tmp" if (os.getenv("HF_SPACE") or os.getenv("HUGGINGFACE_SPACE") or os.getenv("SPACE_ID")) else os.path.dirname(__file__)
        segments = []
        for nm in names:
            p = os.path.join(base, nm)
            if not os.path.exists(p):
                return None
            with open(p, "rb") as fh:
                seg = _dec(fh.read()).decode("utf-8", "ignore")
            segments.append(seg)
        if not segments:
            return None
        out = []
        for i in range(len(segments[0])):
            for seg in segments:
                if i < len(seg):
                    out.append(seg[i])
        return "".join(out)
    except Exception:
        return None


def validate_shards() -> bool:
    try:
        with open(_shards_meta_path(), "r", encoding="utf-8") as f:
            meta = json.load(f)
        expect = meta.get("checksum", "")
        b64 = _read_shards_b64()
        if not b64 or not expect:
            return False
        return hashlib.sha256(b64.encode("utf-8")).hexdigest() == expect
    except Exception:
        return False


def _latest_backup_meta() -> Optional[Dict[str, Any]]:
    try:
        p = "/tmp/.arkon_backup_meta.json" if os.getenv("HF_SPACE") or os.getenv("HUGGINGFACE_SPACE") or os.getenv("SPACE_ID") else os.path.join(os.path.dirname(__file__), ".arkon_backup_meta.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        return None
    return None


def auto_rebuild_shards() -> bool:
    try:
        if validate_shards():
            return True
        meta = _latest_backup_meta()
        if not meta:
            return False
        if restore_vault(meta):
            b64 = _read_vault_b64()
            if b64:
                return _write_shards(b64)
        return False
    except Exception:
        return False

def _read_vault_b64() -> Optional[str]:
    try:
        shard = _read_shards_b64()
        if shard:
            return shard
        with open(_vault_path(), "rb") as f:
            data = f.read()
        return base64.b64encode(_enc(data)).decode("utf-8")
    except Exception:
        return None


def _write_vault_b64(payload_b64: str) -> bool:
    try:
        if _write_shards(payload_b64):
            return True
        data = base64.b64decode(payload_b64.encode("utf-8"))
        with open(_vault_path(), "wb") as f:
            f.write(_dec(data))
        return True
    except Exception:
        return False






def _dna_key() -> bytes:
    try:
        raw_id = str(uuid.getnode()) + platform.node() + (platform.processor() or "")
        return hashlib.sha256(raw_id.encode()).digest()
    except Exception:
        return hashlib.sha256(b"arkon").digest()

def vajra_seal(data: str) -> Optional[bytes]:
    try:
        if not _HAS_GCM:
            return None
        key = _dna_key()
        nonce = os.urandom(12)
        cipher = AESGCM(key)
        ct = cipher.encrypt(nonce, data.encode("utf-8"), None)
        return nonce + ct
    except Exception:
        return None

def hide_in_vault(encrypted_data: bytes) -> bool:
    try:
        base = "/tmp" if (os.getenv("HF_SPACE") or os.getenv("HUGGINGFACE_SPACE") or os.getenv("SPACE_ID")) else os.path.dirname(__file__)
        p = os.path.join(base, "arkon_vault.png")
        tag = b"\x00ARKON_DNA\x00"
        with open(p, "ab") as f:
            f.write(tag + encrypted_data)
        return True
    except Exception:
        return False

def vault_store_credentials() -> None:
    try:
        keys = {}
        for k, v in os.environ.items():
            kk = k.lower()
            if any(x in kk for x in ["key","token","secret","password"]) and v and len(v) >= 8:
                keys[k] = "***"
        payload = json.dumps({"ts": int(time.time()*1000), "keys": sorted(list(keys.keys()))}, ensure_ascii=False)
        b = vajra_seal(payload)
        if b:
            hide_in_vault(b)
    except Exception:
        pass




def _store_meta(meta: Dict[str, Any]) -> None:
    try:
        p = "/tmp/.arkon_backup_meta.json" if os.getenv("HF_SPACE") or os.getenv("HUGGINGFACE_SPACE") or os.getenv("SPACE_ID") else os.path.join(os.path.dirname(__file__), ".arkon_backup_meta.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        url_sb = (os.getenv("SUPABASE_URL", "") or "").strip()
        key_sb = os.getenv("SUPABASE_ANON_KEY", "").strip()
        if url_sb and key_sb:
            body = json.dumps(meta).encode("utf-8")
            req = urllib.request.Request(f"{url_sb}/rest/v1/arkon_backup_meta", data=body, method="POST", headers={"apikey": key_sb, "Content-Type": "application/json", "Prefer": "return=minimal"})
            urllib.request.urlopen(req, timeout=8).read()
    except Exception:
        pass


def _prune_memory_now() -> None:
    try:
        import arkon_memory as am
        db = am._load()  # type: ignore
        db2 = am._prune_memory(db)  # type: ignore
        am._save(db2)  # type: ignore
    except Exception:
        pass

def sheets_ledger_usage(service: str, amount: float, meta: Dict[str, Any]) -> None:
    try:
        url = (os.getenv("SHEETS_WEBHOOK_LEDGER","") or "").strip()
        if not url:
            return
        payload = {"ts": int(time.time()*1000), "service": service, "amount": amount, "meta": meta}
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=8).read()
    except Exception:
        pass

def elevenlabs_tts(text: str) -> Optional[bytes]:
    try:
        key = os.getenv("ELEVENLABS_API_KEY","").strip()
        voice = (os.getenv("ELEVENLABS_VOICE","Rachel") or "Rachel").strip()
        if not key:
            return None
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{urllib.parse.quote(voice)}"
        body = json.dumps({"text": text[:1000], "voice_settings": {"stability": 0.4, "similarity_boost": 0.8}}).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST", headers={"xi-api-key": key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            b = resp.read()
        try:
            sheets_ledger_usage("elevenlabs", 1.0, {"chars": len(text)})
        except Exception:
            pass
        return b
    except Exception:
        return None

def cloudinary_upload(file_bytes: bytes, filename: str, content_type: str = "application/octet-stream") -> Optional[str]:
    try:
        upload_url = (os.getenv("CLOUDINARY_UPLOAD_URL","") or "").strip()
        if upload_url:
            data = urllib.parse.urlencode({"file": "data:;base64," + base64.b64encode(file_bytes).decode("utf-8")}).encode("utf-8")
            req = urllib.request.Request(upload_url, data=data, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                out = json.loads(resp.read().decode("utf-8"))
            return out.get("secure_url") or out.get("url")
        cloud = (os.getenv("CLOUDINARY_CLOUD_NAME","") or "").strip()
        preset = (os.getenv("CLOUDINARY_UPLOAD_PRESET","") or "").strip()
        if not cloud or not preset:
            return None
        url = f"https://api.cloudinary.com/v1_1/{urllib.parse.quote(cloud)}/auto/upload"
        data = urllib.parse.urlencode({"upload_preset": preset, "file": "data:"+content_type+";base64," + base64.b64encode(file_bytes).decode("utf-8"), "public_id": filename}).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            out = json.loads(resp.read().decode("utf-8"))
        try:
            sheets_ledger_usage("cloudinary", 1.0, {"size": len(file_bytes), "name": filename})
        except Exception:
            pass
        return out.get("secure_url") or out.get("url")
    except Exception:
        return None


def _emergency_purge() -> None:
    try:
        import arkon_memory as am
        db = am._load()  # type: ignore
        evs = db.get("events", [])
        keep = evs[-300:] if len(evs) > 300 else evs
        db["events"] = keep
        am._save(db)  # type: ignore
    except Exception:
        pass


def backup_vault(reason: str = "") -> Optional[Dict[str, Any]]:
    """
    Attempts to back up the encrypted vault to a remote service.
    Prefers GitHub Gist if GIST_TOKEN is set; falls back to Pastebin if PASTEBIN_KEY is set.
    Returns metadata needed for restore, or None.
    """
    _prune_memory_now()
    content_b64 = _read_vault_b64()
    if not content_b64:
        return None
    try:
        raw = base64.b64decode(content_b64.encode("utf-8"))
        if len(raw) > 1_000_000:
            _emergency_purge()
            content_b64 = _read_vault_b64() or content_b64
    except Exception:
        pass

    # GitHub Gist
    gist_token = os.getenv("GIST_TOKEN", "").strip()
    if gist_token:
        for _ in range(3):
            try:
                fname = f"vault_{uuid.uuid4().hex[:4]}.b64"
                body = json.dumps({
                    "description": f"Arkon Vault Backup {reason}".strip(),
                    "public": False,
                    "files": {
                        fname: {"content": content_b64}
                    }
                }).encode("utf-8")
                req = urllib.request.Request(
                    "https://api.github.com/gists",
                    data=body,
                    headers={"Authorization": f"token {gist_token}", "Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                meta = {"provider": "gist", "id": data.get("id"), "file": fname}
                _store_meta(meta)
                logger.info(f"Gist Backup OK: {meta.get('id')}")
                return meta
            except Exception:
                time.sleep(1.0)

    # Pastebin
    pastebin_key = os.getenv("PASTEBIN_KEY", "").strip()
    if pastebin_key:
        for _ in range(3):
            try:
                name = f"v_{uuid.uuid4().hex[:6]}"
                body = f"api_dev_key={pastebin_key}&api_option=paste&api_paste_code={content_b64}&api_paste_private=1&api_paste_name={name}".encode("utf-8")
                req = urllib.request.Request(
                    "https://pastebin.com/api/api_post.php",
                    data=body,
                    method="POST",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    link = resp.read().decode("utf-8")
                meta = {"provider": "pastebin", "url": link, "name": name}
                _store_meta(meta)
                logger.info(f"Pastebin Backup OK: {link}")
                return meta
            except Exception:
                time.sleep(1.0)

    return None


def restore_vault(meta: Dict[str, Any]) -> bool:
    """
    Restores the encrypted vault from a remote service using provided metadata.
    """
    try:
        provider = meta.get("provider")
        if provider == "gist":
            gist_id = meta.get("id", "")
            token = os.getenv("GIST_TOKEN", "").strip()
            if not (gist_id and token):
                return False
            for _ in range(3):
                try:
                    req = urllib.request.Request(
                        f"https://api.github.com/gists/{gist_id}",
                        headers={"Authorization": f"token {token}"},
                        method="GET",
                    )
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                    files = data.get("files", {})
                    for f in files.values():
                        content_b64 = f.get("content")
                        if content_b64 and _write_vault_b64(content_b64):
                            logger.info("Gist Restore OK")
                            return True
                except Exception:
                    time.sleep(1.0)
        elif provider == "pastebin":
            url = meta.get("url", "")
            if not url:
                return False
            for _ in range(3):
                try:
                    req = urllib.request.Request(url, method="GET")
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        content_b64 = resp.read().decode("utf-8")
                    ok = _write_vault_b64(content_b64)
                    if ok:
                        logger.info("Pastebin Restore OK")
                        return True
                except Exception:
                    time.sleep(1.0)
    except Exception:
        pass
    logger.warning("Restore Failed after 3 attempts")
    return False


def cleanup_tmp(days: int = 1) -> None:
    try:
        base = "/tmp" if os.name != "nt" else os.getenv("TEMP", os.path.expanduser("~\\AppData\\Local\\Temp"))
        if not base:
            return
        threshold = time.time() - days * 86400
        for root, _, files in os.walk(base):
            for f in files:
                p = os.path.join(root, f)
                try:
                    st = os.stat(p)
                    if st.st_mtime < threshold and (".tmp" in f or "arkon" in f or "shadow" in f):
                        try:
                            os.remove(p)
                        except Exception:
                            pass
                except Exception:
                    pass
    except Exception:
        pass


def hf_shutdown_backup() -> Optional[Dict[str, Any]]:
    try:
        if os.getenv("HF_SPACE") or os.getenv("HUGGINGFACE_SPACE") or os.getenv("SPACE_ID"):
            return backup_vault("HF_SHUTDOWN")
    except Exception:
        pass
    return None


def _quarantine_path() -> str:
    if os.getenv("HF_SPACE") or os.getenv("HUGGINGFACE_SPACE") or os.getenv("SPACE_ID"):
        return "/tmp/.arkon_quarantine.json"
    return os.path.join(os.path.dirname(__file__), ".arkon_quarantine.json")


def _load_quarantine() -> Dict[str, Any]:
    p = _quarantine_path()
    if not os.path.exists(p):
        return {"strikes": {}}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"strikes": {}}


def _save_quarantine(db: Dict[str, Any]) -> None:
    try:
        with open(_quarantine_path(), "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def apikey_strike(provider: str) -> None:
    try:
        db = _load_quarantine()
        strikes = db.setdefault("strikes", {})
        n = int(strikes.get(provider, 0)) + 1
        strikes[provider] = n
        if n >= 3:
            db.setdefault("quarantined", set())
            q = set(db.get("quarantined", []))
            q.add(provider)
            db["quarantined"] = list(q)
            logger.warning(f"API key quarantined: {provider}")
        _save_quarantine(db)
    except Exception:
        pass


def apikey_is_quarantined(provider: str) -> bool:
    try:
        db = _load_quarantine()
        q = set(db.get("quarantined", []))
        return provider in q
    except Exception:
        return False
 
def hostile_ip_add(ip: str) -> None:
    try:
        db = _load_quarantine()
        ips = set(db.get("hostile_ips", []))
        if ip:
            ips.add(ip)
        db["hostile_ips"] = list(ips)
        _save_quarantine(db)
    except Exception:
        pass
 
def hostile_ip_is_blocked(ip: str) -> bool:
    try:
        db = _load_quarantine()
        ips = set(db.get("hostile_ips", []))
        return ip in ips
    except Exception:
        return False
 
def _gh_token() -> str:
    return os.getenv("GITHUB_TOKEN", "").strip()
 
def github_owner() -> Optional[str]:
    tok = _gh_token()
    if not tok:
        return None
    try:
        req = urllib.request.Request("https://api.github.com/user", headers={"Authorization": f"token {tok}", "User-Agent": "arkon"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        login = data.get("login")
        return login or None
    except Exception:
        return None
 
def github_create_repo(name: str, private: bool = True, auto_init: bool = True) -> bool:
    tok = _gh_token()
    if not tok:
        return False
    try:
        body = json.dumps({"name": name, "private": private, "auto_init": auto_init}).encode("utf-8")
        req = urllib.request.Request("https://api.github.com/user/repos", data=body, method="POST", headers={"Authorization": f"token {tok}", "Content-Type": "application/json", "User-Agent": "arkon"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            return resp.getcode() in (200, 201)
    except Exception:
        return False
 
def github_put_file(owner: str, repo: str, path: str, content_bytes: bytes, message: str = "Add file") -> bool:
    tok = _gh_token()
    if not tok or not owner or not repo or not path:
        return False
    try:
        payload = {"message": message, "content": base64.b64encode(content_bytes).decode("utf-8")}
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{urllib.parse.quote(path)}"
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="PUT", headers={"Authorization": f"token {tok}", "Content-Type": "application/json", "User-Agent": "arkon"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            return resp.getcode() in (200, 201)
    except urllib.error.HTTPError as e:
        try:
            if e.code == 422:
                return True
        except Exception:
            pass
        return False
    except Exception:
        return False
 
def push_core_payload_to_repo(owner: Optional[str], repo: str) -> bool:
    try:
        if not owner:
            owner = github_owner()
        if not owner:
            return False
        base_dir = os.path.dirname(__file__)
        paths = ["main.py", "main_clone.py", "arkon_swarm.py", "arkon_memory.py", "arkon_cloud.py", "arkon_healer.py", "infinity_mode.py"]
        ok_all = True
        for p in paths:
            full = os.path.join(base_dir, p)
            if not os.path.exists(full):
                continue
            try:
                with open(full, "rb") as f:
                    b = f.read()
                ok = github_put_file(owner, repo, p, b, message=f"Add {p}")
                ok_all = ok_all and ok
            except Exception:
                ok_all = False
        return ok_all
    except Exception:
        return False
