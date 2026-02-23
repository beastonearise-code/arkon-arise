import asyncio
import os
import random
import time
import json
import base64
import re
from typing import List, Dict, Any, Optional, Tuple

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET


def _ua() -> str:
    uas = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    ]
    return random.choice(uas)


def shadow_search(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    try:
        import importlib
        DDGS = getattr(importlib.import_module("duckduckgo_search"), "DDGS", None)
        if DDGS is None:
            raise RuntimeError("ddgs missing")
        with DDGS() as ddgs:
            rows = ddgs.text(query, max_results=max_results)
            return [{"title": r.get("title", ""), "href": r.get("href", ""), "snippet": r.get("body", "")} for r in rows]
    except Exception:
        try:
            q = urllib.parse.quote(query)
            req = urllib.request.Request(f"https://duckduckgo.com/html/?q={q}", headers={"User-Agent": _ua()})
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", "ignore")
            links = []
            for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, flags=re.I | re.S):
                href = m.group(1)
                title = re.sub("<.*?>", "", m.group(2))
                links.append({"title": title, "href": href, "snippet": ""})
                if len(links) >= max_results:
                    break
            return links
        except Exception:
            return []


def reddit_trends(max_items: int = 10) -> List[Dict[str, str]]:
    try:
        req = urllib.request.Request("https://old.reddit.com/r/popular/", headers={"User-Agent": _ua()})
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", "ignore")
        items = []
        for m in re.finditer(r'<a[^>]+class="title[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, flags=re.I | re.S):
            href = m.group(1)
            title = re.sub("<.*?>", "", m.group(2)).strip()
            if title:
                items.append({"title": title, "url": href})
            if len(items) >= max_items:
                break
        return items
    except Exception:
        return []


def rss_pulse(feeds: Optional[List[str]] = None, max_items: int = 20) -> List[Dict[str, str]]:
    lst = feeds or [
        "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US",
        "https://news.google.com/rss",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
    ]
    out = []
    for url in lst:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _ua()})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = resp.read()
            root = ET.fromstring(data.decode("utf-8", "ignore"))
            for item in root.iterfind(".//item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                if title and link:
                    out.append({"title": title, "url": link})
                    if len(out) >= max_items:
                        return out
        except Exception:
            continue
    return out


def pollinations_image(prompt: str, out_path: str) -> bool:
    try:
        u = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
        req = urllib.request.Request(u, headers={"User-Agent": _ua()})
        with urllib.request.urlopen(req, timeout=30) as resp:
            img = resp.read()
        with open(out_path, "wb") as f:
            f.write(img)
        return True
    except Exception:
        return False


def edge_tts_narrate(text: str, out_path: str, voice: str = "en-US-JennyNeural") -> bool:
    try:
        import importlib
        edge_tts = importlib.import_module("edge_tts")
    except Exception:
        return False
    async def run():
        c = edge_tts.Communicate(text, voice=voice)
        await c.save(out_path)
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    try:
        asyncio.get_event_loop().run_until_complete(run())
        return True
    except Exception:
        return False


def stitch_reels(paths: List[str], out_path: str) -> bool:
    try:
        import importlib
        mpe = importlib.import_module("moviepy.editor")
        VideoFileClip = getattr(mpe, "VideoFileClip")
        concatenate_videoclips = getattr(mpe, "concatenate_videoclips")
    except Exception:
        return False
    try:
        clips = [VideoFileClip(p) for p in paths]
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(out_path, codec="libx264", audio_codec="aac", fps=24, verbose=False, logger=None)
        for c in clips:
            c.close()
        final.close()
        return True
    except Exception:
        return False


def check_sharpness(image_path: str) -> Optional[float]:
    try:
        import importlib
        cv2 = importlib.import_module("cv2")
    except Exception:
        return None
    try:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None
        val = cv2.Laplacian(img, cv2.CV_64F).var()
        return float(val)
    except Exception:
        return None


def thumbnail_quality(image_path: str) -> Optional[Dict[str, float]]:
    try:
        import importlib
        cv2 = importlib.import_module("cv2")
        np = importlib.import_module("numpy")
    except Exception:
        return None
    try:
        img = cv2.imread(image_path)
        if img is None:
            return None
        sharp = cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        s = hsv[:, :, 1].astype("float32")
        colorfulness = float(s.mean())
        return {"sharpness": float(sharp), "colorfulness": colorfulness}
    except Exception:
        return None


def hf_space_generate(space: str, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        import importlib
        Client = getattr(importlib.import_module("gradio_client"), "Client", None)
        if Client is None:
            raise RuntimeError("gradio_client missing")
    except Exception:
        return None
    try:
        client = Client(space)
        r = client.predict(**inputs)
        if isinstance(r, (list, tuple)):
            return {"result": list(r)}
        return {"result": r}
    except Exception:
        return None


async def insta_human_visit(url: str) -> bool:
    try:
        from playwright.async_api import async_playwright
        try:
            from playwright_stealth import stealth_async as stealth
        except Exception:
            stealth = None
    except Exception:
        return False
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        proxy_list = os.getenv("PROXY_LIST", "").strip()
        proxy = None
        if proxy_list:
            parts = [x.strip() for x in proxy_list.split(",") if x.strip()]
            if parts:
                proxy = {"server": random.choice(parts)}
        context = await browser.new_context(user_agent=_ua(), viewport={"width": 1280, "height": 800}, proxy=proxy)
        page = await context.new_page()
        if stealth:
            try:
                await stealth(page)
            except Exception:
                pass
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            for _ in range(5):
                x0 = random.randint(10, 400)
                y0 = random.randint(10, 400)
                x1 = random.randint(100, 900)
                y1 = random.randint(100, 700)
                await page.mouse.move(x0, y0, steps=random.randint(10, 25))
                await page.mouse.move(x1, y1, steps=random.randint(10, 25))
                await page.mouse.wheel(0, random.randint(200, 800))
                await asyncio.sleep(random.uniform(0.4, 1.2))
        except Exception:
            await context.close()
            await browser.close()
            return False
        await context.close()
        await browser.close()
        return True


def generate_hooks(topic: str) -> List[str]:
    t = topic.strip()
    hooks = [
        f"Wait—{t} is not what you think. Watch this.",
        f"Before you scroll, this {t} flips the script.",
        f"You’ve been doing {t} wrong; here’s the 3‑second fix.",
    ]
    return hooks


def _clean_text(txt: str) -> str:
    return re.sub(r"\s+", " ", re.sub("<.*?>", " ", txt or "")).strip()


def competitor_audit(query: str, take: int = 5) -> Dict[str, Any]:
    rows = shadow_search(query, max_results=take)
    out = []
    for r in rows[:take]:
        url = r.get("href") or r.get("url") or ""
        if not url:
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _ua()})
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", "ignore")
            fonts = list({m.group(1) for m in re.finditer(r"font-family\s*:\s*([^;}{]+)", html, flags=re.I)})
            heads = [m.group(1) for m in re.finditer(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, flags=re.I | re.S)]
            heads = [_clean_text(h) for h in heads if _clean_text(h)]
            meta_m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html, flags=re.I)
            meta = meta_m.group(1).strip() if meta_m else ""
            out.append({"url": url, "fonts": fonts[:5], "headings": heads[:10], "summary": meta[:200]})
        except Exception:
            continue
    return {"query": query, "samples": out}


def anti_flag_check(text: str) -> Dict[str, Any]:
    banned = {"kill", "violence", "hate", "adult", "gamble", "scam", "crypto pump", "nsfw"}
    lower = text.lower()
    hits = [w for w in banned if w in lower]
    return {"safe": len(hits) == 0, "hits": hits}


def optimize_captions(caption: str) -> Dict[str, str]:
    cap = caption.strip()
    yt = cap[:100] + ("…" if len(cap) > 100 else "")
    ig = cap[:150] + ("…" if len(cap) > 150 else "")
    return {"youtube_shorts": yt, "instagram_reels": ig, "aspect_ratio": "9:16"}


def trend_hijack() -> Dict[str, Any]:
    r = reddit_trends(10)
    n = rss_pulse([], 10)
    topics = [i["title"] for i in (r + n)][:10]
    scripts = []
    for t in topics:
        hooks = generate_hooks(t)[:1]
        scripts.append({"topic": t, "hook": hooks[0], "script": f"Here’s why {t} matters now and how to react fast."})
    return {"topics": topics, "suggestions": scripts}


def swarm_orchestrate(query: str) -> Dict[str, Any]:
    researcher = {
        "trends": trend_hijack(),
        "audit": competitor_audit(query, take=5),
    }
    top_topic = researcher["trends"]["topics"][0] if researcher["trends"]["topics"] else query
    creator = {
        "hooks": generate_hooks(top_topic),
    }
    assets = {}
    img_out = "swarm_image.png"
    if pollinations_image(top_topic, img_out):
        assets["image"] = img_out
        q = thumbnail_quality(img_out)
        assets["thumbnail_quality"] = q
        if q and (q.get("sharpness", 0) < 120 or q.get("colorfulness", 0) < 60):
            assets["quality_gate"] = {"pass": False, "reason": "Below thresholds: sharpness>120 and colorfulness>60"}
        else:
            assets["quality_gate"] = {"pass": True}
    ghost_poster = {
        "platforms": ["YouTube Shorts", "Instagram Reels"],
        "captions": optimize_captions(creator["hooks"][0] if creator["hooks"] else top_topic),
        "anti_flag": anti_flag_check((creator["hooks"][0] if creator["hooks"] else top_topic)),
        "post_allowed": assets.get("quality_gate", {}).get("pass", True) and anti_flag_check((creator["hooks"][0] if creator["hooks"] else top_topic)).get("safe", True),
    }
    return {"researcher": researcher, "creator": creator, "assets": assets, "ghost_poster": ghost_poster}


def quality_gate(image_path: str, sharp_min: float = 120.0, color_min: float = 60.0) -> Dict[str, Any]:
    q = thumbnail_quality(image_path) or {}
    sharp = float(q.get("sharpness", 0))
    col = float(q.get("colorfulness", 0))
    passed = (sharp >= sharp_min) and (col >= color_min)
    return {"pass": passed, "sharpness": sharp, "colorfulness": col, "sharp_min": sharp_min, "color_min": color_min}

def youtube_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    k = os.getenv("YOUTUBE_API_KEY", "").strip()
    out: List[Dict[str, str]] = []
    q = urllib.parse.quote(query)
    if k:
        try:
            url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={q}&type=video&maxResults={max_results}&key={urllib.parse.quote(k)}"
            req = urllib.request.Request(url, headers={"User-Agent": _ua()})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            for item in data.get("items", []):
                idv = item.get("id", {}).get("videoId", "")
                sn = item.get("snippet", {})
                title = sn.get("title", "")
                channel = sn.get("channelTitle", "")
                if idv:
                    out.append({"title": title, "url": f"https://www.youtube.com/watch?v={idv}", "channel": channel})
                    if len(out) >= max_results:
                        break
            return out
        except Exception:
            pass
    try:
        ddg = shadow_search(f"site:youtube.com {query}", max_results=max_results)
        for r in ddg:
            out.append({"title": r.get("title",""), "url": r.get("href","") or r.get("url",""), "channel": ""})
        return out
    except Exception:
        return out

def compile_ebook_html(topic: str, out_path: str) -> bool:
    try:
        rows = shadow_search(topic, max_results=8)
        try:
            from arkon_memory import rag_query
            ctxs = rag_query(topic, top_k=3)
        except Exception:
            ctxs = []
        html = ["<html><head><meta charset='utf-8'><title>Ebook</title></head><body>"]
        html.append(f"<h1>{topic}</h1>")
        html.append("<h2>Context</h2><ul>")
        for c in ctxs:
            html.append(f"<li>{(c.get('text','')[:500]).replace('<','&lt;')}</li>")
        html.append("</ul><h2>Sources</h2><ul>")
        for r in rows:
            href = r.get("href") or r.get("url") or ""
            if href:
                html.append(f"<li><a href='{href}'>{r.get('title','')}</a></li>")
        html.append("</ul></body></html>")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(html))
        return True
    except Exception:
        return False

async def site_scanner(url: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"url": url, "meta": {}, "leaks": [], "heads": []}
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return out
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=_ua(), viewport={"width": 1280, "height": 800})
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            html = await page.content()
            import re as _re
            for m in _re.finditer(r'<meta[^>]+name=["\']([^"\']+)["\'][^>]+content=["\']([^"\']+)["\']', html, flags=_re.I):
                out["meta"][m.group(1).lower()] = m.group(2)
            out["heads"] = [h for h in [_clean_text(m.group(1)) for m in _re.finditer(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, flags=_re.I | _re.S)] if h]
            leak_patterns = [r'AKIA[0-9A-Z]{16}', r'AIza[0-9A-Za-z_\-]{35}', r'sk-[A-Za-z0-9]{20,}']
            for lp in leak_patterns:
                for m in _re.finditer(lp, html):
                    out["leaks"].append({"pattern": lp, "value": m.group(0)})
            await context.close()
            await browser.close()
    except Exception:
        return out
    return out

def instagram_prepare_reel(topic: str, image_out: str = "reel.png") -> Dict[str, Any]:
    hooks = generate_hooks(topic)
    ok_img = pollinations_image(topic, image_out)
    hook = hooks[0] if hooks else topic
    audio_url = None
    image_url = None
    try:
        from arkon_cloud import elevenlabs_tts, cloudinary_upload, sheets_ledger_usage
        b = elevenlabs_tts(hook) or None
        if b:
            au = cloudinary_upload(b, "arkon_hook_audio", "audio/mpeg")
            if au:
                audio_url = au
        if ok_img:
            try:
                with open(image_out, "rb") as f:
                    ib = f.read()
                iu = cloudinary_upload(ib, "arkon_reel_image", "image/png")
                if iu:
                    image_url = iu
            except Exception:
                pass
        try:
            sheets_ledger_usage("content_pipeline", 0.0, {"topic": topic, "audio_url": audio_url or "", "image_url": image_url or ""})
        except Exception:
            pass
    except Exception:
        pass
    return {"topic": topic, "hook": hook, "image": image_out if ok_img else None, "audio_url": audio_url, "image_url": image_url}

def stress_simulation(n: int = 100) -> Dict[str, Any]:
    out = {"ok": 0, "err": 0}
    feats = [
        lambda: reddit_trends(5),
        lambda: rss_pulse([], 5),
        lambda: youtube_search("technology", 3),
        lambda: shadow_search("ai security", 3),
    ]
    for i in range(n):
        try:
            f = feats[i % len(feats)]
            _ = f()
            out["ok"] += 1
        except Exception:
            out["err"] += 1
    return out
