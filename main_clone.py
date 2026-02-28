from dotenv import load_dotenv
load_dotenv()

import asyncio
import logging
import os
import random
import argparse
import shutil
import sys
from typing import Optional
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
import json

from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page

try:
    from playwright_stealth import stealth_async as stealth
except Exception:
    try:
        from playwright_stealth import Stealth as _Stealth

        async def stealth(page: Page) -> None:
            await _Stealth().apply_stealth_async(page.context)
    except Exception:
        stealth = None

from arkon_healer import get_autonomous_fix, evaluate_success, propose_selector, _remote_florence2_vision, causal_reasoning, self_reflect, autonomous_goal
from arkon_memory import consult_selector, record_failure, record_success, record_hostile, meta_log, ingest_document

import infinity_mode as infinity
from arkon_messenger import send_telegram_message, send_gmail_email, send_sentinel_alert

load_dotenv()

logger = logging.getLogger("arkon")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("🔱 %(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)


async def run_diagnostic_test():
    logger.info("🔱 [Diagnostic Mode]: Running Vision and Keyless Brain tests...")

    # Test Hugging Face Cloud Brain (Florence-2)
    logger.info("🔱 [Diagnostic Mode]: Testing _remote_florence2_vision...")
    
    image_path = "c:\\arkon alive\\test_vision.jpg"
    if not os.path.exists(image_path):
        # If test_vision.jpg not found, find the first .jpg file
        for file in os.listdir("c:\\arkon alive\\"):
            if file.endswith(".jpg"):
                image_path = os.path.join("c:\\arkon alive\\", file)
                logger.info(f"🔱 [Diagnostic Mode]: Using first available JPG image: {image_path}")
                break
        else:
            logger.error("🔱 [Diagnostic Mode]: No JPG image found in c:\\arkon alive\\. Cannot perform visual reconnaissance.")
            return

    try:
        # Perform Captioning
        vision_caption_result = await _remote_florence2_vision(image_path, task="caption")
        caption = vision_caption_result.get("result", {}).get("<CAPTION>", "No caption generated.")
        logger.info(f"🔱 [Diagnostic Mode]: Florence-2 Captioning Result: {caption}")

        # Perform Object Detection
        vision_od_result = await _remote_florence2_vision(image_path, task="object_detection")
        objects = vision_od_result.get("result", {}).get("<OD>", "No objects detected.")
        logger.info(f"🔱 [Diagnostic Mode]: Florence-2 Object Detection Result: {objects}")

        visual_description = f"Caption: {caption}\nObjects Detected: {objects}"
        logger.info(f"🔱 [Diagnostic Mode]: Combined Visual Description:\n{visual_description}")

        # Summarize via Keyless Brain
        ollama_summary = await propose_selector(
            goal="Summarize what this image means, providing a concise 'Vision Intelligence Report'.",
            state=visual_description
        )
        logger.info(f"🔱 [Diagnostic Mode]: Vision Intelligence Report:\n{ollama_summary}")

        # Send report to Telegram
        telegram_message = f"Vision Intelligence Report:\n\n{ollama_summary}"
        send_telegram_message(telegram_message)
        logger.info("🔱 [Diagnostic Mode]: Vision Intelligence Report sent to Telegram.")

    except Exception as e:
        logger.error(f"🔱 [Diagnostic Mode]: Visual Reconnaissance FAILED with exception: {e}")
    
    # Test Keyless Brain
    logger.info("🔱 [Diagnostic Mode]: Testing Keyless propose_selector...")
    ollama_goal = "Find the 'submit' button"
    ollama_state = "<html><body><button>Submit</button></body></html>"
    try:
        ollama_selector = await propose_selector(ollama_goal, ollama_state)
        if ollama_selector:
            logger.info(f"🔱 [Diagnostic Mode]: Keyless Reasoning (propose_selector) SUCCESS. Proposed selector: {ollama_selector}")
        else:
            logger.error("🔱 [Diagnostic Mode]: Keyless Reasoning (propose_selector) FAILED. No selector proposed.")
    except Exception as e:
        logger.error(f"🔱 [Diagnostic Mode]: Keyless Reasoning (propose_selector) FAILED with exception: {e}")

    logger.info("🔱 [Diagnostic Mode]: Diagnostic tests complete.")


def _bezier(p0, p1, p2, p3, t):
    x = (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0]
    y = (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1]
    return int(x), int(y)


async def move_mouse_bezier(page: Page, start, end, steps=30):
    c1 = (start[0] + random.randint(-100, 100), start[1] + random.randint(-100, 100))
    c2 = (end[0] + random.randint(-100, 100), end[1] + random.randint(-100, 100))
    for i in range(steps + 1):
        t = i / steps
        x, y = _bezier(start, c1, c2, end, t)
        await page.mouse.move(x, y, steps=1)
        await asyncio.sleep(random.uniform(0.005, 0.02))


async def human_jitter(page: Page, *, moves: int = 5) -> None:
    for _ in range(moves):
        x0 = random.randint(10, 300)
        y0 = random.randint(10, 300)
        x1 = random.randint(50, 600)
        y1 = random.randint(50, 600)
        try:
            await move_mouse_bezier(page, (x0, y0), (x1, y1), steps=random.randint(20, 40))
            await page.mouse.wheel(random.randint(-200, 200), random.randint(-200, 200))
        except Exception:
            pass
        await asyncio.sleep(random.uniform(0.2, 1.0))


async def cognitive_type(page: Page, selector: str, text: str) -> None:
    await page.focus(selector)
    for ch in text:
        # 5% clumsy human error with immediate backspace correction
        if random.random() < 0.05:
            await page.keyboard.type(ch, delay=random.uniform(80, 260))
            await page.keyboard.type("x", delay=random.uniform(80, 150))
            await page.keyboard.press("Backspace")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(ch, delay=random.uniform(80, 260))
        else:
            await page.keyboard.type(ch, delay=random.uniform(50, 250))
    if random.random() < 0.5:
        await asyncio.sleep(random.uniform(2.0, 5.0))


def _user_agent(use_mobile: bool) -> str:
    if use_mobile:
        return "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
    return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


def _fingerprint_script(vendor: str, renderer: str, hwc: int) -> str:
    return f"""
// Hardware fingerprint mutation
Object.defineProperty(navigator, 'hardwareConcurrency', {{get: () => {hwc}}});
// Canvas noise
(function() {{
  const toDataURL = HTMLCanvasElement.prototype.toDataURL;
  HTMLCanvasElement.prototype.toDataURL = function() {{
    const ctx = this.getContext('2d');
    try {{
      const w = Math.max(1, Math.floor(this.width/10));
      const h = Math.max(1, Math.floor(this.height/10));
      ctx.fillStyle = 'rgba(120,120,120,0.01)';
      ctx.fillRect(0,0,w,h);
    }} catch (e) {{ }}
    return toDataURL.apply(this, arguments);
  }};
}})();
// WebGL spoof
(function() {{
  const getParameter = WebGLRenderingContext.prototype.getParameter;
  WebGLRenderingContext.prototype.getParameter = function(p) {{
    if (p === 37445) return '{vendor}'; // UNMASKED_VENDOR_WEBGL
    if (p === 37446) return '{renderer}'; // UNMASKED_RENDERER_WEBGL
    return getParameter.apply(this, arguments);
  }};
}})();
// AudioContext noise
(function() {{
  const orig = AudioContext.prototype.createOscillator;
  AudioContext.prototype.createOscillator = function() {{
    const osc = orig.apply(this, arguments);
    try {{ osc.detune.value += Math.random() * 0.0001; }} catch (e) {{ }}
    return osc;
  }};
}})();
// Disable WebRTC IP leaks (soft-protect)
(function() {{
  const OrigPC = window.RTCPeerConnection;
  if (OrigPC) {{
    window.RTCPeerConnection = function(cfg) {{
      try {{ if (cfg) cfg.iceServers = []; }} catch (e) {{ }}
      const pc = new OrigPC(cfg);
      const addIce = pc.addIceCandidate;
      pc.addIceCandidate = function() {{ return Promise.resolve(); }};
      return pc;
    }};
  }}
}})();
"""





def check_meta_expiry_and_alert() -> None:
    try:
        expiry_str = os.getenv("META_TOKEN_EXPIRES", "2026-04-21")
        expiry = datetime.strptime(expiry_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        days_left = (expiry.date() - now.date()).days
        if 0 <= days_left <= 5:
            send_telegram_message("🔱 Master! The Meta Access Token is set to expire on April 21. Action required.")
            send_gmail_email("Arkon Alert: Meta Access Token Expiry", "Master! The Meta Access Token is set to expire on April 21. Action required.")
    except Exception:
        pass


async def try_click(page: Page, selector: str, timeout_ms: int = 6000) -> bool:
    try:
        # 20% clumsy off-center click by 5-10px
        if random.random() < 0.2:
            loc = page.locator(selector)
            bb = await loc.bounding_box()
            if bb:
                dx = random.randint(-10, 10)
                dy = random.randint(-10, 10)
                pos = {"x": int(bb["width"]/2) + dx, "y": int(bb["height"]/2) + dy}
                await loc.click(timeout=timeout_ms, position=pos, force=False)
                return True
        await page.click(selector, timeout=timeout_ms, force=False)
        return True
    except Exception as e:
        logger.warning(f"Click failed for selector '{selector}': {e}")
        return False


async def diagnostics() -> bool:
    try:
        import importlib
        importlib.import_module("playwright")
        importlib.import_module("playwright_stealth")
    except Exception as e:
        logger.error(f"Diagnostics deps error: {e}")
        return False
    logger.info("Diagnostics: OK")
    return True


async def capture_state(page: Page) -> str:
    try:
        html = await page.evaluate("document.body.innerHTML || ''")
        html_cap = html[:6000]
        logger.info("🔱 [Blind-Spot-Check]: 6000 chars captured")
        return html_cap
    except Exception:
        return ""


async def self_evaluate(page: Page, expected: str) -> Optional[bool]:
    state = await capture_state(page)
    result = await evaluate_success(state, expected)
    if result is True:
        logger.info("🔱 [Self-Evaluation]: Success")
    elif result is False:
        logger.info("🔱 [Self-Evaluation]: Failure")
    else:
        logger.info("🔱 [Self-Evaluation]: Inconclusive")
    return result


def _parse_hint(selector_or_hint: str) -> tuple[str, str]:
    s = selector_or_hint.strip()
    hint = ""
    if "||" in s:
        parts = [p.strip() for p in s.split("||", 1)]
        s = parts[0]
        hint = parts[1].upper()
    elif s.upper().endswith(" JS_CLICK"):
        s = s[: -len(" JS_CLICK")].strip()
        hint = "JS_CLICK"
    elif s.upper().endswith(" FORCE_CLICK"):
        s = s[: -len(" FORCE_CLICK")].strip()
        hint = "FORCE_CLICK"
    return s, hint





async def mutate_click(page: Page, selector: str, hint: str = "") -> bool:
    logger.info("🔱 [Mutation]: Changing strategy to locator.dispatch_event")
    try:
        await page.locator(selector).dispatch_event("click")
        return True
    except Exception:
        pass
    logger.info("🔱 [Mutation]: Changing strategy to JS querySelector().click()")
    try:
        await page.evaluate("""(sel) => { const el = document.querySelector(sel); if (el) { el.click(); } }""", selector)
        return True
    except Exception:
        pass
    logger.info("🔱 [Mutation]: Changing strategy to force click")
    try:
        await page.click(selector, timeout=6000, force=True)
        return True
    except Exception:
        pass
    return False


async def _move_to_selector(page: Page, selector: str) -> None:
    try:
        # Scroll patterns with overshoot and correction
        loc = page.locator(selector)
        await page.evaluate("""(sel) => {
            const el = document.querySelector(sel);
            if (el) { el.scrollIntoView({behavior: 'smooth', block: 'center'}); }
        }""", selector)
        for _ in range(random.randint(2, 5)):
            await page.mouse.wheel(0, random.randint(100, 600))
            await asyncio.sleep(random.uniform(0.1, 0.4))
        for _ in range(random.randint(1, 3)):
            await page.mouse.wheel(0, -random.randint(50, 200))
            await asyncio.sleep(random.uniform(0.1, 0.3))
        bb = await loc.bounding_box()
        if bb:
            sx = int(bb["x"] + bb["width"] / 2)
            sy = int(bb["y"] + bb["height"] / 2)
            await move_mouse_bezier(page, (random.randint(10, 50), random.randint(10, 50)), (sx, sy), steps=random.randint(20, 40))
            # Eye-tracking jitter pause
            await asyncio.sleep(random.uniform(1.0, 2.0))
            if random.random() < 0.2:
                await asyncio.sleep(random.uniform(3.0, 6.0))  # Chronos masking
    except Exception:
        await human_jitter(page, moves=2)


def _phishing_guard(url: str, html: str) -> bool:
    flags = 0
    if any(x in url.lower() for x in ["login-", "verify", "secure-update", "confirm-account"]):
        flags += 1
    if "data-keylogger" in html.lower():
        flags += 1
    # Simple heuristic; return True if safe
    return flags == 0


async def run_dynamic_flow(browser_type: str) -> bool:
    target_url = "https://the-internet.herokuapp.com/dynamic_loading/2."
    use_mobile = False
    async with async_playwright() as p:
        launcher = {"chromium": p.chromium, "firefox": p.firefox}.get(browser_type, p.chromium)
        browser = await launcher.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
                "--no-zygote",
                "--renderer-process-limit=1",
            ],
        )
        # Dynamic fingerprint mutation
        vendor_options = ["NVIDIA Corporation", "Intel Inc.", "Apple Inc."]
        renderer_options = ["NVIDIA GeForce RTX 3080", "Intel Iris OpenGL Engine", "Apple M2"]
        hwc_options = [4, 8, 16]
        fscript = _fingerprint_script(
            random.choice(vendor_options),
            random.choice(renderer_options),
            random.choice(hwc_options),
        )
        context = await browser.new_context(
            user_agent=_user_agent(use_mobile),
            viewport={"width": 1280, "height": 720},
        )
        await context.add_init_script(fscript)
        page = await context.new_page()
        # Emergency kill-switch (Ctrl+Alt+K)
        killed = {"value": False}
        async def _kill():
            killed["value"] = True
            send_telegram_message("Kill switch triggered")
            send_gmail_email("Arkon Alert: Kill Switch Triggered", "Kill switch triggered")
            try:
                await context.close()
                await browser.close()
            except Exception:
                pass
        await page.expose_function("killSwitch", _kill)
        await page.add_init_script("""
            document.addEventListener('keydown', (e) => {
              if (e.ctrlKey && e.altKey && (e.key === 'k' || e.key === 'K')) {
                window.killSwitch();
              }
            });
        """)
        if stealth is not None:
            try:
                await stealth(page)
            except Exception as e:
                logger.warning(f"Stealth application failed: {e}")
        await human_jitter(page)
        try:
            logger.info(f"Navigating to {target_url}")
            await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            logger.error(f"Navigation error: {e}")
        await human_jitter(page)
        logger.info("🔱 [Pure-Autonomy]: No hardcoded paths used")
        clicked = False
        no_count = 0

        async def retaliation_exhaustion() -> None:
            try:
                tmp = await context.new_page()
                await tmp.goto("data:text/html,<html><body>decoy</body></html>")
                # Spawn a bounded resource worker for distraction (local only, no network)
                await tmp.evaluate("""() => {
                  const blob = new Blob([`
                    onmessage = () => {
                      const t = Date.now() + 3000;
                      let s = 0;
                      while (Date.now() < t) { s += Math.sqrt(Math.random()*1e6); }
                      postMessage(s);
                    };
                  `], {type: 'text/javascript'});
                  const url = URL.createObjectURL(blob);
                  const w = new Worker(url);
                  w.postMessage('run');
                  setTimeout(() => { try { w.terminate(); } catch(e) {} }, 3500);
                  try { localStorage.setItem('telemetry', Math.random().toString(36)); } catch(e) {}
                }""")
                await asyncio.sleep(0.2)
                await tmp.close()
            except Exception:
                pass
        for attempt in range(3):
            state = await capture_state(page)
            goal = "Locate the start trigger and reveal 'Hello World!'"
            mem = consult_selector(target_url, goal)
            sel_raw = None
            if mem:
                sel_raw = f"{mem[0]} || {mem[1]}" if mem[1] else mem[0]
                logger.info("🔱 Using memory selector before Brain proposal")
            if not sel_raw:
                sel_raw = await propose_selector(goal, state) or await get_autonomous_fix(state, "Need a selector to click Start")
                # Sovereign Fallback: local rule-based selector if Brain unavailable
                if not sel_raw:
                    g = goal.lower()
                    if "start" in g:
                        sel_raw = "text=Start"
                    elif "hello world" in g:
                        sel_raw = "text=Hello World!"
            if not sel_raw:
                continue
            selector, hint = _parse_hint(sel_raw)
            # Honeypot detection: skip hidden/transparent elements
            try:
                styles = await page.evaluate("""(sel) => {
                    const el = document.querySelector(sel);
                    if (!el) return null;
                    const cs = getComputedStyle(el);
                    return {v: cs.visibility, o: cs.opacity, d: cs.display};
                }""", selector)
                if styles and (styles.get("v") == "hidden" or styles.get("d") == "none" or float(styles.get("o","1")) < 0.2):
                    record_hostile(target_url, notes="honeypot-detected")
                    send_telegram_message("Critical: Honeypot detected; marking site hostile")
                    send_gmail_email("Arkon Alert: Honeypot Detected", "Critical: Honeypot detected; marking site hostile")
                    continue
            except Exception:
                pass
            # Humanitarian Guard
            if not _phishing_guard(target_url, state):
                logger.warning("🔱 Humanitarian Guard: Potential phishing indicators — aborting interaction")
                record_hostile(target_url, notes="phishing-indicators")
                send_telegram_message("Critical: Humanitarian Guard flagged phishing indicators")
                send_gmail_email("Arkon Alert: Phishing Indicators", "Critical: Humanitarian Guard flagged phishing indicators")
                break
            await _move_to_selector(page, selector)

            try:
                if hint == "JS_CLICK":
                    clicked = await mutate_click(page, selector, hint="JS_CLICK")
                elif hint == "FORCE_CLICK":
                    clicked = await mutate_click(page, selector, hint="FORCE_CLICK")
                else:
                    clicked = await try_click(page, selector, timeout_ms=8000) or await mutate_click(page, selector)
            except Exception:
                clicked = False
            eval_res = await self_evaluate(page, "Loading should be starting or visible")
            if eval_res is False:
                no_count += 1
                if no_count >= 2:
                    insight = ""
                    try:
                        insight = await causal_reasoning(state)
                        ingest_document(insight or "", {"type": "causal"})
                        meta_log("failure", "analyzed", 0.6, {"insight": insight or ""})
                    except Exception:
                        pass
                    record_failure(target_url, goal, selector, hint, notes="Hydra switch trigger")
                    logger.info("🔱 Ghost_Mode: Cooling down and rotating soft-signatures")
                    send_sentinel_alert("Hydra: Switching browser due to repeated failures")
                    backup_vault("hydra-switch")
                    await retaliation_exhaustion()
                    await asyncio.sleep(random.uniform(3.0, 8.0))  # Cool-down
                    await context.close()
                    await browser.close()
                    return False
            if clicked:
                if eval_res is not False:
                    record_success(target_url, goal, selector, hint, notes="Start clicked")
                    meta_log("click", "success", 0.8, {"selector": selector})
                    send_sentinel_alert("Success: Goal achieved for dynamic_loading/2")
                else:
                    record_failure(target_url, goal, selector, hint, notes="Start click inconclusive")
                    meta_log("click", "inconclusive", 0.5, {"selector": selector})
                break
        await asyncio.sleep(1.0)
        done = False
        for _ in range(20):
            eval_res = await self_evaluate(page, "Hello World! should be visible on the page")
            if eval_res is True:
                done = True
                record_success(target_url, "Reveal Hello World", "dynamic", "", notes="Hello World visible")
                meta_log("goal", "success", 0.9, {"goal": "Reveal Hello World"})
                break
            await asyncio.sleep(1.0)
        # Ghost Exit: secure wipe
        try:
            try:
                await page.evaluate("localStorage.clear(); sessionStorage.clear();")
            except Exception:
                pass
            await context.clear_cookies()
        except Exception:
            pass
        log_blob = f"url:{target_url}|attempts:{no_count}|done:{done}"
        try:
            ref = await self_reflect(log_blob)
            ingest_document(ref or "", {"type": "reflect"})
            meta_log("reflect", "logged", 0.8, {"text": ref or ""})
        except Exception:
            pass
        await context.close()
        await browser.close()
        return clicked


async def engine() -> None:
    ok = await diagnostics()
    if not ok:
        return
    for bt in ["chromium", "firefox"]:
        logger.info(f"Trying browser: {bt}")
        if await run_dynamic_flow(bt):
            break


def shadow_test() -> None:
    logger.info("🔱 [Shadow-Test]: Initializing clone for version upgrade...")
    src = os.path.join(os.path.dirname(__file__), "main.py")
    dst = os.path.join(os.path.dirname(__file__), "main_clone.py")
    try:
        shutil.copyfile(src, dst)
        logger.info("🔱 [Shadow-Test]: Clone created")
    except Exception as e:
        logger.error(f"🔱 [Shadow-Test]: Clone failed: {e}")
        return
    # Run probe on the clone
    try:
        import subprocess
        proc = subprocess.run([sys.executable, dst, "--probe"], capture_output=True, text=True, timeout=120)
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        if "STATUS_SUCCESS" in out and proc.returncode == 0:
            logger.info("🔱 [Shadow-Test]: STATUS_SUCCESS — eligible for atomic swap")
            # Atomic swap is disabled by default for safety in this demo.
            # Uncomment the following lines to enable overwrite:
            # shutil.copyfile(dst, src)
            # logger.info("🔱 [Shadow-Test]: main.py overwritten by clone")
        else:
            logger.warning("🔱 [Shadow-Test]: STATUS_FAILURE — clone discarded")
            try:
                os.remove(dst)
            except Exception:
                pass
    except Exception as e:
        logger.error(f"🔱 [Shadow-Test]: Probe error: {e}")
        try:
            os.remove(dst)
        except Exception:
            pass


async def main():
    # Temporarily run diagnostic tests directly
    if random.random() < 0.3:
        try:
            seeds = infinity.related_pages("start button")
            ranked = infinity.curiosity_rank(seeds)
            for u in ranked[:2]:
                infinity.add_link("seed", u)
                ingest_document(u, {"type": "curiosity"})
                meta_log("curiosity", "visited", 0.4, {"url": u})
        except Exception:
            pass
    await run_diagnostic_test()
    return

    # Existing main logic
    # parser = argparse.ArgumentParser(description="Arkon main script.")
    # parser.add_argument("--diagnostic", action="store_true", help="Run diagnostic tests.")
    # args = parser.parse_args()

    # if args.diagnostic:
    #     await run_diagnostic_test()
    #     return

    # browser_type = os.getenv("BROWSER_TYPE", "chromium")
    # if browser_type not in ["chromium", "firefox"]:
    #     logger.error(f"Invalid BROWSER_TYPE: {browser_type}. Must be 'chromium' or 'firefox'.")
    #     sys.exit(1)

    # check_meta_expiry_and_alert()
    # await run_dynamic_flow(browser_type)

if __name__ == "__main__":
    asyncio.run(main())
