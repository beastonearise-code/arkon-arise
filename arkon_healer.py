import os
import logging
import asyncio
from typing import Optional, Dict, Any, Tuple, List
import requests
import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForCausalLM
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

_hf_key: Optional[str] = (os.getenv("HUGGINGFACE_API_TOKEN", "").strip() or None)

async def _remote_florence2_vision(image_path: str, task: str = "caption") -> Dict[str, Any]:
    try:
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        model = AutoModelForCausalLM.from_pretrained("microsoft/Florence-2-large", torch_dtype=torch_dtype, trust_remote_code=True).to(device)
        processor = AutoProcessor.from_pretrained("microsoft/Florence-2-large")
        image = Image.open(image_path)
        if task == "caption":
            prompt = "<CAPTION>"
        elif task == "object_detection":
            prompt = "<OD>"
        else:
            return {"error": "Invalid task"}
        inputs = processor(text=prompt, images=image, return_tensors="pt").to(device, torch_dtype)
        generated_ids = model.generate(
            input_ids=inputs["input_ids"],
            pixel_values=inputs["pixel_values"],
            max_new_tokens=512,
            num_beams=3,
            do_sample=False
        )
        generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
        parsed_answer = processor.post_process_generation(generated_text, task=prompt, image_size=(image.width, image.height))
        return {"result": parsed_answer}
    except Exception as e:
        logger.error(f"_remote_florence2_vision error: {e}")
        return {"error": str(e)}

async def florence2_describe_image_url(image_url: str) -> Dict[str, Any]:
    try:
        tmp_path = None
        resp = requests.get(image_url, timeout=30)
        resp.raise_for_status()
        tmp_path = os.path.join(os.getcwd(), f"_tmp_img_{os.getpid()}.jpg")
        with open(tmp_path, "wb") as f:
            f.write(resp.content)
        caption = await _remote_florence2_vision(tmp_path, task="caption")
        od = await _remote_florence2_vision(tmp_path, task="object_detection")
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        return {"caption": caption, "objects": od}
    except Exception as e:
        logger.error(f"florence2_describe_image_url error: {e}")
        return {"error": str(e)}

def _ddgs_search_modes(q: str) -> List[dict]:
    results: List[dict] = []
    with DDGS() as ddgs:
        for r in ddgs.text(q, max_results=8):
            results.append({"source": "text", **r})
        for r in ddgs.news(q, max_results=4):
            results.append({"source": "news", **r})
    return results

async def _ddgs_brain(prompt: str, attempts: int = 5) -> str:
    def _run_sync() -> str:
        rs = _ddgs_search_modes(prompt)
        if not rs:
            return "No results."
        seen = set()
        lines: List[str] = []
        for r in rs:
            t = (r.get("title") or "").strip()
            b = (r.get("body") or r.get("snippet") or "").strip()
            u = r.get("href") or r.get("url") or ""
            key = (t, b)
            if key in seen:
                continue
            seen.add(key)
            if t or b:
                lines.append(f"- {t}: {b} ({u})")
        head = f"Query: {prompt}"
        return "\n".join([head] + lines[:12])
    delay = 2.5
    for i in range(attempts):
        try:
            return await asyncio.to_thread(_run_sync)
        except Exception as e:
            await asyncio.sleep(delay)
            delay = min(delay * 1.8, 30.0)
    return "No answer available."

async def propose_selector(goal: str, state: str) -> str:
    q = f"{goal}. Context: {state}"
    return await _ddgs_brain(q)

async def get_autonomous_fix(problem_description: str, current_state: str) -> str:
    """
    Placeholder for a function that autonomously generates a fix for a given problem.
    """
    logger.info(f"Attempting to get autonomous fix for: {problem_description}")
    return f"Proposed fix for '{problem_description}': Analyze current state and suggest a solution."

async def evaluate_success(action_result: Any, expected_outcome: Any) -> Tuple[bool, str]:
    """
    Placeholder for a function that evaluates the success of an action.
    """
    logger.info(f"Evaluating success of action. Result: {action_result}, Expected: {expected_outcome}")
    # In a real scenario, this would involve comparing results against expectations.
    if action_result == expected_outcome:
        return True, "Action was successful."
    else:
        return False, "Action failed to achieve expected outcome."
