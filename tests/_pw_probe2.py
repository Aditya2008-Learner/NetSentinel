import asyncio
from playwright.async_api import async_playwright

def log(m):
    print(m, flush=True)

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page.on("pageerror", lambda e: log("PAGEERROR " + str(e)[:600]))
        page.on("console", lambda m: log(f"CON[{m.type}] {m.text[:300]}") if m.type in ("error", "warning") else None)
        resp = []
        page.on("response", lambda r: resp.append((r.status, r.url)) if r.status >= 400 else None)
        await page.goto("http://127.0.0.1:8013/dashboard", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        for s, u in resp:
            log(f"HTTP {s} {u}")
        state = await page.evaluate('''() => ({
            demo: typeof window.NetSentinelDemo,
            sound: typeof window.NetSentinelSound,
            switchView: typeof window.switchView,
            sileo: typeof window.sileo
        })''')
        log("STATE " + str(state))
        await browser.close()

asyncio.run(run())
