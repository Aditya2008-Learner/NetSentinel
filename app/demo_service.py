import copy
import io
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False
    Image = None

_BASE_DIR = Path(__file__).resolve().parent.parent
_STATE_FILE = _BASE_DIR / "data" / "demo_state.json"
DEMO_SCENARIOS_DIR = _BASE_DIR / "data" / "scenarios"
DEMO_ARTIFACTS_DIR = _BASE_DIR / "data" / "demo_artifacts"
DEMO_CARRIER_PATH = DEMO_ARTIFACTS_DIR / "demo_carrier.png"
DEMO_STEGO_PATH = DEMO_ARTIFACTS_DIR / "demo_stego_artifact.png"

# Minimal valid 1x1 transparent PNG fallback bytes
_FALLBACK_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00"
    b"\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
)
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

_INITIAL_STATE = {
    "bandwidth_multiplier": 1.0,
    "packet_rate_multiplier": 1.0,
    "active_scenario": None,
    "collector_health": "LIVE",
    "cpu_percent": 14.5,
    "memory_percent": 32.8,
    "latency_ms": 1.8,
    "packet_drop_rate": 0.0001,
    "active_workers": 4,
}

_INITIAL_DEVICES = [
    {
        "id": "DEV-001",
        "ip_address": "192.168.1.1",
        "mac_address": "c8:4c:75:10:20:01",
        "vendor": "Cisco Systems",
        "hostname": "gw-core-01.corp.internal",
        "status": "Active",
        "observation_source": "ARP Table / Gateway",
        "first_seen": "2026-10-15 08:00:00",
        "last_seen": "2026-11-09 12:00:00",
    },
    {
        "id": "DEV-002",
        "ip_address": "192.168.1.10",
        "mac_address": "00:50:56:a1:b2:01",
        "vendor": "VMware Inc.",
        "hostname": "dc01.corp.internal",
        "status": "Active",
        "observation_source": "Active Directory sync",
        "first_seen": "2026-10-15 08:00:00",
        "last_seen": "2026-11-09 12:00:00",
    },
    {
        "id": "DEV-003",
        "ip_address": "192.168.1.50",
        "mac_address": "00:50:56:a1:b2:50",
        "vendor": "Canonical / Ubuntu",
        "hostname": "web-prod-01.corp.internal",
        "status": "Active",
        "observation_source": "NetFlow Exporter",
        "first_seen": "2026-10-16 09:30:00",
        "last_seen": "2026-11-09 12:00:00",
    },
    {
        "id": "DEV-004",
        "ip_address": "192.168.1.60",
        "mac_address": "00:50:56:a1:b2:60",
        "vendor": "Red Hat / PostgreSQL",
        "hostname": "db-cluster-primary.corp.internal",
        "status": "Active",
        "observation_source": "NetFlow Exporter",
        "first_seen": "2026-10-16 09:30:00",
        "last_seen": "2026-11-09 12:00:00",
    },
    {
        "id": "DEV-005",
        "ip_address": "192.168.1.105",
        "mac_address": "3c:22:fb:88:99:aa",
        "vendor": "Apple Inc.",
        "hostname": "macbook-analyst-jdoe.corp.internal",
        "status": "Active",
        "observation_source": "DHCP Lease",
        "first_seen": "2026-11-01 07:45:00",
        "last_seen": "2026-11-09 12:00:00",
    },
    {
        "id": "DEV-006",
        "ip_address": "192.168.1.200",
        "mac_address": "08:00:27:fa:ce:01",
        "vendor": "OffSec Labs / VirtualBox",
        "hostname": "sec-audit-kali.corp.internal",
        "status": "Suspicious",
        "observation_source": "Rogue Port Scan Detector",
        "first_seen": "2026-11-09 09:12:00",
        "last_seen": "2026-11-09 11:45:00",
    },
    {
        "id": "DEV-007",
        "ip_address": "192.168.1.220",
        "mac_address": "b8:27:eb:34:56:78",
        "vendor": "Raspberry Pi Foundation",
        "hostname": "sensor-hvac-server-room.iot.internal",
        "status": "Active",
        "observation_source": "mDNS Beacon",
        "first_seen": "2026-10-20 14:00:00",
        "last_seen": "2026-11-09 12:00:00",
    },
    {
        "id": "DEV-008",
        "ip_address": "192.168.1.240",
        "mac_address": "00:1e:67:d3:4e:90",
        "vendor": "Dell EMC",
        "hostname": "san-storage-vault.corp.internal",
        "status": "Idle",
        "observation_source": "iSCSI Discovery",
        "first_seen": "2026-10-15 08:00:00",
        "last_seen": "2026-11-09 12:00:00",
    },
]

_INITIAL_FLOWS = []
for i in range(55):
    protocols = ["TCP", "UDP", "HTTPS", "DNS", "SSH", "RDP", "ICMP"]
    src_ips = ["192.168.1.105", "192.168.1.10", "192.168.1.50", "192.168.1.60", "192.168.1.200", "203.0.113.88", "198.51.100.14"]
    dst_ips = ["192.168.1.1", "192.168.1.50", "192.168.1.60", "10.0.0.5", "8.8.8.8"]
    _INITIAL_FLOWS.append({
        "timestamp": f"2026-11-09T12:{i % 60:02d}:00Z",
        "src_ip": src_ips[i % len(src_ips)],
        "dst_ip": dst_ips[i % len(dst_ips)],
        "src_port": 1024 + (i * 37) % 60000,
        "dst_port": [80, 443, 53, 22, 3389, 3260][i % 6],
        "protocol": protocols[i % len(protocols)],
        "packets": 10 + (i * 13) % 500,
        "bytes": 512 + (i * 1234) % 65536,
    })

_INITIAL_ALERTS = [
    {
        "alert_id": "ALT-DEMO-001",
        "rule_id": "RULE-BRUTE-FORCE",
        "title": "Repeated SSH Authentication Failures (Brute Force)",
        "severity": "CRITICAL",
        "confidence": 0.96,
        "source_ip": "203.0.113.88",
        "dest_ip": "192.168.1.50",
        "details": "Over 48 consecutive SSH login failures observed within 90 seconds from suspicious external ASN.",
        "status": "OPEN",
        "assigned_analyst": None,
        "detected_at": "2026-11-09T08:15:10Z",
    },
    {
        "alert_id": "ALT-DEMO-002",
        "rule_id": "RULE-PORT-SCAN",
        "title": "Rapid TCP SYN Port Scan Detected",
        "severity": "HIGH",
        "confidence": 0.92,
        "source_ip": "192.168.1.200",
        "dest_ip": "192.168.1.50",
        "details": "Single source queried 64 distinct ports in under 12 seconds targeting web production tier.",
        "status": "OPEN",
        "assigned_analyst": None,
        "detected_at": "2026-11-09T09:15:30Z",
    },
    {
        "alert_id": "ALT-DEMO-003",
        "rule_id": "RULE-EXFIL-DATA",
        "title": "Potential Steganographic Data Exfiltration",
        "severity": "HIGH",
        "confidence": 0.89,
        "source_ip": "192.168.1.105",
        "dest_ip": "198.51.100.14",
        "details": "Outbound PNG upload containing anomalous LSB spatial entropy score of 88.5 and suspicious file name.",
        "status": "ACKNOWLEDGED",
        "assigned_analyst": "Sarah Jenkins",
        "detected_at": "2026-11-08T14:20:00Z",
    },
    {
        "alert_id": "ALT-DEMO-004",
        "rule_id": "RULE-HIGH-BANDWIDTH",
        "title": "Abnormal Off-Hours Database Replication Spike",
        "severity": "MEDIUM",
        "confidence": 0.78,
        "source_ip": "192.168.1.60",
        "dest_ip": "192.168.1.240",
        "details": "Bulk transfer of 4.2 GB detected outside scheduled maintenance window.",
        "status": "ACKNOWLEDGED",
        "assigned_analyst": "Marcus Vance",
        "detected_at": "2026-11-08T22:10:00Z",
    },
    {
        "alert_id": "ALT-DEMO-005",
        "rule_id": "RULE-DNS-TUNNEL",
        "title": "Excessive Subdomain Query Entropy (DNS Tunneling)",
        "severity": "MEDIUM",
        "confidence": 0.74,
        "source_ip": "192.168.1.220",
        "dest_ip": "8.8.8.8",
        "details": "High-frequency TXT lookups against dynamic apex domain with randomized base64 subdomains.",
        "status": "RESOLVED",
        "assigned_analyst": "Elena Rostova",
        "detected_at": "2026-11-07T10:00:00Z",
    },
    {
        "alert_id": "ALT-DEMO-006",
        "rule_id": "RULE-NEW-DEVICE",
        "title": "Unregistered MAC Address on Internal VLAN",
        "severity": "LOW",
        "confidence": 0.65,
        "source_ip": "192.168.1.199",
        "dest_ip": "192.168.1.1",
        "details": "New device with unknown vendor OUI broadcasting DHCP discover packets on VLAN 10.",
        "status": "RESOLVED",
        "assigned_analyst": "Sarah Jenkins",
        "detected_at": "2026-11-06T11:00:00Z",
    },
]

_INITIAL_CASES = [
    {
        "case_id": "CASE-DEMO-001",
        "title": "External SSH Credential Stuffing & Lateral Movement Probe",
        "status": "INVESTIGATING",
        "owner": "Sarah Jenkins (Lead IR Analyst)",
        "summary": "Inbound brute force attack originating from external IP 203.0.113.88 against web-prod-01 followed by internal reconnaissance probes from 192.168.1.200.",
        "created_at": "2026-11-09T08:15:00Z",
        "updated_at": "2026-11-09T11:30:00Z",
        "timeline": [
            {"event_id": 1, "timestamp": "2026-11-09T08:15:10Z", "actor": "NetSentinel Sensor", "action": "Triggered alert ALT-DEMO-001 (SSH Brute Force from 203.0.113.88)", "artifact_ref": "PCAP-20261109-0815.cap"},
            {"event_id": 2, "timestamp": "2026-11-09T08:22:45Z", "actor": "Sarah Jenkins", "action": "Triage alert ALT-DEMO-001 to ACKNOWLEDGED; applied perimeter firewall temporary block", "artifact_ref": "FW-RULE-9941"},
            {"event_id": 3, "timestamp": "2026-11-09T09:05:00Z", "actor": "Marcus Vance", "action": "Extracted auth.log from web-prod-01; verified zero successful authentications occurred", "artifact_ref": "SHA256:5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"},
            {"event_id": 4, "timestamp": "2026-11-09T11:30:00Z", "actor": "Sarah Jenkins", "action": "Initiated secondary sweep of internal subnets for lateral pivoting attempts", "artifact_ref": "SWEEP-SUB-192-168-1.json"}
        ]
    },
    {
        "case_id": "CASE-DEMO-002",
        "title": "Suspected Steganographic Insider Data Leak via Image Assets",
        "status": "CONTAINED",
        "owner": "Marcus Vance (Forensic Specialist)",
        "summary": "Analyst workstation uploaded employee directory photo with embedded cryptographic token to an unauthorized external file locker.",
        "created_at": "2026-11-08T14:20:00Z",
        "updated_at": "2026-11-09T10:00:00Z",
        "timeline": [
            {"event_id": 1, "timestamp": "2026-11-08T14:20:00Z", "actor": "NetSentinel DLP", "action": "Flagged outbound HTTP POST containing suspicious image asset 'corp_badge_sample.png'", "artifact_ref": "ARTIFACT-IMG-8821.png"},
            {"event_id": 2, "timestamp": "2026-11-08T15:10:00Z", "actor": "Marcus Vance", "action": "Ran NetSentinel LSB stego extraction engine; uncovered hidden token 'NetSentinel-Demo-Evidence-Token-987'", "artifact_ref": "STEGO-EXTRACT-REPORT-002"},
            {"event_id": 3, "timestamp": "2026-11-09T09:00:00Z", "actor": "HR & SecOps", "action": "Revoked workstation network access for 192.168.1.105 pending full forensic disk image", "artifact_ref": "DISARM-TOKEN-4410"},
            {"event_id": 4, "timestamp": "2026-11-09T10:00:00Z", "actor": "Marcus Vance", "action": "Marked case status as CONTAINED; forensic disk imaging completed", "artifact_ref": "E01-IMAGE-WORKSTATION-105"}
        ]
    },
    {
        "case_id": "CASE-DEMO-003",
        "title": "DNS Tunneling Channel from IoT Temperature Monitor",
        "status": "CLOSED",
        "owner": "Elena Rostova (Threat Hunter)",
        "summary": "Misconfigured third-party temperature sensor firmware sending telemetry encoded in base64 DNS queries rather than HTTPS.",
        "created_at": "2026-11-07T10:00:00Z",
        "updated_at": "2026-11-08T16:00:00Z",
        "timeline": [
            {"event_id": 1, "timestamp": "2026-11-07T10:00:00Z", "actor": "NetSentinel Behavioral", "action": "Detected high entropy DNS requests from 192.168.1.220", "artifact_ref": "DNS-QUERY-LOG-1107"},
            {"event_id": 2, "timestamp": "2026-11-07T14:30:00Z", "actor": "Elena Rostova", "action": "Reverse engineered sensor payload; decoded environmental readings (temperature/humidity)", "artifact_ref": "DECODE-SCRIPT-IOT.py"},
            {"event_id": 3, "timestamp": "2026-11-08T16:00:00Z", "actor": "Facilities IT", "action": "Updated IoT sensor firmware to v2.4.1 HTTPS telemetry endpoint; closed alert", "artifact_ref": "FIRMWARE-V241.bin"}
        ]
    }
]

_INITIAL_THREAT_INTEL = {
    "198.51.100.14": {
        "ip": "198.51.100.14",
        "risk_score": 92,
        "classification": "Malicious Exfiltration Endpoint",
        "threat_level": "CRITICAL",
        "asn": "AS64500 (Demo External Hosting)",
        "country": "US",
        "threat_tags": ["C2 Infrastructure", "Data Exfiltration", "Known File Locker"],
        "reverse_dns": "c2-relay-node-04.badthreat.demo",
        "explanation": "Identified as receiving unauthorized outbound data transfers containing high-entropy steganographic image payloads.",
        "is_demo": True,
        "notice": "DEMO INTELLIGENCE DATA — NOT A LIVE THREAT FEED",
    },
    "203.0.113.88": {
        "ip": "203.0.113.88",
        "risk_score": 96,
        "classification": "Credential Stuffing / Brute Force Node",
        "threat_level": "CRITICAL",
        "asn": "AS65111 (External Proxy Net)",
        "country": "RU",
        "threat_tags": ["Credential Stuffing", "SSH Brute Force", "Tor Exit Node"],
        "reverse_dns": "scanner-eval.sec-audit.demo",
        "explanation": "Active source of automated multi-vector SSH login attempts and credential stuffing attacks against production assets.",
        "is_demo": True,
        "notice": "DEMO INTELLIGENCE DATA — NOT A LIVE THREAT FEED",
    },
    "192.168.1.1": {
        "ip": "192.168.1.1",
        "risk_score": 2,
        "classification": "Clean Gateway Router",
        "threat_level": "CLEAN",
        "asn": "RFC1918 Private Network",
        "country": "INTERNAL",
        "threat_tags": ["Gateway", "Internal Core", "Trusted"],
        "reverse_dns": "gw-core-01.corp.internal",
        "explanation": "Primary local subnet default gateway router. Fully trusted internal routing infrastructure.",
        "is_demo": True,
        "notice": "DEMO INTELLIGENCE DATA — NOT A LIVE THREAT FEED",
    },
    "192.168.1.105": {
        "ip": "192.168.1.105",
        "risk_score": 45,
        "classification": "Compromised Analyst Workstation",
        "threat_level": "MEDIUM",
        "asn": "RFC1918 Private Network",
        "country": "INTERNAL",
        "threat_tags": ["Endpoint", "Analyst", "Quarantined"],
        "reverse_dns": "macbook-analyst-jdoe.corp.internal",
        "explanation": "Internal workstation flagged for executing steganography embedding scripts and transmitting outbound artifacts.",
        "is_demo": True,
        "notice": "DEMO INTELLIGENCE DATA — NOT A LIVE THREAT FEED",
    },
}

_state = copy.deepcopy(_INITIAL_STATE)
_devices = copy.deepcopy(_INITIAL_DEVICES)
_flows = copy.deepcopy(_INITIAL_FLOWS)
_alerts = copy.deepcopy(_INITIAL_ALERTS)
_cases = copy.deepcopy(_INITIAL_CASES)
_threat_intel = copy.deepcopy(_INITIAL_THREAT_INTEL)

def _save_persisted_state() -> None:
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "state": _state,
            "alerts": _alerts,
            "devices": _devices,
        }
        temp_file = _STATE_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        temp_file.replace(_STATE_FILE)
    except Exception:
        pass

def _load_persisted_state() -> None:
    global _state, _alerts, _devices
    if not _STATE_FILE.exists():
        return
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            if "state" in data and isinstance(data["state"], dict):
                _state = copy.deepcopy(data["state"])
            if "alerts" in data and isinstance(data["alerts"], list):
                _alerts = copy.deepcopy(data["alerts"])
            if "devices" in data and isinstance(data["devices"], list):
                _devices = copy.deepcopy(data["devices"])
    except Exception:
        pass

_load_persisted_state()

def reset_demo_state() -> None:
    global _state, _devices, _flows, _alerts, _cases, _threat_intel
    _state = copy.deepcopy(_INITIAL_STATE)
    _devices = copy.deepcopy(_INITIAL_DEVICES)
    _flows = copy.deepcopy(_INITIAL_FLOWS)
    _alerts = copy.deepcopy(_INITIAL_ALERTS)
    _cases = copy.deepcopy(_INITIAL_CASES)
    _threat_intel = copy.deepcopy(_INITIAL_THREAT_INTEL)
    if _STATE_FILE.exists():
        _STATE_FILE.unlink(missing_ok=True)

def get_demo_scenarios() -> list:
    scenarios = []
    if DEMO_SCENARIOS_DIR.is_dir():
        for p in DEMO_SCENARIOS_DIR.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    scenarios.append(json.load(f))
            except Exception:
                pass
    scenarios.sort(key=lambda s: str(s.get("id", "")))
    return scenarios

def get_demo_state() -> dict:
    return copy.deepcopy(_state)

def update_demo_state(updates: dict) -> dict:
    global _state
    if not isinstance(updates, dict):
        return copy.deepcopy(_state)
    if "bandwidth_multiplier" in updates:
        val = float(updates["bandwidth_multiplier"])
        _state["bandwidth_multiplier"] = max(0.2, min(5.0, val))
    if "packet_rate_multiplier" in updates:
        val = float(updates["packet_rate_multiplier"])
        _state["packet_rate_multiplier"] = max(0.2, min(5.0, val))
    if "active_scenario" in updates:
        scen = updates["active_scenario"]
        valid_scenarios = {s["id"] for s in get_demo_scenarios() if "id" in s} | {"spike", "portscan", "bruteforce", "exfiltration", None, ""}
        if scen in valid_scenarios:
            _state["active_scenario"] = scen if scen else None
    if "collector_health" in updates:
        health = str(updates["collector_health"]).upper()
        if health in ["LIVE", "DEGRADED", "DISCONNECTED"]:
            _state["collector_health"] = health
    _save_persisted_state()
    return copy.deepcopy(_state)

def get_demo_devices() -> list:
    return copy.deepcopy(_devices)

def get_demo_flows(protocol: str = None, q: str = None) -> list:
    flows = copy.deepcopy(_flows)
    if protocol:
        flows = [f for f in flows if f.get("protocol", "").upper() == protocol.upper()]
    if q:
        ql = q.lower()
        flows = [
            f for f in flows
            if ql in str(f.get("src_ip", "")).lower()
            or ql in str(f.get("dst_ip", "")).lower()
            or ql in str(f.get("protocol", "")).lower()
        ]
    return flows

def get_demo_alerts(severity: str = None, status: str = None) -> list:
    alerts = copy.deepcopy(_alerts)
    if severity:
        alerts = [a for a in alerts if a.get("severity", "").upper() == severity.upper()]
    if status:
        alerts = [a for a in alerts if a.get("status", "").upper() == status.upper()]
    return alerts

def get_demo_cases() -> list:
    return copy.deepcopy(_cases)

def get_demo_case(case_id: str) -> dict:
    for c in _cases:
        if c["case_id"] == case_id:
            return copy.deepcopy(c)
    return {}

def get_demo_threat_intel(ip: str = None) -> dict:
    if ip:
        if ip in _threat_intel:
            return copy.deepcopy(_threat_intel[ip])
        return {
            "ip": ip,
            "risk_score": 10,
            "classification": "Unknown / Unclassified IP",
            "threat_level": "LOW",
            "asn": "Unknown ASN",
            "country": "GLOBAL",
            "threat_tags": ["Unclassified"],
            "reverse_dns": f"ip-{ip.replace('.', '-')}.demo.net",
            "explanation": "No prior threat intelligence flags recorded for this IP address in demo corpus.",
            "is_demo": True,
            "notice": "DEMO INTELLIGENCE DATA — NOT A LIVE THREAT FEED",
        }
    return copy.deepcopy(_threat_intel)

def get_demo_system_health() -> dict:
    health = _state["collector_health"]
    cpu = _state["cpu_percent"]
    mem = _state["memory_percent"]
    latency = _state["latency_ms"]
    drop_rate = _state["packet_drop_rate"]
    if health == "DEGRADED":
        latency = 75.4
        drop_rate = 0.038
        cpu = 68.2
    elif health == "DISCONNECTED":
        cpu = 0.0
        mem = 12.0
        latency = 0.0
        drop_rate = 1.0
    return {
        "collector_status": health,
        "cpu_percent": cpu,
        "memory_percent": mem,
        "latency_ms": latency,
        "packet_drop_rate": drop_rate,
        "active_workers": _state["active_workers"],
        "is_demo": True,
        "notice": "DEMO SYSTEM HEALTH METRICS",
    }

def get_demo_telemetry(time_range: str = "1h") -> dict:
    bw_mult = _state["bandwidth_multiplier"]
    pkt_mult = _state["packet_rate_multiplier"]
    scenario = _state["active_scenario"]
    health = _state["collector_health"]
    loaded_scenarios = {s["id"]: s for s in get_demo_scenarios() if "id" in s}
    active_scen_config = loaded_scenarios.get(scenario)

    points = 24
    series = []
    base_time = datetime.now(timezone.utc)
    for i in range(points):
        t_offset = (i - points) * 150
        ts = datetime.fromtimestamp(base_time.timestamp() + t_offset, tz=timezone.utc).isoformat()
        
        if health == "DISCONNECTED":
            bw = 0.0
            pps = 0
            flows = 0
            cpu = 2.0
            drop = 1.0
        else:
            bw = (45.0 + 15.0 * math.sin(i / 3.0)) * bw_mult
            pps = int((1200 + 400 * math.cos(i / 2.0)) * pkt_mult)
            flows = int(35 + 10 * math.sin(i / 4.0))
            cpu = 15.0 + 5.0 * math.sin(i / 3.0)
            drop = 0.0001

            if active_scen_config and i >= points - 6:
                bw *= float(active_scen_config.get("bandwidth_multiplier", 1.0))
                pps = int(pps * float(active_scen_config.get("packet_rate_multiplier", 1.0)))
                cpu += float(active_scen_config.get("cpu_impact", 0.0))
                if scenario == "portscan":
                    flows += 80
                elif scenario == "exfiltration":
                    drop = 0.015
            elif scenario == "spike" and i >= points - 6:
                bw *= 3.5
                pps = int(pps * 3.0)
                cpu += 40.0
            elif scenario == "portscan" and i >= points - 6:
                pps = int(pps * 4.5)
                flows += 80
                cpu += 25.0
            elif scenario == "bruteforce" and i >= points - 6:
                pps = int(pps * 2.2)
                cpu += 18.0
            elif scenario == "exfiltration" and i >= points - 6:
                bw *= 4.0
                drop = 0.015

            if health == "DEGRADED":
                drop = 0.045
                cpu += 30.0

        inbound = round(bw * 0.65, 2)
        outbound = round(bw * 0.35, 2)
        series.append({
            "timestamp": ts,
            "bandwidth_mbps": round(max(0.0, bw), 2),
            "inbound_mbps": inbound,
            "outbound_mbps": outbound,
            "packets_per_sec": max(0, pps),
            "active_flows": max(0, flows),
            "cpu_percent": round(max(0.0, min(100.0, cpu)), 1),
            "memory_percent": round(_state["memory_percent"], 1),
            "latency_ms": round(85.0 if health == "DEGRADED" else (0.0 if health == "DISCONNECTED" else 1.8), 1),
            "packet_drop_rate": drop,
        })

    return {
        "time_range": time_range,
        "bandwidth_multiplier": bw_mult,
        "packet_rate_multiplier": pkt_mult,
        "active_scenario": scenario,
        "collector_health": health,
        "summary": {
            "avg_bandwidth_mbps": round(sum(s["bandwidth_mbps"] for s in series) / len(series), 2) if series else 0,
            "peak_bandwidth_mbps": max((s["bandwidth_mbps"] for s in series), default=0),
            "total_packets": sum(s["packets_per_sec"] for s in series),
            "current_drop_rate": series[-1]["packet_drop_rate"] if series else 0,
            "active_flows_count": series[-1]["active_flows"] if series else 0,
        },
        "series": series,
    }

def triage_demo_alert(alert_id: str, status: str, analyst: str = None) -> dict:
    target_alert = None
    for a in _alerts:
        if a["alert_id"] == alert_id:
            target_alert = a
            break
    if not target_alert:
        raise ValueError(f"Alert {alert_id} not found in demo data")

    new_status = status.upper()
    if new_status not in ["OPEN", "ACKNOWLEDGED", "RESOLVED"]:
        new_status = "ACKNOWLEDGED"

    target_alert["status"] = new_status
    target_alert["assigned_analyst"] = analyst or "SecOps Analyst"
    now_iso = datetime.now(timezone.utc).isoformat()

    target_case = _cases[0]
    for c in _cases:
        if c["case_id"] == "CASE-DEMO-001":
            target_case = c
            break

    timeline_event = {
        "event_id": len(target_case["timeline"]) + 1,
        "timestamp": now_iso,
        "actor": analyst or "SecOps Analyst",
        "action": f"Triaged alert {alert_id} ({target_alert['title']}) to {new_status}",
        "artifact_ref": f"ALERT-REF-{alert_id}",
    }
    target_case["timeline"].append(timeline_event)
    target_case["updated_at"] = now_iso
    _save_persisted_state()

    return copy.deepcopy(target_alert)

def get_demo_csv_text() -> str:
    header = "timestamp,src_ip,dst_ip,src_port,dst_port,protocol,bytes\n"
    rows = []
    base = "2026-11-09T10:00:"
    for i in range(11):
        rows.append(f"{base}{10+i:02d}Z,192.168.1.20,10.0.0.6,{30000+i},443,TCP,1024")
    for p in [21, 22, 23, 25, 80, 110, 139, 443]:
        rows.append(f"{base}35Z,192.168.1.200,192.168.1.50,55555,{p},TCP,64")
    for i in range(6):
        rows.append(f"{base}{45+i:02d}Z,203.0.113.88,192.168.1.50,{50000+i},22,TCP,128")
    return header + "\n".join(rows) + "\n"

def get_demo_carrier_image() -> bytes:
    if DEMO_CARRIER_PATH.is_file():
        return DEMO_CARRIER_PATH.read_bytes()
    if _HAS_PIL and Image is not None:
        img = Image.new("RGB", (120, 80), color=(40, 90, 140))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data = buf.getvalue()
        try:
            DEMO_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
            DEMO_CARRIER_PATH.write_bytes(data)
        except OSError:
            pass
        return data
    return _FALLBACK_PNG_BYTES

def get_demo_stego_image() -> bytes:
    if DEMO_STEGO_PATH.is_file():
        return DEMO_STEGO_PATH.read_bytes()
    if _HAS_PIL and Image is not None:
        secret_text = "NetSentinel-Demo-Evidence-Token-987"
        secret_bytes = secret_text.encode("utf-8")
        length_prefix = len(secret_bytes).to_bytes(4, byteorder="big")
        payload = length_prefix + secret_bytes
        binary_payload = "".join(format(b, "08b") for b in payload)

        img = Image.new("RGB", (120, 80), color=(50, 80, 120))
        pixels = list(img.getdata())
        new_pixels = []
        idx = 0
        data_len = len(binary_payload)
        for r, g, b in pixels:
            if idx < data_len:
                r = (r & ~1) | int(binary_payload[idx])
                idx += 1
            if idx < data_len:
                g = (g & ~1) | int(binary_payload[idx])
                idx += 1
            if idx < data_len:
                b = (b & ~1) | int(binary_payload[idx])
                idx += 1
            new_pixels.append((r, g, b))

        encoded = Image.new("RGB", (120, 80))
        encoded.putdata(new_pixels)
        buf = io.BytesIO()
        encoded.save(buf, format="PNG")
        data = buf.getvalue()
        try:
            DEMO_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
            DEMO_STEGO_PATH.write_bytes(data)
        except OSError:
            pass
        return data
    return _FALLBACK_PNG_BYTES

def get_demo_baseline_files() -> dict:
    clean_text = (
        "# /etc/security/demo_kernel_auth.cfg\n"
        "# NetSentinel Forensic Baseline Snapshot\n"
        "AUTH_MODE=ENFORCED_PKI\n"
        "PERMIT_ROOT_LOGIN=NO\n"
        "MAX_AUTH_TRIES=3\n"
        "PASSWORD_MIN_LEN=16\n"
        "SECURE_AUDIT_LOG=/var/log/audit/audit.log\n"
        "INTEGRITY_CHECK_INTERVAL=300\n"
    )
    tampered_text = (
        "# /etc/security/demo_kernel_auth.cfg\n"
        "# NetSentinel Forensic Baseline Snapshot\n"
        "AUTH_MODE=ENFORCED_PKI\n"
        "PERMIT_ROOT_LOGIN=YES  # [TAMPER: Backdoor access enabled]\n"
        "MAX_AUTH_TRIES=999\n"
        "PASSWORD_MIN_LEN=4\n"
        "SECURE_AUDIT_LOG=/dev/null  # [TAMPER: Audit trail suppressed]\n"
        "INTEGRITY_CHECK_INTERVAL=300\n"
    )
    clean_bytes = clean_text.encode("utf-8")
    tampered_bytes = tampered_text.encode("utf-8")
    clean_hash = hashlib.sha256(clean_bytes).hexdigest()
    tampered_hash = hashlib.sha256(tampered_bytes).hexdigest()
    return {
        "clean": {
            "filename": "demo_kernel_auth.cfg",
            "bytes": clean_bytes,
            "sha256": clean_hash,
            "description": "Baseline configuration artifact (Production Gold Standard)",
        },
        "tampered": {
            "filename": "demo_kernel_auth.cfg",
            "bytes": tampered_bytes,
            "sha256": tampered_hash,
            "description": "Compromised configuration artifact (Unauthorized Modifications Detected)",
        },
        "clean_bytes": clean_bytes,
        "tampered_bytes": tampered_bytes,
        "clean_hash": clean_hash,
        "tampered_hash": tampered_hash,
        "filename": "demo_kernel_auth.cfg",
    }

def generate_demo_pdf_report(case_id: str = None) -> bytes:
    target_case = None
    if case_id:
        for c in _cases:
            if c["case_id"] == case_id:
                target_case = c
                break
    if not target_case:
        target_case = _cases[0]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=40,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#0f172a"),
        alignment=1,
    )
    banner_style = ParagraphStyle(
        "ReportBanner",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#b91c1c"),
        alignment=1,
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6,
    )
    th_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
    )
    td_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1e293b"),
    )
    td_pass_style = ParagraphStyle(
        "TableCellPass",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#16a34a"),
    )
    td_fail_style = ParagraphStyle(
        "TableCellFail",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#dc2626"),
    )

    story = []

    story.append(Paragraph("NET SENTINEL — DIGITAL FORENSICS & THREAT INVESTIGATION REPORT", title_style))
    story.append(Spacer(1, 6))

    banner_data = [[Paragraph("[ DEMONSTRATION DATA — NOT A GENUINE LEGAL FORENSIC ARTIFACT ]", banner_style)]]
    banner_table = Table(banner_data, colWidths=[540])
    banner_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef2f2")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#fca5a5")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(banner_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Case Overview", heading_style))
    overview_data = [
        [Paragraph("Case Reference", th_style), Paragraph(target_case["case_id"], td_style)],
        [Paragraph("Title", th_style), Paragraph(target_case["title"], td_style)],
        [Paragraph("Priority / Severity", th_style), Paragraph("CRITICAL / HIGH", td_style)],
        [Paragraph("Assigned Analyst", th_style), Paragraph(target_case["owner"], td_style)],
        [Paragraph("Incident Date", th_style), Paragraph(target_case["created_at"], td_style)],
        [Paragraph("Status", th_style), Paragraph(target_case["status"], td_style)],
    ]
    overview_table = Table(overview_data, colWidths=[140, 400])
    overview_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#1e293b")),
        ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#f8fafc")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(overview_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Executive Summary", heading_style))
    story.append(Paragraph(target_case["summary"], body_style))
    story.append(Paragraph("NetSentinel automated runtime telemetry and behavioral anomaly analysis confirm unauthorized reconnaissance and vector probing. Immediate containment protocols have been executed across impacted network segments.", body_style))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Incident Timeline", heading_style))
    timeline_header = [
        Paragraph("Timestamp (UTC)", th_style),
        Paragraph("Actor", th_style),
        Paragraph("Action Taken", th_style),
        Paragraph("Forensic Artifact Ref", th_style),
    ]
    timeline_rows = [timeline_header]
    for ev in target_case["timeline"]:
        timeline_rows.append([
            Paragraph(str(ev.get("timestamp", "")), td_style),
            Paragraph(str(ev.get("actor", "")), td_style),
            Paragraph(str(ev.get("action", "")), td_style),
            Paragraph(str(ev.get("artifact_ref", "")), td_style),
        ])
    timeline_table = Table(timeline_rows, colWidths=[110, 100, 210, 120])
    timeline_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.append(timeline_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Cryptographic Evidence Verification", heading_style))
    crypto_header = [
        Paragraph("Artifact Name", th_style),
        Paragraph("SHA-256 Digest", th_style),
        Paragraph("Integrity Status", th_style),
    ]
    crypto_data = [
        crypto_header,
        [Paragraph("auth.log (web-prod-01)", td_style), Paragraph("5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8", td_style), Paragraph("VERIFIED MATCH", td_pass_style)],
        [Paragraph("PCAP-20261109-0815.cap", td_style), Paragraph("8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4", td_style), Paragraph("VERIFIED MATCH", td_pass_style)],
        [Paragraph("corp_badge_sample.png", td_style), Paragraph("a35c91f584e0984803d5236b3b27b9d794cb1f09230198063a18600c3b0df3f8", td_style), Paragraph("VERIFIED MATCH", td_pass_style)],
        [Paragraph("demo_kernel_auth.cfg", td_style), Paragraph("7d793037a0760186574b0282f2f435e7b1e50774690f473bca524745184c3add", td_style), Paragraph("TAMPER DETECTED", td_fail_style)],
    ]
    crypto_table = Table(crypto_data, colWidths=[140, 280, 120])
    crypto_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.append(crypto_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Recommended Containment & Remediation", heading_style))
    remediation_steps = [
        "1. Isolate Affected Endpoints: Immediately sever non-management VLAN routing for identified compromised hosts.",
        "2. Revoke Credentials & Rotate Keys: Invalidate active sessions, SSH authorized_keys, and service account tokens associated with target hosts.",
        "3. Firewall Egress Enforcement: Block external command-and-control destination IPs (203.0.113.88, 198.51.100.14) across perimeter firewalls.",
        "4. Deep Memory & Disk Acquisition: Preserve live RAM capture and bitstream forensic disk images (E01 format) for full root cause chain-of-custody.",
        "5. Baseline Integrity Restoration: Re-flash configuration files and verify checksums against the known-good immutable baseline repository.",
    ]
    for step in remediation_steps:
        story.append(Paragraph(step, body_style))

    def add_footer(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.setFillColor(colors.HexColor("#718096"))
        footer_text = "Generated by Net Sentinel Forensic Intelligence Platform • Trial Mode • Page 1"
        canvas_obj.drawCentredString(letter[0] / 2.0, 20, footer_text)
        canvas_obj.restoreState()

    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    return buf.getvalue()
