"""Local SQLite buffering and offline queueing for the collector."""

import sqlite3
import json
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger("net_sentinel_collector")

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS local_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payload TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class LocalStorageBuffer:
    """Buffers network event batches locally when offline."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(SCHEMA_DDL)
            conn.commit()
        finally:
            conn.close()

    def enqueue(self, events: List[dict]) -> None:
        if not events:
            return
        conn = sqlite3.connect(self.db_path)
        try:
            payload = json.dumps(events)
            conn.execute("INSERT INTO local_queue (payload) VALUES (?)", (payload,))
            conn.commit()
        except Exception as exc:
            logger.error("Failed to buffer events locally: %s", exc)
        finally:
            conn.close()

    def get_pending_batches(self, limit: int = 10) -> List[tuple]:
        """Return list of (row_id, events_list) tuples."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute("SELECT id, payload FROM local_queue ORDER BY id ASC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [(r["id"], json.loads(r["payload"])) for r in rows]
        except Exception as exc:
            logger.error("Failed to read local queue: %s", exc)
            return []
        finally:
            conn.close()

    def remove_batch(self, row_id: int) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("DELETE FROM local_queue WHERE id = ?", (row_id,))
            conn.commit()
        except Exception as exc:
            logger.error("Failed to delete acknowledged batch %s: %s", row_id, exc)
        finally:
            conn.close()

    def queue_size(self) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM local_queue")
            return cursor.fetchone()[0]
        except Exception:
            return 0
        finally:
            conn.close()
