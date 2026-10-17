"""This task-day runtime/input snapshot, no old tests or native tools."""
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

from common import DOCS, D3, LEGACY, LEGACY_SHA, MONITOR, OLD, ROOT, identity, save


def main():
    out = DOCS / "PREFLIGHT"
    out.mkdir(parents=True, exist_ok=False)
    assert identity(LEGACY)["sha256"] == LEGACY_SHA
    prefix = Path(sys.base_prefix)
    runtime = [Path(sys.executable), *prefix.glob("*.dll"), *prefix.glob("DLLs/*.dll"), *prefix.glob("DLLs/*.pyd")]
    runtime += [p for p in (prefix / "Lib").rglob("*.py") if "site-packages" not in p.parts]
    dependencies = [identity(p) for p in sorted(set(runtime))]
    argv = [sys.executable, "--version"]
    start = time.monotonic()
    with (out / "python.stdout.bin").open("xb") as stdout, (out / "python.stderr.bin").open("xb") as stderr:
        call = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr, timeout=30, check=False)
    assert call.returncode == 0
    task = Path("E:/FPGA/GAOYUNFPGA/night_task/10.17/task-day/M3_当日任务单_2026-10-17.md")
    other = task.parent / "M3_完赛任务单_2026-10-15.md"
    assert identity(task)["sha256"] == "4142a701d0f48c3965c0596641be859d85cf7788b2d17d5d3af64f0e1745af75"
    assert identity(other)["sha256"] == "7235fb23d4584687259d2743aaa4b91a517e2b5bd3dc8867f0e29857f3b14033"
    record = {"status": "PREFLIGHT_PASS_NO_FUNCTIONAL_ROUND", "argv": argv, "cwd": str(ROOT),
              "exit_code": call.returncode, "seconds": time.monotonic() - start,
              "UTC": datetime.now(timezone.utc).isoformat(), "machine": platform.node(), "python_version": sys.version,
              "runtime": dependencies, "inputs": [identity(p) for p in [task, other, D3, LEGACY, OLD / "fixture.py",
                    MONITOR / "CONTRACT.md", MONITOR / "RESULT.md", MONITOR / "ROUND_02/case_00.csv"]],
              "stdout": identity(out / "python.stdout.bin"), "stderr": identity(out / "python.stderr.bin"),
              "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "origin_develop": subprocess.check_output(["git", "rev-parse", "origin/develop"], cwd=ROOT, text=True).strip(),
              "Icarus_calls": 0, "ModelSim_Gowin_hardware_calls": 0}
    save(out / "PREFLIGHT.json", record)
    print(json.dumps({"status": record["status"], "runtime_files": len(dependencies), "exit_code": call.returncode}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
