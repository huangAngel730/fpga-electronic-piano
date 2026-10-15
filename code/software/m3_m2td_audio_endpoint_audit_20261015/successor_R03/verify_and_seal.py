"""Bounded software recovery verification and evidence seal. Never starts Gowin."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DOC = REPO / "code/docs/test/m3_m2td_audio_endpoint_audit_20261015/successor_R03"


def identity(path):
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, choices=("r01", "r02"))
    args = parser.parse_args()
    logs = DOC / ("verification_" + args.run_id)
    logs.mkdir(exist_ok=False)
    protected = sorted(HERE.glob("*.py")) + [Path(sys.executable)]
    protected += sorted((DOC / "input_audit_r01/derived_original_bytes").rglob("*"))
    protected = [p for p in protected if p.is_file()]
    before = {str(p): identity(p) for p in protected}
    commands = [("recovery", "freeze_audit.py", ["--output", str(DOC / ("input_audit_verify_" + args.run_id))]),
                ("unit", "test_freeze_audit.py", [])]
    records = []
    for name, script, tail in commands:
        argv = [sys.executable, "-I", "-S", "-B", "-X", "utf8", str(HERE / script), *tail]
        started = time.monotonic()
        p = subprocess.run(argv, cwd=REPO, capture_output=True, timeout=30, check=False)
        (logs / (name + ".stdout.txt")).write_bytes(p.stdout)
        (logs / (name + ".stderr.txt")).write_bytes(p.stderr)
        records.append({"argv": argv, "cwd": str(REPO), "exit_code": p.returncode, "seconds": time.monotonic() - started,
                        "stdout": identity(logs / (name + ".stdout.txt")), "stderr": identity(logs / (name + ".stderr.txt"))})
    after = {str(p): identity(p) for p in protected}
    status = "RECOVERY_SOFTWARE_PASS_PHYSICAL_BLOCKED" if before == after and all(x["exit_code"] == 0 for x in records) else "SOFTWARE_FAIL"
    result = {"status": status, "time_utc": datetime.now(timezone.utc).isoformat(), "python_version": sys.version,
              "commands": records, "before": before, "after": after, "unchanged": before == after,
              "physical_tool_starts": 0, "physical_allowance_consumed": False, "board_release_allowed": False}
    (logs / "RECEIPT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "exit_codes": [r["exit_code"] for r in records], "physical_allowance_consumed": False}))
    return 0 if status == "RECOVERY_SOFTWARE_PASS_PHYSICAL_BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
