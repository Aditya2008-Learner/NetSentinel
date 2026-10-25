#!/usr/bin/env python
"""Generate a comprehensive sample CSV of network logs for testing.

The output file is written to :file:`data/sample.csv` relative to the project
root. The script creates normal traffic alongside rows that trigger all five
analysis heuristics:
1. Source flood
2. Destination flood
3. Port scan
4. SSH/RDP brute force
5. Large data transfer
"""

import csv
import pathlib
from datetime import datetime, timedelta

OUTPUT_DIR = pathlib.Path("data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "sample.csv"


def generate_rows() -> list[dict[str, str]]:
    base = datetime.now().replace(microsecond=0)
    rows = []

    # 1. Normal traffic
    for i in range(5):
        rows.append(
            {
                "timestamp": (base + timedelta(seconds=i)).isoformat(),
                "src_ip": "192.168.1.10",
                "dst_ip": "10.0.0.5",
                "src_port": str(10000 + i),
                "dst_port": "80",
                "protocol": "TCP",
                "bytes": "512",
            }
        )

    # 2. High source traffic trigger (>10)
    for i in range(12):
        rows.append(
            {
                "timestamp": (base + timedelta(seconds=i)).isoformat(),
                "src_ip": "192.168.1.20",
                "dst_ip": "10.0.0.6",
                "src_port": str(30000 + i),
                "dst_port": "443",
                "protocol": "TCP",
                "bytes": "1024",
            }
        )

    # 3. High destination traffic trigger (>20)
    for i in range(25):
        rows.append(
            {
                "timestamp": (base + timedelta(seconds=i)).isoformat(),
                "src_ip": f"192.168.1.{100 + i}",
                "dst_ip": "10.0.0.7",
                "src_port": str(40000 + i),
                "dst_port": "80",
                "protocol": "TCP",
                "bytes": "256",
            }
        )

    # 4. Port scan trigger (>=8 ports from one source to one host)
    scan_base = base + timedelta(minutes=1)
    for port in range(1000, 1010):
        rows.append(
            {
                "timestamp": scan_base.isoformat(),
                "src_ip": "192.168.1.55",
                "dst_ip": "10.0.0.99",
                "src_port": "55555",
                "dst_port": str(port),
                "protocol": "TCP",
                "bytes": "64",
            }
        )

    # 5. SSH brute force trigger (>=6 connections to port 22)
    brute_base = base + timedelta(minutes=2)
    for i in range(7):
        rows.append(
            {
                "timestamp": (brute_base + timedelta(seconds=i)).isoformat(),
                "src_ip": "203.0.113.5",
                "dst_ip": "10.0.0.15",
                "src_port": str(50000 + i),
                "dst_port": "22",
                "protocol": "TCP",
                "bytes": "128",
            }
        )

    # 6. Large transfer trigger (>10MB)
    transfer_base = base + timedelta(minutes=3)
    rows.append(
        {
            "timestamp": transfer_base.isoformat(),
            "src_ip": "192.168.1.88",
            "dst_ip": "10.0.0.200",
            "src_port": "60000",
            "dst_port": "443",
            "protocol": "TCP",
            "bytes": str(15 * 1024 * 1024),
        }
    )

    return rows


def main():
    rows = generate_rows()
    with OUTPUT_FILE.open("w", newline="") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "timestamp",
                "src_ip",
                "dst_ip",
                "src_port",
                "dst_port",
                "protocol",
                "bytes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows)} sample rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
