"""Audit existing public geometry logs only; no tool or RTL invocation."""
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
LOG = HERE / "ROUND_01/positive.stdout"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def unpack(value):
    packed = int(value, 16)
    return [(packed >> (slot*10)) & 1023 for slot in range(8)]


def main():
    before = {str(p): sha(p) for p in (LOG, Path(__file__).resolve(), Path(sys.executable))}
    text = LOG.read_text(encoding="utf-8")
    records = []
    for line in text.splitlines():
        if line.startswith("CHECK "):
            name = line.split()[1]
            fields = dict(re.findall(r"([a-z][a-z0-9_]*)=([0-9a-f]+)", line))
            records.append((name, fields))
    falling = [r for name, r in records if name == "PREVIEW120_CONTINUOUS_INTEGER_GEOMETRY"]
    assert len(falling) == 140
    geometry = []
    for offset, r in enumerate(falling, 1):
        expected_end = min(480, offset*4)
        expected_top = min(480, max(0, (offset-20)*4))
        assert r["falling"] == "ff"
        assert unpack(r["ft"]) == [expected_top]*8
        assert unpack(r["fe"]) == [expected_end]*8
        geometry.append({"offset": offset, "frame": int(r["frame"]),
                         "top_each_slot": expected_top, "end_each_slot": expected_end})
    live = next(r for name, r in records if name == "EIGHT_LIVE_SLOTS")
    assert unpack(live["top"]) == [462]+[470]*7
    assert unpack(live["end"]) == [480]*8
    released = next(r for name, r in records if name == "RELEASE_TRANSLATES_NEXT_SNAPSHOT")
    assert unpack(released["end"]) == [476]*8
    assert len(re.findall(r"^EVENT ", text, re.M)) == 82
    assert len(re.findall(r"^SCORE ", text, re.M)) == 10
    summary = re.search(r"^PASS PRO_PARALLEL_FIXTURE (.+)$", text, re.M)[1]
    assert int(re.search(r"checks=(\d+)", summary)[1]) == len(records) == 487
    after = {str(p): sha(p) for p in (LOG, Path(__file__).resolve(), Path(sys.executable))}
    assert before == after
    result = {"passed": True, "kind": "READ_ONLY_AUDIT_OF_EXISTING_RTL_PUBLIC_LOG",
        "before": before, "after": after, "rtl_invocations": 0,
        "event_records": 82, "score_records": 10, "check_records": 487,
        "falling_geometry_samples": len(geometry), "verified_slots_per_sample": 8,
        "falling_vectors": "SAME_HIT_AND_DURATION_DIFFERENT_NOTE_IDS_NOT_INDEPENDENT_TIME_SCORES",
        "geometry": geometry, "live_eight_slot_top": unpack(live["top"]),
        "live_eight_slot_end": unpack(live["end"]), "released_eight_slot_end": unpack(released["end"]),
        "rgb": "BLANKING_BLACK_ONLY_NO_COLOR_PIXEL_OR_SCREEN_CLAIM",
        "audio": "CADENCE_COMMIT_UNDERRUN_ONLY_NO_SERIAL_SAMPLE_COMPARISON",
        "board_release_allowed": False}
    with (HERE / "RECORDED_GEOMETRY_AUDIT.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("before", "after", "geometry")}))


if __name__ == "__main__":
    main()
