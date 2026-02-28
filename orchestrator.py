import os
import time
import json
from typing import Any, Dict, Optional, List, Tuple
import requests
from arkon_memory import save_failure_trace

def _ollama_url() -> str:
    return os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

def _has_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("MISTRAL_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))

def _ollama_generate(model: str, prompt: str, temperature: float = 0.2, max_tokens: int = 512) -> Optional[str]:
    try:
        url = f"{_ollama_url()}/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": False, "options": {"temperature": temperature, "num_predict": max_tokens}}
        r = requests.post(url, json=payload, timeout=20)
        r.raise_for_status()
        j = r.json()
        return j.get("response")
    except Exception:
        return None

def route_reasoning(prompt: str) -> str:
    models = ["mistral", "llama3", "qwen2"]
    for m in models:
        ans = _ollama_generate(m, prompt)
        if ans:
            return ans.strip()
    return f"Reasoning fallback: {prompt}"

def route_coding(prompt: str) -> str:
    models = ["codellama", "starcoder2", "deepseek-coder"]
    for m in models:
        ans = _ollama_generate(m, prompt)
        if ans:
            return ans.strip()
    return f"Code plan fallback: {prompt}"

def route_vision_caption(prompt: str) -> str:
    ans = _ollama_generate("florence2", prompt)
    return ans.strip() if ans else prompt

def react(task: str, context: Optional[str] = None) -> Dict[str, Any]:
    try:
        thought = route_reasoning(f"Analyze: {task}\nContext: {context or ''}")
        plan = route_reasoning(f"Plan step-by-step for: {task}")
        action = route_coding(f"Propose code changes for: {task}\nContext: {context or ''}")
        observation = "pending"
        return {"thought": thought, "plan": plan, "action": action, "observation": observation}
    except Exception as e:
        save_failure_trace(task, str(e), {"stage": "react"})
        return {"thought": "", "plan": "", "action": "", "observation": "error"}

class Guardian:
    def __init__(self, notifier=None):
        self.notifier = notifier
    def request(self, action: str, details: str) -> bool:
        try:
            if self.notifier:
                self.notifier(f"Permission requested: {action}\n{details}")
        except Exception:
            pass
        return False

def vision_to_action(objects: Dict[str, Any], target: Optional[str] = None) -> Optional[Tuple[int, int]]:
    try:
        od = objects.get("result", {}).get("<OD>", {})
        arr = od if isinstance(od, list) else []
        best = None
        for o in arr:
            lbl = (o.get("label") or "").lower()
            if target and target.lower() not in lbl:
                continue
            b = o.get("box") or {}
            x = int(b.get("x", 0)); y = int(b.get("y", 0)); w = int(b.get("w", 0)); h = int(b.get("h", 0))
            cx, cy = x + max(1, w)//2, y + max(1, h)//2
            best = (cx, cy)
            break
        return best
    except Exception:
        return None
