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


def test_csv_with_exact_3_columns_timestamp_src_ip_dst_ip():
    """Verify that a CSV containing only timestamp, src_ip, dst_ip succeeds."""
    csv_content = (
        "timestamp,src_ip,dst_ip\n"
        "2026-10-27T18:00:00Z,192.168.1.5,10.0.0.1\n"
        "2026-10-27T18:00:30Z,192.168.1.5,10.0.0.2\n"
    )
    res = client.post(
        "/api/network/analyze",
        files={"file": ("telemetry.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    assert res.status_code == 200
    data = res.json()
    assert "events" in data
    assert "summary" in data
    assert data["summary"]["total_records_analyzed"] == 2


def test_csv_with_capitalized_and_alias_headers():
    """Verify that capitalized headers and standard aliases (Timestamp, Source_IP, Destination_IP) are accepted."""
    csv_content = (
        "Timestamp,Source_IP,Destination_IP\n"
        "2026-10-27 18:00:00,192.168.1.5,10.0.0.1\n"
    )
    res = client.post(
        "/api/network/analyze",
        files={"file": ("telemetry.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    assert res.status_code == 200
    assert res.json()["summary"]["total_records_analyzed"] == 1


def test_csv_with_semicolon_delimiter():
    """Verify that CSV files using semicolon delimiters are automatically handled."""
    csv_content = (
        "timestamp;src_ip;dst_ip\n"
        "2026-10-27 18:00:00;192.168.1.5;10.0.0.1\n"
    )
    res = client.post(
        "/api/network/analyze",
        files={"file": ("semicolon.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    assert res.status_code == 200
    assert res.json()["summary"]["total_records_analyzed"] == 1


def test_csv_with_unix_epoch_and_iso_timestamps():
    """Verify that Unix epoch (seconds & ms) and ISO timestamps parse properly."""
    csv_content = (
        "timestamp,src_ip,dst_ip\n"
        "1730052583,192.168.1.5,10.0.0.1\n"
        "1730052583000,192.168.1.6,10.0.0.2\n"
        "2026/10/27 18:00:00,192.168.1.7,10.0.0.3\n"
    )
    res = client.post(
        "/api/network/analyze",
        files={"file": ("epochs.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    assert res.status_code == 200
    assert res.json()["summary"]["total_records_analyzed"] == 3


def test_csv_empty_file_returns_400():
    """Empty CSV files must return a descriptive HTTP 400 error."""
    res = client.post(
        "/api/network/analyze",
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


def test_csv_headers_only_zero_rows_returns_200():
    """CSV containing valid headers but 0 rows returns 200 with 0 events."""
    csv_content = "timestamp,src_ip,dst_ip\n"
    res = client.post(
        "/api/network/analyze",
        files={"file": ("zero_rows.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["events"] == []
    assert data["summary"]["total_records_analyzed"] == 0


def test_csv_wrong_field_name_returns_422():
    """Sending file under wrong field name returns 422 Unprocessable Entity."""
    res = client.post(
        "/api/network/analyze",
        files={"wrong_field": ("test.csv", b"timestamp,src_ip,dst_ip\n", "text/csv")},
    )
    assert res.status_code == 422


def test_csv_non_csv_extension_returns_400():
    """Uploading a non-csv extension returns 400."""
    res = client.post(
        "/api/network/analyze",
        files={"file": ("logs.exe", b"timestamp,src_ip,dst_ip\n", "text/plain")},
    )
    assert res.status_code == 400
    assert "Only CSV files are accepted" in res.json()["detail"]


def test_sample_csv_endpoint():
    response = client.get("/api/network/sample")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "timestamp" in response.text


def test_api_get_sample_csv():
    response = client.get("/api/network/sample")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    first_line = response.text.splitlines()[0]
    for col in ("timestamp", "src_ip", "dst_ip"):
        assert col in first_line


def test_csv_with_trailing_blank_lines(tmp_path):
    csv_path = tmp_path / "trailing_blank_lines.csv"
    csv_path.write_text(
        "timestamp,src_ip,dst_ip\n"
        "2023-10-01T12:00:00,192.168.1.10,10.0.0.5\n"
        "\n"
        "2023-10-01T12:00:01,192.168.1.10,10.0.0.5\n"
        "\n\n"
    )
    with open(csv_path, "rb") as fp:
        files = {"file": ("trailing_blank_lines.csv", fp, "text/csv")}
        response = client.post("/api/network/analyze", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_records_analyzed"] == 2


def test_csv_with_ip_port_suffixes(tmp_path):
    csv_path = tmp_path / "ip_ports.csv"
    csv_path.write_text(
        "timestamp,src_ip,dst_ip,src_port,dst_port,protocol,bytes\n"
        "2023-10-01T12:00:00,192.168.1.10:8080,10.0.0.5:443,10000,443,TCP,15728640\n"
    )
    with open(csv_path, "rb") as fp:
        files = {"file": ("ip_ports.csv", fp, "text/csv")}
        response = client.post("/api/network/analyze", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_records_analyzed"] == 1
    assert len(data["events"]) == 1
    assert data["events"][0]["src_ip"] == "192.168.1.10"
    assert data["events"][0]["dst_ip"] == "10.0.0.5"


def test_csv_upload_with_trailing_blank_lines(tmp_path):
    csv_path = tmp_path / "trailing_blank.csv"
    csv_path.write_text(
        "timestamp,src_ip,dst_ip\n"
        "2023-10-01T12:00:00,192.168.1.10:8080,10.0.0.5:443\n"
        "\n"
        "2023-10-01T12:00:01,192.168.1.10,10.0.0.5\n"
        "\n\n"
    )
    with open(csv_path, "rb") as fp:
        files = {"file": ("trailing_blank.csv", fp, "text/csv")}
        response = client.post("/api/network/analyze", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_records_analyzed"] == 2


def test_anchored_paths():
    from app.database import DB_PATH, BASE_DIR as DB_BASE_DIR
    from app.main import BASE_DIR, STATIC_DIR, TEMPLATES_DIR, UPLOAD_DIR
    assert DB_BASE_DIR.is_dir()
    assert BASE_DIR.is_dir()
    assert STATIC_DIR == BASE_DIR / "static"
    assert TEMPLATES_DIR == BASE_DIR / "templates"
    if not (os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")):
        assert DB_PATH == DB_BASE_DIR / "data" / "netsentinel.db"
        assert UPLOAD_DIR == BASE_DIR / "data" / "uploads"


def test_seed_devices_on_empty_db(tmp_path):
    import sqlite3
    from app.database import init_db_conn
    db_file = tmp_path / "seed_test.db"
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    init_db_conn(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM devices ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    assert len(rows) == 2
    dev1 = rows[0]
    assert dev1["id"] == "DEV-001"
    assert dev1["ip_address"] == "192.168.1.1"
    assert dev1["mac_address"] == "a1:b2:c3:d4:e5:f6"
    assert dev1["hostname"] == "Local Gateway"
    assert dev1["status"] == "Active"
    assert dev1["observation_source"] == "ARP Cache / Gateway"
    assert dev1["first_seen"] is not None
    assert dev1["last_seen"] is not None
    dev2 = rows[1]
    assert dev2["id"] == "DEV-002"
    assert dev2["ip_address"] == "192.168.1.50"
    assert dev2["mac_address"] == "f6:e5:d4:c3:b2:a1"
    assert dev2["hostname"] == "Analysis Node"
    assert dev2["status"] == "Active"
    assert dev2["observation_source"] == "Local Interface"


def test_api_devices_crud():
    get_res = client.get("/api/devices")
    assert get_res.status_code == 200
    devices = get_res.json()
    assert isinstance(devices, list)

    bad_res1 = client.post("/api/devices", data={"hostname": "   ", "ip_address": "10.0.0.1"})
    assert bad_res1.status_code == 400
    assert "Hostname cannot be empty" in bad_res1.json()["detail"]

    bad_res2 = client.post("/api/devices", data={"hostname": "Server", "ip_address": "   "})
    assert bad_res2.status_code == 400
    assert "IP address cannot be empty" in bad_res2.json()["detail"]

    create_res = client.post(
        "/api/devices",
        data={
            "hostname": "Threat Sensor Alpha",
            "ip_address": "10.10.10.25",
            "mac_address": "00:11:22:33:44:55",
            "status": "Active",
            "observation_source": "Manual Entry",
        },
    )
    assert create_res.status_code == 200
    created = create_res.json()
    assert created["id"].startswith("DEV-")
    assert created["hostname"] == "Threat Sensor Alpha"
    assert created["ip_address"] == "10.10.10.25"
    assert created["mac_address"] == "00:11:22:33:44:55"
    assert created["status"] == "Active"
    assert created["observation_source"] == "Manual Entry"
    assert created["first_seen"] is not None
    assert created["last_seen"] is not None

    del_res = client.delete(f"/api/devices/{created['id']}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    del_missing = client.delete(f"/api/devices/{created['id']}")
    assert del_missing.status_code == 404
    assert del_missing.json()["detail"] == "Device not found"


def test_api_network_history_and_analysis_persistence():
    csv_content = (
        "timestamp,src_ip,dst_ip,src_port,dst_port,protocol,bytes\n"
        "2023-10-01T12:00:00,192.168.1.100,10.0.0.5,10000,80,TCP,500\n"
    )
    res = client.post(
        "/api/network/analyze",
        files={"file": ("history_test_file.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    assert res.status_code == 200

    hist_res = client.get("/api/network/history?limit=10")
    assert hist_res.status_code == 200
    history = hist_res.json()
    assert isinstance(history, list)
    assert len(history) > 0

    latest = history[0]
    assert latest["filename"] == "history_test_file.csv"
    assert latest["operation_type"] == "Network Log Analysis"
    assert latest["status"] == "Completed"
    assert isinstance(latest["details"], dict)
    assert "total_records" in latest["details"]
    assert "threat_count" in latest["details"]
    assert "threat_breakdown" in latest["details"]
    assert latest["details"]["total_records"] == 1


def test_api_global_search():
    empty_res = client.get("/api/search?q=")
    assert empty_res.status_code == 200
    empty_data = empty_res.json()
    assert empty_data["query"] == ""
    assert empty_data["total_results"] == 0
    assert empty_data["results"]["investigations"] == []
    assert empty_data["results"]["devices"] == []
    assert empty_data["results"]["integrity_baselines"] == []
    assert empty_data["results"]["analysis_history"] == []

    client.post("/api/investigations", data={"title": "UniqueSearchTitle99", "case_ref": "REF-SRCH"})

    search_res = client.get("/api/search?q=uniquesearchtitle99")
    assert search_res.status_code == 200
    data = search_res.json()
    assert data["query"] == "uniquesearchtitle99"
    assert data["total_results"] >= 1
    found_titles = [inv["title"] for inv in data["results"]["investigations"]]
    assert "UniqueSearchTitle99" in found_titles

    dev_search = client.get("/api/search?q=192.168.1.1")
    assert dev_search.status_code == 200
    dev_data = dev_search.json()
    assert dev_data["total_results"] >= 1
    found_ips = [d["ip_address"] for d in dev_data["results"]["devices"]]
    assert "192.168.1.1" in found_ips


def test_landing_page_serves_landing_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "SIGNAL / EVIDENCE" in response.text
    assert "Every connection" in response.text
    assert "leaves a trace" in response.text
    assert "Open Workspace" in response.text
    assert "network-canvas" in response.text
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert "content-security-policy" in response.headers


def test_dashboard_page_serves_index_html():
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Net Sentinel" in response.text
    assert "Overview Dashboard" in response.text
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert "content-security-policy" in response.headers


def test_telemetry_timestamp_alignment():
    from datetime import datetime
    from app.main import _build_telemetry_series
    series = _build_telemetry_series("1h", {"active": False, "scenario": ""})
    assert len(series) == 12
    # Check that timestamps align to 300 second boundary
    for pt in series:
        dt = datetime.strptime(pt["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
        ts = int(dt.timestamp())
        assert ts % 300 == 0


def test_integrity_register_and_verify():
    import hashlib
    import uuid
    filename = f"config_{uuid.uuid4().hex[:8]}.cfg"
    content = b"CriticalSecurityConfiguration123"
    expected_hash = hashlib.sha256(content).hexdigest()

    # Verify before registration without reference_hash -> UNREGISTERED
    res_unreg = client.post(
        "/api/integrity/verify",
        files={"file": (filename, content, "application/octet-stream")},
    )
    assert res_unreg.status_code == 200
    unreg_data = res_unreg.json()
    assert unreg_data["status"] == "UNREGISTERED"
    assert unreg_data["match"] is None

    # Register baseline
    res_reg = client.post(
        "/api/integrity/register",
        files={"file": (filename, content, "application/octet-stream")},
    )
    assert res_reg.status_code == 200
    reg_data = res_reg.json()
    assert reg_data["success"] is True
    assert reg_data["sha256"] == expected_hash

    # Verify against registered baseline -> VERIFIED
    res_verify = client.post(
        "/api/integrity/verify",
        files={"file": (filename, content, "application/octet-stream")},
    )
    assert res_verify.status_code == 200
    verify_data = res_verify.json()
    assert verify_data["match"] is True
    assert verify_data["status"] == "VERIFIED"
    assert verify_data["baseline_hash"] == expected_hash

    # Tampered file verification -> TAMPERED_OR_MISMATCH
    tampered_content = b"TamperedSecurityConfiguration999"
    res_tamper = client.post(
        "/api/integrity/verify",
        files={"file": (filename, tampered_content, "application/octet-stream")},
    )
    assert res_tamper.status_code == 200
    tamper_data = res_tamper.json()
    assert tamper_data["match"] is False
    assert tamper_data["status"] == "TAMPERED_OR_MISMATCH"


def test_investigation_dual_case_creation_and_timeline():
    # Create investigation
    res = client.post(
        "/api/investigations",
        data={"title": "Dual Case Test Investigation", "description": "Investigating anomaly", "case_ref": "REF-DUAL-01"},
    )
    assert res.status_code == 200
    inv_id = res.json()["id"]

    # Retrieve SOC cases and verify it appears with timeline
    soc_res = client.get("/api/soc/cases")
    assert soc_res.status_code == 200
    cases = soc_res.json()
    matched = [c for c in cases if c["case_id"] == inv_id]
    assert len(matched) == 1
    assert matched[0]["title"] == "Dual Case Test Investigation"
    assert len(matched[0]["timeline"]) >= 1
    assert any("Dual Case Test Investigation" in t["action"] for t in matched[0]["timeline"])


def test_network_history_limit_capping():
    res = client.get("/api/network/history?limit=500")
    assert res.status_code == 200
    records = res.json()
    assert len(records) <= 200


def test_integrity_verification_decoupled_from_baseline_creation():
    import hashlib
    import uuid
    from app.database import get_db_connection

    test_filename = f"integrity_decoupled_{uuid.uuid4().hex[:8]}.cfg"
    content = b"KernelModuleSecurityParameters_v1.0"
    expected_hash = hashlib.sha256(content).hexdigest()

    # 1. Upload to /api/integrity/verify without baseline or reference hash
    verify_unreg = client.post(
        "/api/integrity/verify",
        files={"file": (test_filename, content, "application/octet-stream")},
    )
    assert verify_unreg.status_code == 200
    data_unreg = verify_unreg.json()
    assert data_unreg["status"] == "UNREGISTERED"
    assert data_unreg["match"] is None
    assert data_unreg["current_sha256"] == expected_hash

    # Confirm NO baseline entry was created in database
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM integrity_baselines WHERE filename = ?", (test_filename,))
        count = cur.fetchone()[0]
        assert count == 0, "Verify should not create a baseline record in the database"
    finally:
        conn.close()

    # 2. Register via /api/integrity/register
    reg_res = client.post(
        "/api/integrity/register",
        files={"file": (test_filename, content, "application/octet-stream")},
    )
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    assert reg_data["success"] is True
    assert reg_data["sha256"] == expected_hash

    # 3. Subsequent verify returns status="VERIFIED" and match=True
    verify_match = client.post(
        "/api/integrity/verify",
        files={"file": (test_filename, content, "application/octet-stream")},
    )
    assert verify_match.status_code == 200
    data_match = verify_match.json()
    assert data_match["status"] == "VERIFIED"
    assert data_match["match"] is True
    assert data_match["baseline_hash"] == expected_hash

    # 4. Verify with an altered/mismatched reference hash and check status="TAMPERED_OR_MISMATCH" and match=False
    mismatched_hash = "0" * 64
    verify_mismatch = client.post(
        "/api/integrity/verify",
        files={"file": (test_filename, content, "application/octet-stream")},
        data={"reference_hash": mismatched_hash},
    )
    assert verify_mismatch.status_code == 200
    data_mismatch = verify_mismatch.json()
    assert data_mismatch["status"] == "TAMPERED_OR_MISMATCH"
    assert data_mismatch["match"] is False


def test_investigation_creation_syncs_timeline():
    import uuid
    from app.database import get_db_connection

    case_ref = f"REF-SYNC-{uuid.uuid4().hex[:6]}"
    title = f"Timeline Sync Case {uuid.uuid4().hex[:6]}"
    desc = "Automated test for investigation timeline synchronization"

    # Create investigation
    create_res = client.post(
        "/api/investigations",
        data={"title": title, "description": desc, "case_ref": case_ref},
    )
    assert create_res.status_code == 200
    inv = create_res.json()
    inv_id = inv["id"]
    assert inv_id.startswith("INV-")

    # Verify entry in incident_cases table
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM incident_cases WHERE case_id = ?", (inv_id,))
        case_row = cur.fetchone()
        assert case_row is not None, f"Expected incident_cases entry for {inv_id}"
        assert case_row["title"] == title

        # Verify initial event in incident_timeline table
        cur.execute("SELECT * FROM incident_timeline WHERE case_id = ? ORDER BY timestamp ASC", (inv_id,))
        timeline_events = cur.fetchall()
        assert len(timeline_events) >= 1, f"Expected initial timeline event for {inv_id}"
        assert any(title in e["action"] for e in timeline_events)
    finally:
        conn.close()

    # Verify visibility via GET /api/soc/cases
    soc_res = client.get("/api/soc/cases")
    assert soc_res.status_code == 200
    cases = soc_res.json()
    matching_cases = [c for c in cases if c["case_id"] == inv_id]
    assert len(matching_cases) == 1
    target_case = matching_cases[0]
    assert target_case["title"] == title
    assert len(target_case.get("timeline", [])) >= 1
    assert any(title in t["action"] for t in target_case["timeline"])


def test_telemetry_step_alignment():
    from datetime import datetime

    # Consecutive calls to /api/telemetry?range=15m
    r1 = client.get("/api/telemetry?range=15m")
    r2 = client.get("/api/telemetry?range=15m")
    assert r1.status_code == 200
    assert r2.status_code == 200

    series1 = r1.json()["series"]
    series2 = r2.json()["series"]
    assert len(series1) == 15
    assert len(series2) == 15

    # Timestamps should be stable across consecutive calls
    timestamps1 = [p["timestamp"] for p in series1]
    timestamps2 = [p["timestamp"] for p in series2]
    assert timestamps1 == timestamps2

    # Timestamps must be step-aligned to 60-second boundaries (not shifting second-by-second)
    for ts_str in timestamps1:
        dt = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ")
        epoch = int(dt.timestamp())
        assert epoch % 60 == 0, f"Timestamp {ts_str} (epoch {epoch}) is not step-aligned to 60s"


def test_stego_streaming_extraction_invalid():
    import io
    from PIL import Image
    from app.stego_service import extract_secret_from_bytes

    # Create a clean RGB image with no embedded message
    img = Image.new("RGB", (64, 64), color=(30, 60, 90))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    clean_bytes = buf.getvalue()

    success, message = extract_secret_from_bytes(clean_bytes)
    assert success is False
    assert message == "No hidden message found or invalid payload length"


def test_integrity_verify_whitespace_reference_hash():
    import hashlib
    import uuid

    filename = f"whitespace_ref_{uuid.uuid4().hex[:8]}.cfg"
    content = b"UnregisteredContentForWhitespaceRefTest"
    expected_hash = hashlib.sha256(content).hexdigest()

    # Verify with whitespace-only reference_hash on unregistered file
    res = client.post(
        "/api/integrity/verify",
        data={"reference_hash": "   \t  \n  "},
        files={"file": (filename, content, "application/octet-stream")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "UNREGISTERED"
    assert data["match"] is None
    assert data["current_sha256"] == expected_hash


def test_integrity_register_invalid_manual_sha256():
    # 1. Invalid hex characters
    res_bad_hex = client.post(
        "/api/integrity/register",
        data={"filename": "test_bad_hex.cfg", "sha256": "g" * 64},
    )
    assert res_bad_hex.status_code == 400
    assert "Invalid SHA-256 hash format" in res_bad_hex.json()["detail"]

    # 2. Too short
    res_short = client.post(
        "/api/integrity/register",
        data={"filename": "test_short.cfg", "sha256": "abcd1234"},
    )
    assert res_short.status_code == 400
    assert "Invalid SHA-256 hash format" in res_short.json()["detail"]

    # 3. Too long
    res_long = client.post(
        "/api/integrity/register",
        data={"filename": "test_long.cfg", "sha256": "a" * 65},
    )
    assert res_long.status_code == 400
    assert "Invalid SHA-256 hash format" in res_long.json()["detail"]

    # 4. Whitespace-only sha256 or filename
    res_ws_hash = client.post(
        "/api/integrity/register",
        data={"filename": "test_ws.cfg", "sha256": "   "},
    )
    assert res_ws_hash.status_code == 400

    res_ws_name = client.post(
        "/api/integrity/register",
        data={"filename": "   ", "sha256": "a" * 64},
    )
    assert res_ws_name.status_code == 400

    # 5. Valid manual sha256 registration succeeds
    valid_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    res_valid = client.post(
        "/api/integrity/register",
        data={"filename": "test_valid.cfg", "sha256": valid_hash},
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["success"] is True
    assert res_valid.json()["sha256"] == valid_hash


def test_demo_api_suite():
    # 1. GET /api/demo/state
    res = client.get("/api/demo/state")
    assert res.status_code == 200
    state = res.json()
    assert "bandwidth_multiplier" in state

    # 2. POST /api/demo/state
    res = client.post("/api/demo/state", json={"bandwidth_multiplier": 2.5, "active_scenario": "spike"})
    assert res.status_code == 200
    updated_state = res.json()
    assert updated_state["bandwidth_multiplier"] == 2.5
    assert updated_state["active_scenario"] == "spike"

    # 3. POST /api/demo/reset
    res = client.post("/api/demo/reset")
    assert res.status_code == 200
    reset_data = res.json()
    assert reset_data["success"] is True
    assert reset_data["state"]["bandwidth_multiplier"] == 1.0

    # 4. GET /api/demo/telemetry
    res = client.get("/api/demo/telemetry?range=1h")
    assert res.status_code == 200
    telemetry = res.json()
    assert "series" in telemetry
    assert len(telemetry["series"]) > 0

    # 5. GET /api/demo/devices
    res = client.get("/api/demo/devices")
    assert res.status_code == 200
    devices = res.json()
    assert isinstance(devices, list)
    assert len(devices) > 0

    # 6. GET /api/demo/flows
    res = client.get("/api/demo/flows")
    assert res.status_code == 200
    flows = res.json()
    assert isinstance(flows, list)
    assert len(flows) > 0

    res_filtered = client.get("/api/demo/flows?protocol=TCP&q=192.168.1")
    assert res_filtered.status_code == 200
    filtered_flows = res_filtered.json()
    assert isinstance(filtered_flows, list)

    # 7. GET /api/demo/alerts
    res = client.get("/api/demo/alerts")
    assert res.status_code == 200
    alerts = res.json()
    assert isinstance(alerts, list)
    assert len(alerts) > 0

    res_crit = client.get("/api/demo/alerts?severity=CRITICAL")
    assert res_crit.status_code == 200
    assert all(a["severity"] == "CRITICAL" for a in res_crit.json())

    # 8. POST /api/demo/alerts/{alert_id}/triage
    alert_id = alerts[0]["alert_id"]
    res_triage = client.post(
        f"/api/demo/alerts/{alert_id}/triage",
        json={"status": "RESOLVED", "analyst": "Test Analyst"},
    )
    assert res_triage.status_code == 200
    triaged = res_triage.json()
    assert triaged["status"] == "RESOLVED"
    assert triaged["assigned_analyst"] == "Test Analyst"

    # 404 for non-existent alert triage
    res_bad_triage = client.post(
        "/api/demo/alerts/NON_EXISTENT_ID/triage",
        json={"status": "RESOLVED"},
    )
    assert res_bad_triage.status_code == 404

    # 9. GET /api/demo/cases
    res = client.get("/api/demo/cases")
    assert res.status_code == 200
    cases = res.json()
    assert isinstance(cases, list)
    assert len(cases) > 0
    assert "timeline" in cases[0]

    # 10. GET /api/demo/threat-intel/{ip}
    res = client.get("/api/demo/threat-intel/203.0.113.88")
    assert res.status_code == 200
    intel = res.json()
    assert intel["ip"] == "203.0.113.88"
    assert "risk_score" in intel

    # 11. GET /api/demo/health
    res = client.get("/api/demo/health")
    assert res.status_code == 200
    health = res.json()
    assert "collector_status" in health

    # 12. GET /api/demo/report/pdf
    res = client.get("/api/demo/report/pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")

    # 13. GET /api/demo/files/{file_type}
    # csv
    res = client.get("/api/demo/files/csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "timestamp,src_ip,dst_ip" in res.text

    # carrier
    res = client.get("/api/demo/files/carrier")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert res.content[:8] == b"\x89PNG\r\n\x1a\n"

    # stego
    res = client.get("/api/demo/files/stego")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert res.content[:8] == b"\x89PNG\r\n\x1a\n"

    # clean
    res = client.get("/api/demo/files/clean")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/octet-stream"
    assert b"AUTH_MODE=ENFORCED_PKI" in res.content

    # tampered
    res = client.get("/api/demo/files/tampered")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/octet-stream"
    assert b"TAMPER: Backdoor access enabled" in res.content

    # baseline_info
    res = client.get("/api/demo/files/baseline_info")
    assert res.status_code == 200
    binfo = res.json()
    assert "clean_hash" in binfo
    assert "tampered_hash" in binfo
    assert "filename" in binfo

    # 404 for unknown file_type
    res = client.get("/api/demo/files/unknown_file_type")
    assert res.status_code == 404


