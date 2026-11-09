"""Configuration settings for the Windows Live Network Collector.

NET_SENTINEL_API_KEY:
    Authentication API key used by the collector to authenticate HTTP ingest
    requests sent to the backend endpoint (via the X-Collector-Key header).
    Must match the server-side COLLECTOR_API_KEY.
    For production environments, ensure this value is supplied via the
    NET_SENTINEL_API_KEY environment variable.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger("net_sentinel_collector")

# Backend ingestion API endpoint
BACKEND_URL = os.environ.get("NET_SENTINEL_BACKEND_URL", "https://net-sentinel-zeta.vercel.app/api/collector/events")

# Collector authentication API key validation and fallback
_DEFAULT_DEV_KEY = "ns-live-collector-secure-key-2026"
_env_key = os.environ.get("NET_SENTINEL_API_KEY")

if not _env_key:
    logger.warning(
        "NET_SENTINEL_API_KEY is not set in environment. Default development key is being used. "
        "Recommend setting NET_SENTINEL_API_KEY for production deployments."
    )
    COLLECTOR_API_KEY = _DEFAULT_DEV_KEY
else:
    COLLECTOR_API_KEY = _env_key.strip()

NET_SENTINEL_API_KEY = COLLECTOR_API_KEY

# Aggregation interval in seconds (flows are aggregated and sent every N seconds)
AGGREGATION_INTERVAL = int(os.environ.get("NET_SENTINEL_AGGREGATION_INTERVAL", "5"))

# Local SQLite buffer for offline queueing when backend is unreachable
BASE_DIR = Path(__file__).resolve().parent
LOCAL_DB_PATH = BASE_DIR / "collector_buffer.db"

# Max local queue size before dropping oldest records
MAX_LOCAL_QUEUE_SIZE = 10000

# Default packet capture filter (e.g. "ip or ip6")
CAPTURE_FILTER = os.environ.get("NET_SENTINEL_CAPTURE_FILTER", "ip or ip6")
