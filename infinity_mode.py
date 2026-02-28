import asyncio
import os
import random
import time
import json
import base64
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple

# 🔱 Sovereign Integration
try:
    from arkon_memory import ingest_document, meta_log, working_memory_add, save_failure_trace
    from arkon_messenger import send_telegram_message, instagram_post_image
except ImportError:
    print("🔱 Warning: Core modules (Memory/Messenger) not found. Running in isolation.")

_knowledge_graph: Dict[str, List[str]] = {}

# --- 🔱 Curiosity & Knowledge Mapping ---
def add_link(src: str, dst: str) -> None:
    try:
        arr = _knowledge_graph.setdefault(src, [])
        if dst not in arr:
            arr.append(dst)
    except: pass

def build_knowledge_graph() -> Dict[str, List[str]]:
    """🔱 Returns a snapshot of what Arkon has learned."""
    return {k: list(v) for k, v in _knowledge_graph.items()}

async def curiosity_driven_browse(seed_topic: str):
    """🔱 The core autonomous loop that explores the web and records insights."""
    try:
        print(f"🔱 Arkon curiosity triggered for: {seed_topic}")
        try: meta_log("Curiosity", "Initiated", 0.7, {"topic": seed_topic})
        except: pass

        pages = related_pages(seed_topic)
        for page in pages[:3]:
            add_link(seed_topic, page)
            # 🔱 Store knowledge in the Sovereign Vault
            ingest_document(f"Learned insight: {seed_topic} is linked to {page}", {"type": "curiosity", "seed": seed_topic})
        
        return f"🔱 Arkon curiosity explored {len(pages)} paths for '{seed_topic}'."
    except Exception as e:
        try: save_failure_trace("Curiosity_Browse", str(e))
        except: pass
        return f"❌ Curiosity Error: {e}"

# --- 🔱 Stealth Search & Discovery ---
def _ua() -> str:
    uas = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
    ]
    return random.choice(uas)

def shadow_search(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    """🔱 Secure search without tracking."""
    try:
        import importlib
        DDGS = getattr(importlib.import_module("duckduckgo_search"), "DDGS", None)
        with DDGS() as ddgs:
            rows = list(ddgs.text(query, max_results=max_results))
            return [{"title": r.get("title", ""), "href": r.get("href", ""), "snippet": r.get("body", "")} for r in rows]
    except Exception:
        # 🔱 Fallback to direct HTML scraping if library fails
        try:
            q = urllib.parse.quote(query)
            req = urllib.request.Request(f"https://duckduckgo.com/html/?q={q}", headers={"User-Agent": _ua()})
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", "ignore")
            links = []
            # Improved regex for DDG scraping
            for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, flags=re.I|re.S):
                href = m.group(1)
                title = re.sub("<.*?>", "", m.group(2))
                links.append({"title": title.strip(), "href": href, "snippet": ""})
            return links[:max_results]
        except: return []

def related_pages(seed: str, max_results: int = 6) -> List[str]:
    rows = shadow_search(seed, max_results=max_results)
    return [r.get("href") for r in rows if r.get("href")]

# --- 🔱 Trend Hijacking & Social Blast ---
def reddit_trends(max_items: int = 10) -> List[Dict[str, str]]:
    try:
        req = urllib.request.Request("https://old.reddit.com/r/popular/", headers={"User-Agent": _ua()})
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", "ignore")
        items = []
        for m in re.finditer(r'<a[^>]+class="title[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, flags=re.I|re.S):
            title = re.sub("<.*?>", "", m.group(2)).strip()
            if title: items.append({"title": title, "url": m.group(1)})
        return items[:max_items]
    except: return []

def trend_hijack() -> Dict[str, Any]:
    """🔱 Scans Reddit/RSS and prepares potential content."""
    trends = reddit_trends(5)
    topics = [i["title"] for i in trends]
    suggestions = [{"topic": t, "script": f"🔱 [Trend Alert]: {t}"} for t in topics]
    return {"topics": topics, "suggestions": suggestions}

async def autonomous_trend_post():
    """🔱 Bridge: Finds a trend, generates an image, and posts to Instagram."""
    trends = trend_hijack()
    if trends["topics"]:
        top_topic = trends["topics"][0]
        img_name = "trend_visual.png"
        
        print(f"🔱 Arkon detected trend: {top_topic}. Generating visual...")
        if pollinations_image(top_topic, img_name):
            caption = f"🔱 ARKON TREND ALERT: {top_topic} #Arkon #Sovereign #AI #Trends"
            # 🔱 Using the success from our earlier trial!
            instagram_post_image(img_name, caption)
            return f"🔱 Autonomous post successful for: {top_topic}"
    return "🔱 No trending topics found to post."

def pollinations_image(prompt: str, out_path: str) -> bool:
    try:
        # Optimized for Instagram (1024x1024)
        u = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1024&height=1024&nologo=true&seed={random.randint(1,9999)}"
        req = urllib.request.Request(u, headers={"User-Agent": _ua()})
        with urllib.request.urlopen(req, timeout=30) as resp:
            with open(out_path, "wb") as f: f.write(resp.read())
        return True
    except: return False

# --- 🔱 Vision & Analysis Utilities ---
def thumbnail_quality(image_path: str) -> Optional[Dict[str, float]]:
    """🔱 CV2 Analysis to ensure content is top-tier."""
    try:
        import cv2
        import numpy as np
        img = cv2.imread(image_path)
        if img is None: return None
        # Laplacian Variance for Sharpness
        sharp = cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        # Mean Saturation for Colorfulness
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        colorfulness = float(hsv[:, :, 1].mean())
        return {"sharpness": float(sharp), "colorfulness": colorfulness}
    except: return None

async def site_scanner(url: str) -> Dict[str, Any]:
    """🔱 High-level scan using Playwright (Stealth Mode)."""
    out = {"url": url, "meta": {}, "heads": []}
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(user_agent=_ua())
            await page.goto(url, timeout=20000, wait_until="networkidle")
            # Extract H1s and H2s for knowledge graph
            out["heads"] = await page.evaluate("() => Array.from(document.querySelectorAll('h1, h2')).map(h => h.innerText.trim())")
            await browser.close()
    except: pass
    return out

print("🔱 Arkon Infinity Mode (Curiosity Engine) Initialized.")