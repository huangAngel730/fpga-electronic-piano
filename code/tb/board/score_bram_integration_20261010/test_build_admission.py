"""Reject invalid build admission before any EDA process is launched."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
RUNNER = ROOT / "code/scripts/run_138k_score_bram_build_once.py"
PROJECT = ROOT / "code/build/138k_score_bram/staged_20261010_strict_receipt_v2"
PROOFS = [ROOT / "code/output" / f"m2_score_bram_fulltop_20261010_{n}/receipt.json"
          for n in ("02", "01", "03", "05")]


class BuildAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="m2_RAM_build_admission_", dir=ROOT / "code/output"))
        cls.results = []

    def invoke(self, name, proofs=None, target=None, timeout=1800, reason=None):
        output = target or ROOT / "code/build/138k_score_bram/runs" / (self.root.name + "_" + name)
        command = [sys.executable, "-B", "-X", "utf8", str(RUNNER), "--project", str(PROJECT),
                   "--output", str(output), "--simulation-receipts",
                   *map(str, proofs or PROOFS), "--timeout-seconds", str(timeout), "--preflight-only"]
        result = subprocess.run(command, capture_output=True, timeout=30)
        (self.root / (name + ".stdout.bin")).write_bytes(result.stdout)
        (self.root / (name + ".stderr.bin")).write_bytes(result.stderr)
        self.results.append({"name": name, "exit": result.returncode, "expected_reason": reason,
                             "output_created": output.exists(), "command": command})
        self.assertNotEqual(result.returncode, 0)
        if reason:
            self.assertIn(reason.encode("ascii"), result.stdout + result.stderr)
        return output

    def test_invalid_proofs_and_output(self):
        self.invoke("duplicate", [PROOFS[0], PROOFS[1], PROOFS[1], PROOFS[3]],
                    reason="DUPLICATE_SIMULATION_PROOF")
        self.invoke("timeout", timeout=1801, reason="TIMEOUT_OUT_OF_RANGE")
        existing = ROOT / "code/build/138k_score_bram/runs/fulltop_20261010_01"
        self.invoke("overwrite", target=existing, reason="REFUSE_OVERWRITE")
        escaped = self.root / "outside_run_scope"
        self.invoke("escape", target=escaped)
        self.assertFalse(escaped.exists())
        for case, field, value, reason in (("numeric_pass", "passed", 1, "SIMULATION_NOT_QUALIFIED"),
                                          ("wrong_project", "frozen_receipt_SHA256", "0" * 64,
                                           "SIMULATED_PROJECT_IDENTITY_MISMATCH")):
            proof = json.loads(PROOFS[0].read_bytes())
            proof[field] = value
            path = self.root / (case + ".json")
            path.write_text(json.dumps(proof), encoding="utf-8")
            output = self.invoke(case, [path, *PROOFS[1:]], reason=reason)
            self.assertFalse(output.exists())

    @classmethod
    def tearDownClass(cls):
        (cls.root / "receipt.json").write_text(json.dumps({
            "scope": "build admission software negatives only; preflight-only on every invocation",
            "new_EDA_calls": 0, "cases": cls.results}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print("BUILD_ADMISSION_OUTPUT=" + str(cls.root), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
