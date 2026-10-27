"""FastAPI application for Net Sentinel.

Network Intelligence. Threat Detection. Digital Forensics.
"""

import asyncio
import io
import logging
import os
import pathlib
import sqlite3
import time
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "").split(",") or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
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
    return response


app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    UPLOAD_DIR = pathlib.Path("/tmp/uploads")
else:
    UPLOAD_DIR = pathlib.Path("data/uploads")
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
async def dashboard_spa(request: Request):
    """Serve the single-page Net Sentinel security dashboard."""
    return templates.TemplateResponse(request, "index.html", {})


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
        text = content.decode("utf-8")
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
        text = content.decode("utf-8")
        events = await asyncio.to_thread(analyze_logs, text)
        summary = await asyncio.to_thread(summarize, events)
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
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted for network analysis")
    try:
        content = await _read_limited(file)
        text = content.decode("utf-8")
        events = await asyncio.to_thread(analyze_logs, text)
        summary = await asyncio.to_thread(summarize, events)
        return {"events": events, "summary": summary}
    except HTTPException:
        raise
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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
    inv_id = f"INV-{int(datetime.utcnow().timestamp())}"
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO investigations (id, title, description, case_ref, status)
            VALUES (?, ?, ?, ?, 'Open')
            """,
            (inv_id, title, description, case_ref),
        )
        conn.commit()
    finally:
        conn.close()
    return {"id": inv_id, "title": title, "status": "Open", "message": "Investigation created successfully"}


# --- Steganography Lab API ---
@app.post("/api/stego/embed")
async def api_embed_secret(
    file: UploadFile = File(...),
    secret: str = Form(...),
):
    file_bytes = await _read_limited(file)
    file_path = UPLOAD_DIR / file.filename
    output_path = UPLOAD_DIR / f"encoded_{file.filename.rsplit('.', 1)[0]}.png"

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    success, msg = await asyncio.to_thread(embed_secret_in_image, str(file_path), secret, str(output_path))
    if not success:
        raise HTTPException(status_code=400, detail=msg)

    return {
        "success": True,
        "message": msg,
        "download_url": f"/api/stego/download/{output_path.name}",
    }


@app.get("/api/stego/download/{filename}")
async def api_download_stego(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="image/png", filename=filename)


@app.post("/api/stego/extract")
async def api_extract_secret(file: UploadFile = File(...)):
    file_bytes = await _read_limited(file)
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    success, result = await asyncio.to_thread(extract_secret_from_image, str(file_path))
    if not success:
        raise HTTPException(status_code=400, detail=result)

    return {"success": True, "secret": result}


# --- Image Forensics API ---
@app.post("/api/forensics/analyze")
async def api_forensics_analyze(file: UploadFile = File(...)):
    file_bytes = await _read_limited(file)
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    analysis = await asyncio.to_thread(analyze_image_forensics, str(file_path), file_bytes)
    if "error" in analysis:
        raise HTTPException(status_code=400, detail=analysis["error"])
    return analysis


# --- Integrity Verification API ---
@app.post("/api/integrity/verify")
async def api_integrity_verify(
    file: UploadFile = File(...),
    reference_hash: Optional[str] = Form(None),
):
    file_bytes = await _read_limited(file)
    current_hash = calculate_sha256(file_bytes)

    match = None
    if reference_hash:
        match = current_hash.lower() == reference_hash.strip().lower()

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO integrity_baselines (id, filename, sha256, file_size, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                f"HASH-{int(datetime.utcnow().timestamp())}",
                file.filename,
                current_hash,
                len(file_bytes),
                "Verified via UI",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "filename": file.filename,
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


@app.get("/api/telemetry")
async def api_telemetry(time_range: Literal["15m", "1h", "6h", "24h"] = Query("1h", alias="range")):
    """Return time-series network telemetry data with active simulation anomalies."""
    import random

    sim = await asyncio.to_thread(_get_simulation)

    now = int(datetime.utcnow().timestamp())
    num_points = 12
    step = 300
    if time_range == "15m":
        num_points = 15
        step = 60
    elif time_range == "6h":
        num_points = 18
        step = 1200
    elif time_range == "24h":
        num_points = 24
        step = 3600

    series = []
    rng = random.Random(42)
    for i in range(num_points):
        ts = now - ((num_points - 1 - i) * step)
        dt_str = datetime.utcfromtimestamp(ts).strftime("%H:%M:%S")
        inbound = rng.uniform(12.5, 45.8)
        outbound = rng.uniform(5.2, 28.4)
        pps = int(rng.uniform(320, 1450))
        latency = rng.uniform(11.2, 38.6)

        if sim["active"] and i >= num_points - 4:
            if sim["scenario"] == "spike":
                inbound *= 4.5
                pps = int(pps * 3.2)
            elif sim["scenario"] == "portscan":
                pps = int(pps * 5.0)
                latency *= 2.8
            elif sim["scenario"] == "bruteforce":
                latency *= 4.0
                outbound *= 2.5

        series.append(
            {
                "timestamp": dt_str,
                "inbound_mbps": round(inbound, 2),
                "outbound_mbps": round(outbound, 2),
                "packets_per_sec": int(pps),
                "latency_ms": round(latency, 1),
            }
        )

    return {
        "range": time_range,
        "source": "DEMO DATA (Standalone Telemetry Simulator)",
        "simulation_active": sim["active"],
        "active_scenario": sim["scenario"],
        "series": series,
    }
