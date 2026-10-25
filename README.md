# Net Sentinel — Cybersecurity Monitoring, Threat Detection & Digital Forensics Platform

**Network Intelligence. Threat Detection. Digital Forensics.**

Net Sentinel is a professional, web-based cybersecurity platform designed for security operations centers, academic environments, and university IDEATHON 2026 presentations. It combines authorized network traffic monitoring and heuristic threat detection with digital forensics capabilities including steganography embedding/extraction, image forensic entropy analysis, and SHA-256 file integrity verification.

---

## Key Features

1. **Professional Cybersecurity Dashboard**: Dark cybersecurity theme with deep navy/charcoal styling, cyan/teal accents, persistent sidebar navigation, system status indicators, and summary metrics.
2. **Network Security & Heuristic Threat Detection**: Upload network connection logs (CSV) to automatically detect port scans, source bursts, destination floods, SSH/RDP brute-force attempts, and large data transfers with explainable guidance and recommended investigation steps.
3. **Device Inventory**: Track observed hosts, IP/MAC addresses, and observation sources.
4. **Digital Investigations Workspace**: Create cases, assign case reference numbers, track findings, and maintain an audit history.
5. **Steganography Lab**: Separate embed and extract workflows using LSB (Least Significant Bit) manipulation on lossless PNG images with capacity validation.
6. **Image Forensics**: Inspect image metadata, dimensions, file hashes, and statistical LSB noise distribution to identify potential steganographic indicators.
7. **File Integrity Verification**: Compute SHA-256 cryptographic hashes and compare files against trusted reference hashes to detect unauthorized alterations.
8. **Investigation Reports & Export**: Export comprehensive case data and audit summaries in JSON format for reporting and presentation.
9. **Demo & Standalone Mode**: Fully functional standalone mode that operates without requiring specialized kernel-level packet capture drivers or root permissions.

---

## Architecture

- **Backend**: FastAPI (Python 3.11+) with asynchronous routing and modular service separation (`app/services.py`, `app/stego_service.py`, `app/database.py`).
- **Persistence**: SQLite database (`data/netsentinel.db`) storing investigations, device records, integrity baselines, and analysis history.
- **Image Processing**: Pillow (PIL) for LSB encoding, decoding, and forensics analysis.
- **Frontend**: Single-Page Application (SPA) layout with dynamic view switching, clean CSS variables, and modular JavaScript (`static/app.js`).
- **Testing**: PyTest suite covering API endpoints and heuristics (`tests/`).

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

Start the development server using the root launcher script:
```bash
py main.py
```
*(Or via uvicorn directly: `uvicorn app.main:app --reload`)*

Open your browser at:
- **Dashboard**: `http://localhost:8000/`
- **Interactive API Docs**: `http://localhost:8000/docs`

---

## Testing

Run the automated test suite using pytest:
```bash
pytest
```

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
    main.py           # FastAPI routes & web endpoints
    database.py       # SQLite database initialization & connection
    services.py       # Heuristic threat detection engine & summarizer
    stego_service.py  # LSB steganography & image forensics analysis
  data/
    netsentinel.db    # SQLite persistence
    sample.csv        # Sample network connection logs
  scripts/
    generate_sample_data.py
  static/
    styles.css        # Professional dark cybersecurity theme
    app.js            # Frontend SPA navigation & API integration
  templates/
    index.html        # Main dashboard layout & sidebar views
  tests/
    test_api.py       # FastAPI endpoint tests
    test_services.py  # Detection heuristics tests
  requirements.txt    # Python dependencies (FastAPI, Pillow, pytest, etc.)
  main.py             # Application entrypoint
  README.md
```
