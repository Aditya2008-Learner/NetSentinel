"""Interface enumeration and selection utilities for Windows Npcap/Scapy."""

import logging
from typing import List, Dict, Any

logger = logging.getLogger("net_sentinel_collector")

try:
    from scapy.all import get_if_list, get_if_addr, conf
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False


def list_available_interfaces() -> List[Dict[str, Any]]:
    """Enumerate available network interfaces with addresses and descriptions."""
    interfaces = []
    if not SCAPY_AVAILABLE:
        logger.warning("Scapy is not installed. Returning dummy interface.")
        return [{"name": "Default Interface", "ip": "127.0.0.1", "description": "Scapy unavailable"}]

    try:
        if_list = get_if_list()
        for idx, if_name in enumerate(if_list):
            ip_addr = "Unknown"
            try:
                ip_addr = get_if_addr(if_name)
            except Exception:
                pass
            
            interfaces.append({
                "id": idx,
                "name": if_name,
                "ip": ip_addr,
                "description": f"Interface: {if_name} (IP: {ip_addr})"
            })
    except Exception as exc:
        logger.error("Failed to enumerate interfaces: %s", exc)
        interfaces.append({"id": 0, "name": conf.iface, "ip": "127.0.0.1", "description": "Default active interface"})

    return interfaces


def select_interface(interface_name: str) -> str:
    """Validate and return the selected interface name."""
    if not interface_name:
        return conf.iface
    return interface_name
