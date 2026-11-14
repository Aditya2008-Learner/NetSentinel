import asyncio
import json
from playwright.async_api import async_playwright

def log(msg):
    print(msg, flush=True)

async def inspect(page):
    return await page.evaluate('''() => {
        const active = document.querySelector('.view-panel.active');
        const banner = document.getElementById('persistent-demo-banner');
        const toasts = Array.from(document.querySelectorAll('#sileo-toaster .sileo-toast:not(.sileo-toast-leaving)')).map(t => t.innerText.trim().replace(/\\n/g, ' ').slice(0, 90));
        return {
            activeId: active ? active.id : null,
            opacity: active ? getComputedStyle(active).opacity : null,
            display: active ? getComputedStyle(active).display : null,
            height: active ? active.getBoundingClientRect().height : 0,
            textLen: active ? active.innerText.trim().length : 0,
            bannerHidden: banner ? banner.classList.contains('hidden') : null,
            bannerVisible: banner ? getComputedStyle(banner).display !== 'none' && !banner.classList.contains('hidden') : null,
            toastCount: toasts.length,
            toasts: toasts,
            demoActive: !!(window.NetSentinelDemo && window.NetSentinelDemo.isActive && window.NetSentinelDemo.isActive())
        };
    }''')

async def run():
    console_errors, page_errors = [], []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        page.on("console", lambda m: console_errors.append(f"[{m.type}] {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: page_errors.append(str(e)))

        await page.goto("http://127.0.0.1:8013/dashboard", wait_until="networkidle")
        await page.wait_for_timeout(800)

        # Enter demo via top nav
        await page.locator("#top-nav-demo-toggle-btn").click()
        await page.wait_for_timeout(1200)
        st = await inspect(page)
        log(f"ENTER demoActive={st['demoActive']} bannerHidden={st['bannerHidden']} active={st['activeId']} op={st['opacity']} disp={st['display']} h={st['height']} textLen={st['textLen']} toasts={st['toastCount']} {st['toasts']}")

        # Exit via banner button (force if covered)
        btn = page.locator("#demo-banner-exit-btn")
        box = await btn.bounding_box()
        log(f"EXIT_BTN box={box} visible={await btn.is_visible()}")
        await btn.click(force=True)
        await page.wait_for_timeout(1000)
        st = await inspect(page)
        log(f"EXIT demoActive={st['demoActive']} bannerHidden={st['bannerHidden']} active={st['activeId']} op={st['opacity']} disp={st['display']} h={st['height']} textLen={st['textLen']} toasts={st['toastCount']} {st['toasts']}")

        # Re-enter
        await page.locator("#top-nav-demo-toggle-btn").click()
        await page.wait_for_timeout(1200)
        st = await inspect(page)
        log(f"REENTER demoActive={st['demoActive']} bannerHidden={st['bannerHidden']} active={st['activeId']} op={st['opacity']} disp={st['display']} h={st['height']} textLen={st['textLen']} toasts={st['toastCount']} {st['toasts']}")

        # Switch tabs while in demo
        for vid in ["network-view", "devices-view", "topology-view"]:
            await page.locator(f'.nav-item[data-target="{vid}"]').click()
            await page.wait_for_timeout(600)
            st = await inspect(page)
            log(f"DEMO_TAB {vid}: active={st['activeId']} op={st['opacity']} disp={st['display']} h={st['height']} textLen={st['textLen']} bannerHidden={st['bannerHidden']} toasts={st['toastCount']}")

        log(f"PAGE_ERRORS {len(page_errors)}")
        for e in page_errors[:10]:
            log("  " + e[:400])
        log(f"CONSOLE_ERRORS {len(console_errors)}")
        for c in console_errors[:20]:
            log("  " + c[:400])
        await browser.close()

asyncio.run(run())
