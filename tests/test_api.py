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


