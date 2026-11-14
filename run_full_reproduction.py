import asyncio
import os
from playwright.async_api import async_playwright

async def run():
    os.makedirs("tests/screenshots", exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: console_logs.append(f"[ERROR] {err}"))

        print("1. Opening dashboard...")
        await page.goto("https://net-sentinel-zeta.vercel.app/dashboard", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        await page.screenshot(path="tests/screenshots/step1_initial_dashboard.png")

        # Record initial DOM state
        init_state = await page.evaluate('''() => {
            const active = document.querySelector('.view-panel.active');
            const wrapper = document.getElementById('views-wrapper');
            const main = document.querySelector('main');
            const appContainer = document.getElementById('app-container');
            return {
                activePanelId: active ? active.id : null,
                activeComputedDisplay: active ? getComputedStyle(active).display : null,
                activeComputedOpacity: active ? getComputedStyle(active).opacity : null,
                activeInlineDisplay: active ? active.style.display : null,
                activeInlineOpacity: active ? active.style.opacity : null,
                wrapperComputedBg: wrapper ? getComputedStyle(wrapper).backgroundColor : null,
                wrapperComputedDisplay: wrapper ? getComputedStyle(wrapper).display : null,
                mainComputedBg: main ? getComputedStyle(main).backgroundColor : null,
                appContainerBg: appContainer ? getComputedStyle(appContainer).backgroundColor : null,
                bodyBg: getComputedStyle(document.body).backgroundColor
            };
        }''')
        print(f"Initial DOM state: {init_state}")

        # Helper to get full state
        async def inspect_ui(label):
            return await page.evaluate('''(lbl) => {
                const active = document.querySelector('.view-panel.active');
                const wrapper = document.getElementById('views-wrapper');
                const toaster = document.getElementById('sileo-toaster');
                const toasts = Array.from(document.querySelectorAll('.sileo-toast')).map(t => {
                    const title = t.querySelector('.sileo-title');
                    const desc = t.querySelector('.sileo-description');
                    return {
                        id: t.dataset.sileoId,
                        classes: t.className,
                        title: title ? title.textContent.trim() : null,
                        desc: desc ? desc.textContent.trim() : null,
                        fullText: t.innerText.trim().replace(/\\n/g, ' ')
                    };
                });
                const panels = Array.from(document.querySelectorAll('.view-panel')).map(p => ({
                    id: p.id,
                    active: p.classList.contains('active'),
                    inlineDisplay: p.style.display,
                    inlineOpacity: p.style.opacity,
                    computedDisplay: getComputedStyle(p).display,
                    computedOpacity: getComputedStyle(p).opacity
                }));
                return {
                    label: lbl,
                    activeId: active ? active.id : null,
                    wrapperBg: wrapper ? getComputedStyle(wrapper).backgroundColor : null,
                    panels: panels,
                    toastsCount: toasts.length,
                    toasts: toasts
                };
            }''', label)

        # 4a. Click #top-nav-demo-toggle-btn
        print("\n4a. Clicking #top-nav-demo-toggle-btn...")
        await page.click("#top-nav-demo-toggle-btn")
        await page.wait_for_timeout(1000)
        await page.screenshot(path="tests/screenshots/step2_top_nav_demo_clicked.png")
        state_top_nav = await inspect_ui("top-nav-demo-toggle-btn")
        print(f"After top-nav-demo-toggle-btn:")
        print(f"  Active ID: {state_top_nav['activeId']}")
        print(f"  Panels: {state_top_nav['panels'][:3]}")
        print(f"  Toasts count: {state_top_nav['toastsCount']}, Toasts: {state_top_nav['toasts']}")

        # Clear demo state in sessionStorage and reload cleanly
        await page.evaluate('() => { sessionStorage.clear(); }')
        await page.goto("https://net-sentinel-zeta.vercel.app/dashboard", wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)

        # 4b. Click #overview-try-demo-btn
        print("\n4b. Clicking #overview-try-demo-btn...")
        await page.click("#overview-try-demo-btn")
        await page.wait_for_timeout(1000)
        await page.screenshot(path="tests/screenshots/step3_overview_try_demo_clicked.png")
        state_overview = await inspect_ui("overview-try-demo-btn")
        print(f"After overview-try-demo-btn:")
        print(f"  Active ID: {state_overview['activeId']}")
        print(f"  Panels: {state_overview['panels'][:3]}")
        print(f"  Toasts count: {state_overview['toastsCount']}, Toasts: {state_overview['toasts']}")

        # Clear demo state and reload cleanly
        await page.evaluate('() => { sessionStorage.clear(); }')
        await page.goto("https://net-sentinel-zeta.vercel.app/dashboard", wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)

        # 4c. Switch to network-view and click #network-try-demo-btn
        print("\n4c. Switching to network-view...")
        await page.click('.nav-item[data-target="network-view"]')
        await page.wait_for_timeout(500)
        print("Clicking #network-try-demo-btn...")
        await page.click("#network-try-demo-btn")
        
        # Monitor repeatedly over 3 seconds
        for s in [0.5, 1.5, 3.0]:
            await page.wait_for_timeout(1000 if s > 0.5 else 500)
            st = await inspect_ui(f"network-try-demo-btn at {s}s")
            print(f"At {s}s: active={st['activeId']}, toastsCount={st['toastsCount']}")
            if st['toasts']:
                print(f"   Last toast: {st['toasts'][-1]['fullText']}")
        
        await page.screenshot(path="tests/screenshots/step4_network_try_demo_clicked.png")

        # Clear demo state and reload cleanly
        await page.evaluate('() => { sessionStorage.clear(); }')
        await page.goto("https://net-sentinel-zeta.vercel.app/dashboard", wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)

        # 4d. Switch to live-collector-view and click #live-collector-try-demo-btn
        print("\n4d. Switching to live-collector-view...")
        await page.click('.nav-item[data-target="live-collector-view"]')
        await page.wait_for_timeout(500)
        print("Clicking #live-collector-try-demo-btn...")
        await page.click("#live-collector-try-demo-btn")
        
        for s in [0.5, 1.5, 3.0]:
            await page.wait_for_timeout(1000 if s > 0.5 else 500)
            st = await inspect_ui(f"live-collector-try-demo-btn at {s}s")
            print(f"At {s}s: active={st['activeId']}, toastsCount={st['toastsCount']}")
            if st['toasts']:
                print(f"   Last toast: {st['toasts'][-1]['fullText']}")
                
        await page.screenshot(path="tests/screenshots/step5_live_collector_try_demo_clicked.png")

        # 4e. Navigating from landing page with ?demo=csv_analysis
        print("\n4e. Navigating with ?demo=csv_analysis...")
        await page.evaluate('() => { sessionStorage.clear(); }')
        await page.goto("https://net-sentinel-zeta.vercel.app/dashboard?demo=csv_analysis", wait_until="domcontentloaded")
        for s in [0.5, 1.5, 3.0]:
            await page.wait_for_timeout(1000 if s > 0.5 else 500)
            st = await inspect_ui(f"?demo=csv_analysis at {s}s")
            print(f"At {s}s: active={st['activeId']}, toastsCount={st['toastsCount']}")
            if st['toasts']:
                print(f"   Toasts sample: {[t['fullText'] for t in st['toasts'][:3]]}")

        await page.screenshot(path="tests/screenshots/step6_query_param_demo_csv.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
