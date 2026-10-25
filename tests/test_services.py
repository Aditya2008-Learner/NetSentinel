import pytest

from app.services import analyze_logs, summarize, RULE_DEFINITIONS


def test_analyze_all_heuristics():
    csv_rows = [
        "timestamp,src_ip,dst_ip,src_port,dst_port,protocol,bytes",
        # 1. Source flood (>10)
        *[
            f"2023-10-01T12:00:{i:02d},192.168.1.20,10.0.0.6,{30000+i},443,TCP,1000"
            for i in range(12)
        ],
        # 2. Destination flood (>20)
        *[
            f"2023-10-01T12:01:{i:02d},192.168.1.{100+i},10.0.0.7,{40000+i},80,TCP,500"
            for i in range(25)
        ],
        # 3. Port scan (>=8 ports)
        *[
            f"2023-10-01T12:02:00,192.168.1.55,10.0.0.99,55555,{2000+p},TCP,64"
            for p in range(10)
        ],
        # 4. SSH brute force (>=6 to port 22)
        *[
            f"2023-10-01T12:03:0{i},203.0.113.5,10.0.0.15,{50000+i},22,TCP,128"
            for i in range(7)
        ],
        # 5. Large transfer (>10MB)
        "2023-10-01T12:04:00,192.168.1.88,10.0.0.200,60000,443,TCP,15728640",
    ]
    csv_text = "\n".join(csv_rows)
    events = analyze_logs(csv_text)

    reasons = [e["reason"] for e in events]
    assert any("High source traffic" in r for r in reasons)
    assert any("High destination traffic" in r for r in reasons)
    assert any("port scan" in r for r in reasons)
    assert any("brute force" in r for r in reasons)
    assert any("Large transfer" in r for r in reasons)

    # Check structured fields
    for e in events:
        assert e["severity"] in {"high", "medium", "low"}
        assert "rule_id" in e
        assert e["rule_id"] in RULE_DEFINITIONS
        assert "observed_value_num" in e
        assert "threshold_num" in e
        assert "observed_label" in e
        assert "recommended_action" in e
        assert e["observed_value_num"] > 0
        assert e["threshold_num"] > 0
        assert isinstance(e["recommended_action"], str)
        assert len(e["recommended_action"]) > 0

    # Verify rule IDs match expected heuristics
    rule_ids = {e["rule_id"] for e in events}
    assert "source_burst" in rule_ids
    assert "dest_flood" in rule_ids
    assert "port_scan" in rule_ids
    assert "brute_force" in rule_ids
    assert "large_transfer" in rule_ids

    # Check deduplication: one alert per rule per minute per src/dst
    # Source burst: 12 connections but only 1 alert (fires at 11th connection)
    source_burst_events = [e for e in events if e["rule_id"] == "source_burst"]
    assert len(source_burst_events) == 1
    assert source_burst_events[0]["observed_value_num"] == 11

    summary = summarize(events)
    assert summary["total"] == len(events)
    assert summary["by_severity"]["high"] > 0
    assert summary["by_severity"]["medium"] > 0
    assert summary["by_severity"]["low"] > 0
    assert summary["unique_sources"] > 0
    assert summary["unique_destinations"] > 0
