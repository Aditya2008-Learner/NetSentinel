"""Automated unit and integration tests for Net Sentinel backend collector ingestion."""

import pytest
from fastapi.testclient import TestClient
from app.main import app, COLLECTOR_API_KEY

client = TestClient(app)


def test_collector_ingestion_unauthorized():
    """Ingestion without API key must be rejected with 401."""
    response = client.post(
        "/api/collector/events",
        json={"events": []}
    )
    assert response.status_code == 401


def test_collector_ingestion_valid_batch():
    """Authorized batch flow ingestion must succeed and store records."""
    payload = {
        "events": [
            {
                "timestamp": "2026-10-31T10:00:00Z",
                "src_ip": "192.168.1.10",
                "dst_ip": "10.0.0.5",
                "src_port": 50000,
                "dst_port": 443,
                "protocol": "TCP",
                "packets": 12,
                "bytes": 4500,
                "first_seen": "2026-10-31T10:00:00Z",
                "last_seen": "2026-10-31T10:00:05Z",
                "interface": "Ethernet0"
            }
        ]
    }
    response = client.post(
        "/api/collector/events",
        json=payload,
        headers={"X-Collector-Key": COLLECTOR_API_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["processed"] == 1


def test_collector_status_endpoint():
    """Collector status endpoint must return status, flows, and top sources."""
    response = client.get("/api/collector/status")
    assert response.status_code == 200
    data = response.json()
    assert "collector" in data
    assert "flows" in data
    assert "top_sources" in data
    assert "top_destinations" in data
    assert "protocols" in data


def test_collector_batch_oversized():
    """Batches exceeding 1000 events must be rejected with 400."""
    large_payload = {
        "events": [{"src_ip": "1.1.1.1", "dst_ip": "2.2.2.2"} for _ in range(1001)]
    }
    response = client.post(
        "/api/collector/events",
        json=large_payload,
        headers={"X-Collector-Key": COLLECTOR_API_KEY}
    )
    assert response.status_code == 400
