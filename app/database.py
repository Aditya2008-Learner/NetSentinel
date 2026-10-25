"""Database setup and connection management for Net Sentinel."""

import sqlite3
import pathlib
from typing import Generator

DB_PATH = pathlib.Path("data/netsentinel.db")


def get_db_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db_connection()
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

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at", DB_PATH)
