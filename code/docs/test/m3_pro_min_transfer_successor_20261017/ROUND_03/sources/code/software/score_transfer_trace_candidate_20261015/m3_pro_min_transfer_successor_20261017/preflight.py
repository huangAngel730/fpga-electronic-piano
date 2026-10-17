"""Read-only E3 runtime/source preflight, no module simulation."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from common import DOCS, MIDI, MIDI_SHA, OLD_PY, ROOT, TOOL, identity, save


def main():
    out = DOCS / "PREFLIGHT"
    out.mkdir(parents=True, exist_ok=False)
    files = sorted(p for p in TOOL.rglob("*") if p.is_file())
    prefix = Path(sys.base_prefix)
    files += [Path(sys.executable), *prefix.glob("*.dll"), *prefix.glob("DLLs/*.dll"), *prefix.glob("DLLs/*.pyd")]
    files += sorted(p for p in (prefix / "Lib").rglob("*.py") if "site-packages" not in p.parts)
    runtime = [identity(p) for p in dict.fromkeys(files)]
    steps = []
    for label, argv in (("python", [sys.executable, "--version"]),
                        ("iverilog", [str(TOOL / "bin/iverilog.exe"), "-V"]),
                        ("vvp", [str(TOOL / "bin/vvp.exe"), "-V"])):
        started = time.monotonic()
        with (out / (label + ".stdout.bin")).open("xb") as stdout, (out / (label + ".stderr.bin")).open("xb") as stderr:
            p = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr, timeout=30, check=False)
        item = {"argv": argv, "cwd": str(ROOT), "exit_code": p.returncode,
                "seconds": time.monotonic() - started, "stdout": identity(out / (label + ".stdout.bin")),
                "stderr": identity(out / (label + ".stderr.bin"))}
        steps.append(item)
        assert p.returncode == 0, label + "_STARTUP_FAILED"
    assert identity(MIDI)["sha256"] == MIDI_SHA and MIDI.stat().st_size == 300
    # Published byte identities are strict, including original newline bytes.
    assert identity(OLD_PY[1])["sha256"] == "8e2a065dcea4fef997da2b0fda7e16a314c65c436b654903ca388be407ddfc07"
    protocol = ROOT / "code/docs/hardware/score_transfer_v1/PROTOCOL.md"
    assert identity(protocol)["sha256"] == "431b5cd7ae678c97bcb0be720a775b51a031f096161a0dbef36bdeea5f41f15b"
    task = Path("E:/FPGA/GAOYUNFPGA/night_task/10.17/M3_四项完整拓展主责任务单_2026-10-17 (1).md")
    assert identity(task)["sha256"] == "b8e6372b7cd9261f276247754a8f2f9bc8841c31344edc3116a78827d964ed0e"
    record = {"status": "PREFLIGHT_PASS_NO_FUNCTIONAL_ROUND", "time_utc": datetime.now(timezone.utc).isoformat(),
              "machine": platform.node(), "python_version": sys.version, "steps": steps,
              "environment": {k: os.environ.get(k) for k in ("PATH", "SYSTEMROOT", "TEMP")},
              "runtime": runtime, "midi": identity(MIDI), "task": identity(task), "protocol": identity(protocol),
              "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "origin_develop": subprocess.check_output(["git", "rev-parse", "origin/develop"], cwd=ROOT, text=True).strip(),
              "board_release_allowed": False}
    save(out / "PREFLIGHT.json", record)
    print(json.dumps({"status": record["status"], "runtime_files": len(runtime), "versions_exit": [s["exit_code"] for s in steps]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
