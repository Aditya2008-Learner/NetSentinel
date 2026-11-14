import asyncio
import json
import sys
from playwright.async_api import async_playwright

FEATURES = [
    ("Overview", "overview-view", "#overview-try-demo-btn"),
    ("Network/CSV", "network-view", "#network-try-demo-btn"),
    ("Devices", "devices-view", "#devices-try-demo-btn"),
    ("Flows", "live-collector-view", "#live-collector-try-demo-btn"),
    ("SOC Alerts", "soc-alerts-view", "#soc-alerts-try-demo-btn"),
    ("Topology", "topology-view", "#topology-try-demo-btn"),
    ("Investigations", "investigations-view", "#investigations-try-demo-btn"),
    ("Stego", "stego-view", "#stego-try-demo-btn"),
    ("Forensics", "forensics-view", "#forensics-try-demo-btn"),
    ("Integrity", "integrity-view", "#integrity-try-demo-btn"),
    ("Reports", "reports-view", "#reports-try-demo-btn"),
    ("Settings", "settings-view", "#settings-try-demo-btn"),
]

results = []

def log(msg):
    print(msg, flush=True)

async def inspect(page):
    return await page.evaluate('''() => {
        const active = document.querySelector('.view-panel.active');
        const wrapper = document.getElementById('views-wrapper');
        const banner = document.getElementById('persistent-demo-banner');
        const toasts = Array.from(document.querySelectorAll('#sileo-toaster .sileo-toast:not(.sileo-toast-leaving)')).map(t => ({
            id: t.id,
            text: t.innerText.trim().replace(/\\n/g, ' ')
        }));
        const cs = wrapper ? getComputedStyle(wrapper) : null;
        return {
            activeId: active ? active.id : null,
            opacity: active ? getComputedStyle(active).opacity : null,
            display: active ? getComputedStyle(active).display : null,
            inlineOpacity: active ? active.style.opacity : null,
            inlineDisplay: active ? active.style.display : null,
            wrapperDisplay: cs ? cs.display : null,
            wrapperVisibility: cs ? cs.visibility : null,
            wrapperOpacity: cs ? cs.opacity : null,
            wrapperHeight: wrapper ? wrapper.getBoundingClientRect().height : 0,
            activeHeight: active ? active.getBoundingClientRect().height : 0,
            activeTextLen: active ? active.innerText.trim().length : 0,
            bannerHidden: banner ? banner.classList.contains('hidden') : null,
            toastCount: toasts.length,
            toasts: toasts
        };
    }''')

async def run():
    console_errors = []
    page_errors = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        page.on("console", lambda m: console_errors.append(f"[{m.type}] {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: page_errors.append(str(e)))

        log("NAV dashboard")
        await page.goto("http://127.0.0.1:8013/dashboard", wait_until="networkidle")
        await page.wait_for_timeout(800)

        for label, view_id, btn in FEATURES:
            await page.evaluate("() => sessionStorage.clear()")
            await page.goto("http://127.0.0.1:8013/dashboard", wait_until="domcontentloaded")
            await page.wait_for_timeout(600)
            nav = page.locator(f'.nav-item[data-target="{view_id}"]')
            await nav.click()
            await page.wait_for_timeout(400)
            before = await inspect(page)
            await page.locator(btn).click()
            await page.wait_for_timeout(1200)
            st = await inspect(page)
            ok_panel = st["activeId"] == view_id and st["opacity"] == "1" and st["display"] == "block"
            visible = st["wrapperDisplay"] != "none" and st["activeHeight"] > 20 and st["activeTextLen"] > 0
            ok_toast = st["toastCount"] <= 1
            row = {
                "feature": label,
                "ok_panel": ok_panel,
                "visible": visible,
                "ok_toast": ok_toast,
                "activeId": st["activeId"],
                "opacity": st["opacity"],
                "display": st["display"],
                "activeHeight": st["activeHeight"],
                "activeTextLen": st["activeTextLen"],
                "toastCount": st["toastCount"],
                "toasts": [t["text"][:80] for t in st["toasts"]],
            }
            results.append(row)
            log(f"FEATURE {label}: panel={ok_panel} visible={visible} toast<={1}:{ok_toast} count={st['toastCount']} id={st['activeId']} op={st['opacity']} disp={st['display']} h={st['activeHeight']}")

        # Wait 5s on Network Security demo
        await page.evaluate("() => sessionStorage.clear()")
        await page.goto("http://127.0.0.1:8013/dashboard", wait_until="domcontentloaded")
        await page.wait_for_timeout(600)
        await page.locator('.nav-item[data-target="network-view"]').click()
        await page.wait_for_timeout(300)
        await page.locator("#network-try-demo-btn").click()
        await page.wait_for_timeout(800)
        t0 = (await inspect(page))["toastCount"]
        samples = [t0]
        for _ in range(5):
            await page.wait_for_timeout(1000)
            samples.append((await inspect(page))["toastCount"])
        log(f"NETWORK_5S toast counts over 5s: {samples}")

        # Switch multiple tabs
        tabs = ["overview-view", "devices-view", "soc-alerts-view", "reports-view", "settings-view"]
        tab_ok = True
        for vid in tabs:
            await page.locator(f'.nav-item[data-target="{vid}"]').click()
            await page.wait_for_timeout(500)
            st = await inspect(page)
            good = st["activeId"] == vid and st["opacity"] == "1" and st["display"] == "block" and st["activeHeight"] > 20
            tab_ok = tab_ok and good
            log(f"TAB {vid}: ok={good} op={st['opacity']} disp={st['display']} h={st['activeHeight']} toasts={st['toastCount']}")
        log(f"TABS_ALL_OK {tab_ok}")

        # Dedup
        dedup = await page.evaluate('''() => {
            const before = document.querySelectorAll('#sileo-toaster .sileo-toast:not(.sileo-toast-leaving)').length;
            for (let i = 0; i < 5; i++) window.sileo.success("Test deduplication");
            const afterNodes = Array.from(document.querySelectorAll('#sileo-toaster .sileo-toast:not(.sileo-toast-leaving)'));
            const matches = afterNodes.filter(t => t.innerText.includes("Test deduplication"));
            return { before, after: afterNodes.length, matchCount: matches.length };
        }''')
        log(f"DEDUP {json.dumps(dedup)}")

        # Exit demo
        await page.locator("#demo-banner-exit-btn").click()
        await page.wait_for_timeout(800)
        exit_st = await inspect(page)
        log(f"EXIT bannerHidden={exit_st['bannerHidden']} active={exit_st['activeId']} op={exit_st['opacity']} h={exit_st['activeHeight']} textLen={exit_st['activeTextLen']}")

        # Re-enter
        await page.locator("#top-nav-demo-toggle-btn").click()
        await page.wait_for_timeout(1000)
        re_st = await inspect(page)
        log(f"REENTER bannerHidden={re_st['bannerHidden']} active={re_st['activeId']} op={re_st['opacity']} disp={re_st['display']} toastCount={re_st['toastCount']} h={re_st['activeHeight']}")

        log(f"PAGE_ERRORS {len(page_errors)}")
        for e in page_errors[:10]:
            log(f"  PAGEERROR {e[:300]}")
        errs = [c for c in console_errors if c.startswith("[error]")]
        log(f"CONSOLE_ERRORS {len(errs)}")
        for c in errs[:15]:
            log(f"  {c[:300]}")
        warns = [c for c in console_errors if c.startswith("[warning]")]
        log(f"CONSOLE_WARNINGS {len(warns)}")
        for c in warns[:8]:
            log(f"  {c[:200]}")

        fails = [r for r in results if not (r["ok_panel"] and r["visible"] and r["ok_toast"])]
        log(f"SUMMARY features={len(results)} fails={len(fails)}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
