import asyncio
from playwright.async_api import async_playwright

def log(m):
    print(m, flush=True)

async def run():
    errs = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page.on("pageerror", lambda e: errs.append("PAGE " + str(e)))
        page.on("console", lambda m: errs.append(f"CON[{m.type}] {m.text}") if m.type == "error" else None)
        await page.goto("http://127.0.0.1:8013/dashboard", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        info = await page.evaluate('''() => {
            const b = document.getElementById('top-nav-demo-toggle-btn');
            const listeners = typeof getEventListeners === 'function' ? Object.keys(getEventListeners(b)) : 'n/a';
            return {
                hasDemo: typeof window.NetSentinelDemo,
                demoKeys: window.NetSentinelDemo ? Object.keys(window.NetSentinelDemo) : null,
                btnText: b ? b.innerText : null,
                btnDisabled: b ? b.disabled : null,
                sileo: typeof window.sileo,
                listeners
            };
        }''')
        log("INFO " + str(info))
        clicked = await page.evaluate('''() => {
            const b = document.getElementById('top-nav-demo-toggle-btn');
            b.click();
            return {
                active: window.NetSentinelDemo.isDemoMode(),
                status: window.NetSentinelDemo.getStatus(),
                bannerHidden: document.getElementById('persistent-demo-banner').classList.contains('hidden'),
                btnText: b.innerText.trim()
            };
        }''')
        log("AFTER_JS_CLICK " + str(clicked))
        await page.wait_for_timeout(1500)
        after = await page.evaluate('''() => ({
            active: window.NetSentinelDemo.isDemoMode(),
            status: window.NetSentinelDemo.getStatus(),
            bannerHidden: document.getElementById('persistent-demo-banner').classList.contains('hidden'),
            toastCount: document.querySelectorAll('#sileo-toaster .sileo-toast').length,
            toastTexts: Array.from(document.querySelectorAll('#sileo-toaster .sileo-toast')).map(t => t.innerText.trim().slice(0,80))
        })''')
        log("AFTER_WAIT " + str(after))
        for e in errs[:15]:
            log("ERR " + e[:300])
        await browser.close()

asyncio.run(run())
