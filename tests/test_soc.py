"""Unit and integration tests for Phase 3 Cyber Security Operations Center (SOC) APIs and threat detection."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db_connection
from app.services import evaluate_threats_for_flows

client = TestClient(app)


def test_soc_rules_list():
    response = client.get("/api/soc/rules")
    assert response.status_code == 200
    rules = response.json()
    assert isinstance(rules, list)
    assert len(rules) >= 3
    rule_ids = [r["rule_id"] for r in rules]
    assert "RULE-PORT-SCAN" in rule_ids
    assert "RULE-BRUTE-FORCE" in rule_ids


def test_threat_detection_evaluation():
    conn = get_db_connection()
    try:
        # Simulate a port scan: source IP 192.168.1.100 hitting 8 distinct ports
        flows = []
        for p in range(1, 10):
            flows.append({
                "timestamp": "2026-11-06T12:00:00Z",
                "src_ip": "192.168.1.100",
                "dst_ip": "10.0.0.1",
                "src_port": 54321,
                "dst_port": p,
                "protocol": "TCP",
                "packets": 1,
                "bytes": 64
            })
        alerts = evaluate_threats_for_flows(conn, flows)
        assert len(alerts) > 0
        port_scan_alert = next((a for a in alerts if "Port Scanning" in a["title"]), None)
        assert port_scan_alert is not None
        assert port_scan_alert["severity"] == "HIGH"
    finally:
        conn.close()


def test_soc_alerts_and_triage():
    # Fetch alerts
    response = client.get("/api/soc/alerts")
    assert response.status_code == 200
    alerts = response.json()
    assert isinstance(alerts, list)

    if len(alerts) > 0:
        alert_id = alerts[0]["alert_id"]
        # Triage alert
        triage_resp = client.post(f"/api/soc/alerts/{alert_id}/triage", json={"status": "ACKNOWLEDGED", "analyst": "Test-Analyst"})
        assert triage_resp.status_code == 200
        assert triage_resp.json()["success"] is True
        assert triage_resp.json()["status"] == "ACKNOWLEDGED"


def test_incident_cases_crud():
    # Create case
    create_resp = client.post("/api/soc/cases", json={"title": "Test Incident Case", "owner": "Security Team", "summary": "Initial investigation notes."})
    assert create_resp.status_code == 200
    data = create_resp.json()
    assert data["success"] is True
    case_id = data["case_id"]

    # Get cases
    list_resp = client.get("/api/soc/cases")
    assert list_resp.status_code == 200
    cases = list_resp.json()
    assert any(c["case_id"] == case_id for c in cases)

    # Add timeline event
    timeline_resp = client.post(f"/api/soc/cases/{case_id}/timeline", json={"actor": "Analyst", "action": "Extracted forensic artifacts", "artifact_ref": "SHA256:abc123xyz"})
    assert timeline_resp.status_code == 200
    assert timeline_resp.json()["success"] is True


def test_network_intelligence_topology():
    response = client.get("/api/intelligence/topology")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)


def test_executive_reporting():
    response = client.post("/api/reports/executive", json={"time_window": "24H"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "report_id" in data
    assert "posture_score" in data
    assert "summary" in data
    assert isinstance(data["posture_score"], (int, float))
