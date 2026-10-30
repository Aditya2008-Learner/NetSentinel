# Net Sentinel — Cybersecurity Monitoring, Threat Detection & Digital Forensics Platform

**Network Intelligence. Threat Detection. Digital Forensics.**

Net Sentinel is an enterprise-grade, web-based cybersecurity platform designed for security operations centers, incident responders, academic research environments, and university IDEATHON 2026 presentations. It combines authorized network traffic monitoring and heuristic threat detection with digital forensics capabilities including steganography embedding/extraction, image forensic entropy analysis, and SHA-256 file integrity verification.

- **Live Demo**: [https://net-sentinel-zeta.vercel.app/](https://net-sentinel-zeta.vercel.app/)

---

## Core Routes

- `/`: **Enterprise Product Landing Page** — Animated HTML5 canvas network topology with dynamic physics, interactive capabilities overview, incident response workflow walkthrough, live analysis demo preview, and direct entry points to the dashboard.
- `/dashboard`: **Unified Cybersecurity & Digital Forensics Dashboard SPA** — Mission-critical single-page application for real-time log ingestion, heuristic threat analysis, host device inventory management, digital investigations case tracking, steganographic analysis, image forensics, and baseline integrity verification.

---

## Key Features

1. **Enterprise Landing Page & Interactive Network Topology**: High-performance animated HTML5 canvas showcasing dynamic network nodes, packet pulses, interactive cursor repulsion/connection dynamics, feature highlights, and interactive preview workflows.
2. **Heuristic Threat Detection Engine**: Ingests network connection logs (CSV) to automatically detect threats across 5 distinct heuristics:
   - **Port Scans**: High volume of unique destination ports targeted on single hosts.
   - **Source Bursts**: Anomalous traffic volume spikes originating from single source IPs.
   - **Destination Floods**: Concentrated connection floods overwhelming target endpoints.
   - **Brute-Force SSH/RDP**: Repeated authentication attempts targeting administrative service ports (22, 3389).
   - **Large Transfers**: High-volume data transfers (>10 MB) signaling potential data exfiltration.
   Provides explainable threat ratings, severity scoring, and actionable remediation guidance.
3. **Dynamic Device Inventory Management**: Full CRUD capabilities (list, add, search, and delete) for tracked host endpoints, IP/MAC addresses, observation sources, and first/last-seen timestamps.
4. **Real-Time Global Search**: Unified multi-entity search across cases, devices, integrity baselines, and historical analysis runs with real-time modal previews and deep-link navigation.
5. **Analysis History & Audit Logging**: Persisted analysis runs recording overall threat levels, detected anomaly counts, categorized breakdowns, timestamped records, and historical log lookups.
6. **Digital Investigations Workspace**: Case management system to create investigation cases, assign reference numbers, track findings, maintain audit histories, and export comprehensive case data in JSON format.
7. **Steganography Lab**: LSB (Least Significant Bit) steganography suite with separate embed and extract workflows, client-side payload capacity validation, lossless PNG processing, and ephemeral base64 streaming for instant artifact retrieval.
8. **Image Forensics & Entropy Analysis**: Heuristic variance scoring, LSB noise distribution inspection, dimensional integrity verification, and lossless vs. lossy compression checks to identify steganographic anomalies.
9. **File Integrity Verification**: SHA-256 cryptographic hash computation with baseline registration and matching to verify system file integrity and flag tampering.
10. **Demo & Standalone Mode**: Zero kernel-driver dependencies; fully operational standalone architecture requiring no specialized packet-capture hardware or root privileges.

---

## Architecture

- **Backend**: FastAPI (Python 3.10+) utilizing asynchronous routing, strict Pydantic schemas, and modular domain services (`app/services.py`, `app/stego_service.py`, `app/database.py`).
- **Persistence**: SQLite database (`data/netsentinel.db`) maintaining schema-enforced tables for investigations, device records, integrity baselines, and analysis history.
- **Image Processing**: Pillow (PIL) for byte-level LSB encoding, decoding, RGB matrix validation, and statistical entropy analysis.
- **Frontend**: Responsive Single-Page Application (SPA) and Enterprise Landing Page built with semantic HTML5, custom CSS design systems, dynamic view routing, and vanilla JavaScript (`static/landing.js`, `static/app.js`).
- **Testing**: Comprehensive PyTest automation suite covering HTTP endpoints, heuristics, CSV ingestion, and template rendering.

---

## Prerequisites

- Python 3.10+ (Python 3.11 recommended)
- pip

---

## Installation & Setup

1. Clone or navigate to the project directory:
   ```bash
   cd NetSentinel
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Initialize the SQLite database:
   ```bash
   python -m app.database
   ```

4. Generate sample network log data:
   ```bash
   python scripts/generate_sample_data.py
   ```

---

## Running the Application

Start the local server using Python:
```bash
python main.py
```
*(Or via uvicorn directly: `uvicorn app.main:app --reload`)*

Access the platform through your browser:
- **Landing Page**: `http://localhost:8000/`
- **Dashboard**: `http://localhost:8000/dashboard`
- **Interactive API Docs**: `http://localhost:8000/docs`
- **System Health Probe**: `http://localhost:8000/healthz`

---

## Testing

Run the automated test suite with pytest:
```bash
pytest
```

The test suite includes 48 pytest tests covering API endpoints, heuristics, CSV parsing, and route rendering:
- **API Endpoints**: CRUD operations and endpoints for `/api/devices`, `/api/investigations`, `/api/baselines`, `/api/network/analyze`, `/api/search`, and `/healthz`.
- **Heuristic Threat Detection**: Detection accuracy for all 5 heuristic algorithms (port scans, source bursts, destination floods, brute-force SSH/RDP, and large transfers).
- **CSV Parsing**: Resilient ingestion of network connection logs, header variations, and malformed records.
- **Steganography & Forensics**: LSB embed/extract validation, payload overflow boundaries, and entropy variance calculations.
- **Route Rendering**: Full HTML template rendering for `/` (Landing Page) and `/dashboard` (Dashboard SPA).

---

## SDG Alignment (SRMIST IDEATHON 2026)

- **SDG 9 (Industry, Innovation and Infrastructure)**: Builds accessible, lightweight cybersecurity infrastructure for educational and small organizational networks without requiring expensive enterprise security suites.
- **SDG 16 (Peace, Justice and Strong Institutions)**: Promotes digital trust, transparent investigations, integrity verification, and verifiable forensics evidence.

---

## Project Structure

```
NetSentinel/
  app/
    __init__.py
    database.py       # SQLite database initialization, schemas & connection helpers
    main.py           # FastAPI web application routes, API handlers & health probes
    services.py       # Heuristic threat detection engine, log parser & inventory service
    stego_service.py  # LSB steganography engine, metadata extractor & entropy scoring
  data/
    netsentinel.db    # SQLite persistence file
    sample.csv        # Sample network connection logs with benign and threat patterns
  scripts/
    generate_sample_data.py  # Synthetic network traffic generator for demonstrations
  static/
    app.js            # Dashboard SPA view navigation, AJAX handling & UI state
    favicon.svg       # Platform SVG branding icon
    landing.css       # Enterprise landing page styling & responsive grid layouts
    landing.js        # HTML5 canvas interactive network topology particle animation
    social-card.svg   # Open Graph social preview asset
    styles.css        # Professional dark cybersecurity dashboard theme & layout
  templates/
    index.html        # Unified cybersecurity dashboard SPA template
    landing.html      # Enterprise product landing page template
  tests/
    __init__.py
    test_api.py       # Endpoint, route rendering, and CRUD integration tests
    test_services.py  # Threat detection heuristic and forensics unit tests
  main.py             # Root launcher script with uvicorn configuration
  pytest.ini          # Pytest configuration and environment paths
  requirements.txt    # Production & test dependencies (FastAPI, Uvicorn, Pillow, pytest)
  README.md           # Comprehensive project documentation
```
