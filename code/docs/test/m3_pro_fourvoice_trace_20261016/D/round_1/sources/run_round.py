"""D/D2 immutable numbered round; global 90s budget, at most four rounds."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

from preflight import ROOT, DOCS, identity


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", required=True, type=int)
    args = ap.parse_args()
    assert 1 <= args.round <= 4
    out = DOCS / ("round_" + str(args.round))
    out.mkdir(exist_ok=False)
    snapshots = out / "sources"
    snapshots.mkdir()
    sources = {p.name: identity(p) for p in Path(__file__).parent.glob("*.py")}
    for name, item in sources.items():
        (snapshots / name).write_bytes(Path(item["path"]).read_bytes())
        assert identity(snapshots / name)["sha256"] == item["sha256"]
    preflight = json.loads((DOCS / "preflight_20261017/PREFLIGHT.json").read_text(encoding="utf-8"))
    for item in preflight["dependencies"]:
        assert identity(Path(item["path"])) == item
    argv = [sys.executable, "-X", "utf8", str(Path(__file__).parent / "test_suite.py"), "--output", str(out / "cases")]
    launch = {"round": args.round, "source_before": sources, "argv": argv, "cwd": str(ROOT),
              "machine": platform.node(), "python": identity(Path(sys.executable)), "dependencies": preflight["dependencies"],
              "timeout_s": 90, "started_utc": datetime.now(timezone.utc).isoformat(), "EDA_calls": 0}
    (out / "LAUNCH.json").write_text(json.dumps(launch, indent=2) + "\n", encoding="utf-8")
    begin = time.monotonic()
    code = 1; timeout = False
    with (out / "stdout.txt").open("xb") as stdout, (out / "stderr.txt").open("xb") as stderr:
        child = subprocess.Popen(argv, cwd=ROOT, stdout=stdout, stderr=stderr)
        with (out / "CONSUMED.json").open("x", encoding="utf-8") as stream:
            json.dump({"round": args.round, "pid": child.pid, "created_utc": datetime.now(timezone.utc).isoformat(),
                       "launch": identity(out / "LAUNCH.json"), "budget_owner": "D_D2_4_ROUNDS_D3_2_RESERVED"}, stream, indent=2)
        try:
            code = child.wait(timeout=90)
        except subprocess.TimeoutExpired:
            timeout = True; code = 124
            subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True, check=False)
            child.wait(timeout=5)
    receipt = {**launch, "exit_code": code, "timeout": timeout, "seconds": time.monotonic() - begin,
        "ended_utc": datetime.now(timezone.utc).isoformat(), "source_after": {n: identity(Path(i["path"])) for n, i in sources.items()},
        "stdout": identity(out / "stdout.txt"), "stderr": identity(out / "stderr.txt")}
    (out / "RUN_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"round": args.round, "exit_code": code, "seconds": receipt["seconds"], "timeout": timeout}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
