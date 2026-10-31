"""Privacy-first packet metadata capture using Scapy."""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Optional

logger = logging.getLogger("net_sentinel_collector")

try:
    from scapy.all import sniff, IP, IPv6, TCP, UDP, ICMP
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False


class PacketCaptureEngine:
    """Captures packet metadata (no payloads) from a selected Windows interface."""

    def __init__(self, interface: str, on_packet_callback: Callable[[dict], None], filter_str: str = "ip or ip6"):
        self.interface = interface
        self.callback = on_packet_callback
        self.filter_str = filter_str
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.is_running = False
        self.packets_captured = 0
        self.bytes_captured = 0

    def start(self) -> bool:
        if self.is_running:
            return True
        if not SCAPY_AVAILABLE:
            logger.error("Scapy is not installed. Cannot start packet capture.")
            return False

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        self.is_running = True
        logger.info("Packet capture started on interface '%s'", self.interface)
        return True

    def stop(self) -> None:
        if not self.is_running:
            return
        self._stop_event.set()
        self.is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("Packet capture stopped.")

    def _capture_loop(self) -> None:
        def _packet_handler(packet):
            if self._stop_event.is_set():
                return
            try:
                meta = self._parse_packet(packet)
                if meta:
                    self.packets_captured += 1
                    self.bytes_captured += meta.get("length", 0)
                    self.callback(meta)
            except Exception as exc:
                logger.debug("Error parsing packet: %s", exc)

        try:
            sniff(
                iface=self.interface,
                prn=_packet_handler,
                filter=self.filter_str,
                store=False,
                stop_filter=lambda _: self._stop_event.is_set()
            )
        except Exception as exc:
            logger.error("Packet capture error on interface '%s': %s", self.interface, exc)
            self.is_running = False

    def _parse_packet(self, packet) -> Optional[dict]:
        timestamp = datetime.now(timezone.utc).isoformat()
        src_ip = "0.0.0.0"
        dst_ip = "0.0.0.0"
        src_port = 0
        dst_port = 0
        protocol = "OTHER"
        length = len(packet)

        if packet.haslayer(IP):
            ip_layer = packet[IP]
            src_ip = ip_layer.src
            dst_ip = ip_layer.dst
        elif packet.haslayer(IPv6):
            ip6_layer = packet[IPv6]
            src_ip = ip6_layer.src
            dst_ip = ip6_layer.dst
        else:
            return None  # Non-IP packet ignored

        if packet.haslayer(TCP):
            tcp_layer = packet[TCP]
            src_port = tcp_layer.sport
            dst_port = tcp_layer.dport
            protocol = "TCP"
        elif packet.haslayer(UDP):
            udp_layer = packet[UDP]
            src_port = udp_layer.sport
            dst_port = udp_layer.dport
            protocol = "UDP"
        elif packet.haslayer(ICMP):
            protocol = "ICMP"

        return {
            "timestamp": timestamp,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "src_port": src_port,
            "dst_port": dst_port,
            "protocol": protocol,
            "length": length,
            "interface": self.interface
        }
