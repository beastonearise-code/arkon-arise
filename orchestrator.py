import os
import time
import json
import requests
from typing import Any, Dict, Optional, List, Tuple
from arkon_memory import save_failure_trace

# 🔱 Sovereign Identity: Variable Sync
OLLAMA_BASE_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

def _ollama_generate(model: str, prompt: str, temperature: float = 0.2, max_tokens: int = 512) -> Optional[str]:
    """🔱 Resilient Generation: Hits local Ollama with extended timeout."""
    try:
        url = f"{OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model": model, 
            "prompt": prompt, 
            "stream": False, 
            "options": {"temperature": temperature, "num_predict": max_tokens}
        }
        # Increased timeout to 60s for local inference lag
        r = requests.post(url, json=payload, timeout=60)
        r.raise_for_status()
        return r.json().get("response")
    except Exception:
        return None

def route_task(prompt: str, context: str = "General") -> str:
    """🔱 Intelligent Router: Decisions between Reasoning and Coding."""
    if any(w in prompt.lower() for w in ["code", "fix", "error", "script", "python"]):
        return route_coding(prompt)
    return route_reasoning(prompt)

def route_reasoning(prompt: str) -> str:
    """🔱 Neural Relay: Tries multiple reasoning models."""
    models = ["mistral", "llama3", "qwen2", "phi3"]
    for m in models:
        ans = _ollama_generate(m, prompt)
        if ans: return ans.strip()
    return f"🔱 [Sovereign Fallback]: My local logic gates are heavy. Direct Input: {prompt}"

def route_coding(prompt: str) -> str:
    """🔱 Forge Relay: Specialized for code generation."""
    models = ["codellama", "deepseek-coder", "starcoder2"]
    for m in models:
        ans = _ollama_generate(m, prompt)
        if ans: return ans.strip()
    return f"🔱 [Forge Fallback]: Logic for coding is currently under maintenance."

def react(task: str, context: Optional[str] = None) -> Dict[str, Any]:
    """🔱 ReAct Protocol: Thought -> Plan -> Action loop."""
    try:
        thought = route_reasoning(f"Analyze: {task}\nContext: {context or ''}")
        plan = route_reasoning(f"Plan step-by-step for: {task}")
        action = route_coding(f"Propose fix/code for: {task}\nContext: {context or ''}")
        return {
            "thought": thought, 
            "plan": plan, 
            "action": action, 
            "observation": "🔱 Sovereign Analysis Complete."
        }
    except Exception as e:
        save_failure_trace("Orchestrator_ReAct", str(e))
        return {"thought": "", "plan": "", "action": "", "observation": f"Error: {e}"}

def vision_to_action(objects: Dict[str, Any], target: Optional[str] = None) -> Optional[Tuple[int, int]]:
    """🔱 Visual-Motor Sync: Translates OD boxes to coordinates."""
    try:
        # Handling Florence-2 specific output format
        od = objects.get("result", {}).get("<OD>", [])
        for o in od:
            lbl = (o.get("label") or "").lower()
            if target and target.lower() not in lbl: continue
            
            box = o.get("box", [0, 0, 1, 1]) # [y1, x1, y2, x2] usually
            # Calculate Center
            cy, cx = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
            return int(cx), int(cy)
        return None
    except: return None

print("🔱 Arkon Orchestrator (The Brain Core) Online.")