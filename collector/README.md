# Net Sentinel Windows Live Network Collector

Privacy-first Windows packet metadata collector for Net Sentinel.

## Prerequisites

1. **Python 3.10+** installed on Windows 10/11.
2. **Npcap** packet capture driver installed (in WinPcap API-compatible mode). Download from [npcap.com](https://npcap.com/).

## Installation

1. Navigate to the `collector/` directory:
   ```bash
   cd collector
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. List available network interfaces:
   ```bash
   python main.py --list-interfaces
   ```
2. Start monitoring on a selected interface (e.g. interface `0` or name):
   ```bash
   python main.py --interface 0
   ```
3. Stop collection anytime by pressing `Ctrl+C`.
