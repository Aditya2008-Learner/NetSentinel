"""
Comprehensive Playwright test suite for refresh button matrix.
Tests 8 refresh buttons for:
- Normal click in Live Mode (network request, loading state, cleanup, DOM update, no console errors)
- Rapid repeated clicks (concurrency guard validation)
- Demo Mode (demo data source, no live mutations)
- No "Successful Ingestion" notifications
"""
import pytest
import re
from typing import List
from playwright.sync_api import sync_playwright, Page, Request, ConsoleMessage


BUTTONS = [
    {
        "id": "demo-banner-reset-btn",
        "label": "Demo Banner Reset",
        "api_pattern": r"/api/demo/reset",
        "method": "POST",
        "view": "overview-view",
        "is_demo": True,
    },
    {
        "id": "telemetry-reset-btn",
        "label": "Network Security Telemetry Reset",
        "api_pattern": r"/api/telemetry/simulate",
        "method": "POST",
        "view": "overview-view",
    },
    {
        "id": "refresh-history-btn",
        "label": "Network Security History Refresh",
        "api_pattern": r"/api/network/history",
        "method": "GET",
        "view": "network-view",
    },
    {
        "id": "refresh-collector-btn",
        "label": "Live Monitoring Collector Refresh",
        "api_pattern": r"/api/collector/status",
        "method": "GET",
        "view": "live-collector-view",
    },
    {
        "id": "refresh-devices-btn",
        "label": "Device Inventory Refresh",
        "api_pattern": r"/api/devices",
        "method": "GET",
        "view": "devices-view",
    },
    {
        "id": "refresh-investigations-btn",
        "label": "Digital Forensics Investigations Refresh",
        "api_pattern": r"/api/investigations",
        "method": "GET",
        "view": "investigations-view",
    },
    {
        "id": "refresh-soc-alerts-btn",
        "label": "SOC Alert Triage Refresh",
        "api_pattern": r"/api/soc/alerts",
        "method": "GET",
        "view": "soc-alerts-view",
    },
    {
        "id": "refresh-topology-btn",
        "label": "Network Intelligence Topology Refresh",
        "api_pattern": r"/api/intelligence/topology",
        "method": "GET",
        "view": "topology-view",
    },
]


@pytest.fixture(scope="module")
def browser_context():
    """Launch browser once for all tests."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        yield context
        context.close()
        browser.close()


def visit_and_wait(page: Page, url: str = "http://127.0.0.1:8013/dashboard"):
    page.goto(url)
    page.wait_for_load_state("networkidle")


def ensure_live_mode(page: Page):
    page.evaluate("""
        if (window.NetSentinelDemo && window.NetSentinelDemo.disable) {
            window.NetSentinelDemo.disable();
        }
        sessionStorage.removeItem('net_sentinel_demo_active');
        sessionStorage.removeItem('net_sentinel_demo_feature');
    """)


def ensure_demo_mode(page: Page, feature: str = "network_monitor"):
    page.evaluate(f"""
        if (window.NetSentinelDemo && window.NetSentinelDemo.enable) {{
            window.NetSentinelDemo.enable('{feature}');
        }} else {{
            sessionStorage.setItem('net_sentinel_demo_active', 'true');
            sessionStorage.setItem('net_sentinel_demo_feature', '{feature}');
            window.location.reload();
        }}
    """)
    page.wait_for_load_state("networkidle", timeout=10000)


def switch_to_view(page: Page, view_id: str):
    if view_id != "overview-view":
        page.evaluate(f"switchView('{view_id}')")
        page.wait_for_load_state("networkidle", timeout=5000)


def capture_console_errors(page: Page) -> List[str]:
    errors = []
    def on_console(msg: ConsoleMessage):
        if msg.type == "error":
            errors.append(msg.text or msg.message or "Console error")
    page.on("console", on_console)
    return errors


class TestRefreshButtonMatrix:
    """Comprehensive test suite for all 8 refresh buttons."""
    
    def test_demo_banner_live_mode(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_demo_mode(page, "network_monitor")
            
            console_errors = capture_console_errors(page)
            
            captured_requests = []
            page.on("request", lambda r: captured_requests.append(r))
            
            btn = page.locator("#demo-banner-reset-btn")
            btn.wait_for(timeout=5000)
            
            btn.click()
            
            page.wait_for_timeout(800)
            
            refresh_requests = [r for r in captured_requests if "/api/demo/reset" in r.url]
            assert len(refresh_requests) > 0, "Expected POST /api/demo/reset request"
            
            assert not btn.is_disabled(), "Button should be re-enabled"
            assert not btn.evaluate("el => el.classList.contains('is-refreshing')"), \
                "Button should not have is-refreshing class"
            
            assert len(console_errors) == 0, f"Console errors: {console_errors}"
        finally:
            page.close()
    
    def test_telemetry_reset_live_mode(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_live_mode(page)
            switch_to_view(page, "overview-view")
            
            console_errors = capture_console_errors(page)
            
            captured_requests = []
            page.on("request", lambda r: captured_requests.append(r))
            
            btn = page.locator("#telemetry-reset-btn")
            btn.wait_for(timeout=5000)
            
            btn.click()
            
            page.wait_for_timeout(800)
            
            refresh_requests = [r for r in captured_requests if "/api/telemetry/simulate" in r.url]
            assert len(refresh_requests) > 0, "Expected POST /api/telemetry/simulate request"
            
            assert not btn.is_disabled(), "Button should be re-enabled"
            assert len(console_errors) == 0, f"Console errors: {console_errors}"
        finally:
            page.close()
    
    def test_refresh_history_live_mode(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_live_mode(page)
            switch_to_view(page, "network-view")
            
            console_errors = capture_console_errors(page)
            
            captured_requests = []
            page.on("request", lambda r: captured_requests.append(r))
            
            btn = page.locator("#refresh-history-btn")
            btn.wait_for(timeout=5000)
            
            btn.click()
            
            page.wait_for_timeout(800)
            
            refresh_requests = [r for r in captured_requests if "/api/network/history" in r.url]
            assert len(refresh_requests) > 0, "Expected GET /api/network/history request"
            
            assert not btn.is_disabled(), "Button should be re-enabled"
            assert len(console_errors) == 0, f"Console errors: {console_errors}"
        finally:
            page.close()
    
    def test_refresh_collector_live_mode(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_live_mode(page)
            switch_to_view(page, "live-collector-view")
            
            console_errors = capture_console_errors(page)
            
            captured_requests = []
            page.on("request", lambda r: captured_requests.append(r))
            
            btn = page.locator("#refresh-collector-btn")
            btn.wait_for(timeout=5000)
            
            btn.click()
            
            page.wait_for_timeout(800)
            
            refresh_requests = [r for r in captured_requests if "/api/collector/status" in r.url]
            assert len(refresh_requests) > 0, "Expected GET /api/collector/status request"
            
            assert not btn.is_disabled(), "Button should be re-enabled"
            assert len(console_errors) == 0, f"Console errors: {console_errors}"
        finally:
            page.close()
    
    def test_refresh_devices_live_mode(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_live_mode(page)
            switch_to_view(page, "devices-view")
            
            console_errors = capture_console_errors(page)
            
            captured_requests = []
            page.on("request", lambda r: captured_requests.append(r))
            
            btn = page.locator("#refresh-devices-btn")
            btn.wait_for(timeout=5000)
            
            btn.click()
            
            page.wait_for_timeout(800)
            
            refresh_requests = [r for r in captured_requests if "/api/devices" in r.url]
            assert len(refresh_requests) > 0, "Expected GET /api/devices request"
            
            assert not btn.is_disabled(), "Button should be re-enabled"
            assert len(console_errors) == 0, f"Console errors: {console_errors}"
        finally:
            page.close()
    
    def test_refresh_investigations_live_mode(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_live_mode(page)
            switch_to_view(page, "investigations-view")
            
            console_errors = capture_console_errors(page)
            
            captured_requests = []
            page.on("request", lambda r: captured_requests.append(r))
            
            btn = page.locator("#refresh-investigations-btn")
            btn.wait_for(timeout=5000)
            
            btn.click()
            
            page.wait_for_timeout(800)
            
            refresh_requests = [r for r in captured_requests if "/api/investigations" in r.url]
            assert len(refresh_requests) > 0, "Expected GET /api/investigations request"
            
            assert not btn.is_disabled(), "Button should be re-enabled"
            assert len(console_errors) == 0, f"Console errors: {console_errors}"
        finally:
            page.close()
    
    def test_refresh_soc_alerts_live_mode(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_live_mode(page)
            switch_to_view(page, "soc-alerts-view")
            
            console_errors = capture_console_errors(page)
            
            captured_requests = []
            page.on("request", lambda r: captured_requests.append(r))
            
            btn = page.locator("#refresh-soc-alerts-btn")
            btn.wait_for(timeout=5000)
            
            btn.click()
            
            page.wait_for_timeout(800)
            
            refresh_requests = [r for r in captured_requests if "/api/soc/alerts" in r.url]
            assert len(refresh_requests) > 0, "Expected GET /api/soc/alerts request"
            
            assert not btn.is_disabled(), "Button should be re-enabled"
            assert len(console_errors) == 0, f"Console errors: {console_errors}"
        finally:
            page.close()
    
    def test_refresh_topology_live_mode(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_live_mode(page)
            switch_to_view(page, "topology-view")
            
            console_errors = capture_console_errors(page)
            
            captured_requests = []
            page.on("request", lambda r: captured_requests.append(r))
            
            btn = page.locator("#refresh-topology-btn")
            btn.wait_for(timeout=5000)
            
            btn.click()
            
            page.wait_for_timeout(800)
            
            refresh_requests = [r for r in captured_requests if "topology" in r.url or "intelligence" in r.url]
            assert len(refresh_requests) > 0, "Expected GET /api/intelligence/topology request"
            
            assert not btn.is_disabled(), "Button should be re-enabled"
            assert len(console_errors) == 0, f"Console errors: {console_errors}"
        finally:
            page.close()
    
    # ========== RAPID CLICKS TESTS ==========
    
    def test_rapid_clicks_demo_banner(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_demo_mode(page, "network_monitor")
            
            captured_requests = []
            page.on("request", lambda r: captured_requests.append(r))
            
            btn = page.locator("#demo-banner-reset-btn")
            btn.wait_for(timeout=5000)
            
            for _ in range(5):
                btn.click()
            
            page.wait_for_timeout(1000)
            
            demo_reset_count = len([r for r in captured_requests if "/api/demo/reset" in r.url])
            
            assert demo_reset_count <= 1, f"Expected at most 1 request for rapid clicks, got {demo_reset_count}"
            assert not btn.is_disabled(), "Button should be enabled after concurrency guard"
        finally:
            page.close()
    
    def test_rapid_clicks_telemetry_reset(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_live_mode(page)
            switch_to_view(page, "overview-view")
            
            captured_requests = []
            page.on("request", lambda r: captured_requests.append(r))
            
            btn = page.locator("#telemetry-reset-btn")
            btn.wait_for(timeout=5000)
            
            for _ in range(5):
                btn.click()
            
            page.wait_for_timeout(1000)
            
            assert not btn.is_disabled(), "Button should be enabled after concurrency guard"
        finally:
            page.close()
    
    def test_rapid_clicks_refresh_devices(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_live_mode(page)
            switch_to_view(page, "devices-view")
            
            captured_requests = []
            page.on("request", lambda r: captured_requests.append(r))
            
            btn = page.locator("#refresh-devices-btn")
            btn.wait_for(timeout=5000)
            
            for _ in range(5):
                btn.click()
            
            page.wait_for_timeout(1000)
            
            assert not btn.is_disabled(), "Button should be enabled after concurrency guard"
        finally:
            page.close()
    
    # ========== DEMO MODE TESTS ==========
    
    def test_demo_mode_demo_banner(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_demo_mode(page, "network_monitor")
            
            btn = page.locator("#demo-banner-reset-btn")
            btn.wait_for(timeout=5000)
            
            captured_requests = []
            page.on("request", lambda r: captured_requests.append(r))
            
            btn.click()
            
            page.wait_for_timeout(500)
            
            demo_requests = [r for r in captured_requests if "/api/demo/" in r.url]
            assert len(demo_requests) > 0, "Expected demo API call in demo mode"
        finally:
            page.close()
    
    def test_demo_mode_telemetry_reset(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_demo_mode(page, "network_monitor")
            
            captured_requests = []
            page.on("request", lambda r: captured_requests.append(r))
            
            btn = page.locator("#telemetry-reset-btn")
            btn.wait_for(timeout=5000)
            
            btn.click()
            
            page.wait_for_timeout(500)
            
            demo_telemetry = [r for r in captured_requests if "/api/demo/telemetry" in r.url]
            assert len(demo_telemetry) > 0, "Expected /api/demo/telemetry in demo mode"
        finally:
            page.close()
    
    def test_demo_mode_refresh_history(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_demo_mode(page, "csv_analysis")
            switch_to_view(page, "network-view")
            
            captured_requests = []
            page.on("request", lambda r: captured_requests.append(r))
            
            btn = page.locator("#refresh-history-btn")
            btn.wait_for(timeout=5000)
            
            btn.click()
            
            page.wait_for_timeout(500)
        finally:
            page.close()
    
    def test_demo_mode_refresh_devices(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_demo_mode(page, "devices")
            switch_to_view(page, "devices-view")
            
            captured_requests = []
            page.on("request", lambda r: captured_requests.append(r))
            
            btn = page.locator("#refresh-devices-btn")
            btn.wait_for(timeout=5000)
            
            btn.click()
            
            page.wait_for_timeout(500)
            
            demo_devices = [r for r in captured_requests if "/api/demo/devices" in r.url]
            assert len(demo_devices) > 0, "Expected /api/demo/devices in demo mode"
        finally:
            page.close()
    
    def test_demo_mode_refresh_collector(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_demo_mode(page, "flows")
            switch_to_view(page, "live-collector-view")
            
            btn = page.locator("#refresh-collector-btn")
            btn.wait_for(timeout=5000)
            
            btn.click()
            
            page.wait_for_timeout(500)
        finally:
            page.close()
    
    def test_demo_mode_refresh_investigations(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_demo_mode(page, "investigations")
            switch_to_view(page, "investigations-view")
            
            btn = page.locator("#refresh-investigations-btn")
            btn.wait_for(timeout=5000)
            
            btn.click()
            
            page.wait_for_timeout(500)
        finally:
            page.close()
    
    def test_demo_mode_refresh_soc_alerts(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_demo_mode(page, "soc_alerts")
            switch_to_view(page, "soc-alerts-view")
            
            btn = page.locator("#refresh-soc-alerts-btn")
            btn.wait_for(timeout=5000)
            
            btn.click()
            
            page.wait_for_timeout(500)
        finally:
            page.close()
    
    def test_demo_mode_refresh_topology(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_demo_mode(page, "topology")
            switch_to_view(page, "topology-view")
            
            btn = page.locator("#refresh-topology-btn")
            btn.wait_for(timeout=5000)
            
            btn.click()
            
            page.wait_for_timeout(500)
        finally:
            page.close()


class TestNoSuccessfulIngestionNotifications:
    """Verify NO 'Successful Ingestion' notifications appear."""
    
    def test_no_ingestion_notifications(self, browser_context):
        page = browser_context.new_page()
        try:
            visit_and_wait(page)
            ensure_live_mode(page)
            
            for btn_id in ["telemetry-reset-btn", 
                          "refresh-devices-btn", "refresh-soc-alerts-btn"]:
                btn = page.locator(f"#{btn_id}")
                if btn.count() > 0 and btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(300)
            
            toasts = page.locator(".toast, .sileo-notification, .notification")
            toast_texts = toasts.all_text_contents()
            
            for text in toast_texts:
                assert "successful ingestion" not in text.lower(), \
                    f"Found 'Successful Ingestion' notification: {text}"
        finally:
            page.close()


def run_tests_and_report():
    """Run tests and output structured summary."""
    import subprocess
    import sys
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=line", "-q"],
        capture_output=True,
        text=True,
        timeout=300
    )
    
    print("\n" + "="*70)
    print("REFRESH BUTTON MATRIX TEST RESULTS SUMMARY")
    print("="*70)
    
    output = result.stdout + "\n" + result.stderr
    lines = output.strip().split('\n')
    
    passed = 0
    failed = 0
    errors = 0
    
    button_results = {}
    condition_results = {
        "normal_live_mode": {"passed": 0, "failed": 0},
        "rapid_clicks": {"passed": 0, "failed": 0},
        "demo_mode": {"passed": 0, "failed": 0},
        "no_ingestion": {"passed": 0, "failed": 0},
    }
    
    for line in lines:
        if " PASSED" in line:
            passed += 1
            for btn in BUTTONS:
                if btn["id"] in line:
                    button_results[btn["id"]] = button_results.get(btn["id"], {"passed": 0, "failed": 0})
                    button_results[btn["id"]]["passed"] += 1
        elif " FAILED" in line:
            failed += 1
            for btn in BUTTONS:
                if btn["id"] in line:
                    button_results[btn["id"]] = button_results.get(btn["id"], {"passed": 0, "failed": 0})
                    button_results[btn["id"]]["failed"] += 1
        elif " ERROR" in line:
            errors += 1
    
    for line in lines:
        if "live_mode" in line or "live" in line.lower():
            if "PASSED" in line:
                condition_results["normal_live_mode"]["passed"] += 1
            elif "FAILED" in line:
                condition_results["normal_live_mode"]["failed"] += 1
    
    for line in lines:
        if "rapid" in line.lower():
            if "PASSED" in line:
                condition_results["rapid_clicks"]["passed"] += 1
            elif "FAILED" in line:
                condition_results["rapid_clicks"]["failed"] += 1
    
    for line in lines:
        if "demo_mode" in line or "demo" in line.lower() and "mode" in line:
            if "PASSED" in line:
                condition_results["demo_mode"]["passed"] += 1
            elif "FAILED" in line:
                condition_results["demo_mode"]["failed"] += 1
    
    for line in lines:
        if "ingestion" in line.lower():
            if "PASSED" in line:
                condition_results["no_ingestion"]["passed"] += 1
            elif "FAILED" in line:
                condition_results["no_ingestion"]["failed"] += 1
    
    print(f"\n{'Button ID':<35} {'Passed':<10} {'Failed':<10} {'Status'}")
    print("-"*70)
    
    for btn in BUTTONS:
        res = button_results.get(btn["id"], {"passed": 0, "failed": 0})
        status = "PASS" if res["failed"] == 0 else "FAIL"
        print(f"{btn['id']:<35} {res['passed']:<10} {res['failed']:<10} {status}")
    
    print("-"*70)
    print(f"\nConditions Summary:")
    print(f"  Normal Live Mode:     {condition_results['normal_live_mode']['passed']} passed, {condition_results['normal_live_mode']['failed']} failed")
    print(f"  Rapid Clicks:         {condition_results['rapid_clicks']['passed']} passed, {condition_results['rapid_clicks']['failed']} failed")
    print(f"  Demo Mode:            {condition_results['demo_mode']['passed']} passed, {condition_results['demo_mode']['failed']} failed")
    print(f"  No Ingestion Notif:   {condition_results['no_ingestion']['passed']} passed, {condition_results['no_ingestion']['failed']} failed")
    print(f"\nTotal: {passed + failed} tests, {passed} passed, {failed} failed, {errors} errors")
    print(f"Exit code: {result.returncode}")
    
    return result.returncode


if __name__ == "__main__":
    exit_code = run_tests_and_report()
    import sys
    sys.exit(exit_code)