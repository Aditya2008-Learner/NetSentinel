"""Simple analysis service for NetSentinel.

Reads a CSV string of connection logs and returns suspicious events. The
heuristics stay small on purpose so a demo can explain every flag:

1. A source IP that opens more than 10 connections in one minute.
2. A destination IP that receives more than 20 connections in one minute.
3. A source that touches 8 or more distinct ports on one host in one minute.
4. Six or more connections to SSH (22) or RDP (3389) from one source in a minute.
5. A single flow larger than 10 MB.

Events are deduplicated: only the first alert per (rule_id, source_ip, destination_ip, minute) is emitted.
Each event includes structured metadata for explainability: observed value,
threshold, and a recommended defensive investigation step.

Rule definitions and thresholds are configurable.
"""

import csv
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

__all__ = ["analyze_logs", "summarize", "SRC_THRESHOLD", "DST_THRESHOLD", "RULE_DEFINITIONS"]

SRC_THRESHOLD = 10
DST_THRESHOLD = 20
SCAN_PORT_THRESHOLD = 8
BRUTE_FORCE_THRESHOLD = 6
LARGE_TRANSFER_BYTES = 10 * 1024 * 1024
SENSITIVE_PORTS = {22, 3389}

# Structured rule definitions for explainability metadata
RULE_DEFINITIONS = {
    "source_burst": {
        "severity": "medium",
        "threshold_num": 10,
        "observed_label": "{count} connections > {threshold} per minute",
        "recommended_action": "Review source IP for compromised host or misconfigured service. Check connection logs for malware indicators.",
    },
    "dest_flood": {
        "severity": "medium",
        "threshold_num": 20,
        "observed_label": "{count} connections > {threshold} per minute",
        "recommended_action": "Investigate destination service health. Check for DDoS attack or application error causing retry storms.",
    },
    "port_scan": {
        "severity": "high",
        "threshold_num": 8,
        "observed_label": "{count} distinct ports in one minute",
        "recommended_action": "Block source IP at firewall. Verify no legitimate scanning tools are running from this host.",
    },
    "brute_force": {
        "severity": "high",
        "threshold_num": 6,
        "observed_label": "{count} attempts > {threshold} per minute",
        "recommended_action": "Check authentication logs for failed logins. Consider account lockout or CAPTCHA for the target service.",
    },
    "large_transfer": {
        "severity": "low",
        "threshold_num": 10 * 1024 * 1024,
        "observed_label": "{megabytes:.1f} MB > {threshold} MB per flow",
        "recommended_action": "Verify transfer legitimacy with data owner. Check for data exfiltration indicators.",
    },
}


def _parse_timestamp(ts: str) -> datetime:
    """Parse ISO-8601, Unix epoch (seconds or ms), or common log timestamps.

    All timestamps are normalized to naive UTC datetime.
    Raises ``ValueError`` if the string cannot be parsed.
    """
    ts = (ts or "").strip().strip('"\'')
    if not ts:
        raise ValueError("Timestamp string is empty")

    # 1. Check for numeric Unix epoch (seconds, float, or milliseconds)
    try:
        val = float(ts)
        # If timestamp is in milliseconds (> 1e11 is year 1973+ in ms, year 5138+ in s)
        if val > 1e11:
            val = val / 1000.0
        return datetime.fromtimestamp(val, tz=timezone.utc).replace(tzinfo=None)
    except (ValueError, OverflowError, OSError):
        pass

    # 2. Normalize delimiters and timezones
    clean_ts = ts.rstrip("Zz").replace("T", " ")
    if "+" in clean_ts:
        clean_ts = clean_ts.split("+")[0].strip()

    # 3. Slash formats: YYYY/MM/DD, MM/DD/YYYY, DD/MM/YYYY
    if "/" in clean_ts:
        for fmt in (
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S.%f",
            "%m/%d/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%Y/%m/%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
        ):
            try:
                return datetime.strptime(clean_ts, fmt)
            except ValueError:
                continue

    # 4. Standard ISO and log formats
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d",
        "%H:%M:%S",
        "%H:%M:%S.%f",
        "%d-%m-%Y %H:%M:%S",
        "%m-%d-%Y %H:%M:%S",
    )
    for fmt in formats:
        try:
            dt = datetime.strptime(clean_ts, fmt)
            if fmt.startswith("%H:%M:%S"):
                today = datetime.utcnow().date()
                dt = datetime.combine(today, dt.time())
            return dt
        except ValueError:
            continue

    # 5. Fallback to datetime.fromisoformat
    try:
        iso_str = ts
        if iso_str.endswith("Z"):
            iso_str = iso_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception as exc:
        raise ValueError(f"Invalid timestamp format '{ts}'") from exc


def _parse_port(value: str) -> Optional[int]:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    if 0 <= port <= 65535:
        return port
    return None


def _parse_bytes(value: str) -> int:
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 0


def analyze_logs(csv_text: str) -> List[Dict[str, object]]:
    """Analyze CSV network logs and return structured, explainable suspicious events.

    Parameters
    ----------
    csv_text: str
        Raw contents of the CSV file.
    Returns
    -------
    List[Dict[str, object]]
        Each dict contains timestamp, src_ip, dst_ip, reason, severity,
        rule_id, observed_value_num, threshold_num, observed_label, and recommended_action.
    """
    raw_text = (csv_text or "").strip()
    if not raw_text:
        raise ValueError("CSV file is empty. Please upload a file containing connection logs.")

    first_line = raw_text.splitlines()[0] if raw_text.splitlines() else ""
    delimiter = ","
    if ";" in first_line and "," not in first_line:
        delimiter = ";"
    elif "\t" in first_line and "," not in first_line:
        delimiter = "\t"

    import io
    reader = csv.DictReader(io.StringIO(raw_text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("CSV file contains no valid header row.")

    # Canonical aliases map: lowercase stripped key -> standard field
    alias_map = {
        "timestamp": "timestamp",
        "time": "timestamp",
        "datetime": "timestamp",
        "date": "timestamp",
        "ts": "timestamp",
        "@timestamp": "timestamp",
        "src_ip": "src_ip",
        "srcip": "src_ip",
        "source_ip": "src_ip",
        "sourceip": "src_ip",
        "source": "src_ip",
        "src": "src_ip",
        "src_addr": "src_ip",
        "source_address": "src_ip",
        "dst_ip": "dst_ip",
        "dstip": "dst_ip",
        "destination_ip": "dst_ip",
        "destinationip": "dst_ip",
        "dest_ip": "dst_ip",
        "destip": "dst_ip",
        "destination": "dst_ip",
        "dest": "dst_ip",
        "dst": "dst_ip",
        "dst_addr": "dst_ip",
        "destination_address": "dst_ip",
        "src_port": "src_port",
        "source_port": "src_port",
        "sport": "src_port",
        "dst_port": "dst_port",
        "destination_port": "dst_port",
        "dest_port": "dst_port",
        "dport": "dst_port",
        "port": "dst_port",
        "protocol": "protocol",
        "proto": "protocol",
        "bytes": "bytes",
        "length": "bytes",
        "size": "bytes",
        "byte_count": "bytes",
    }

    # Map raw fieldnames to canonical names
    header_mapping = {}
    found_canonicals = set()
    for raw_fn in reader.fieldnames:
        clean_fn = raw_fn.strip().lstrip('\ufeff').replace('\ufeff', '').strip('"\'')
        normalized_key = clean_fn.lower().replace("-", "_").replace(" ", "_")
        canonical = alias_map.get(normalized_key)
        if canonical:
            header_mapping[raw_fn] = canonical
            found_canonicals.add(canonical)

    required = {"timestamp", "src_ip", "dst_ip"}
    missing = required - found_canonicals
    if missing:
        raw_headers = [f.strip() for f in reader.fieldnames]
        raise ValueError(
            f"Invalid CSV headers: Found {raw_headers}. Missing required columns: {sorted(list(missing))}. "
            "Required columns: timestamp, src_ip, dst_ip (or aliases such as time, source, destination)."
        )

    rows = list(reader)
    if not rows:
        return []

    events: List[Dict[str, object]] = []
    row_count = 0
    src_counts: Dict[Tuple[str, datetime], int] = defaultdict(int)
    dst_counts: Dict[Tuple[str, datetime], int] = defaultdict(int)
    ports_seen: Dict[Tuple[str, str, datetime], Set[int]] = defaultdict(set)
    auth_counts: Dict[Tuple[str, int, datetime], int] = defaultdict(int)
    seen: Set[Tuple[str, str, str, datetime]] = set()

    def add(
        ts: datetime,
        src: str,
        dst: str,
        rule_id: str,
        observed_value_num: float,
        threshold_num: float,
        observed_label: str,
        reason: str,
    ) -> None:
        minute = ts.replace(second=0, microsecond=0)
        key = (rule_id, src, dst, minute)
        if key in seen:
            return
        seen.add(key)
        rule_def = RULE_DEFINITIONS[rule_id]
        events.append(
            {
                "timestamp": ts.isoformat(),
                "src_ip": src,
                "dst_ip": dst,
                "rule_id": rule_id,
                "reason": reason,
                "severity": rule_def["severity"],
                "observed_value_num": observed_value_num,
                "threshold_num": threshold_num,
                "observed_label": observed_label,
                "recommended_action": rule_def["recommended_action"],
            }
        )

    for row_idx, row in enumerate(rows, start=1):
        # Translate row to canonical fields
        canon_row = {}
        for k, v in row.items():
            if k in header_mapping:
                canon_row[header_mapping[k]] = v

        row_count += 1
        ts_raw = (canon_row.get("timestamp") or "").strip()
        if not ts_raw:
            raise ValueError(f"Row {row_idx}: Missing timestamp value")
        try:
            ts = _parse_timestamp(ts_raw)
        except Exception as exc:
            raise ValueError(f"Row {row_idx}: Invalid timestamp format '{ts_raw}' ({exc})")

        src = (canon_row.get("src_ip") or "").strip()
        dst = (canon_row.get("dst_ip") or "").strip()
        if not src or not dst:
            raise ValueError(f"Row {row_idx}: Missing src_ip or dst_ip")

        minute = ts.replace(second=0, microsecond=0)
        dst_port = _parse_port(canon_row.get("dst_port") or "")
        size = _parse_bytes(canon_row.get("bytes") or "")

        src_key = (src, minute)
        dst_key = (dst, minute)
        src_counts[src_key] += 1
        dst_counts[dst_key] += 1

        if src_counts[src_key] > SRC_THRESHOLD:
            count = src_counts[src_key]
            label = RULE_DEFINITIONS["source_burst"]["observed_label"].format(
                count=count, threshold=SRC_THRESHOLD
            )
            add(
                ts=ts,
                src=src,
                dst=dst,
                rule_id="source_burst",
                observed_value_num=count,
                threshold_num=SRC_THRESHOLD,
                observed_label=label,
                reason=f"High source traffic (> {SRC_THRESHOLD} per minute)",
            )

        if dst_counts[dst_key] > DST_THRESHOLD:
            count = dst_counts[dst_key]
            label = RULE_DEFINITIONS["dest_flood"]["observed_label"].format(
                count=count, threshold=DST_THRESHOLD
            )
            add(
                ts=ts,
                src=src,
                dst=dst,
                rule_id="dest_flood",
                observed_value_num=count,
                threshold_num=DST_THRESHOLD,
                observed_label=label,
                reason=f"High destination traffic (> {DST_THRESHOLD} per minute)",
            )

        if dst_port is not None:
            scan_key = (src, dst, minute)
            ports_seen[scan_key].add(dst_port)
            distinct_ports = len(ports_seen[scan_key])
            if distinct_ports >= SCAN_PORT_THRESHOLD:
                label = RULE_DEFINITIONS["port_scan"]["observed_label"].format(
                    count=distinct_ports
                )
                add(
                    ts=ts,
                    src=src,
                    dst=dst,
                    rule_id="port_scan",
                    observed_value_num=distinct_ports,
                    threshold_num=SCAN_PORT_THRESHOLD,
                    observed_label=label,
                    reason=f"Possible port scan ({distinct_ports} ports in one minute)",
                )

            if dst_port in SENSITIVE_PORTS:
                auth_key = (src, dst_port, minute)
                auth_counts[auth_key] += 1
                attempts = auth_counts[auth_key]
                if attempts >= BRUTE_FORCE_THRESHOLD:
                    service = "SSH" if dst_port == 22 else "RDP"
                    label = RULE_DEFINITIONS["brute_force"]["observed_label"].format(
                        count=attempts, threshold=BRUTE_FORCE_THRESHOLD
                    )
                    add(
                        ts=ts,
                        src=src,
                        dst=dst,
                        rule_id="brute_force",
                        observed_value_num=attempts,
                        threshold_num=BRUTE_FORCE_THRESHOLD,
                        observed_label=label,
                        reason=f"Possible {service} brute force ({attempts} attempts in one minute)",
                    )

        if size > LARGE_TRANSFER_BYTES:
            megabytes = size / (1024 * 1024)
            label = RULE_DEFINITIONS["large_transfer"]["observed_label"].format(
                megabytes=megabytes, threshold=10
            )
            add(
                ts=ts,
                src=src,
                dst=dst,
                rule_id="large_transfer",
                observed_value_num=size,
                threshold_num=LARGE_TRANSFER_BYTES,
                observed_label=label,
                reason=f"Large transfer ({megabytes:.1f} MB in one flow)",
            )

    if row_count == 0:
        raise ValueError("CSV file contains no data rows to analyze.")

    return events


def summarize(events: List[Dict[str, str]], total_rows: int = 0) -> Dict[str, object]:
    """Count events and unique hosts for the dashboard header."""
    by_severity = {"high": 0, "medium": 0, "low": 0}
    sources: Set[str] = set()
    destinations: Set[str] = set()
    for event in events:
        severity = str(event.get("severity") or "low")
        by_severity[severity] = by_severity.get(severity, 0) + 1
        if event.get("src_ip"):
            sources.add(str(event["src_ip"]))
        if event.get("dst_ip"):
            destinations.add(str(event["dst_ip"]))
    return {
        "total": len(events),
        "total_records_analyzed": total_rows,
        "by_severity": by_severity,
        "unique_sources": len(sources),
        "unique_destinations": len(destinations),
    }
