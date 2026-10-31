"""Reliable HTTPS transport with retry, backoff, and offline queueing."""

import logging
import time
import httpx
from typing import List
from .storage import LocalStorageBuffer

logger = logging.getLogger("net_sentinel_collector")


class TransportClient:
    """Submits telemetry batches securely over HTTPS with offline fallback."""

    def __init__(self, backend_url: str, api_key: str, storage: LocalStorageBuffer):
        self.backend_url = backend_url
        self.api_key = api_key
        self.storage = storage
        self.is_online = True

    def submit_events(self, events: List[dict]) -> bool:
        if not events:
            return True

        # First enqueue to local buffer to guarantee durability
        self.storage.enqueue(events)
        return self.flush_queue()

    def flush_queue(self) -> bool:
        batches = self.storage.get_pending_batches(limit=5)
        if not batches:
            return True

        headers = {
            "X-Collector-Key": self.api_key,
            "Content-Type": "application/json"
        }

        success_all = True
        for row_id, batch_events in batches:
            payload = {"events": batch_events}
            try:
                with httpx.Client(timeout=10.0) as client:
                    response = client.post(self.backend_url, json=payload, headers=headers)
                    if response.status_code == 200:
                        self.storage.remove_batch(row_id)
                        self.is_online = True
                        logger.info("Successfully submitted batch of %d flows to backend.", len(batch_events))
                    else:
                        logger.warning("Backend rejected batch (HTTP %d): %s", response.status_code, response.text)
                        self.is_online = False
                        success_all = False
                        break
            except Exception as exc:
                logger.warning("Connection error submitting batch: %s. Buffering locally.", exc)
                self.is_online = False
                success_all = False
                break

        return success_all
