"""Database setup and connection management for Net Sentinel."""

import sqlite3
import pathlib
from typing import Generator

import os

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    DB_PATH = pathlib.Path("/tmp/netsentinel.db")
else:
    DB_PATH = BASE_DIR / "data" / "netsentinel.db"


def init_db_conn(conn: sqlite3.Connection) -> None:
    """Initialize schema tables using an existing connection."""
    cursor = conn.cursor()

    # Investigations table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS investigations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            case_ref TEXT,
            status TEXT DEFAULT 'Open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            findings_summary TEXT
        )
        """
    )

    # Device inventory table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY,
            ip_address TEXT,
            mac_address TEXT,
            hostname TEXT,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP,
            status TEXT DEFAULT 'Active',
            observation_source TEXT
        )
        """
    )

    # File integrity baselines table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS integrity_baselines (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            file_size INTEGER,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
        """
    )

    # Analysis history / logs table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            operation_type TEXT,
            status TEXT,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Live network flows table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS live_flows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            src_ip TEXT,
            dst_ip TEXT,
            src_port INTEGER,
            dst_port INTEGER,
            protocol TEXT,
            packets INTEGER,
            bytes INTEGER,
            first_seen TEXT,
            last_seen TEXT,
            received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Collector status table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS collector_status (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            status TEXT DEFAULT 'DISCONNECTED',
            interface TEXT,
            last_heartbeat TIMESTAMP,
            packets_observed INTEGER DEFAULT 0,
            bytes_observed INTEGER DEFAULT 0
        )
        """
    )
    cursor.execute(
        """
        INSERT OR IGNORE INTO collector_status (id, status, interface, last_heartbeat, packets_observed, bytes_observed)
        VALUES (1, 'DISCONNECTED', 'None', CURRENT_TIMESTAMP, 0, 0)
        """
    )

    cursor.execute("SELECT COUNT(*) FROM devices")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            """
            INSERT INTO devices (id, ip_address, mac_address, hostname, status, observation_source, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("DEV-001", "192.168.1.1", "a1:b2:c3:d4:e5:f6", "Local Gateway", "Active", "ARP Cache / Gateway"),
        )
        cursor.execute(
            """
            INSERT INTO devices (id, ip_address, mac_address, hostname, status, observation_source, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("DEV-002", "192.168.1.50", "f6:e5:d4:c3:b2:a1", "Analysis Node", "Active", "Local Interface"),
        )

    # Phase 3 SOC & Threat Detection Schema
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS detection_rules (
            rule_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            severity TEXT NOT NULL,
            confidence_weight REAL DEFAULT 0.85,
            enabled INTEGER DEFAULT 1,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS security_alerts (
            alert_id TEXT PRIMARY KEY,
            rule_id TEXT REFERENCES detection_rules(rule_id),
            title TEXT NOT NULL,
            severity TEXT NOT NULL,
            confidence REAL NOT NULL,
            source_ip TEXT,
            dest_ip TEXT,
            details TEXT,
            status TEXT DEFAULT 'OPEN',
            assigned_analyst TEXT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS incident_cases (
            case_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'INVESTIGATING',
            owner TEXT,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS incident_timeline (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT REFERENCES incident_cases(case_id) ON DELETE CASCADE,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            actor TEXT,
            action TEXT NOT NULL,
            artifact_ref TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS executive_reports (
            report_id TEXT PRIMARY KEY,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            time_window TEXT NOT NULL,
            total_flows INTEGER,
            total_alerts INTEGER,
            critical_incidents INTEGER,
            posture_score REAL,
            summary_json TEXT
        )
        """
    )

    # Seed default detection rules
    default_rules = [
        ("RULE-PORT-SCAN", "Rapid SYN / Port Scan Indicator", "PORT_SCAN", "HIGH", 0.90, "Detects high volume of distinct destination ports probed from a single source IP."),
        ("RULE-BRUTE-FORCE", "Unusual Connection Frequency / Brute Force", "BRUTE_FORCE", "CRITICAL", 0.95, "Detects high frequency of repeated connection attempts to sensitive authentication ports."),
        ("RULE-HIGH-BANDWIDTH", "Abnormal Volume Data Transfer", "ANOMALY", "MEDIUM", 0.80, "Detects flows transferring abnormal byte volumes exceeding baseline heuristics."),
    ]
    for r_id, r_name, r_cat, r_sev, r_conf, r_desc in default_rules:
        cursor.execute(
            """
            INSERT OR IGNORE INTO detection_rules (rule_id, name, category, severity, confidence_weight, enabled, description)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (r_id, r_name, r_cat, r_sev, r_conf, r_desc)
        )

    # Indexes for query performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_live_flows_received ON live_flows(received_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_live_flows_src_dst ON live_flows(src_ip, dst_ip)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_live_flows_src ON live_flows(src_ip)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_live_flows_dst ON live_flows(dst_ip)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_live_flows_protocol ON live_flows(protocol)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_security_alerts_rule ON security_alerts(rule_id, source_ip, status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrity_baselines_sha ON integrity_baselines(sha256)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrity_baselines_file ON integrity_baselines(filename)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_timeline_case ON incident_timeline(case_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_devices_ip ON devices(ip_address)")

    conn.commit()


def get_db_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
    except sqlite3.OperationalError:
        pass
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db_connection()
    try:
        init_db_conn(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at", DB_PATH)
