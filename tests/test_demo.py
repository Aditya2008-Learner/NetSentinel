import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db_connection
from app.demo_service import reset_demo_state

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_clean_demo_state():
    """Ensure demo in-memory state is reset before each test."""
    reset_demo_state()
    yield
    reset_demo_state()


def test_demo_state_and_update():
    """GET and POST /api/demo/state, verify multiplier updates."""
    # 1. GET initial state
    res_get = client.get("/api/demo/state")
    assert res_get.status_code == 200
    state = res_get.json()
    assert "bandwidth_multiplier" in state
    assert "packet_rate_multiplier" in state
    assert state["bandwidth_multiplier"] == 1.0
    assert state["packet_rate_multiplier"] == 1.0

    # 2. POST update multipliers and scenarios
    update_payload = {
        "bandwidth_multiplier": 2.5,
        "packet_rate_multiplier": 3.0,
        "active_scenario": "spike",
        "collector_health": "DEGRADED",
    }
    res_post = client.post("/api/demo/state", json=update_payload)
    assert res_post.status_code == 200
    updated_state = res_post.json()
    assert updated_state["bandwidth_multiplier"] == 2.5
    assert updated_state["packet_rate_multiplier"] == 3.0
    assert updated_state["active_scenario"] == "spike"
    assert updated_state["collector_health"] == "DEGRADED"

    # Verify updated values persist in GET
    res_verify = client.get("/api/demo/state")
    assert res_verify.status_code == 200
    verified = res_verify.json()
    assert verified["bandwidth_multiplier"] == 2.5
    assert verified["packet_rate_multiplier"] == 3.0
    assert verified["active_scenario"] == "spike"
    assert verified["collector_health"] == "DEGRADED"


def test_demo_reset():
    """POST /api/demo/reset, verify state reset."""
    # Alter state
    client.post("/api/demo/state", json={"bandwidth_multiplier": 4.5, "active_scenario": "portscan"})
    mid_res = client.get("/api/demo/state")
    assert mid_res.json()["bandwidth_multiplier"] == 4.5
    assert mid_res.json()["active_scenario"] == "portscan"

    # Reset
    res_reset = client.post("/api/demo/reset")
    assert res_reset.status_code == 200
    reset_json = res_reset.json()
    assert reset_json["success"] is True
    assert "message" in reset_json
    assert reset_json["state"]["bandwidth_multiplier"] == 1.0
    assert reset_json["state"]["packet_rate_multiplier"] == 1.0
    assert reset_json["state"]["active_scenario"] is None
    assert reset_json["state"]["collector_health"] == "LIVE"

    # Verify GET returns default state
    state = client.get("/api/demo/state").json()
    assert state["bandwidth_multiplier"] == 1.0
    assert state["packet_rate_multiplier"] == 1.0
    assert state["active_scenario"] is None
    assert state["collector_health"] == "LIVE"


def test_demo_telemetry_scaling():
    """GET /api/demo/telemetry, verify data shape and scaling."""
    # Baseline telemetry
    res_base = client.get("/api/demo/telemetry?range=1h")
    assert res_base.status_code == 200
    base_data = res_base.json()
    assert "time_range" in base_data
    assert "summary" in base_data
    assert "series" in base_data
    assert isinstance(base_data["series"], list)
    assert len(base_data["series"]) == 24

    for point in base_data["series"]:
        assert "timestamp" in point
        assert "bandwidth_mbps" in point
        assert "packets_per_sec" in point
        assert "active_flows" in point
        assert "cpu_percent" in point
        assert "memory_percent" in point
        assert "latency_ms" in point
        assert "packet_drop_rate" in point
        assert point["bandwidth_mbps"] >= 0
        assert point["packets_per_sec"] >= 0

    base_avg_bw = base_data["summary"]["avg_bandwidth_mbps"]
    base_total_pkts = base_data["summary"]["total_packets"]

    # Scale multipliers by 2.0
    client.post("/api/demo/state", json={"bandwidth_multiplier": 2.0, "packet_rate_multiplier": 2.0})
    res_scaled = client.get("/api/demo/telemetry?range=1h")
    assert res_scaled.status_code == 200
    scaled_data = res_scaled.json()
    scaled_avg_bw = scaled_data["summary"]["avg_bandwidth_mbps"]
    scaled_total_pkts = scaled_data["summary"]["total_packets"]

    assert scaled_data["bandwidth_multiplier"] == 2.0
    assert scaled_data["packet_rate_multiplier"] == 2.0
    # Scaled values should reflect approximately double the base values
    assert scaled_avg_bw > base_avg_bw * 1.8
    assert scaled_total_pkts > base_total_pkts * 1.8


def test_demo_devices():
    """GET /api/demo/devices, verify 8 enterprise devices returned with expected attributes."""
    res = client.get("/api/demo/devices")
    assert res.status_code == 200
    devices = res.json()
    assert isinstance(devices, list)
    assert len(devices) == 8

    expected_fields = {
        "id",
        "ip_address",
        "mac_address",
        "vendor",
        "hostname",
        "status",
        "observation_source",
        "first_seen",
        "last_seen",
    }
    for dev in devices:
        for field in expected_fields:
            assert field in dev, f"Device missing expected field: {field}"
        assert dev["id"].startswith("DEV-")
        assert dev["status"] in ["Active", "Suspicious", "Idle"]

    device_ids = [d["id"] for d in devices]
    assert len(set(device_ids)) == 8
    assert "DEV-001" in device_ids
    assert "DEV-008" in device_ids


def test_demo_flows():
    """GET /api/demo/flows, verify flow list and protocol filtering."""
    # All flows
    res_all = client.get("/api/demo/flows")
    assert res_all.status_code == 200
    flows = res_all.json()
    assert isinstance(flows, list)
    assert len(flows) == 55

    for flow in flows:
        assert "timestamp" in flow
        assert "src_ip" in flow
        assert "dst_ip" in flow
        assert "src_port" in flow
        assert "dst_port" in flow
        assert "protocol" in flow
        assert "packets" in flow
        assert "bytes" in flow

    # Protocol filtering
    res_tcp = client.get("/api/demo/flows?protocol=TCP")
    assert res_tcp.status_code == 200
    tcp_flows = res_tcp.json()
    assert len(tcp_flows) > 0
    assert all(f["protocol"] == "TCP" for f in tcp_flows)

    res_dns = client.get("/api/demo/flows?protocol=DNS")
    assert res_dns.status_code == 200
    dns_flows = res_dns.json()
    assert len(dns_flows) > 0
    assert all(f["protocol"] == "DNS" for f in dns_flows)

    # Search query filtering
    res_query = client.get("/api/demo/flows?q=198.51.100.14")
    assert res_query.status_code == 200
    q_flows = res_query.json()
    assert len(q_flows) > 0
    assert all("198.51.100.14" in (f["src_ip"] + f["dst_ip"]) for f in q_flows)


def test_demo_alerts_triage():
    """GET /api/demo/alerts, POST /api/demo/alerts/{alert_id}/triage, verify triage status changes in memory."""
    res = client.get("/api/demo/alerts")
    assert res.status_code == 200
    alerts = res.json()
    assert isinstance(alerts, list)
    assert len(alerts) >= 6

    # Verify alert structure
    first_alert = alerts[0]
    alert_id = first_alert["alert_id"]
    initial_status = first_alert["status"]
    assert initial_status == "OPEN"

    # Triage alert to RESOLVED
    triage_payload = {
        "status": "RESOLVED",
        "analyst": "Forensic Specialist Marcus",
    }
    res_triage = client.post(f"/api/demo/alerts/{alert_id}/triage", json=triage_payload)
    assert res_triage.status_code == 200
    triaged_alert = res_triage.json()
    assert triaged_alert["alert_id"] == alert_id
    assert triaged_alert["status"] == "RESOLVED"
    assert triaged_alert["assigned_analyst"] == "Forensic Specialist Marcus"

    # Verify changes persist in subsequent GET
    res_after = client.get("/api/demo/alerts")
    assert res_after.status_code == 200
    updated_list = res_after.json()
    matching = next((a for a in updated_list if a["alert_id"] == alert_id), None)
    assert matching is not None
    assert matching["status"] == "RESOLVED"
    assert matching["assigned_analyst"] == "Forensic Specialist Marcus"

    # Verify 404 on nonexistent alert
    res_missing = client.post(
        "/api/demo/alerts/NON-EXISTENT-ALERT/triage",
        json={"status": "RESOLVED", "analyst": "Ghost"},
    )
    assert res_missing.status_code == 404


def test_demo_cases():
    """GET /api/demo/cases, verify case list with timelines."""
    res = client.get("/api/demo/cases")
    assert res.status_code == 200
    cases = res.json()
    assert isinstance(cases, list)
    assert len(cases) >= 3

    for case in cases:
        assert "case_id" in case
        assert "title" in case
        assert "status" in case
        assert "owner" in case
        assert "summary" in case
        assert "created_at" in case
        assert "timeline" in case
        assert isinstance(case["timeline"], list)
        assert len(case["timeline"]) > 0

        for event in case["timeline"]:
            assert "event_id" in event
            assert "timestamp" in event
            assert "actor" in event
            assert "action" in event
            assert "artifact_ref" in event


def test_demo_threat_intel():
    """GET /api/demo/threat-intel/198.51.100.14, verify risk_score, classification, and is_demo flag."""
    target_ip = "198.51.100.14"
    res = client.get(f"/api/demo/threat-intel/{target_ip}")
    assert res.status_code == 200
    intel = res.json()
    assert intel["ip"] == target_ip
    assert "risk_score" in intel
    assert intel["risk_score"] == 92
    assert "classification" in intel
    assert "Malicious" in intel["classification"]
    assert "is_demo" in intel
    assert intel["is_demo"] is True
    assert "threat_level" in intel
    assert intel["threat_level"] == "CRITICAL"
    assert "notice" in intel


def test_demo_health():
    """GET /api/demo/health, verify health metrics."""
    res = client.get("/api/demo/health")
    assert res.status_code == 200
    health = res.json()
    assert health["collector_status"] == "LIVE"
    assert "cpu_percent" in health
    assert "memory_percent" in health
    assert "latency_ms" in health
    assert "packet_drop_rate" in health
    assert "active_workers" in health
    assert health["is_demo"] is True
    assert health["cpu_percent"] >= 0
    assert health["memory_percent"] >= 0


def test_demo_pdf_report():
    """GET /api/demo/report/pdf, verify HTTP 200, content-type is application/pdf, and content starts with b'%PDF-'."""
    res = client.get("/api/demo/report/pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF-")
    assert len(res.content) > 1000


def test_demo_files():
    """GET /api/demo/files/csv, /carrier, /stego, /clean, /tampered, /baseline_info, verify valid responses."""
    # CSV
    res_csv = client.get("/api/demo/files/csv")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert res_csv.text.startswith("timestamp,src_ip,dst_ip")
    assert "net_sentinel_demo_logs.csv" in res_csv.headers.get("content-disposition", "")

    # Carrier image
    res_carrier = client.get("/api/demo/files/carrier")
    assert res_carrier.status_code == 200
    assert res_carrier.headers["content-type"] == "image/png"
    assert res_carrier.content.startswith(b"\x89PNG\r\n\x1a\n")

    # Stego image
    res_stego = client.get("/api/demo/files/stego")
    assert res_stego.status_code == 200
    assert res_stego.headers["content-type"] == "image/png"
    assert res_stego.content.startswith(b"\x89PNG\r\n\x1a\n")

    # Clean config
    res_clean = client.get("/api/demo/files/clean")
    assert res_clean.status_code == 200
    assert res_clean.headers["content-type"] == "application/octet-stream"
    assert b"AUTH_MODE=ENFORCED_PKI" in res_clean.content
    assert b"PERMIT_ROOT_LOGIN=NO" in res_clean.content

    # Tampered config
    res_tampered = client.get("/api/demo/files/tampered")
    assert res_tampered.status_code == 200
    assert res_tampered.headers["content-type"] == "application/octet-stream"
    assert b"PERMIT_ROOT_LOGIN=YES" in res_tampered.content
    assert b"TAMPER" in res_tampered.content

    # Baseline info
    res_info = client.get("/api/demo/files/baseline_info")
    assert res_info.status_code == 200
    info = res_info.json()
    assert "clean_hash" in info
    assert "tampered_hash" in info
    assert "filename" in info
    assert info["clean_hash"] != info["tampered_hash"]
    assert info["filename"] == "demo_kernel_auth.cfg"


def test_demo_data_isolation():
    """Query production database tables (devices, security_alerts, live_flows, integrity_baselines)

    before and after demo operations, proving that zero demo records or changes leak into production tables.
    """
    conn = get_db_connection()
    tables = ["devices", "security_alerts", "live_flows", "integrity_baselines"]

    def snapshot_counts():
        cursor = conn.cursor()
        counts = {}
        rows = {}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cursor.fetchone()[0]
            cursor.execute(f"SELECT * FROM {table}")
            rows[table] = cursor.fetchall()
        return counts, rows

    counts_before, rows_before = snapshot_counts()

    # Perform extensive demo operations across all demo endpoints
    client.post("/api/demo/state", json={"bandwidth_multiplier": 3.0, "active_scenario": "spike"})
    client.get("/api/demo/state")
    client.get("/api/demo/telemetry?range=24h")
    client.get("/api/demo/devices")
    client.get("/api/demo/flows?protocol=TCP")
    alerts = client.get("/api/demo/alerts").json()
    if alerts:
        client.post(f"/api/demo/alerts/{alerts[0]['alert_id']}/triage", json={"status": "RESOLVED", "analyst": "Demo Isolation Test"})
    client.get("/api/demo/cases")
    client.get("/api/demo/threat-intel/198.51.100.14")
    client.get("/api/demo/health")
    client.get("/api/demo/report/pdf")
    client.get("/api/demo/files/csv")
    client.get("/api/demo/files/carrier")
    client.get("/api/demo/files/stego")
    client.get("/api/demo/files/clean")
    client.get("/api/demo/files/tampered")
    client.get("/api/demo/files/baseline_info")
    client.post("/api/demo/reset")

    counts_after, rows_after = snapshot_counts()
    conn.close()

    # Verify zero leakage into production database tables
    for table in tables:
        assert counts_before[table] == counts_after[table], (
            f"Table '{table}' row count changed after demo operations! "
            f"Before: {counts_before[table]}, After: {counts_after[table]}"
        )
        assert rows_before[table] == rows_after[table], (
            f"Table '{table}' records were modified during demo operations!"
        )
