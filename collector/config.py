"""Configuration settings for the Windows Live Network Collector."""

import os
from pathlib import Path

# Backend ingestion API endpoint
BACKEND_URL = os.environ.get("NET_SENTINEL_BACKEND_URL", "https://net-sentinel-zeta.vercel.app/api/collector/events")

# Collector authentication API key (must match server-side COLLECTOR_API_KEY)
COLLECTOR_API_KEY = os.environ.get("NET_SENTINEL_API_KEY", "ns-live-collector-secure-key-2026")

# Aggregation interval in seconds (flows are aggregated and sent every N seconds)
AGGREGATION_INTERVAL = int(os.environ.get("NET_SENTINEL_AGGREGATION_INTERVAL", "5"))

# Local SQLite buffer for offline queueing when backend is unreachable
BASE_DIR = Path(__file__).resolve().parent
LOCAL_DB_PATH = BASE_DIR / "collector_buffer.db"

# Max local queue size before dropping oldest records
MAX_LOCAL_QUEUE_SIZE = 10000

# Default packet capture filter (e.g. "ip or ip6")
CAPTURE_FILTER = os.environ.get("NET_SENTINEL_CAPTURE_FILTER", "ip or ip6")
