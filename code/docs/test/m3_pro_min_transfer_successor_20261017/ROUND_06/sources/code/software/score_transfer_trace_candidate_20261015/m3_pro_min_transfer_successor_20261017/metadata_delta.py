"""Round6: new coverage-claim controls only, no repeated RTL/serial groups."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from check_e3 import commit_fix_coverage
from common import DOCS, HERE, ROOT, identity, save, sources


def worker(out):
    out.mkdir(exist_ok=False)
    prior = DOCS / "ROUND_05"
    old = DOCS / "ROUND_01/inputs/EXPECTED.json"
    plan_path = prior / "inputs/EXPECTED.json"
    result_path = prior / "checked/RESULT.json"
    receipt_path = prior / "RUN_RECEIPT.json"
    inputs = [identity(p) for p in (old, plan_path, result_path, receipt_path, prior / "CAPTURE.txt")]
    save(out / "EXPECTED.json", {"full_new": "TESTED", "clean_only": "NOT_EXERCISED", "old_plan": "NOT_EXERCISED",
          "missing_cache_reject": "NOT_EXERCISED", "active_session_wrong": "NOT_EXERCISED",
          "RTL_calls": 0, "serial_groups_reexecuted": 0})
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    checked = json.loads(result_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"].startswith("PASS") and receipt["source_before"] == receipt["source_after"]
    assert receipt["runtime_after_same"] and checked["passed"] and checked["cases"] == len(plan["cases"])
    assert checked["capture"] == identity(prior / "CAPTURE.txt") == receipt["positive_capture"]
    proofs = {p["label"]: p for p in checked["reply_proofs"]}
    assert proofs["incomplete_commit_nack8_invalidates"]["metadata"][:4] == [3, 8, 1, 0]
    assert proofs["after_nack8_exact_cached_data_must_not_ack"]["metadata"][:4] == [2, 5, 1, 0]
    assert proofs["after_nack8_next_data_rejected"]["metadata"][:4] == [2, 5, 1, 0]
    full = commit_fix_coverage(plan["cases"])
    assert full == "SUCCESSOR_FIX_TESTED_OLD_SOURCE_PRESERVED"
    controls = {"full_new": full,
                "clean_only": commit_fix_coverage(plan["cases"][:plan["clean_last_case"]]),
                "old_plan": commit_fix_coverage(json.loads(old.read_text(encoding="utf-8"))["cases"])}
    missing = [c for c in plan["cases"] if c["label"] != "after_nack8_exact_cached_data_must_not_ack"]
    controls["missing_cache_reject"] = commit_fix_coverage(missing)
    wrong = deepcopy(plan["cases"])
    next(c for c in wrong if c["label"] == "incomplete_commit_nack8_invalidates")["state"]["active"] = 1
    controls["active_session_wrong"] = commit_fix_coverage(wrong)
    assert all(value == "NOT_EXERCISED" for label, value in controls.items() if label != "full_new")
    assert inputs == [identity(Path(i["path"])) for i in inputs]
    save(out / "RESULT.json", {"passed": True, "level": "L1_COVERAGE_METADATA_DELTA", "controls": controls,
          "functional_source_relation": "Only final coverage label helper changed after successful ROUND05; serial checker logic and RTL not rerun",
          "inputs": inputs, "RTL_calls": 0, "serial_groups_reexecuted": 0, "board_release_allowed": False})
    print(json.dumps({"passed": True, "controls": controls}))
    return 0


def controller():
    out = DOCS / "ROUND_06"
    out.mkdir(exist_ok=False)
    before = [identity(p) for p in sources()]
    preflight = json.loads((DOCS / "PREFLIGHT/PREFLIGHT.json").read_text(encoding="utf-8"))
    assert all(identity(Path(i["path"])) == i for i in preflight["runtime"])
    snapshot = out / "sources"
    for item in before:
        p = Path(item["path"])
        dest = snapshot / p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(p.read_bytes())
        assert identity(dest)["sha256"] == item["sha256"]
    argv = [sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve()), "--worker", str(out / "delta")]
    launch = {"round": 6, "argv": argv, "cwd": str(ROOT), "source_before": before,
              "runtime": preflight["runtime"], "machine": platform.node(), "timeout_s": 90,
              "started_utc": datetime.now(timezone.utc).isoformat(), "RTL_calls": 0}
    save(out / "LAUNCH.json", launch)
    begin = time.monotonic()
    timeout = False
    with (out / "stdout.bin").open("xb") as stdout, (out / "stderr.bin").open("xb") as stderr:
        child = subprocess.Popen(argv, cwd=ROOT, stdout=stdout, stderr=stderr)
        save(out / "CONSUMED.json", {"round": 6, "first_pid": child.pid,
             "created_utc": datetime.now(timezone.utc).isoformat(), "launch": identity(out / "LAUNCH.json"),
             "owner": "E3_SIX_ROUNDS_SHARED"})
        try:
            child_code = child.wait(timeout=90)
        except subprocess.TimeoutExpired:
            timeout = True
            subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True, check=False)
            child.wait(timeout=5)
            child_code = 124
    after = [identity(p) for p in sources()]
    runtime_same = all(identity(Path(i["path"])) == i for i in preflight["runtime"])
    code = child_code if before == after and runtime_same else 65
    receipt = {**launch, "source_after": after, "runtime_after_same": runtime_same, "exit_code": code,
               "child_exit_code": child_code, "status": "PASS_METADATA_DELTA" if code == 0 else "FAIL",
               "timeout": timeout, "seconds": time.monotonic() - begin,
               "ended_utc": datetime.now(timezone.utc).isoformat(), "stdout": identity(out / "stdout.bin"),
               "stderr": identity(out / "stderr.bin"), "hardware_calls": 0, "Git_writes": 0}
    save(out / "RUN_RECEIPT.json", receipt)
    print(json.dumps({"round": 6, "exit_code": code, "seconds": receipt["seconds"], "status": receipt["status"]}))
    return code


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", type=Path)
    args = ap.parse_args()
    raise SystemExit(worker(args.worker) if args.worker else controller())
