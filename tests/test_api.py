import os
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_upload_invalid_file():
    response = client.post("/upload", files={"file": ("notcsv.txt", b"foo", "text/plain")})
    assert response.status_code == 400


def test_upload_valid_csv(tmp_path):
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(
        "timestamp,src_ip,dst_ip,src_port,dst_port,protocol,bytes\n"
        "2023-10-01T12:00:00,192.168.1.10,10.0.0.5,10000,80,TCP,500\n"
    )

    with open(csv_path, "rb") as fp:
        files = {"file": ("sample.csv", fp, "text/csv")}
        response = client.post("/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_dashboard_upload(tmp_path):
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(
        "timestamp,src_ip,dst_ip,src_port,dst_port,protocol,bytes\n"
        "2023-10-01T12:00:00,192.168.1.10,10.0.0.5,10000,22,TCP,100\n"
    )
    with open(csv_path, "rb") as fp:
        files = {"file": ("sample.csv", fp, "text/csv")}
        response = client.post("/upload-dash", files=files)
    assert response.status_code == 200
    assert "Net Sentinel" in response.text


def test_api_telemetry():
    response = client.get("/api/telemetry?range=15m")
    assert response.status_code == 200
    data = response.json()
    assert data["range"] == "15m"
    assert "series" in data
    assert isinstance(data["series"], list)
    assert len(data["series"]) > 0


def test_api_overview():
    response = client.get("/api/overview")
    assert response.status_code == 200
    data = response.json()
    assert "investigations_count" in data
    assert "devices_count" in data


def test_api_investigations():
    response = client.get("/api/investigations")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_api_reports_export():
    response = client.get("/api/reports/export")
    assert response.status_code == 200
    data = response.json()
    assert "report_title" in data
    assert "investigations" in data


def test_telemetry_schema_and_timestamps():
    """Timestamps must be UTC ISO 8601 and all numeric fields must be finite."""
    import math
    response = client.get("/api/telemetry?range=1h")
    assert response.status_code == 200
    data = response.json()
    assert data["range"] == "1h"
    assert "generated_at" in data
    assert data["generated_at"].endswith("Z")
    assert isinstance(data["series"], list)
    assert len(data["series"]) > 0
    for point in data["series"]:
        assert point["timestamp"].endswith("Z"), f"Non-UTC timestamp: {point['timestamp']}"
        for field in ("inbound_mbps", "outbound_mbps", "packets_per_sec", "latency_ms"):
            val = point[field]
            assert isinstance(val, (int, float)), f"{field} is not numeric: {val!r}"
            assert math.isfinite(val), f"{field} is not finite: {val}"
            assert val >= 0, f"{field} is negative: {val}"


def test_telemetry_series_is_time_ordered():
    """Series timestamps must be strictly ascending."""
    response = client.get("/api/telemetry?range=24h")
    assert response.status_code == 200
    series = response.json()["series"]
    timestamps = [p["timestamp"] for p in series]
    assert timestamps == sorted(timestamps), "Series is not time-ordered"


def test_telemetry_invalid_range_rejected():
    """An unrecognised range value must return 422."""
    response = client.get("/api/telemetry?range=99h")
    assert response.status_code == 422


def test_telemetry_simulation_idempotent():
    """Starting the same scenario twice must not error; reset must clear it."""
    r1 = client.post("/api/telemetry/simulate", data={"scenario": "spike"})
    assert r1.status_code == 200
    r2 = client.post("/api/telemetry/simulate", data={"scenario": "spike"})
    assert r2.status_code == 200

    tel = client.get("/api/telemetry?range=15m")
    assert tel.json()["simulation_active"] is True

    reset = client.post("/api/telemetry/simulate", data={"scenario": "reset"})
    assert reset.status_code == 200

    tel2 = client.get("/api/telemetry?range=15m")
    assert tel2.json()["simulation_active"] is False


def test_telemetry_invalid_scenario_rejected():
    response = client.post("/api/telemetry/simulate", data={"scenario": "ddos"})
    assert response.status_code == 400


def test_csv_upload_with_whitespace_and_bom(tmp_path):
    """CSV headers with whitespace and UTF-8 BOM must be parsed correctly."""
    csv_path = tmp_path / "spaced.csv"
    csv_path.write_bytes(
        b"\xef\xbb\xbf-timestamp, src_ip, dst_ip\n".replace(b"-", b"") +
        b"2023-10-01T12:00:00, 192.168.1.10, 10.0.0.5\n"
    )
    with open(csv_path, "rb") as fp:
        files = {"file": ("spaced.csv", fp, "text/csv")}
        response = client.post("/api/network/analyze", files=files)
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert "summary" in data
    assert data["summary"]["total_records_analyzed"] == 1


def test_csv_upload_missing_columns(tmp_path):
    """CSV missing required columns must return 400."""
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("time,ip1,ip2\n2023-10-01,1.1.1.1,2.2.2.2\n")
    with open(csv_path, "rb") as fp:
        files = {"file": ("bad.csv", fp, "text/csv")}
        response = client.post("/api/network/analyze", files=files)
    assert response.status_code == 400
    assert "Required columns" in response.json()["detail"]


def test_api_analytics_24h():
    response = client.get("/api/analytics?range=24H")
    assert response.status_code == 200
    data = response.json()
    assert data["range"] == "24H"
    assert "metrics" in data
    assert "chart_series" in data


def test_api_analytics_7d():
    response = client.get("/api/analytics?range=7D")
    assert response.status_code == 200
    data = response.json()
    assert data["range"] == "7D"
    assert "metrics" in data
    assert "chart_series" in data


def test_api_analytics_export_24h():
    response = client.get("/api/analytics/export?range=24H")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment" in response.headers.get("content-disposition", "")


def test_security_headers_present():
    """Verify essential defense-in-depth security headers are present."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert "content-security-policy" in response.headers


def test_non_utf8_csv_returns_400():
    """Verify non-UTF8 encoded CSV payloads return 400 instead of 500."""
    bad_bytes = b"\xff\xfe\x00\x00\xaa\xbb\xcc\xdd"
    response = client.post("/api/network/analyze", files={"file": ("bad_encoding.csv", bad_bytes, "text/csv")})
    assert response.status_code == 400
    assert "valid UTF-8" in response.json()["detail"]


def test_investigation_title_validation():
    """Empty or whitespace-only investigation titles must be rejected with 400."""
    response = client.post("/api/investigations", data={"title": "   "})
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"]


def test_rapid_investigation_creation_unique_ids():
    """Multiple investigations created rapidly must receive unique IDs and not trigger UNIQUE constraint errors."""
    r1 = client.post("/api/investigations", data={"title": "Case Alpha", "case_ref": "REF-001"})
    r2 = client.post("/api/investigations", data={"title": "Case Beta", "case_ref": "REF-002"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["id"] != r2.json()["id"]


def test_stego_download_path_traversal_blocked():
    """Attempting path traversal on stego download must return 404."""
    response = client.get("/api/stego/download/..%2F..%2Fetc%2Fpasswd")
    assert response.status_code in {400, 404}


def test_stego_embed_returns_base64_and_extracts(tmp_path):
    """Stego embed must return base64 image_data to solve serverless ephemeral storage, and round-trip extraction must succeed."""
    import io
    from PIL import Image

    img = Image.new("RGB", (30, 30), color=(10, 50, 100))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    embed_res = client.post(
        "/api/stego/embed",
        files={"file": ("test_cover.png", png_bytes, "image/png")},
        data={"secret": "ClassifiedSentinelPayload"},
    )
    assert embed_res.status_code == 200
    embed_data = embed_res.json()
    assert embed_data["success"] is True
    assert "image_data" in embed_data
    assert embed_data["image_data"].startswith("data:image/png;base64,")

    # Decode the base64 payload and verify extraction
    import base64
    b64_str = embed_data["image_data"].split(",", 1)[1]
    encoded_png_bytes = base64.b64decode(b64_str)

    extract_res = client.post(
        "/api/stego/extract",
        files={"file": ("encoded.png", encoded_png_bytes, "image/png")},
    )
    assert extract_res.status_code == 200
    assert extract_res.json()["secret"] == "ClassifiedSentinelPayload"


def test_db_auto_initialization(tmp_path):
    """Database connections to a newly created database file must auto-initialize schema tables."""
    import sqlite3
    from app.database import init_db_conn

    test_db = tmp_path / "fresh.db"
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row
    init_db_conn(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cursor.fetchall()}
    assert "investigations" in tables
    assert "devices" in tables
    assert "integrity_baselines" in tables
    conn.close()

