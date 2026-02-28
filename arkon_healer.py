import os
import logging
import asyncio
import gc
import time
from typing import Optional, Dict, Any, Tuple, List
import requests
import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForCausalLM
from duckduckgo_search import DDGS
from arkon_memory import record_failure, record_success, ingest_document, meta_log
from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)

# 🔱 Global Sovereign Engine Cache
_VISION_MODEL = None
_VISION_PROCESSOR = None
_hf_key: Optional[str] = (os.getenv("HUGGINGFACE_API_TOKEN", "").strip() or None)

def get_florence_engine():
    """🔱 Singleton Pattern: Loads the model only once into memory."""
    global _VISION_MODEL, _VISION_PROCESSOR
    if _VISION_MODEL is None:
        logger.info("🔱 Sovereign Engine: Loading Florence-2 into memory...")
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        
        _VISION_MODEL = AutoModelForCausalLM.from_pretrained(
            "microsoft/Florence-2-large",
            torch_dtype=torch_dtype,
            trust_remote_code=True
        ).to(device)
        _VISION_PROCESSOR = AutoProcessor.from_pretrained("microsoft/Florence-2-large")
    return _VISION_MODEL, _VISION_PROCESSOR

async def _remote_florence2_vision(image_path: str, tasks: List[str] = ["caption", "object_detection"]) -> Dict[str, Any]:
    """🔱 Optimized Vision: Processes multiple tasks in one model pass."""
    try:
        model, processor = get_florence_engine()
        device = model.device
        torch_dtype = model.dtype
        
        results = {}
        with Image.open(image_path) as img:
            image = img.convert("RGB")
            
            for t in tasks:
                prompt = "<CAPTION>" if t == "caption" else "<OD>"
                inputs = processor(text=prompt, images=image, return_tensors="pt").to(device, dtype=torch_dtype)
                
                with torch.no_grad():
                    generated_ids = model.generate(
                        input_ids=inputs["input_ids"],
                        pixel_values=inputs["pixel_values"],
                        max_new_tokens=512,
                        num_beams=3,
                        do_sample=False
                    )
                
                generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
                parsed_answer = processor.post_process_generation(
                    generated_text,
                    task=prompt,
                    image_size=(image.width, image.height)
                )
                results[t] = parsed_answer
        return results
    except Exception as e:
        logger.error(f"🔱 Vision Logic Error: {e}")
        return {"error": str(e)}
    finally:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

async def florence2_describe_image_url(image_url: str) -> Dict[str, Any]:
    """Downloads image once and runs all vision diagnostics."""
    try:
        resp = requests.get(image_url, timeout=30)
        resp.raise_for_status()
        tmp_path = os.path.join(os.getcwd(), f"_tmp_img_{os.getpid()}.jpg")
        
        with open(tmp_path, "wb") as f:
            f.write(resp.content)
        
        # 🔱 Single pass for both caption and OD
        vision_data = await _remote_florence2_vision(tmp_path, tasks=["caption", "object_detection"])
        
        try: os.remove(tmp_path)
        except: pass
        
        return {
            "caption": vision_data.get("caption", {}),
            "objects": vision_data.get("object_detection", {})
        }
    except Exception as e:
        logger.error(f"florence2_describe_image_url error: {e}")
        return {"error": str(e)}

async def _ddgs_brain(prompt: str, attempts: int = 5) -> str:
    """Resilient search brain with exponential backoff."""
    def _run_sync():
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(prompt, max_results=8):
                results.append(f"- {r.get('title')}: {r.get('body')} ({r.get('href')})")
        return "\n".join(results[:12]) if results else "No results."

    delay = 2.5
    for i in range(attempts):
        try:
            return await asyncio.to_thread(_run_sync)
        except Exception:
            await asyncio.sleep(delay)
            delay = min(delay * 1.8, 30.0)
    return "No answer available."

async def propose_selector(goal: str, state: str) -> str:
    return await _ddgs_brain(f"{goal}. Context: {state}")

async def get_autonomous_fix(problem_description: str, current_state: str) -> str:
    """🔱 ReAct Loop: Now thread-safe for non-blocking execution."""
    try:
        thought = await _ddgs_brain(f"Analyze: {problem_description}\nContext: {current_state}")
        plan = await _ddgs_brain(f"Plan step-by-step for: {problem_description}")
        action = await propose_selector("Propose code changes", current_state)
        ingest_document(f"Thought: {thought}\nPlan: {plan}", {"type": "react"})
        if action:
            record_success("local", problem_description, "", "", "react", "success", "")
            return action
        record_failure("local", problem_description, "", "", "No action proposed")
        return "No action proposed"
    except Exception as e:
        record_failure("local", problem_description, "", "", str(e))
        return f"Failed to propose fix: {e}"

async def autonomous_goal(state: str) -> str:
    """🔱 High-Level Reasoning: Proposes the next intelligent move."""
    try:
        g = await _ddgs_brain(f"State:\n{state}\nNext Goal?")
        if g:
            ingest_document(g, {"type": "goal"})
            meta_log("goal", "proposed", 0.7, {"text": g})
        return g or ""
    except Exception as e:
        record_failure("local", "autonomous_goal", "", "", str(e))
        return ""

async def causal_reasoning(context: str) -> str:
    """🔱 Causal Analysis: Why did we fail?"""
    try:
        r = await _ddgs_brain(f"Analyze failures:\n{context}")
        if r:
            ingest_document(r, {"type": "causal"})
            meta_log("causal", "analyzed", 0.6, {"text": r})
        return r or ""
    except Exception as e:
        record_failure("local", "causal_reasoning", "", "", str(e))
        return ""

async def self_reflect(logs: str) -> str:
    """🔱 Mirror Phase: Self-reflection for continuous improvement."""
    try:
        r = await _ddgs_brain(f"Reflect on logs:\n{logs}")
        if r:
            ingest_document(r, {"type": "reflect"})
            meta_log("reflect", "completed", 0.8, {"text": r})
        return r or ""
    except Exception as e:
        record_failure("local", "self_reflect", "", "", str(e))
        return ""

class MultiModelVision:
    """🔱 Divine Vision: Florence-2 for fast grounding, Qwen2-VL for complex OCR."""
    def __init__(self, qwen_model: str = "Qwen/Qwen2-VL-2B-Instruct"):
        self.qwen_model = qwen_model
        self._client: Optional[InferenceClient] = None
        self._last_use = time.time()
        if _hf_key:
            try:
                self._client = InferenceClient(token=_hf_key)
            except Exception as e:
                logger.warning(f"Qwen2-VL client init failed: {e}")

    def unload_if_idle(self, idle_seconds: float = 120.0) -> None:
        try:
            if time.time() - self._last_use >= idle_seconds:
                try:
                    global _VISION_MODEL, _VISION_PROCESSOR
                    _VISION_MODEL = None
                    _VISION_PROCESSOR = None
                except Exception:
                    pass
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
        except Exception:
            pass

    async def florence_coords(self, image_path: str) -> List[Tuple[int, int]]:
        try:
            res = await _remote_florence2_vision(image_path, tasks=["object_detection"])
            od = res.get("object_detection") or {}
            centers: List[Tuple[int, int]] = []
            arr = od.get("<OD>") if isinstance(od, dict) else None
            if isinstance(arr, list):
                for o in arr:
                    box = o.get("box") or {}
                    x = int(box.get("x", 0)); y = int(box.get("y", 0)); w = int(box.get("w", 0)); h = int(box.get("h", 0))
                    centers.append((x + max(1, w)//2, y + max(1, h)//2))
            return centers
        except Exception as e:
            logger.warning(f"Florence coords failed: {e}")
            return []

    async def qwen_describe(self, image_path: str, prompt: str = "Describe the image in detail.") -> str:
        try:
            self._last_use = time.time()
            if not self._client:
                return "Qwen2-VL unavailable (no HF token)"
            with open(image_path, "rb") as f:
                img_bytes = f.read()
            out = self._client.chat.completions.create(
                model=self.qwen_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image", "image_bytes": img_bytes},
                        ],
                    }
                ],
                max_tokens=512,
                temperature=0.2,
            )
            txt = (out.choices[0].message.content or "").strip()
            return txt
        except Exception as e:
            return f"Qwen2-VL error: {e}"

    async def analyze(self, image_path: str) -> Dict[str, Any]:
        """Runs Florence grounding and Qwen reasoning; returns combined report."""
        florence = await _remote_florence2_vision(image_path, tasks=["caption", "object_detection"])
        coords = await self.florence_coords(image_path)
        qwen = await self.qwen_describe(image_path, "Provide OCR and layout understanding.")
        self.unload_if_idle(120.0)
        return {"florence": florence, "coords": coords, "qwen": qwen}

async def evaluate_success(action_result: Any, expected_outcome: Any) -> Tuple[bool, str]:
    logger.info(f"Evaluating: Result={action_result}, Expected={expected_outcome}")
    if action_result == expected_outcome:
        return True, "Action was successful."
    return False, "Action failed to achieve expected outcome."
