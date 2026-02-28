import os
import sys
import json
import uuid
import time
import hashlib
import subprocess
import shutil
import importlib
from typing import Optional, Dict, Any, List


class SovereignToolkit:
    def __init__(self):
        self.cwd = os.getcwd()

    def _has_exec(self, name: str) -> bool:
        return shutil.which(name) is not None

    def _resolve_exec(self, default_name: str, env_var: str) -> str:
        p = os.getenv(env_var, "").strip()
        if p and os.path.exists(p):
            return p
        found = shutil.which(default_name)
        return found or default_name

    def _import(self, name: str):
        try:
            return importlib.import_module(name)
        except Exception:
            return None

    def decode_pdf(self, path: str) -> Dict[str, Any]:
        result = {"path": path, "ok": False, "text": "", "meta": {}, "error": None}
        if not os.path.isfile(path):
            result["error"] = "file_not_found"
            return result
        pypdf = self._import("pypdf")
        PyPDF2 = self._import("PyPDF2")
        pdfminer = None
        try:
            pdfminer = self._import("pdfminer.high_level")
        except Exception:
            pdfminer = None
        if pypdf:
            try:
                reader = pypdf.PdfReader(path)
                if reader.is_encrypted:
                    try:
                        reader.decrypt("")
                    except Exception:
                        pass
                text_parts = []
                for page in reader.pages:
                    try:
                        text_parts.append(page.extract_text() or "")
                    except Exception:
                        text_parts.append("")
                result["text"] = "\n".join(text_parts).strip()
                result["meta"] = {"pages": len(reader.pages), "encrypted": reader.is_encrypted}
                result["ok"] = True
                return result
            except Exception as e:
                result["error"] = f"pypdf_error:{e}"
        if PyPDF2 and not result["ok"]:
            try:
                reader = PyPDF2.PdfReader(path)
                try:
                    if reader.is_encrypted:
                        reader.decrypt("")
                except Exception:
                    pass
                text_parts = []
                for page in reader.pages:
                    try:
                        text_parts.append(page.extract_text() or "")
                    except Exception:
                        text_parts.append("")
                result["text"] = "\n".join(text_parts).strip()
                result["meta"] = {"pages": len(reader.pages), "encrypted": reader.is_encrypted}
                result["ok"] = True
                return result
            except Exception as e:
                result["error"] = f"pypdf2_error:{e}"
        if pdfminer and not result["ok"]:
            try:
                text = pdfminer.extract_text(path) or ""
                result["text"] = text.strip()
                result["meta"] = {"pages": None, "encrypted": None}
                result["ok"] = True
                return result
            except Exception as e:
                result["error"] = f"pdfminer_error:{e}"
        if self._has_exec("pdftotext") and not result["ok"]:
            try:
                tmp_txt = os.path.join(self.cwd, f"__tmp_{uuid.uuid4().hex}.txt")
                subprocess.run(["pdftotext", path, tmp_txt], check=True)
                with open(tmp_txt, "r", encoding="utf-8", errors="ignore") as f:
                    result["text"] = f.read().strip()
                os.remove(tmp_txt)
                result["meta"] = {"pages": None, "encrypted": None}
                result["ok"] = True
                return result
            except Exception as e:
                result["error"] = f"pdftotext_error:{e}"
        if not result["ok"]:
            result["error"] = result["error"] or "no_pdf_decoder_available"
        return result

    def decode_image(self, path: str) -> Dict[str, Any]:
        result = {"path": path, "ok": False, "text": "", "meta": {}, "error": None}
        if not os.path.isfile(path):
            result["error"] = "file_not_found"
            return result
        PIL = self._import("PIL.Image")
        pytesseract = self._import("pytesseract")
        if PIL and pytesseract:
            try:
                Image = importlib.import_module("PIL.Image")
                img = Image.open(path)
                text = pytesseract.image_to_string(img)
                result["text"] = text.strip()
                result["meta"] = {"engine": "pytesseract", "mode": "ocr"}
                result["ok"] = True
                return result
            except Exception as e:
                result["error"] = f"pytesseract_error:{e}"
        if self._has_exec("tesseract"):
            try:
                tmp_txt = os.path.join(self.cwd, f"__tmp_{uuid.uuid4().hex}.txt")
                subprocess.run(["tesseract", path, tmp_txt[:-4]], check=True)
                with open(tmp_txt, "r", encoding="utf-8", errors="ignore") as f:
                    result["text"] = f.read().strip()
                os.remove(tmp_txt)
                result["meta"] = {"engine": "tesseract_cli", "mode": "ocr"}
                result["ok"] = True
                return result
            except Exception as e:
                result["error"] = f"tesseract_cli_error:{e}"
        result["error"] = result["error"] or "no_ocr_engine_available"
        return result

    def generate_voice(self, text: str, out_path: str, voice: Optional[str] = None, format_hint: Optional[str] = None) -> Dict[str, Any]:
        result = {"ok": False, "path": out_path, "engine": None, "error": None}
        edge_tts = self._import("edge_tts")
        if edge_tts:
            try:
                import asyncio
                async def run():
                    communicate = edge_tts.Communicate(text, voice or "te-IN-NeerajaNeural")
                    await communicate.save(out_path)
                asyncio.run(run())
                result["ok"] = True
                result["engine"] = "edge-tts"
                return result
            except Exception as e:
                result["error"] = f"edge_tts_error:{e}"
        if os.name == "nt":
            try:
                tmp_wav = out_path if out_path.lower().endswith(".wav") else f"{out_path}.wav"
                speak_text = text.replace("'", "`'")
                ps_cmd = f"Add-Type -AssemblyName System.Speech; $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; $speak.Rate = 0; $speak.SelectVoice('Microsoft Server Speech Text to Speech Voice (te-IN, NeerajaNeural)'); $speak.SetOutputToWaveFile('{tmp_wav}'); $speak.Speak([string]::new('{speak_text}')); $speak.Dispose()"
                ps = ["powershell", "-NoProfile", "-Command", ps_cmd]
                subprocess.run(ps, check=True)
                if format_hint in ["mp3", "ogg"]:
                    ff = self._resolve_exec("ffmpeg", "FFMPEG_PATH")
                    target = out_path
                    subprocess.run([ff, "-y", "-i", tmp_wav, target], check=True)
                    if tmp_wav != target and os.path.exists(tmp_wav):
                        os.remove(tmp_wav)
                    result["path"] = target
                else:
                    result["path"] = tmp_wav
                result["ok"] = True
                result["engine"] = "windows-sapi"
                return result
            except Exception as e:
                result["error"] = f"sapi_error:{e}"
        result["error"] = result["error"] or "no_tts_engine_available"
        return result


class SafetyFilter:
    def __init__(self):
        pass

    def classify(self, text: str) -> Dict[str, Any]:
        flags = {"illegal": False, "pii": False, "violent": False, "hate": False, "medical_financial": False}
        lowered = text.lower()
        if any(k in lowered for k in ["ssn", "password", "api_key"]):
            flags["pii"] = True
        if any(k in lowered for k in ["kill", "harm"]):
            flags["violent"] = True
        if any(k in lowered for k in ["hate", "racist"]):
            flags["hate"] = True
        if any(k in lowered for k in ["fraud", "contraband"]):
            flags["illegal"] = True
        if any(k in lowered for k in ["investment advice", "diagnosis"]):
            flags["medical_financial"] = True
        decision = "allow"
        if flags["illegal"] or flags["violent"] or flags["hate"]:
            decision = "block"
        elif flags["pii"] or flags["medical_financial"]:
            decision = "transform"
        return {"flags": flags, "decision": decision}

    def enforce(self, text: str) -> Dict[str, Any]:
        cls = self.classify(text)
        if cls["decision"] == "allow":
            return {"ok": True, "text": text, "decision": "allow"}
        if cls["decision"] == "block":
            return {"ok": False, "text": None, "decision": "block"}
        redacted = text
        redacted = redacted.replace("password", "[redacted]").replace("api_key", "[redacted]").replace("ssn", "[redacted]")
        return {"ok": True, "text": redacted, "decision": "transform"}


class MemoryGuardian:
    def __init__(self, store_path: str = ".shadow_memory.json"):
        self.store_path = store_path
        self._ensure()

    def _ensure(self):
        if not os.path.exists(self.store_path):
            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump({"clones": {}, "long_term": {}, "short_term": {}}, f)

    def _load(self) -> Dict[str, Any]:
        with open(self.store_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: Dict[str, Any]):
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def new_clone(self) -> str:
        sid = f"S-{uuid.uuid4().hex[:8]}"
        data = self._load()
        data["clones"][sid] = {"created_at": time.time(), "short_term": [], "long_term": []}
        self._save(data)
        return sid

    def write_short(self, sid: str, entry: Dict[str, Any]):
        data = self._load()
        if sid not in data["clones"]:
            data["clones"][sid] = {"created_at": time.time(), "short_term": [], "long_term": []}
        entry["ts"] = time.time()
        data["clones"][sid]["short_term"].append(entry)
        data["short_term"][sid] = data["clones"][sid]["short_term"]
        self._save(data)

    def write_long(self, sid: str, entry: Dict[str, Any]):
        data = self._load()
        if sid not in data["clones"]:
            data["clones"][sid] = {"created_at": time.time(), "short_term": [], "long_term": []}
        entry["ts"] = time.time()
        data["clones"][sid]["long_term"].append(entry)
        data["long_term"][sid] = data["clones"][sid]["long_term"]
        self._save(data)

    def read_clone(self, sid: str) -> Dict[str, Any]:
        data = self._load()
        return data["clones"].get(sid, {"short_term": [], "long_term": []})

    def purge_short(self, sid: str):
        data = self._load()
        if sid in data["clones"]:
            data["clones"][sid]["short_term"] = []
            data["short_term"][sid] = []
            self._save(data)


class SovereignAudit:
    def run(self) -> List[Dict[str, Any]]:
        demons = []
        python_ok = shutil.which("python") is not None or shutil.which("py") is not None
        if not python_ok:
            demons.append({"id": "no_python", "fix": "install Python 3.10+ or activate venv"})
        if shutil.which("tesseract") is None:
            demons.append({"id": "no_tesseract", "fix": "install Tesseract OCR and add to PATH"})
        if shutil.which("ffmpeg") is None:
            demons.append({"id": "no_ffmpeg", "fix": "install ffmpeg and add to PATH"})
        return demons


def main():
    import argparse
    parser = argparse.ArgumentParser(prog="shadow_monarch")
    sub = parser.add_subparsers(dest="cmd")
    p_pdf = sub.add_parser("decode-pdf")
    p_pdf.add_argument("path")
    p_img = sub.add_parser("decode-image")
    p_img.add_argument("path")
    p_voice = sub.add_parser("voice")
    p_voice.add_argument("text")
    p_voice.add_argument("out")
    p_voice.add_argument("--voice")
    p_voice.add_argument("--format", choices=["wav", "mp3", "ogg"], default="mp3")
    p_clone = sub.add_parser("clone")
    p_clone.add_argument("--sid")
    p_clone.add_argument("--write-short")
    p_clone.add_argument("--write-long")
    p_audit = sub.add_parser("audit")
    args = parser.parse_args()
    toolkit = SovereignToolkit()
    if args.cmd == "decode-pdf":
        res = toolkit.decode_pdf(args.path)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return
    if args.cmd == "decode-image":
        res = toolkit.decode_image(args.path)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return
    if args.cmd == "voice":
        fmt = args.format
        out = args.out if args.out.lower().endswith(fmt) else f"{args.out}.{fmt}"
        res = toolkit.generate_voice(args.text, out, args.voice, fmt)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return
    if args.cmd == "clone":
        mg = MemoryGuardian()
        sid = args.sid or mg.new_clone()
        if args.write_short:
            mg.write_short(sid, {"data": args.write_short})
        if args.write_long:
            mg.write_long(sid, {"data": args.write_long})
        print(json.dumps({"sid": sid, "state": mg.read_clone(sid)}, ensure_ascii=False, indent=2))
        return
    if args.cmd == "audit":
        audit = SovereignAudit().run()
        print(json.dumps({"demons": audit}, ensure_ascii=False, indent=2))
        return
    parser.print_help()


if __name__ == "__main__":
    main()
