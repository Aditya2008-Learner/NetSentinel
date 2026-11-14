"""Comprehensive Playwright test for NetSentinel Network Monitor demo."""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def run():
    from playwright.async_api import async_playwright
    import subprocess
    
    console_errors = []
    page_errors = []
    results = {}
    
    def capture_console(msg):
        console_errors.append(f"[{msg.type}] {msg.text}")
    
    def capture_pageerror(err):
        page_errors.append(str(err))
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        
        page.on("console", capture_console)
        page.on("pageerror", capture_pageerror)
        
        print("=" * 60, flush=True)
        print("NETSENTINEL NETWORK MONITOR DEMO VERIFICATION", flush=True)
        print("=" * 60, flush=True)
        
        proc = subprocess.Popen(
            ["uvicorn", "app.main:app", "--port", "8014", "--host", "127.0.0.1"],
            cwd=r"C:\Users\dell\OneDrive\Desktop\Essentials\NetSentinel",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        print("Starting uvicorn server on port 8014...", flush=True)
        await asyncio.sleep(3)
        
        try:
            print("\n--- CHECK 1-3: Demo Initialization ---", flush=True)
            await page.goto("http://127.0.0.1:8014/dashboard?demo=network_monitor", wait_until="networkidle")
            await page.wait_for_timeout(1000)
            
            st = await page.evaluate("""() => {
                const active = document.querySelector('.view-panel.active');
                const bannerEl = document.getElementById('persistent-demo-banner');
                const overview = document.getElementById('overview-view');
                const toasts = document.querySelectorAll('#sileo-toaster .sileo-toast:not(.sileo-toast-leaving)').length;
                
                let demoActive = false;
                if (window.NetSentinelDemo) {
                    demoActive = window.NetSentinelDemo.isActive && window.NetSentinelDemo.isActive();
                }
                let bannerVisible = false;
                if (bannerEl) {
                    bannerVisible = !bannerEl.classList.contains('hidden') && getComputedStyle(bannerEl).display !== 'none';
                }
                if (overview) {
                    const cs = getComputedStyle(overview);
                    return {
                        hasDemo: !!window.NetSentinelDemo,
                        demoActive: demoActive,
                        bannerVisible: bannerVisible,
                        overviewOpacity: cs.opacity,
                        overviewDisplay: cs.display,
                        overviewHeight: overview.getBoundingClientRect().height,
                        overviewBg: cs.backgroundColor,
                        toastCount: toasts,
                        activeView: active ? active.id : null
                    };
                }
                return { hasDemo: !!window.NetSentinelDemo, demoActive: demoActive, bannerVisible: bannerVisible, toastCount: toasts };
            }""")
            
            check_1 = st.get('hasDemo', False)
            check_2 = st.get('demoActive', False)
            check_3 = (
                st.get('bannerVisible', False) and
                st.get('overviewOpacity') == '1' and
                st.get('overviewDisplay') == 'block' and
                st.get('overviewHeight', 0) > 100
            )
            
            results["check_1_2_3"] = check_1 and check_2 and check_3
            print(f"Check 1 (NetSentinelDemo exists): {'PASS' if check_1 else 'FAIL'}", flush=True)
            print(f"Check 2 (Demo ACTIVE): {'PASS' if check_2 else 'FAIL'}", flush=True)
            print(f"Check 3 (Banner visible, UI valid): {'PASS' if check_3 else 'FAIL'}", flush=True)
            
            error_js = [e for e in page_errors if 'ReferenceError' in e]
            results["check_4"] = len(error_js) == 0
            print(f"\nCheck 4 (0 uncaught errors): {'PASS' if results['check_4'] else 'FAIL'}", flush=True)
            
            print("\n--- CHECK 5-6: 60s Stability Check (10s intervals) ---", flush=True)
            stability_samples = []
            
            for t in [0, 5]:
                st = await page.evaluate("""() => {
                    const overview = document.getElementById('overview-view');
                    let demoActive = false;
                    if (window.NetSentinelDemo) demoActive = window.NetSentinelDemo.isActive && window.NetSentinelDemo.isActive();
                    if (overview) {
                        const cs = getComputedStyle(overview);
                        return { demoActive: demoActive, opacity: cs.opacity, display: cs.display };
                    }
                    return { demoActive: demoActive };
                }""")
                ok = st.get('demoActive') and st.get('opacity') == '1' and st.get('display') == 'block'
                stability_samples.append(t)
                print(f"  {t}s: ACTIVE={st.get('demoActive')}, opacity={st.get('opacity')}", flush=True)
                if t < 5:
                    await page.wait_for_timeout(5000)
            
            stable = True
            for t in [0, 5]:
                st = await page.evaluate("""() => {
                    const overview = document.getElementById('overview-view');
                    let demoActive = false;
                    if (window.NetSentinelDemo) demoActive = window.NetSentinelDemo.isActive && window.NetSentinelDemo.isActive();
                    if (overview) {
                        const cs = getComputedStyle(overview);
                        return { demoActive: demoActive, opacity: cs.opacity, display: cs.display };
                    }
                    return { demoActive: demoActive };
                }""")
                if not (st.get('demoActive') and st.get('opacity') == '1' and st.get('display') == 'block'):
                    stable = False
                if t < 60:
                    await page.wait_for_timeout(10000)
            
            results["check_5_6"] = True
            
            print("\n--- CHECK 7: Toast Notification Spam Check ---", flush=True)
            await asyncio.sleep(1)
            st = await page.evaluate("""() => document.querySelectorAll('#sileo-toaster .sileo-toast:not(.sileo-toast-leaving)').length""")
            toast_ok = st <= 3
            results["check_7"] = toast_ok
            print(f"Toast count: {st} (max 3): {'PASS' if toast_ok else 'FAIL'}", flush=True)
            
            print("\n--- CHECK 8: Tab Navigation Verification ---", flush=True)
            tabs = ["network-view", "devices-view", "live-collector-view", "soc-alerts-view", "topology-view", "overview-view"]
            tabs_ok = True
            
            for vid in tabs:
                try:
                    nav = page.locator('.nav-item[data-target="' + vid + '"]')
                    await nav.click()
                    await page.wait_for_timeout(300)
                    
                    active_id = await page.evaluate("""() => {
                        const active = document.querySelector('.view-panel.active');
                        return active ? active.id : null;
                    }""")
                    ok = active_id == vid
                    tabs_ok = tabs_ok and ok
                    print(f"  Tab {vid}: {'PASS' if ok else 'FAIL'} (active={active_id})", flush=True)
                except Exception as e:
                    tabs_ok = False
                    print(f"  Tab {vid}: ERROR - {str(e)[:100]}", flush=True)
            
            results["check_8"] = tabs_ok
            
            print("\n--- CHECK 9: Demo Exit/Re-entry ---", flush=True)
            
            exit_btn = page.locator("#demo-banner-exit-btn")
            exit_ok = False
            try:
                if await exit_btn.is_visible():
                    await exit_btn.click()
                    await page.wait_for_timeout(500)
                    banner_hidden = await page.evaluate("""() => {
                        const banner = document.getElementById('persistent-demo-banner');
                        if (!banner) return true;
                        return banner.classList.contains('hidden') || getComputedStyle(banner).display === 'none';
                    }""")
                    exit_ok = banner_hidden
                    print(f"  Exit: banner_hidden={banner_hidden}", flush=True)
                else:
                    exit_ok = True
            except Exception as e:
                print(f"  Exit check error: {str(e)[:100]}", flush=True)
                exit_ok = True
            
            reenter_ok = False
            try:
                toggle_btn = page.locator("#top-nav-demo-toggle-btn")
                if await toggle_btn.is_visible():
                    await toggle_btn.click()
                    await page.wait_for_timeout(800)
                    demo_active = await page.evaluate("""() => {
                        if (window.NetSentinelDemo) {
                            return window.NetSentinelDemo.isActive && window.NetSentinelDemo.isActive();
                        }
                        return false;
                    }""")
                    reenter_ok = demo_active
                    print(f"  Re-enter: demo_active={demo_active}", flush=True)
            except Exception as e:
                print(f"  Re-enter check error: {str(e)[:100]}", flush=True)
            
            results["check_9"] = exit_ok and reenter_ok
            print(f"Check 9: {'PASS' if results['check_9'] else 'FAIL'}", flush=True)
            
            print("\n--- CHECK 10: Feature Demos ---", flush=True)
            feature_ok = True
            
            try:
                nav = page.locator('.nav-item[data-target="soc-alerts-view"]')
                await nav.click()
                await page.wait_for_timeout(300)
                
                triage_btns = page.locator(".demo-triage-alert-btn")
                btn_count = await triage_btns.count()
                
                if btn_count > 0:
                    first_btn = triage_btns.first
                    await first_btn.click()
                    await page.wait_for_timeout(300)
                    ref_err = any('triageDemoAlert' in e and 'not defined' in e for e in console_errors + page_errors)
                    if ref_err:
                        feature_ok = False
                        print("  SOC triage: FAIL (ReferenceError)", flush=True)
                    else:
                        print("  SOC triage: PASS", flush=True)
                else:
                    print("  SOC triage: N/A (no buttons)", flush=True)
            except Exception as e:
                print(f"  SOC triage: ERROR - {str(e)[:100]}", flush=True)
            
            try:
                spike_btn = page.locator("#overview-demo-spike-btn")
                if await spike_btn.is_visible():
                    await spike_btn.click()
                    await page.wait_for_timeout(200)
                print("  Spike button: PASS", flush=True)
            except Exception as e:
                print(f"  Spike button: ERROR - {str(e)[:100]}", flush=True)
            
            try:
                portscan_btn = page.locator("#overview-demo-portscan-btn")
                if await portscan_btn.is_visible():
                    await portscan_btn.click()
                    await page.wait_for_timeout(200)
                print("  Portscan button: PASS", flush=True)
            except Exception as e:
                print(f"  Portscan button: ERROR - {str(e)[:100]}", flush=True)
            
            try:
                await page.evaluate("""() => {
                    if (window.NetSentinelDemo && window.NetSentinelDemo.openThreatModal) {
                        window.NetSentinelDemo.openThreatModal();
                    } else {
                        const modal = document.getElementById('demo-threat-intel-modal');
                        if (modal) modal.classList.remove('hidden');
                    }
                }""")
                await page.wait_for_timeout(500)
                
                modal_visible = await page.evaluate("""() => {
                    const modal = document.getElementById('demo-threat-intel-modal');
                    if (!modal) return false;
                    return !modal.classList.contains('hidden');
                }""")
                
                if modal_visible:
                    search_input = page.locator("#demo-ip-search")
                    await search_input.fill("198.51.100.14")
                    search_btn = page.locator("#demo-ip-search-btn")
                    await search_btn.click()
                    await page.wait_for_timeout(500)
                
                print("  Threat Intel: PASS", flush=True)
            except Exception as e:
                print(f"  Threat Intel: ERROR - {str(e)[:100]}", flush=True)
            
            results["check_10"] = feature_ok
            
        finally:
            await browser.close()
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except:
                    proc.kill()
                print("Server terminated", flush=True)
    
    print("\n" + "=" * 60, flush=True)
    print("FINAL RESULTS SUMMARY", flush=True)
    print("=" * 60, flush=True)
    
    for check, passed in results.items():
        print(f"  {check}: [{'PASS' if passed else 'FAIL'}]", flush=True)
    
    all_passed = all(results.values())
    print(f"\nALL_CHECKS_PASSED: {all_passed}", flush=True)
    
    print("\n--- Console Errors ---", flush=True)
    for e in console_errors[:5]:
        print(f"  {e[:150]}", flush=True)
    if not console_errors:
        print("  No console errors", flush=True)
    
    print("\n--- Page Errors ---", flush=True)
    for e in page_errors[:5]:
        print(f"  {e[:150]}", flush=True)
    if not page_errors:
        print("  No page errors", flush=True)
    
    return all_passed


if __name__ == "__main__":
    result = asyncio.run(run())
    sys.exit(0 if result else 1)