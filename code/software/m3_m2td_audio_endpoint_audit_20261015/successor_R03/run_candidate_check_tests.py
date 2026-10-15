"""Capture one bounded software predicate regression; no vendor process."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import argparse

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DOC = REPO / "code/docs/test/m3_m2td_audio_endpoint_audit_20261015/successor_R03"


def ident(path):
    b = path.read_bytes()
    return {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", choices=("r02", "r03"), required=True)
    out = DOC / ("candidate_checker_tests_" + ap.parse_args().run_id)
    out.mkdir(exist_ok=False)
    sources = [HERE / "check_candidate_report.py", HERE / "test_candidate_check.py", HERE.parent / "endpoint_audit.py"]
    before = {str(p): ident(p) for p in sources}
    argv = [sys.executable, "-I", "-S", "-B", "-X", "utf8", str(HERE / "test_candidate_check.py")]
    process = subprocess.run(argv, cwd=REPO, capture_output=True, timeout=30, check=False)
    (out / "stdout.txt").write_bytes(process.stdout)
    (out / "stderr.txt").write_bytes(process.stderr)
    after = {str(p): ident(p) for p in sources}
    receipt = {"argv": argv, "cwd": str(REPO), "exit_code": process.returncode, "before": before, "after": after,
               "unchanged": before == after, "stdout": ident(out / "stdout.txt"), "stderr": ident(out / "stderr.txt"),
               "synthetic_predicate_tests_only": True, "new_vendor_calls": 0, "board_release_allowed": False}
    (out / "RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"exit_code": process.returncode, "unchanged": before == after}))
    return process.returncode if before == after else 1


if __name__ == "__main__":
    raise SystemExit(main())
