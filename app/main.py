"""FastAPI application for Net Sentinel.

Network Intelligence. Threat Detection. Digital Forensics.
"""

import asyncio
import base64
import io
import json
import logging
import os
import pathlib
import sqlite3
import time
import uuid
from datetime import datetime
from typing import List, Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from .services import analyze_logs, summarize
from .database import get_db_connection, init_db
from .stego_service import (
    calculate_sha256,
    embed_secret_in_image,
    extract_secret_from_image,
    analyze_image_forensics,
)

def _sanitize_filename(filename: Optional[str]) -> str:
    """Return a sanitized basename stripped of path traversal characters."""
    base = os.path.basename(filename or "file")
    clean = base.lstrip("/\\.").strip()
    return clean or "uploaded_file"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("net_sentinel")

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB
_CHUNK = 64 * 1024  # 64 KB read chunks


async def _read_limited(file: UploadFile) -> bytes:
    """Read an upload in chunks; raise HTTP 413 if it exceeds MAX_UPLOAD_BYTES."""
    buf = io.BytesIO()
    total = 0
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Payload too large. Maximum allowed size is {MAX_UPLOAD_BYTES // (1024*1024)} MB.",
            )
        buf.write(chunk)
    return buf.getvalue()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Net Sentinel", version="1.0.0", lifespan=lifespan)

cors_env = os.environ.get("CORS_ORIGINS", "").strip()
cors_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
if not cors_origins:
    cors_origins = [
        "https://net-sentinel-zeta.vercel.app",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "method=%s path=%s status=%s latency_ms=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    # Add defense-in-depth security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if "Content-Security-Policy" not in response.headers:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
            "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
    return response


BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    UPLOAD_DIR = pathlib.Path("/tmp/uploads")
else:
    UPLOAD_DIR = BASE_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/healthz")
async def healthz():
    """Health probe: verifies DB connectivity and returns uptime metadata."""
    db_ok = False
    try:
        conn = get_db_connection()
        try:
            conn.execute("SELECT 1")
            db_ok = True
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Health check DB failure: %s", exc)

    return {
        "status": "ok" if db_ok else "degraded",
        "db": "connected" if db_ok else "unreachable",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    template_name = "landing.html" if (TEMPLATES_DIR / "landing.html").is_file() else "index.html"
    return templates.TemplateResponse(
        request,
        template_name,
        {},
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_spa(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {},
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@app.get("/api/overview")
async def api_overview():
    """Get overview statistics for the dashboard."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM investigations")
        inv_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM devices")
        device_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM integrity_baselines")
        baseline_count = cursor.fetchone()[0]
        cursor.execute("SELECT * FROM investigations ORDER BY created_at DESC LIMIT 5")
        recent_investigations = [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

    return {
        "investigations_count": inv_count,
        "devices_count": device_count,
        "integrity_baselines_count": baseline_count,
        "recent_investigations": recent_investigations,
        "monitoring_status": "Demo Mode Active (Live Agent Disconnected)",
        "system_health": "Optimal",
    }


# --- Network Security & Logs API ---
@app.post("/upload", response_model=List[dict])
async def upload_log(file: UploadFile = File(...)):
    """Accept a CSV file, analyze its contents and return suspicious events."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted for analysis")
    try:
        content = await _read_limited(file)
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="CSV file encoding must be valid UTF-8")
        return await asyncio.to_thread(analyze_logs, text)
    except HTTPException:
        raise
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/upload-dash", response_class=HTMLResponse)
async def upload_dash(request: Request, file: UploadFile = File(...)):
    """Accept CSV via form, analyze, and render results directly in HTML."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        return templates.TemplateResponse(
            request,
            "index.html",
            {"events": [], "summary": None, "error": "Only CSV files are accepted for analysis."},
            status_code=400,
        )
    try:
        content = await _read_limited(file)
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="CSV file encoding must be valid UTF-8")
        lines = [line for line in text.splitlines() if line.strip()]
        total_rows = max(0, len(lines) - 1)
        events = await asyncio.to_thread(analyze_logs, text)
        summary = await asyncio.to_thread(summarize, events, getattr(events, "total_rows", total_rows))
    except HTTPException as exc:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"events": [], "summary": None, "error": exc.detail},
            status_code=exc.status_code,
        )
    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"events": [], "summary": None, "error": str(exc)},
            status_code=500,
        )
    return templates.TemplateResponse(request, "index.html", {"events": events, "summary": summary})


@app.post("/api/network/analyze", response_model=dict)
async def api_analyze_network_logs(file: UploadFile = File(...)):
    """Upload and analyze network connection logs CSV."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required. Please upload a CSV file.")
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted for network analysis (filename must end with .csv)")
    try:
        content = await _read_limited(file)
        if not content.strip():
            raise HTTPException(status_code=400, detail="Uploaded CSV file is empty. Please upload a file containing connection logs.")
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="CSV file encoding must be valid UTF-8")
        # Count non-empty data rows (minus header)
        lines = [line for line in text.splitlines() if line.strip()]
        total_rows = max(0, len(lines) - 1)
        events = await asyncio.to_thread(analyze_logs, text)
        total_rows = getattr(events, "total_rows", total_rows)
        summary = await asyncio.to_thread(summarize, events, total_rows)
        safe_name = _sanitize_filename(file.filename)
        threat_count = summary.get("total_threats", summary.get("total", 0))
        threat_breakdown = summary.get("breakdown", summary.get("by_severity", {}))
        summary.setdefault("total_threats", threat_count)
        summary.setdefault("breakdown", threat_breakdown)
        details_str = json.dumps({
            "total_records": total_rows,
            "threat_count": summary.get("total_threats", 0),
            "threat_breakdown": summary.get("breakdown", {}),
        })
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO analysis_history (filename, operation_type, status, details, timestamp)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (safe_name, "Network Log Analysis", "Completed", details_str),
            )
            conn.commit()
        finally:
            conn.close()
        return {"events": events, "summary": summary}
    except HTTPException:
        raise
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/network/history")
async def api_get_network_history(limit: int = 20):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM analysis_history ORDER BY id DESC LIMIT ?", (limit,))
        records = []
        for row in cursor.fetchall():
            item = dict(row)
            if item.get("details"):
                try:
                    item["details"] = json.loads(item["details"])
                except (ValueError, TypeError):
                    pass
            records.append(item)
    finally:
        conn.close()
    return records


@app.get("/api/network/sample")
async def api_get_sample_csv():
    """Return sample network connection logs for testing."""
    sample_path = BASE_DIR / "data" / "sample.csv"
    if not sample_path.is_file():
        raise HTTPException(status_code=404, detail="Sample data not found")
    return FileResponse(sample_path, media_type="text/csv", filename="sample.csv")


# --- Investigations API ---
@app.get("/api/investigations")
async def api_get_investigations():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM investigations ORDER BY created_at DESC")
        rows = [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
    return rows


@app.post("/api/investigations")
async def api_create_investigation(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    case_ref: Optional[str] = Form(None),
):
    clean_title = (title or "").strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="Investigation title cannot be empty")
    if len(clean_title) > 250:
        raise HTTPException(status_code=400, detail="Investigation title too long (max 250 characters)")

    inv_id = f"INV-{int(datetime.utcnow().timestamp())}-{uuid.uuid4().hex[:6]}"
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO investigations (id, title, description, case_ref, status)
            VALUES (?, ?, ?, ?, 'Open')
            """,
            (inv_id, clean_title, description, case_ref),
        )
        conn.commit()
    finally:
        conn.close()
    return {"id": inv_id, "title": clean_title, "status": "Open", "message": "Investigation created successfully"}


@app.get("/api/devices")
async def api_get_devices():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM devices ORDER BY last_seen DESC")
        devices = [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
    return devices


@app.post("/api/devices")
async def api_create_device(
    hostname: str = Form(...),
    ip_address: str = Form(...),
    mac_address: Optional[str] = Form(None),
    status: Optional[str] = Form("Active"),
    observation_source: Optional[str] = Form("Manual Entry"),
):
    clean_hostname = (hostname or "").strip()
    clean_ip = (ip_address or "").strip()
    clean_mac = (mac_address or "").strip() if mac_address else None
    clean_status = (status or "").strip() or "Active"
    clean_source = (observation_source or "").strip() or "Manual Entry"

    if not clean_hostname:
        raise HTTPException(status_code=400, detail="Hostname cannot be empty")
    if not clean_ip:
        raise HTTPException(status_code=400, detail="IP address cannot be empty")
    if len(clean_hostname) > 255:
        raise HTTPException(status_code=400, detail="Hostname too long (max 255 characters)")
    if len(clean_ip) > 100:
        raise HTTPException(status_code=400, detail="IP address too long (max 100 characters)")
    if clean_mac and len(clean_mac) > 100:
        raise HTTPException(status_code=400, detail="MAC address too long (max 100 characters)")
    if len(clean_status) > 50:
        raise HTTPException(status_code=400, detail="Status too long (max 50 characters)")
    if len(clean_source) > 100:
        raise HTTPException(status_code=400, detail="Observation source too long (max 100 characters)")

    device_id = f"DEV-{int(datetime.utcnow().timestamp())}-{uuid.uuid4().hex[:4]}"
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO devices (id, ip_address, mac_address, hostname, status, observation_source, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (device_id, clean_ip, clean_mac, clean_hostname, clean_status, clean_source),
        )
        conn.commit()
        cursor.execute("SELECT * FROM devices WHERE id = ?", (device_id,))
        created_device = dict(cursor.fetchone())
    finally:
        conn.close()
    return created_device


@app.delete("/api/devices/{device_id}")
async def api_delete_device(device_id: str):
    clean_id = (device_id or "").strip()
    if not clean_id:
        raise HTTPException(status_code=404, detail="Device not found")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM devices WHERE id = ?", (clean_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Device not found")
        cursor.execute("DELETE FROM devices WHERE id = ?", (clean_id,))
        conn.commit()
    finally:
        conn.close()
    return {"success": True, "message": "Device removed successfully"}


@app.get("/api/search")
async def api_search(q: str = Query("", alias="q")):
    clean_q = (q or "").strip()
    if not clean_q:
        return {
            "query": clean_q,
            "total_results": 0,
            "results": {
                "investigations": [],
                "devices": [],
                "integrity_baselines": [],
                "analysis_history": [],
            },
        }

    pattern = f"%{clean_q}%"
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM investigations
            WHERE title LIKE ? OR description LIKE ? OR case_ref LIKE ? OR findings_summary LIKE ?
            ORDER BY created_at DESC
            """,
            (pattern, pattern, pattern, pattern),
        )
        investigations = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT * FROM devices
            WHERE hostname LIKE ? OR ip_address LIKE ? OR mac_address LIKE ? OR observation_source LIKE ?
            ORDER BY last_seen DESC
            """,
            (pattern, pattern, pattern, pattern),
        )
        devices = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT * FROM integrity_baselines
            WHERE filename LIKE ? OR sha256 LIKE ? OR notes LIKE ?
            ORDER BY recorded_at DESC
            """,
            (pattern, pattern, pattern),
        )
        integrity_baselines = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT * FROM analysis_history
            WHERE filename LIKE ? OR operation_type LIKE ? OR details LIKE ?
            ORDER BY id DESC
            """,
            (pattern, pattern, pattern),
        )
        analysis_history = [dict(row) for row in cursor.fetchall()]

        total_results = (
            len(investigations)
            + len(devices)
            + len(integrity_baselines)
            + len(analysis_history)
        )

        return {
            "query": clean_q,
            "total_results": total_results,
            "results": {
                "investigations": investigations,
                "devices": devices,
                "integrity_baselines": integrity_baselines,
                "analysis_history": analysis_history,
            },
        }
    finally:
        conn.close()


# --- Steganography Lab API ---
@app.post("/api/stego/embed")
async def api_embed_secret(
    file: UploadFile = File(...),
    secret: str = Form(...),
):
    safe_name = _sanitize_filename(file.filename)
    file_bytes = await _read_limited(file)
    file_path = (UPLOAD_DIR / safe_name).resolve()
    if not str(file_path).startswith(str(UPLOAD_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid filename")

    encoded_id = uuid.uuid4().hex[:8]
    out_name = f"encoded_{encoded_id}_{safe_name.rsplit('.', 1)[0]}.png"
    output_path = (UPLOAD_DIR / out_name).resolve()
    if not str(output_path).startswith(str(UPLOAD_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid output path")

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    try:
        success, msg = await asyncio.to_thread(embed_secret_in_image, str(file_path), secret, str(output_path))
        if not success:
            raise HTTPException(status_code=400, detail=msg)

        # Read the encoded output image as base64 so client can download it directly in-memory,
        # completely solving multi-instance serverless ephemeral /tmp storage isolation.
        with open(output_path, "rb") as out_fp:
            encoded_bytes = out_fp.read()
        image_data = f"data:image/png;base64,{base64.b64encode(encoded_bytes).decode('ascii')}"

        return {
            "success": True,
            "message": msg,
            "filename": output_path.name,
            "download_url": f"/api/stego/download/{output_path.name}",
            "image_data": image_data,
        }
    finally:
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass


@app.get("/api/stego/download/{filename}")
async def api_download_stego(filename: str):
    safe_name = _sanitize_filename(filename)
    file_path = (UPLOAD_DIR / safe_name).resolve()
    if not str(file_path).startswith(str(UPLOAD_DIR.resolve())) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="image/png", filename=safe_name)


@app.post("/api/stego/extract")
async def api_extract_secret(file: UploadFile = File(...)):
    safe_name = _sanitize_filename(file.filename)
    file_bytes = await _read_limited(file)
    file_path = (UPLOAD_DIR / safe_name).resolve()
    if not str(file_path).startswith(str(UPLOAD_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid filename")

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    try:
        success, result = await asyncio.to_thread(extract_secret_from_image, str(file_path))
        if not success:
            raise HTTPException(status_code=400, detail=result)
        return {"success": True, "secret": result}
    finally:
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass


# --- Image Forensics API ---
@app.post("/api/forensics/analyze")
async def api_forensics_analyze(file: UploadFile = File(...)):
    safe_name = _sanitize_filename(file.filename)
    file_bytes = await _read_limited(file)
    file_path = (UPLOAD_DIR / safe_name).resolve()
    if not str(file_path).startswith(str(UPLOAD_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid filename")

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    try:
        analysis = await asyncio.to_thread(analyze_image_forensics, str(file_path), file_bytes)
        if "error" in analysis:
            raise HTTPException(status_code=400, detail=analysis["error"])
        return analysis
    finally:
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass


# --- Integrity Verification API ---
@app.post("/api/integrity/verify")
async def api_integrity_verify(
    file: UploadFile = File(...),
    reference_hash: Optional[str] = Form(None),
):
    safe_name = _sanitize_filename(file.filename)
    file_bytes = await _read_limited(file)
    current_hash = calculate_sha256(file_bytes)

    match = None
    if reference_hash:
        match = current_hash.lower() == reference_hash.strip().lower()

    unique_id = f"HASH-{int(datetime.utcnow().timestamp())}-{uuid.uuid4().hex[:6]}"
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO integrity_baselines (id, filename, sha256, file_size, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                unique_id,
                safe_name,
                current_hash,
                len(file_bytes),
                "Verified via UI",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "filename": safe_name,
        "current_sha256": current_hash,
        "reference_hash": reference_hash,
        "match": match,
        "file_size": len(file_bytes),
    }


# --- Reports Export API ---
@app.get("/api/reports/export")
async def api_export_report():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM investigations")
        investigations = [dict(row) for row in cursor.fetchall()]
        cursor.execute("SELECT * FROM devices")
        devices = [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

    return {
        "report_title": "Net Sentinel Security & Forensics Investigation Report",
        "generated_at": datetime.utcnow().isoformat(),
        "investigations": investigations,
        "devices": devices,
        "caveats": "Generated automatically in Demo / Investigation mode. Findings are based on observed metadata and heuristic indicators.",
    }


# --- Telemetry & Simulation API ---
# Simulation state is persisted in the DB to survive multi-worker restarts.
_SIMULATION_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS simulation_state (
    key TEXT PRIMARY KEY,
    value TEXT
)
"""


def _init_simulation_table() -> None:
    conn = get_db_connection()
    try:
        conn.execute(_SIMULATION_TABLE_DDL)
        conn.commit()
    finally:
        conn.close()


def _get_simulation() -> dict:
    conn = get_db_connection()
    try:
        conn.execute(_SIMULATION_TABLE_DDL)
        cursor = conn.execute("SELECT key, value FROM simulation_state")
        rows = {r[0]: r[1] for r in cursor.fetchall()}
    finally:
        conn.close()
    return {
        "scenario": rows.get("scenario"),
        "active": rows.get("active") == "1",
        "start_time": rows.get("start_time"),
    }


def _set_simulation(scenario: Optional[str], active: bool, start_time: Optional[str]) -> None:
    conn = get_db_connection()
    try:
        conn.execute(_SIMULATION_TABLE_DDL)
        for key, value in [
            ("scenario", scenario or ""),
            ("active", "1" if active else "0"),
            ("start_time", start_time or ""),
        ]:
            conn.execute(
                "INSERT OR REPLACE INTO simulation_state (key, value) VALUES (?, ?)",
                (key, value),
            )
        conn.commit()
    finally:
        conn.close()


@app.post("/api/telemetry/simulate")
async def api_telemetry_simulate(scenario: str = Form(...)):
    """Start or stop a safe, simulated security incident scenario."""
    valid = {"spike", "portscan", "bruteforce", "reset"}
    if scenario not in valid:
        raise HTTPException(status_code=400, detail="Invalid attack scenario")

    if scenario == "reset":
        await asyncio.to_thread(_set_simulation, None, False, None)
        return {"success": True, "message": "Simulation reset to baseline."}

    start_time = datetime.utcnow().isoformat()
    await asyncio.to_thread(_set_simulation, scenario, True, start_time)

    simulated_events: list = []
    if scenario == "spike":
        simulated_events = [
            {
                "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
                "severity": "warning",
                "rule_id": "NET-RULE-SPIKE",
                "src_ip": "192.0.2.50",
                "dst_ip": "192.168.1.1",
                "observed_label": "High Bandwidth Data Burst (850 Mbps)",
                "recommended_action": "Inspect egress routes for data exfiltration.",
            }
        ]
    elif scenario == "portscan":
        simulated_events = [
            {
                "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
                "severity": "danger",
                "rule_id": "NET-RULE-PORT-SCAN",
                "src_ip": "192.0.2.10",
                "dst_ip": "192.168.1.50",
                "observed_label": "Rapid SYN Scan across 512 ports",
                "recommended_action": "Block source IP 192.0.2.10 at firewall perimeter.",
            }
        ]
    elif scenario == "bruteforce":
        simulated_events = [
            {
                "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
                "severity": "danger",
                "rule_id": "NET-RULE-BRUTEFORCE",
                "src_ip": "192.0.2.88",
                "dst_ip": "192.168.1.10",
                "observed_label": "42 failed SSH authentication attempts in 30s",
                "recommended_action": "Enforce SSH key-only authentication and rate limiting.",
            }
        ]

    return {
        "success": True,
        "scenario": scenario,
        "message": f"Simulation scenario '{scenario}' activated successfully.",
        "simulated_events": simulated_events,
    }


def _build_telemetry_series(time_range: str, sim: dict) -> list:
    """Generate a deterministic, time-seeded telemetry series.

    The RNG seed is derived from the current UTC minute so values drift
    smoothly between requests rather than jumping to a fixed sequence.
    All timestamps are UTC ISO 8601 strings.
    """
    import math
    import random

    _RANGE_CONFIG = {
        "15m": (15, 60),
        "1h":  (12, 300),
        "6h":  (18, 1200),
        "24h": (24, 3600),
    }
    num_points, step = _RANGE_CONFIG.get(time_range, (12, 300))

    now_ts = int(datetime.utcnow().timestamp())
    # Seed changes once per minute so consecutive polls within the same minute
    # return identical data (no flicker), but the series drifts over time.
    seed = now_ts // 60
    rng = random.Random(seed)

    series = []
    for i in range(num_points):
        ts = now_ts - ((num_points - 1 - i) * step)
        dt_iso = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Smooth sinusoidal base with small random jitter.
        phase = (ts / step) * 0.4
        inbound  = 25.0 + math.sin(phase) * 10.0 + rng.uniform(-2.0, 2.0)
        outbound = 12.0 + math.cos(phase) * 5.0  + rng.uniform(-1.0, 1.0)
        pps      = int(700 + math.sin(phase * 0.8) * 200 + rng.uniform(-30, 30))
        latency  = 18.0 + math.cos(phase * 0.6) * 6.0 + rng.uniform(-1.5, 1.5)

        if sim["active"] and i >= num_points - 4:
            scenario = sim["scenario"]
            if scenario == "spike":
                inbound *= 4.5
                pps = int(pps * 3.2)
            elif scenario == "portscan":
                pps = int(pps * 5.0)
                latency *= 2.8
            elif scenario == "bruteforce":
                latency *= 4.0
                outbound *= 2.5

        series.append({
            "timestamp": dt_iso,
            "inbound_mbps": round(max(0.0, inbound), 2),
            "outbound_mbps": round(max(0.0, outbound), 2),
            "packets_per_sec": max(0, pps),
            "latency_ms": round(max(0.0, latency), 1),
        })

    return series


@app.get("/api/telemetry")
async def api_telemetry(time_range: Literal["15m", "1h", "6h", "24h"] = Query("1h", alias="range")):
    """Return time-series network telemetry data with active simulation anomalies.

    All timestamps are UTC ISO 8601. Values are always finite positive numbers.
    The series is generated off the event loop thread.
    """
    sim = await asyncio.to_thread(_get_simulation)
    series = await asyncio.to_thread(_build_telemetry_series, time_range, sim)

    return {
        "range": time_range,
        "source": "DEMO DATA (Standalone Telemetry Simulator)",
        "simulation_active": sim["active"],
        "active_scenario": sim["scenario"] or None,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "series": series,
    }


# --- Network Security Analytics API ---
@app.get("/api/analytics")
async def api_analytics(time_range: Literal["24H", "7D", "30D", "90D"] = Query("24H", alias="range")):
    """Return aggregated network security analytics metrics, 12-point mini charts, and telemetry curve."""
    import random
    import math

    # Seed deterministically by day/hour for consistent rendering
    now_ts = int(datetime.utcnow().timestamp())
    seed_offset = {"24H": 1, "7D": 7, "30D": 30, "90D": 90}.get(time_range, 1)
    rng = random.Random(now_ts // 3600 + seed_offset)

    # Base ranges and intervals
    labels_map = {
        "24H": ("Last 24 hours compared with the previous 24 hours", 24 * 3600, 2 * 3600, "%H:00"),
        "7D":  ("Last 7 days compared with the previous 7 days", 7 * 86400, 14 * 3600, "%b %d"),
        "30D": ("Last 30 days compared with the previous 30 days", 30 * 86400, 60 * 3600, "%b %d"),
        "90D": ("Last 90 days compared with the previous 90 days", 90 * 86400, 180 * 3600, "%b %d"),
    }
    comp_subline, total_sec, step_sec, date_fmt = labels_map.get(time_range, labels_map["24H"])

    # 1. Throughput (Mbps)
    base_tp = {"24H": 34.2, "7D": 41.8, "30D": 38.5, "90D": 45.1}[time_range]
    tp_val = round(base_tp + rng.uniform(-1.5, 2.5), 1)
    tp_pct = round(rng.uniform(-4.2, 8.6), 1)
    tp_bars = [round(max(10.0, base_tp + math.sin(i * 0.6) * 12 + rng.uniform(-3, 3)), 1) for i in range(12)]

    # 2. Threat Events
    base_threats = {"24H": 14, "7D": 89, "30D": 342, "90D": 1120}[time_range]
    threat_val = int(base_threats + rng.randint(-3, 5))
    threat_pct = round(rng.uniform(-12.5, 18.4), 1)
    threat_bars = [max(1, int((base_threats / 12) + math.sin(i * 0.8) * 4 + rng.randint(-2, 3))) for i in range(12)]

    # 3. Active Hosts
    base_hosts = {"24H": 48, "7D": 124, "30D": 310, "90D": 850}[time_range]
    hosts_val = int(base_hosts + rng.randint(-2, 6))
    hosts_diff = rng.randint(-5, 14)
    hosts_bars = [max(5, int((base_hosts / 12) * 1.5 + math.cos(i * 0.5) * 8 + rng.randint(-3, 3))) for i in range(12)]

    # 4. Latency (ms)
    base_lat = {"24H": 18.4, "7D": 19.2, "30D": 21.0, "90D": 22.8}[time_range]
    lat_val = round(base_lat + rng.uniform(-1.0, 1.8), 1)
    lat_diff = round(rng.uniform(-2.5, 3.2), 1)
    lat_bars = [round(max(5.0, base_lat + math.cos(i * 0.7) * 4 + rng.uniform(-1.5, 1.5)), 1) for i in range(12)]

    # Timeline series for main chart (12 evenly spaced points across interval)
    main_series = []
    for i in range(12):
        ts = now_ts - ((11 - i) * step_sec)
        dt_label = datetime.utcfromtimestamp(ts).strftime(date_fmt)
        in_val = round(max(5.0, base_tp * 0.9 + math.sin(i * 0.55) * 14.0 + rng.uniform(-3, 3)), 1)
        out_val = round(max(3.0, (base_tp * 0.45) + math.cos(i * 0.55) * 7.0 + rng.uniform(-2, 2)), 1)
        main_series.append({
            "timestamp": dt_label,
            "inbound_mbps": in_val,
            "outbound_mbps": out_val,
        })

    return {
        "range": time_range,
        "comparison_subline": comp_subline,
        "metrics": {
            "throughput": {
                "label": "Network Throughput",
                "value": tp_val,
                "unit": "Mbps",
                "change_pct": tp_pct,
                "favorable": tp_pct >= 0,
                "bars": tp_bars
            },
            "threats": {
                "label": "Threat Events",
                "value": threat_val,
                "unit": "events",
                "change_pct": threat_pct,
                "favorable": threat_pct <= 0, # Fewer threats is favorable
                "bars": threat_bars
            },
            "hosts": {
                "label": "Active Hosts",
                "value": hosts_val,
                "unit": "hosts",
                "change_abs": hosts_diff,
                "favorable": hosts_diff >= 0,
                "bars": hosts_bars
            },
            "latency": {
                "label": "Average Latency",
                "value": lat_val,
                "unit": "ms",
                "change_diff": lat_diff,
                "favorable": lat_diff <= 0, # Lower latency is favorable
                "bars": lat_bars
            }
        },
        "chart_series": main_series,
        "source": "DEMO DATA (Security Analytics Aggregator)"
    }


@app.get("/api/analytics/export")
async def api_analytics_export(time_range: Literal["24H", "7D", "30D", "90D"] = Query("24H", alias="range")):
    """Export currently selected range analytics as CSV data."""
    import io
    import csv

    analytics = await api_analytics(time_range=time_range)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Net Sentinel Network Security Analytics Report"])
    writer.writerow(["Range", time_range])
    writer.writerow(["Comparison Period", analytics["comparison_subline"]])
    writer.writerow(["Generated At (UTC)", datetime.utcnow().isoformat()])
    writer.writerow([])
    writer.writerow(["Metric", "Current Value", "Unit", "Change Indicator"])
    m = analytics["metrics"]
    writer.writerow([m["throughput"]["label"], m["throughput"]["value"], m["throughput"]["unit"], f"{m['throughput']['change_pct']}%"])
    writer.writerow([m["threats"]["label"], m["threats"]["value"], m["threats"]["unit"], f"{m['threats']['change_pct']}%"])
    writer.writerow([m["hosts"]["label"], m["hosts"]["value"], m["hosts"]["unit"], f"{m['hosts']['change_abs']} hosts"])
    writer.writerow([m["latency"]["label"], m["latency"]["value"], m["latency"]["unit"], f"{m['latency']['change_diff']} ms"])
    writer.writerow([])
    writer.writerow(["Timestamp Interval", "Inbound Traffic (Mbps)", "Outbound Traffic (Mbps)"])
    for pt in analytics["chart_series"]:
        writer.writerow([pt["timestamp"], pt["inbound_mbps"], pt["outbound_mbps"]])

    from fastapi.responses import Response
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=net_sentinel_analytics_{time_range.lower()}.csv"}
    )
