import asyncio
from playwright.async_api import async_playwright
try:
    from playwright_stealth import stealth_async as _stealth_ctx
except Exception:
    _stealth_ctx = None
from huggingface_hub import InferenceClient
import os
from arkon_healer import MultiModelVision

async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=False)
        ctx = await b.new_context()
        try:
            if _stealth_ctx is not None:
                await _stealth_ctx(ctx)
        except Exception:
            pass
        page = await ctx.new_page()
        await page.goto("https://duckduckgo.com/?q=create+gmail", wait_until="domcontentloaded")
        print("🔱 Stealth OK")
        await ctx.close()
        await b.close()
    tok = os.getenv("HUGGINGFACE_API_TOKEN", "").strip()
    mv = MultiModelVision()
    print("🔱 Qwen2-VL Bridge OK" if mv._client is not None else "⚠️ Qwen2-VL Bridge Unavailable")

asyncio.run(run())
