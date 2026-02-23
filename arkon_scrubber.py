import os
import shutil
from typing import Optional
import subprocess
import json
import time

def _pil_image_module():
    try:
        import importlib
        return importlib.import_module("PIL.Image")
    except Exception:
        return None


def _strip_jpeg_exif(src: str, dst: str) -> bool:
    try:
        with open(src, "rb") as f:
            data = f.read()
        if not data.startswith(b"\xff\xd8"):
            return False
        out = bytearray()
        i = 2
        out += b"\xff\xd8"
        while i + 4 <= len(data):
            if data[i] != 0xFF:
                break
            marker = data[i + 1]
            if marker == 0xDA:
                out += data[i:]
                break
            seg_len = int.from_bytes(data[i + 2 : i + 4], "big")
            if marker == 0xE1:
                i += 2 + seg_len
                continue
            out += data[i : i + 2 + seg_len]
            i += 2 + seg_len
        with open(dst, "wb") as f:
            f.write(out)
        return True
    except Exception:
        return False


def _resolve_exec(default_name: str, env_var: str) -> str:
    p = os.getenv(env_var, "").strip()
    if p and os.path.exists(p):
        return p
    found = shutil.which(default_name)
    return found or default_name


def _media_registry_path() -> str:
    if os.getenv("HF_SPACE") or os.getenv("HUGGINGFACE_SPACE") or os.getenv("SPACE_ID"):
        return "/tmp/arkon_media_registry.json"
    return os.path.join(os.path.dirname(__file__), "arkon_media_registry.json")


def _load_registry() -> dict:
    p = _media_registry_path()
    if not os.path.exists(p):
        return {"items": []}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"items": []}


def _save_registry(db: dict) -> None:
    try:
        with open(_media_registry_path(), "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def media_register(path: str) -> None:
    try:
        db = _load_registry()
        db.setdefault("items", []).append({"path": path, "ts": int(time.time())})
        _save_registry(db)
    except Exception:
        pass


def secure_delete(path: str) -> bool:
    try:
        if not os.path.isfile(path):
            return False
        size = os.path.getsize(path)
        try:
            with open(path, "r+b", buffering=0) as f:
                chunk = os.urandom(65536)
                total = 0
                while total < size:
                    n = min(65536, size - total)
                    f.write(chunk[:n])
                    total += n
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            pass
        try:
            _metrics_add_bytes(size)
        except Exception:
            pass
        try:
            os.remove(path)
        except Exception:
            return False
        return True
    except Exception:
        return False


def _metrics_path() -> str:
    if os.getenv("HF_SPACE") or os.getenv("HUGGINGFACE_SPACE") or os.getenv("SPACE_ID"):
        return "/tmp/.arkon_metrics.json"
    return os.path.join(os.path.dirname(__file__), ".arkon_metrics.json")


def _metrics_load() -> dict:
    p = _metrics_path()
    if not os.path.exists(p):
        return {"bytes_shredded_24h": 0, "hostile": 0, "attributions": 0}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"bytes_shredded_24h": 0, "hostile": 0, "attributions": 0}


def _metrics_save(db: dict) -> None:
    try:
        with open(_metrics_path(), "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _metrics_add_bytes(n: int) -> None:
    db = _metrics_load()
    db["bytes_shredded_24h"] = int(db.get("bytes_shredded_24h", 0)) + int(n)
    _metrics_save(db)


def sweep_media(hours: int = 24) -> None:
    try:
        db = _load_registry()
        items = db.get("items", [])
        now = int(time.time())
        keep = []
        for it in items:
            p = it.get("path", "")
            ts = int(it.get("ts", 0))
            if not p:
                continue
            if now - ts >= hours * 3600:
                secure_delete(p)
            else:
                keep.append(it)
        db["items"] = keep
        _save_registry(db)
    except Exception:
        pass


def _png_open(path: str):
    pil = _pil_image_module()
    if pil is None:
        raise RuntimeError("PIL not available")
    img = pil.open(path).convert("RGBA")
    return img


def lsb_embed_text(src_png: str, dst_png: str, text: str) -> bool:
    try:
        pil = _pil_image_module()
        if pil is None:
            return False
        img = _png_open(src_png)
        data = list(img.getdata())
        b = text.encode("utf-8")
        bits = []
        ln = len(b)
        for i in range(32):
            bits.append((ln >> i) & 1)
        for by in b:
            for i in range(8):
                bits.append((by >> i) & 1)
        idx = 0
        out = []
        for px in data:
            r, g, bl, a = px
            if idx < len(bits):
                bl = (bl & ~1) | bits[idx]
                idx += 1
            out.append((r, g, bl, a))
        if idx < len(bits):
            return False
        img2 = pil.new("RGBA", img.size)
        img2.putdata(out)
        img2.save(dst_png)
        media_register(dst_png)
        secure_delete(src_png)
        return True
    except Exception:
        return False


def lsb_extract_text(png_path: str) -> str:
    try:
        img = _png_open(png_path)
        data = list(img.getdata())
        bits = []
        for px in data[:4096]:
            bits.append(px[2] & 1)
        ln = 0
        for i in range(32):
            ln |= (bits[i] & 1) << i
        out_bytes = bytearray()
        bit_idx = 32
        for _ in range(ln):
            by = 0
            for i in range(8):
                by |= (bits[bit_idx] & 1) << i
                bit_idx += 1
            out_bytes.append(by)
        return out_bytes.decode("utf-8", "ignore")
    except Exception:
        return ""


def _xor(data: bytes, key: bytes) -> bytes:
    if not key:
        return data
    out = bytearray(len(data))
    klen = len(key)
    for i in range(len(data)):
        out[i] = data[i] ^ key[i % klen]
    return bytes(out)


def lsb_embed_bytes(src_png: str, dst_png: str, payload: bytes) -> bool:
    try:
        pil = _pil_image_module()
        if pil is None:
            return False
        img = _png_open(src_png)
        data = list(img.getdata())
        key = (os.getenv("LSB_KEY", "") or os.getenv("LEVIATHAN_KEY", "")).encode("utf-8")
        enc = _xor(payload, key)
        bits = []
        ln = len(enc)
        for i in range(32):
            bits.append((ln >> i) & 1)
        for by in enc:
            for i in range(8):
                bits.append((by >> i) & 1)
        capacity = len(data)
        if len(bits) > capacity:
            return False
        idx = 0
        out = []
        for px in data:
            r, g, bl, a = px
            if idx < len(bits):
                bl = (bl & 0xFE) | (bits[idx] & 0x01)
                idx += 1
            out.append((r, g, bl, a))
        if idx < len(bits):
            return False
        img2 = pil.new("RGBA", img.size)
        img2.putdata(out)
        img2.save(dst_png)
        media_register(dst_png)
        secure_delete(src_png)
        return True
    except Exception:
        return False


def lsb_extract_bytes(png_path: str) -> bytes:
    try:
        img = _png_open(png_path)
        data = list(img.getdata())
        bits = []
        for px in data:
            bits.append(px[2] & 1)
        ln = 0
        for i in range(32):
            ln |= (bits[i] & 1) << i
        out_bytes = bytearray()
        bit_idx = 32
        for _ in range(ln):
            by = 0
            for i in range(8):
                by |= (bits[bit_idx] & 1) << i
                bit_idx += 1
            out_bytes.append(by)
        key = (os.getenv("LSB_KEY", "") or os.getenv("LEVIATHAN_KEY", "")).encode("utf-8")
        return _xor(bytes(out_bytes), key)
    except Exception:
        return b""


def _strip_png_chunks(src: str, dst: str) -> bool:
    try:
        with open(src, "rb") as f:
            data = f.read()
        if not (data.startswith(b"\x89PNG\r\n\x1a\n")):
            return False
        out = bytearray(data[:8])
        i = 8
        while i + 12 <= len(data):
            length = int.from_bytes(data[i : i + 4], "big")
            chunk = data[i + 4 : i + 8]
            end = i + 8 + length + 4
            if chunk in [b"tEXt", b"zTXt", b"iTXt"]:
                i = end
                continue
            out += data[i : end]
            i = end
        with open(dst, "wb") as f:
            f.write(out)
        return True
    except Exception:
        return False


def scrub_metadata(src_path: str, dst_path: Optional[str] = None) -> str:
    dst = dst_path or src_path
    ext = os.path.splitext(src_path)[1].lower()
    pil = _pil_image_module()
    if pil is not None and ext in [".jpg", ".jpeg", ".png"]:
        try:
            img = pil.open(src_path)
            params = {}
            if ext in [".jpg", ".jpeg"]:
                params = {"exif": b""}
            img.save(dst, **params)
            try:
                if src_path != dst:
                    secure_delete(src_path)
            except Exception:
                pass
            media_register(dst)
            return dst
        except Exception:
            pass
    if ext in [".jpg", ".jpeg"]:
        if _strip_jpeg_exif(src_path, dst):
            try:
                if src_path != dst:
                    secure_delete(src_path)
            except Exception:
                pass
            media_register(dst)
            return dst
    if ext == ".png":
        if _strip_png_chunks(src_path, dst):
            try:
                if src_path != dst:
                    secure_delete(src_path)
            except Exception:
                pass
            media_register(dst)
            return dst
    try:
        shutil.copyfile(src_path, dst)
        try:
            if src_path != dst:
                secure_delete(src_path)
        except Exception:
            pass
        media_register(dst)
        return dst
    except Exception:
        return src_path


def scrub_video(src_path: str, dst_path: Optional[str] = None) -> str:
    dst = dst_path or src_path
    ff = _resolve_exec("ffmpeg", "FFMPEG_PATH")
    try:
        subprocess.run([ff, "-y", "-i", src_path, "-map_metadata", "-1", "-c", "copy", dst], check=True)
        try:
            if src_path != dst:
                secure_delete(src_path)
        except Exception:
            pass
        media_register(dst)
        return dst
    except Exception:
        return src_path


def is_clean(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    pil = _pil_image_module()
    if pil is not None and ext in [".jpg", ".jpeg", ".png"]:
        try:
            img = pil.open(path)
            exif = getattr(img, "info", {}).get("exif")
            if exif:
                return False
            return True
        except Exception:
            return False
    return True
