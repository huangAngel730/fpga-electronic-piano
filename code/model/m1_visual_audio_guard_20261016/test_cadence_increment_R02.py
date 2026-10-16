"""Only the R02 cadence boundary delta; do not rerun the R01 suite."""

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest

import visual_audio_guard as guard


def packed(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def save(path, data):
    with path.open("xb") as output:
        output.write(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--basis", type=Path, required=True)
    parser.add_argument("--basis-sha256", required=True)
    parser.add_argument("--r01-evidence", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    basis = args.basis.resolve()
    if guard.sha256_file(basis) != args.basis_sha256:
        parser.error("A basis SHA mismatch")
    evidence = args.evidence_dir.resolve()
    evidence.mkdir(exist_ok=False)
    started = time.monotonic()
    started_utc = datetime.now(timezone.utc).isoformat()
    source_path = Path(guard.__file__).resolve()
    original_path = args.r01_evidence.resolve() / "identical_complete_window/before.json"
    original = guard.read_json(original_path)
    watched = [basis, source_path, Path(__file__).resolve(), original_path, Path(sys.executable).resolve()]
    before_sha = {str(path): guard.sha256_file(path) for path in watched}
    records = []
    cases = [("same_gaps_2499", [833, 833, 833], 0), ("same_gaps_2501", [834, 834, 833], 0), ("gap_832_rejected", [833, 832, 834], 2)]

    class Incremental(unittest.TestCase):
        def execute(self, name, gaps, expected_exit):
            root = evidence / name
            root.mkdir()
            document = copy.deepcopy(original)
            rows = document["frames"][2:6]
            cycle = rows[0]["cycle"]
            for index, row in enumerate(rows):
                if index:
                    cycle += gaps[index - 1]
                row.update(epoch=0, frame=index, cycle=cycle, commit_cycle=cycle - 20)
            document["frames"] = rows
            document["window"] = {"first_cycle": rows[0]["cycle"], "last_cycle": rows[-1]["cycle"], "expected_frames": len(rows)}
            contract = {key: copy.deepcopy(document[key]) for key in guard.CONTRACT_KEYS}
            contract["schema"] = guard.CONTRACT_SCHEMA
            for label, value in [("before", document), ("after", document), ("contract", contract)]:
                save(root / (label + ".json"), packed(value))
            output_path = root / "comparison.json"
            command = [sys.executable, "-X", "utf8", "-B", str(source_path), "--before", str(root / "before.json"), "--after", str(root / "after.json"), "--contract", str(root / "contract.json"), "--basis", str(basis), "--output", str(output_path)]
            start = time.monotonic()
            completed = subprocess.run(command, cwd=source_path.parent, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False)
            save(root / "stdout.bin", completed.stdout)
            save(root / "stderr.bin", completed.stderr)
            record = {"case": name, "gaps": gaps, "sum_three_gaps": sum(gaps), "argv": command, "cwd": str(source_path.parent), "expected_exit": expected_exit, "exit_code": completed.returncode, "elapsed_seconds": round(time.monotonic() - start, 6), "timed_out": False, "files": {path.name: {"bytes": path.stat().st_size, "sha256": guard.sha256_file(path)} for path in sorted(root.iterdir())}}
            records.append(record)
            save(root / "receipt.json", packed(record))
            self.assertEqual(completed.returncode, expected_exit, completed.stderr.decode("utf-8", "replace"))
            if expected_exit == 0:
                result = guard.read_json(output_path)
                self.assertEqual(result["real_result"], "PENDING_REAL_CAPTURE")
                self.assertEqual(result["visual_audio_nondegradation"], "NOT_SIGNED_BY_THIS_SOFTWARE")
            else:
                self.assertIn(b"frame cadence outside 833/834 cycles", completed.stderr)
                self.assertFalse(output_path.exists())

    for name, gaps, expected in cases:
        def directed(self, name=name, gaps=gaps, expected=expected):
            self.execute(name, gaps, expected)
        setattr(Incremental, "test_" + name, directed)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Incremental))
    after_sha = {str(path): guard.sha256_file(path) for path in watched}
    unchanged = before_sha == after_sha
    report = {"schema": "M1_B_CADENCE_INCREMENT_R02_V1", "started_utc": started_utc, "test_count": result.testsRun, "accepted_cases": 2, "rejection_cases": 1, "failures": len(result.failures), "errors": len(result.errors), "source_before_sha256": before_sha, "source_after_sha256": after_sha, "source_unchanged": unchanged, "elapsed_seconds": round(time.monotonic() - started, 6), "case_receipts": [name + "/receipt.json" for name, _, _ in cases], "R01_status": "HISTORY_OLD_CADENCE_OVERCONSTRAINT_NOT_RERUN", "real_result": "PENDING_REAL_CAPTURE", "result": "SOFTWARE_INCREMENT_ACCEPTED" if result.wasSuccessful() and unchanged else "SOFTWARE_INCREMENT_FAILED"}
    save(evidence / "INCREMENT_SUMMARY_R02.json", packed(report))
    print(json.dumps({key: report[key] for key in ("result", "test_count", "real_result")}))
    return 0 if result.wasSuccessful() and unchanged else 1


if __name__ == "__main__":
    raise SystemExit(main())
