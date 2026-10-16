"""Full damaged derivatives of actual R02 bytes. No RTL execution or fake PASS."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

from consume_capture import sha256


PIN = "a2509a2b5555437ff8ee1da4799e8210ad80e95a058881a5d26111a935e5b5d3"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", required=True, type=Path)
    ap.add_argument("--positive-result", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    assert sha256(args.capture) == PIN
    result = json.loads(args.positive_result.read_text(encoding="utf-8"))
    first = result["request_ledger"][0]
    nonzero = next(r for r in result["request_ledger"] if r["left"] != 0)
    last_rise = next(r["last_rise_cycle"] for r in result["serial_half_frames"] if r["pcm16"] != 0)
    prior, last_fall, window = None, None, None
    stable_cycle = None
    with args.capture.open(encoding="utf-8") as stream:
        for line in stream:
            r = json.loads(line)
            if r.get("kind") != "TICK":
                continue
            if prior is not None:
                if r["cycle"] > 10000 and stable_cycle is None and r["bclk"] == prior["bclk"]:
                    stable_cycle = r["cycle"]
                if prior["bclk"] == 1 and r["bclk"] == 0:
                    if r["cycle"] > last_rise:
                        window = (last_fall, r["cycle"])
                        break
                    last_fall = r["cycle"]
            prior = r
    assert window is not None
    specifications = [
        ("missing_tick", "TICK_ORDER_MISSING_DUPLICATE_OR_EPOCH"),
        ("duplicate_tick", "TICK_ORDER_MISSING_DUPLICATE_OR_EPOCH"),
        ("out_of_order", "TICK_ORDER_MISSING_DUPLICATE_OR_EPOCH"),
        ("x_pin", "X_OR_NONINTEGER"),
        ("wrong_commit_id", "STALE_DUPLICATE_OR_UNREQUESTED_COMMIT"),
        ("wrong_committed_pcm", "PLAY_PCM_COMMIT_OR_HOLD_ALIGNMENT"),
        ("din_changes_away_from_falling", "WS_DIN_CHANGED_OUTSIDE_FALLING_BCLK"),
        ("valid_slot_serial_lsb_corruption", "SERIAL_PCM_OR_CHANNEL_MISMATCH"),
        ("first_request_misses_real_frame", "REQUEST_NEXT_FRAME_DEADLINE_MISSED"),
        ("reset_then_end_no_low_tick", "END_WITH_UNOBSERVED_RESET"),
    ]
    receipts = []
    for name, expected in specifications:
        folder = args.output / name
        folder.mkdir()
        damaged = folder / "DAMAGED_FROM_REAL_CAPTURE.jsonl"
        changes = []
        holding = None
        reset_tail = False
        with args.capture.open(encoding="utf-8") as src, damaged.open("x", encoding="utf-8", newline="\n") as dst:
            for line in src:
                row = json.loads(line)
                if reset_tail:
                    continue
                if name == "reset_then_end_no_low_tick" and row.get("kind") == "RESET":
                    dst.write(line)
                    dst.write(json.dumps({"kind": "END", "cycle": row["cycle"], "epoch": row["epoch"]}) + "\n")
                    changes.append({"kind": "END_IMMEDIATELY_AFTER_REAL_RESET", "cycle": row["cycle"]})
                    reset_tail = True
                    continue
                if row.get("kind") != "TICK":
                    dst.write(line)
                    continue
                c = row["cycle"]
                if name == "missing_tick" and c == 2000:
                    changes.append({"cycle": c, "action": "REMOVE"})
                    continue
                if name == "duplicate_tick" and c == 2000:
                    dst.write(line)
                    changes.append({"cycle": c, "action": "DUPLICATE"})
                if name == "out_of_order" and c == 2000:
                    holding = line
                    continue
                if name == "out_of_order" and c == 2001:
                    dst.write(line)
                    dst.write(holding)
                    changes.append({"cycles": [2000, 2001], "action": "REVERSE"})
                    continue
                modified = False
                if name == "x_pin" and c == stable_cycle:
                    row["din"] = "x"; modified = True
                if name == "wrong_commit_id" and c == first["commit_cycle"]:
                    row["committed_id"] = 999; modified = True
                if name == "wrong_committed_pcm" and c == nonzero["commit_cycle"]:
                    row["left"] += 256; modified = True
                if name == "din_changes_away_from_falling" and c == stable_cycle:
                    row["din"] ^= 1; modified = True
                if name == "valid_slot_serial_lsb_corruption" and window[0] <= c < window[1]:
                    row["din"] ^= 1; modified = True
                if name == "first_request_misses_real_frame" and first["commit_cycle"] <= c <= first["sample_cycle"]:
                    row.update(commit=0, pending=0, play_left=0, play_right=0, clip_count=0)
                    modified = True
                if modified:
                    changes.append({"cycle": c, "action": "MODIFIED_FIELDS"})
                    dst.write(json.dumps(row, separators=(",", ":")) + "\n")
                else:
                    dst.write(line)
        digest = sha256(damaged)
        argv = [sys.executable, "-X", "utf8", str(Path(__file__).parent / "consume_capture.py"),
                str(damaged), "--sha256", digest, "--output", str(folder / "REJECTION.json")]
        start = time.monotonic()
        with (folder / "stdout.txt").open("xb") as out, (folder / "stderr.txt").open("xb") as err:
            child = subprocess.run(argv, stdout=out, stderr=err, check=False, timeout=300)
        rejected = json.loads((folder / "REJECTION.json").read_text(encoding="utf-8"))
        passed = child.returncode == 1 and rejected.get("diagnostic") == expected
        item = {"name": name, "expected": expected, "actual": rejected.get("diagnostic"), "passed": passed,
                "exit_code": child.returncode, "seconds": time.monotonic() - start, "argv": argv,
                "original_capture_sha256": PIN, "damaged_capture_sha256": digest,
                "damaged_bytes": damaged.stat().st_size, "changes": changes,
                "stdout_sha256": sha256(folder / "stdout.txt"), "stderr_sha256": sha256(folder / "stderr.txt"),
                "kind": "FULL_DAMAGED_DERIVATIVE_NOT_A_NEW_RTL_RUN"}
        (folder / "CASE_RECEIPT.json").write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8")
        archive = folder / "FULL_DAMAGED_CAPTURE.zip"
        with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as z:
            z.write(damaged, damaged.name)
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            with z.open(damaged.name) as stream:
                h = hashlib.sha256()
                for block in iter(lambda: stream.read(1048576), b""):
                    h.update(block)
            assert h.hexdigest() == digest
        # Only our own generated file; its exact bytes remain in verified ZIP.
        damaged.unlink()
        receipts.append(item)
        if not passed:
            break
    assert sha256(args.capture) == PIN
    (args.output / "RESULTS.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"cases": len(receipts), "passed": sum(r["passed"] for r in receipts),
                      "failed": [r["name"] for r in receipts if not r["passed"]],
                      "anti_stereo_swap_real_coverage": "NOT_DISTINGUISHABLE_EQUAL_CHANNEL_SAMPLES",
                      "RTL_invocations": 0}))
    return int(len(receipts) != len(specifications) or not all(r["passed"] for r in receipts))


if __name__ == "__main__":
    raise SystemExit(main())
