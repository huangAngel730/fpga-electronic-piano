"""B2 fresh task-day six-round budget; Python group<=90s, no native tools."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

from common import DOCS, HERE, ROOT, identity, save, sources


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", required=True, type=int)
    ap.add_argument("--start-case", default="positive")
    ap.add_argument("--reuse-base", type=Path)
    args = ap.parse_args()
    assert 1 <= args.round <= 6
    out = DOCS / f"ROUND_{args.round:02}"
    out.mkdir(exist_ok=False)
    preflight = json.loads((DOCS / "PREFLIGHT/PREFLIGHT.json").read_text(encoding="utf-8"))
    assert all(identity(Path(i["path"])) == i for i in preflight["runtime"]), "RUNTIME_DRIFT"
    assert all(identity(Path(i["path"])) == i for i in preflight["inputs"]), "READ_ONLY_INPUT_DRIFT"
    before = [identity(p) for p in sources()]
    snapshot = out / "sources"
    for item in before:
        p = Path(item["path"])
        dest = snapshot / p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(p.read_bytes())
        assert identity(dest)["sha256"] == item["sha256"]
    argv = [sys.executable, "-B", "-X", "utf8", str(HERE / "selftest.py"), "--output", str(out / "cases"), "--start-case", args.start_case]
    if args.reuse_base:
        argv += ["--reuse-base", str(args.reuse_base)]
    limit = min(90, (datetime(2026, 10, 17, 6, 4, 35, tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds())
    assert limit > 0, "TASK_DAY_DEADLINE"
    launch = {"round": args.round, "argv": argv, "cwd": str(ROOT), "source_before": before,
              "runtime": preflight["runtime"], "machine": platform.node(), "limit_s": limit,
              "started_utc": datetime.now(timezone.utc).isoformat(), "max_new_rounds": 6,
              "Icarus_ModelSim_Gowin_hardware_calls": 0, "old_test_suites_executed": 0}
    save(out / "LAUNCH.json", launch)
    begin = time.monotonic()
    timeout = False
    with (out / "stdout.bin").open("xb") as stdout, (out / "stderr.bin").open("xb") as stderr:
        child = subprocess.Popen(argv, cwd=ROOT, stdout=stdout, stderr=stderr)
        save(out / "CONSUMED.json", {"round": args.round, "first_pid": child.pid,
             "created_utc": datetime.now(timezone.utc).isoformat(), "launch": identity(out / "LAUNCH.json"),
             "owner": "B2_TASK_DAY_NEW_SIX_ROUNDS_SHARED_WITH_OWN_AGENTS"})
        try:
            child_code = child.wait(timeout=limit)
        except subprocess.TimeoutExpired:
            timeout = True
            subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True, check=False)
            child.wait(timeout=5)
            child_code = 124
    after = [identity(p) for p in sources()]
    runtime_same = all(identity(Path(i["path"])) == i for i in preflight["runtime"])
    code = child_code if before == after and runtime_same else 65
    receipt = {**launch, "source_after": after, "runtime_after_same": runtime_same,
               "child_exit_code": child_code, "exit_code": code, "timeout": timeout,
               "seconds": time.monotonic() - begin, "ended_utc": datetime.now(timezone.utc).isoformat(),
               "stdout": identity(out / "stdout.bin"), "stderr": identity(out / "stderr.bin"),
               "status": "PASS_NEW_ADAPTER_TESTS_ONLY" if code == 0 else "FAIL", "board_release_allowed": False}
    save(out / "RUN_RECEIPT.json", receipt)
    print(json.dumps({k: receipt[k] for k in ("round", "status", "exit_code", "seconds")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
