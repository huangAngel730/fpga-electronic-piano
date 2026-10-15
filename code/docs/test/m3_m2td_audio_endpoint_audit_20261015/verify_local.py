"""Bounded software-only commands, raw streams and SHA receipts; exclusive output."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import argparse

ROOT = Path(__file__).resolve().parent


def identity(path):
    blob = path.read_bytes()
    return {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, choices=("r02", "r03", "r04"))
    run_id = parser.parse_args().run_id
    output = ROOT / ("verification_" + run_id)
    output.mkdir(exist_ok=False)
    originals = ROOT / "observed_r03/originals"
    inputs = sorted(ROOT.glob("*.py")) + [ROOT / "targets.json"] + sorted(originals.rglob("*"))
    inputs = [p for p in inputs if p.is_file()]
    evidence = ROOT.parents[3] / "code/docs/evidence/m2_m1td_physical_20261015"
    inputs += [evidence / "M2_138K_M1TD_整机PnR_STA_20261015.zip",
               evidence / "M2_138K_M1双音色延迟_ModelSim自包含输入_20261015.zip"]
    before = {str(p): identity(p) for p in inputs}
    commands = [
        ("observe", "inspect_original.py", ["--output", str(ROOT / ("observed_verify_" + run_id))]),
        ("derive", "source_identity.py", ["--output", str(ROOT / ("source_derived_verify_" + run_id))]),
        ("unit", "test_observations.py", []),
    ]
    receipts = []
    for name, script, args in commands:
        argv = [sys.executable, "-I", "-S", "-B", "-X", "utf8", str(ROOT / script), *args]
        start = time.monotonic()
        process = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=20, check=False)
        (output / (name + ".stdout.log")).write_bytes(process.stdout)
        (output / (name + ".stderr.log")).write_bytes(process.stderr)
        receipts.append({"name": name, "argv": argv, "cwd": str(ROOT), "exit_code": process.returncode,
                         "seconds": time.monotonic() - start, "timeout_seconds": 20,
                         "stdout": identity(output / (name + ".stdout.log")),
                         "stderr": identity(output / (name + ".stderr.log"))})
    after = {str(p): identity(p) for p in inputs}
    receipt = {"software_only": True, "new_eda_calls": 0, "board_release_allowed": False,
               "before": before, "after": after, "unchanged": before == after, "commands": receipts,
               "status": "SOFTWARE_PASS" if before == after and all(r["exit_code"] == 0 for r in receipts) else "FAIL"}
    (output / "RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "command_exit_codes": [r["exit_code"] for r in receipts], "source_input_unchanged": before == after}))
    return 0 if receipt["status"] == "SOFTWARE_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
