"""Main entry point for the Windows Live Network Collector."""

import argparse
import logging
import sys
import time
from .config import BACKEND_URL, COLLECTOR_API_KEY, AGGREGATION_INTERVAL, LOCAL_DB_PATH, CAPTURE_FILTER
from .interfaces import list_available_interfaces, select_interface
from .capture import PacketCaptureEngine
from .event_processor import EventProcessor
from .storage import LocalStorageBuffer
from .transport import TransportClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("net_sentinel_collector")


def main():
    parser = argparse.ArgumentParser(description="Net Sentinel Windows Live Network Collector")
    parser.add_argument("--list-interfaces", action="store_true", help="List available network interfaces and exit")
    parser.add_argument("--interface", type=str, default="", help="Name or index of network interface to capture from")
    parser.add_argument("--backend", type=str, default=BACKEND_URL, help="Backend ingestion URL")
    parser.add_argument("--key", type=str, default=COLLECTOR_API_KEY, help="Collector API key")
    args = parser.parse_args()

    print("=== Net Sentinel Windows Live Network Collector ===")
    interfaces = list_available_interfaces()

    if args.list_interfaces:
        print("\nAvailable Network Interfaces:")
        for iface in interfaces:
            print(f"  [{iface['id']}] {iface['name']} (IP: {iface['ip']})")
        sys.exit(0)

    # Determine interface
    selected_iface = interfaces[0]["name"]
    if args.interface:
        for iface in interfaces:
            if str(iface['id']) == args.interface or iface['name'].lower() == args.interface.lower():
                selected_iface = iface['name']
                break
        else:
            selected_iface = args.interface

    print(f"\nSelected Interface: {selected_iface}")
    print(f"Backend Ingestion URL: {args.backend}")
    print(f"Aggregation Interval: {AGGREGATION_INTERVAL} seconds")
    print("\n--- WARNING: Authorized Monitoring Only ---")
    print("Press Ctrl+C to stop collection at any time.\n")

    processor = EventProcessor()
    storage = LocalStorageBuffer(LOCAL_DB_PATH)
    transport = TransportClient(args.backend, args.key, storage)

    engine = PacketCaptureEngine(
        interface=selected_iface,
        on_packet_callback=processor.add_packet,
        filter_str=CAPTURE_FILTER
    )

    if not engine.start():
        logger.error("Failed to start packet capture engine. Ensure Scapy and Npcap are installed.")
        sys.exit(1)

    try:
        while True:
            time.sleep(AGGREGATION_INTERVAL)
            batch = processor.flush_flows()
            if batch:
                logger.info("Captured %d flows. Submitting to backend...", len(batch))
                transport.submit_events(batch)
            else:
                # Periodic queue flush check
                if storage.queue_size() > 0:
                    transport.flush_queue()
    except KeyboardInterrupt:
        print("\nStopping collector...")
        engine.stop()
        print("Collector stopped safely.")
        sys.exit(0)


if __name__ == "__main__":
    main()
