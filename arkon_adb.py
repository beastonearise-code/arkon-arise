import subprocess
from typing import Optional

def _run(cmd: str) -> bool:
    try:
        subprocess.run(cmd, shell=True, check=True)
        return True
    except Exception:
        return False

def connect(serial: Optional[str] = None) -> bool:
    if serial:
        return _run(f"adb connect {serial}")
    return _run("adb devices")

def tap(x: int, y: int) -> bool:
    return _run(f"adb shell input tap {x} {y}")

def swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> bool:
    return _run(f"adb shell input swipe {x1} {y1} {x2} {y2} {duration_ms}")

def input_text(text: str) -> bool:
    return _run(f"adb shell input text \"{text}\"")
