"""Aggregates raw packet metadata into network flow records over timed windows."""

import logging
from collections import defaultdict
from typing import Dict, List

logger = logging.getLogger("net_sentinel_collector")


class EventProcessor:
    """Aggregates individual packet observations into network flows."""

    def __init__(self):
        # Key: (src_ip, dst_ip, src_port, dst_port, protocol) -> flow stats
        self._flows: Dict[tuple, dict] = defaultdict(lambda: {
            "packet_count": 0,
            "byte_count": 0,
            "first_seen": None,
            "last_seen": None
        })
        self._lock = False

    def add_packet(self, meta: dict) -> None:
        key = (
            meta.get("src_ip"),
            meta.get("dst_ip"),
            meta.get("src_port"),
            meta.get("dst_port"),
            meta.get("protocol")
        )
        ts = meta.get("timestamp")
        length = meta.get("length", 0)

        flow = self._flows[key]
        flow["packet_count"] += 1
        flow["byte_count"] += length
        if not flow["first_seen"]:
            flow["first_seen"] = ts
        flow["last_seen"] = ts

    def flush_flows(self) -> List[dict]:
        """Extract and clear accumulated flows into a batch of summary records."""
        batch = []
        for key, stats in self._flows.items():
            src_ip, dst_ip, src_port, dst_port, protocol = key
            batch.append({
                "timestamp": stats["last_seen"],
                "src_ip": src_ip,
                "dst_ip": dst_ip,
                "src_port": src_port,
                "dst_port": dst_port,
                "protocol": protocol,
                "packets": stats["packet_count"],
                "bytes": stats["byte_count"],
                "first_seen": stats["first_seen"],
                "last_seen": stats["last_seen"]
            })
        self._flows.clear()
        return batch
