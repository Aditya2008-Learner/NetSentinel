import asyncio
import time
from playwright.async_api import async_playwright

async def run_test():
    url = "https://net-sentinel-zeta.vercel.app/dashboard?demo=network_monitor"
    console_errors = []
    page_errors = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        async def on_page_error(err):
            page_errors.append(str(err))
        async def on_console(msg):
            if msg.type == "error":
                console_errors.append(f"[{msg.type}] {msg.text}")

        page.on("pageerror", on_page_error)
        page.on("console", on_console)

        print(f"Navigating to {url}...", flush=True)
        await page.goto(url, wait_until="networkidle")

        await asyncio.sleep(3)

        demo_defined = await page.evaluate("() => typeof window.NetSentinelDemo !== 'undefined'")
        demo_status = await page.evaluate("""() => {
            const d = window.NetSentinelDemo;
            if (!d) return null;
            return d.status || d?.getState?.()?.status || (d.currentFeature ? 'ACTIVE' : 'INITIALIZING');
        }""")

        banner_visible = await page.evaluate("""() => {
            const el = document.getElementById('persistent-demo-banner');
            if (!el) return false;
            const style = window.getComputedStyle(el);
            return !el.classList.contains('hidden') && style.display !== 'none' && style.visibility !== 'hidden';
        }""")

        overview_info = await page.evaluate("""() => {
            const el = document.getElementById('overview-view');
            if (!el) return { found: false };
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return {
                found: true,
                display: style.display,
                opacity: style.opacity,
                height: rect.height,
                visible: style.display !== 'none' && parseFloat(style.opacity) > 0 && rect.height > 100
            };
        }""")

        print(f"window.NetSentinelDemo defined: {demo_defined}", flush=True)
        print(f"Demo status: {demo_status}", flush=True)
        print(f"Persistent demo banner visible: {banner_visible}", flush=True)
        print(f"#overview-view checks: {overview_info}", flush=True)
        print(f"Page errors so far: {len(page_errors)} -> {page_errors}", flush=True)
        print(f"Console errors so far: {len(console_errors)} -> {console_errors}", flush=True)

        print("Switching to soc-alerts-view...", flush=True)
        await page.evaluate("""() => {
            const btn = document.querySelector('.nav-item[data-target="soc-alerts-view"]');
            if (btn) { btn.click(); return 'clicked nav item'; }
            const link = document.querySelector('a[href*="soc-alerts"], a[aria-label*="SOC Alerts"]');
            if (link) { link.click(); return 'clicked link'; }
            if (typeof window.switchView === 'function') { window.switchView('soc-alerts-view'); return 'switchView'; }
            return 'not found';
        }""")
        await asyncio.sleep(1.5)

        triage_btn = page.locator(".demo-triage-alert-btn")
        count = await triage_btn.count()
        print(f".demo-triage-alert-btn count: {count}", flush=True)

        triage_clicked = False
        if count > 0:
            await triage_btn.first.click()
            triage_clicked = True
            await asyncio.sleep(1)
        else:
            alerts = await page.evaluate("""() => Array.from(document.querySelectorAll('#soc-alerts-tbody tr')).map(r => r.innerHTML.length > 0).length""")
            print(f"Alert rows found: {alerts}", flush=True)

        await browser.close()

        print("\n--- FINAL SUMMARY ---", flush=True)
        print(f"window.NetSentinelDemo defined: {demo_defined}", flush=True)
        print(f"Demo status: {demo_status}", flush=True)
        print(f"Banner visible: {banner_visible}", flush=True)
        print(f"#overview-view visible: {overview_info.get('visible', False)}", flush=True)
        print(f"Triage button clicked: {triage_clicked}", flush=True)
        print(f"Total Page Errors: {len(page_errors)} ({page_errors})", flush=True)
        print(f"Total Console Errors: {len(console_errors)} ({console_errors})", flush=True)

if __name__ == "__main__":
    asyncio.run(run_test())
