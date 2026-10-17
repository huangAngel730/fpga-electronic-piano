"""Independent source/destination ledger and timestamp checker for normal VVP."""
from pathlib import Path
import argparse
import json
import re


def check(capture, catalogue_path):
    rows = []
    for line in catalogue_path.read_text(encoding="utf-8").splitlines():
        raw = int(line, 16)
        left, right, delay = (raw >> 40) & 0xffffff, (raw >> 16) & 0xffffff, raw & 65535
        rows.append((left if left < 8388608 else left-16777216,
                     right if right < 8388608 else right-16777216, delay))
    text = capture.read_text(encoding="utf-8")
    a = [tuple(map(int, m)) for m in re.findall(r"^A (\d+) (\d+) (-?\d+) (-?\d+) (\d+)$", text, re.M)]
    o = [tuple(map(int, m)) for m in re.findall(r"^O (\d+) (\d+) (-?\d+) (-?\d+) (\d+) (\d+) (\d+)$", text, re.M)]
    d = [tuple(map(int, m)) for m in re.findall(r"^D (\d+) (\d+) (-?\d+) (-?\d+)$", text, re.M)]
    i = [tuple(map(int, m)) for m in re.findall(r"^I (\d+) (\d+) (-?\d+) (-?\d+)$", text, re.M)]
    assert len(rows) == len(a) == len(o) == 14241, "SOURCE_COUNT"
    assert len(d) == len(i) == 14074 and d == i, "CORE_CONSUMPTION_LEDGER"
    for seq, (aa, oo, row) in enumerate(zip(a, o, rows)):
        assert aa[1:] == (seq, row[0], row[1], 1), "SOURCE_PCM"
        assert oo[1:4] == (seq, row[0], row[1]) and oo[4]+oo[5] == 1, "OBSERVER_PCM"
        assert oo[0]-aa[0] == 25000, "PRE_NBA_OBSERVER_ONE_AUDIO_EDGE"
    for n in range(1,5849):
        assert a[n][0]-a[n-1][0] == rows[n][2]*25000, "REAL_RELATIVE_TIMESTAMP"
    enqueued = [(t,seq,l,r) for t,seq,l,r,e,drop,q in o if e]
    assert [row[1:] for row in d] == [row[1:] for row in enqueued], "FIFO_DELIVERY_EXACTLY_ONCE"
    assert all(dst[0] > src[0] for src,dst in zip(enqueued,d)), "DELIVERY_CAUSALITY"
    dropped = [seq for t,seq,l,r,e,drop,q in o if drop]
    assert dropped == list(range(12026,12193)), "DROPPED_RANGE"
    assert len(re.findall(r"^R ",text,re.M)) == 2, "RESTART_COUNT"
    assert len(re.findall(r"^S ",text,re.M)) == 8, "SNAPSHOT_SCAN_COUNT"
    assert len(re.findall(r"^P ",text,re.M)) == 5, "PUBLISH_COUNT"
    assert "FIRST_REJECT" not in text and "FATAL" not in text, "POSITIVE_REJECT"
    assert re.search(r"^PASS E2 requested=14241 observed=14241 delivered=14074 drops=167 gaps=1 windows=1 restarts=2 scans=8 pixels=\d+$",text,re.M), "END_SUMMARY"
    return {"passed": True,"real_cadence_pairs_checked":5848,"source_frames":len(a),
            "observer_frames":len(o),"delivered_core_frames":len(d),"drop_range_inclusive":[12026,12192],
            "normal_ordinal_after_display_reset":5849,"scans":8,"published_snapshots":5,
            "level":"L2_ISOLATED_HISTORICAL_RTL_REPLAY_AND_SYNTHETIC_STRESS",
            "board_release_allowed":False}


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("capture",type=Path)
    parser.add_argument("catalogue",type=Path)
    args=parser.parse_args()
    print(json.dumps(check(args.capture,args.catalogue),indent=2))
