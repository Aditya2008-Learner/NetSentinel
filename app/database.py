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

    conn.commit()


def get_db_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    is_new = not DB_PATH.exists()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.row_factory = sqlite3.Row
    if is_new:
        init_db_conn(conn)
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
