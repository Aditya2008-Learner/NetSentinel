"""FastAPI application for Net Sentinel.

Network Intelligence. Threat Detection. Digital Forensics.
"""

import os
import sqlite3
import pathlib
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .services import analyze_logs, summarize
from .database import get_db_connection, init_db
from .stego_service import (
    calculate_sha256,
    embed_secret_in_image,
    extract_secret_from_image,
    analyze_image_forensics,
)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Net Sentinel", version="1.0.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Ensure uploads directory exists (use /tmp on Vercel)
if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    UPLOAD_DIR = pathlib.Path("/tmp/uploads")
else:
    UPLOAD_DIR = pathlib.Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/", response_class=HTMLResponse)
async def dashboard_spa(request: Request):
    """Serve the single-page Net Sentinel security dashboard."""
    return templates.TemplateResponse(
        request,
        "index.html",
        {},
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
        raise HTTPException(
            status_code=400, detail="Only CSV files are accepted for analysis"
        )
    try:
        content = await file.read()
        text = content.decode("utf-8")
        return analyze_logs(text)
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
            {
                "events": [],
                "summary": None,
                "error": "Only CSV files are accepted for analysis.",
            },
            status_code=400,
        )
    try:
        content = await file.read()
        text = content.decode("utf-8")
        events = analyze_logs(text)
        summary = summarize(events)
    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "events": [],
                "summary": None,
                "error": str(exc),
            },
            status_code=500,
        )
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "events": events,
            "summary": summary,
        },
    )


@app.post("/api/network/analyze", response_model=dict)
async def api_analyze_network_logs(file: UploadFile = File(...)):
    """Upload and analyze network connection logs CSV."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400, detail="Only CSV files are accepted for network analysis"
        )
    try:
        content = await file.read()
        text = content.decode("utf-8")
        events = analyze_logs(text)
        summary = summarize(events)
        return {"events": events, "summary": summary}
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
    file_path = UPLOAD_DIR / file.filename
    output_path = UPLOAD_DIR / f"encoded_{file.filename.rsplit('.', 1)[0]}.png"
    
    with open(file_path, "wb") as f:
        f.write(await file.read())

    success, msg = embed_secret_in_image(str(file_path), secret, str(output_path))
    if not success:
        raise HTTPException(status_code=400, detail=msg)

    return {
        "success": True,
        "message": msg,
        "download_url": f"/api/stego/download/{output_path.name}"
    }


@app.get("/api/stego/download/{filename}")
async def api_download_stego(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="image/png", filename=filename)


@app.post("/api/stego/extract")
async def api_extract_secret(file: UploadFile = File(...)):
    file_path = UPLOAD_DIR / file.filename
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    success, result = extract_secret_from_image(str(file_path))
    if not success:
        raise HTTPException(status_code=400, detail=result)

    return {"success": True, "secret": result}


# --- Image Forensics API ---
@app.post("/api/forensics/analyze")
async def api_forensics_analyze(file: UploadFile = File(...)):
    file_bytes = await file.read()
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    analysis = analyze_image_forensics(str(file_path), file_bytes)
    if "error" in analysis:
        raise HTTPException(status_code=400, detail=analysis["error"])
    return analysis


# --- Integrity Verification API ---
@app.post("/api/integrity/verify")
async def api_integrity_verify(
    file: UploadFile = File(...),
    reference_hash: Optional[str] = Form(None),
):
    file_bytes = await file.read()
    current_hash = calculate_sha256(file_bytes)
    
    match = None
    if reference_hash:
        match = current_hash.lower() == reference_hash.strip().lower()

    # Save to baseline db history
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO integrity_baselines (id, filename, sha256, file_size, notes)
        VALUES (?, ?, ?, ?, ?)
        """,
        (f"HASH-{int(datetime.utcnow().timestamp())}", file.filename, current_hash, len(file_bytes), "Verified via UI"),
    )
    conn.commit()
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
        "caveats": "Generated automatically in Demo / Investigation mode. Findings are based on observed metadata and heuristic indicators."
    }


# In-memory active simulation state
ACTIVE_SIMULATION = {
    "scenario": None, # "spike", "portscan", "bruteforce"
    "active": False,
    "start_time": None
}

@app.post("/api/telemetry/simulate")
async def api_telemetry_simulate(scenario: str = Form(...)):
    """Start or stop a safe, simulated security incident scenario."""
    if scenario not in ["spike", "portscan", "bruteforce", "reset"]:
        raise HTTPException(status_code=400, detail="Invalid attack scenario")
    
    if scenario == "reset":
        ACTIVE_SIMULATION["scenario"] = None
        ACTIVE_SIMULATION["active"] = False
        return {"success": True, "message": "Simulation reset to baseline."}

    ACTIVE_SIMULATION["scenario"] = scenario
    ACTIVE_SIMULATION["active"] = True
    ACTIVE_SIMULATION["start_time"] = datetime.utcnow().isoformat()
    
    simulated_events = []
    if scenario == "spike":
        simulated_events = [{
            "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
            "severity": "warning",
            "rule_id": "NET-RULE-SPIKE",
            "src_ip": "192.0.2.50",
            "dst_ip": "192.168.1.1",
            "observed_label": "High Bandwidth Data Burst (850 Mbps)",
            "recommended_action": "Inspect egress routes for data exfiltration."
        }]
    elif scenario == "portscan":
        simulated_events = [{
            "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
            "severity": "danger",
            "rule_id": "NET-RULE-PORT-SCAN",
            "src_ip": "192.0.2.10",
            "dst_ip": "192.168.1.50",
            "observed_label": "Rapid SYN Scan across 512 ports",
            "recommended_action": "Block source IP 192.0.2.10 at firewall perimeter."
        }]
    elif scenario == "bruteforce":
        simulated_events = [{
            "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
            "severity": "danger",
            "rule_id": "NET-RULE-BRUTEFORCE",
            "src_ip": "192.0.2.88",
            "dst_ip": "192.168.1.10",
            "observed_label": "42 failed SSH authentication attempts in 30s",
            "recommended_action": "Enforce SSH key-only authentication and rate limiting."
        }]

    return {
        "success": True,
        "scenario": scenario,
        "message": f"Simulation scenario '{scenario}' activated successfully.",
        "simulated_events": simulated_events
    }


@app.get("/api/telemetry")
async def api_telemetry(time_range: str = Query("1h", alias="range")):
    """Return time-series network telemetry data with active simulation anomalies."""
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
    import random
    rng = random.Random(42)
    for i in range(num_points):
        ts = now - ((num_points - 1 - i) * step)
        dt_str = datetime.utcfromtimestamp(ts).strftime("%H:%M:%S")
        inbound = rng.uniform(12.5, 45.8)
        outbound = rng.uniform(5.2, 28.4)
        pps = int(rng.uniform(320, 1450))
        latency = rng.uniform(11.2, 38.6)

        # Inject anomalies if simulation is active near the end of the series
        if ACTIVE_SIMULATION["active"] and i >= num_points - 4:
            if ACTIVE_SIMULATION["scenario"] == "spike":
                inbound *= 4.5
                pps *= 3.2
            elif ACTIVE_SIMULATION["scenario"] == "portscan":
                pps *= 5.0
                latency *= 2.8
            elif ACTIVE_SIMULATION["scenario"] == "bruteforce":
                latency *= 4.0
                outbound *= 2.5

        series.append({
            "timestamp": dt_str,
            "inbound_mbps": round(inbound, 2),
            "outbound_mbps": round(outbound, 2),
            "packets_per_sec": int(pps),
            "latency_ms": round(latency, 1)
        })

    return {
        "range": time_range,
        "source": "DEMO DATA (Standalone Telemetry Simulator)",
        "simulation_active": ACTIVE_SIMULATION["active"],
        "active_scenario": ACTIVE_SIMULATION["scenario"],
        "series": series
    }
