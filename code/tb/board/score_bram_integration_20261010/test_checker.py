"""Synthetic parser fixtures only; this suite does not execute RTL."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "code/tb/board/score_receive_integration_20261009"
SPEC = importlib.util.spec_from_file_location("fixed_vectors", BASE / "vectors.py")
vectors = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vectors)
CHECKER = Path(__file__).with_name("check_capture.py")


class WireCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent = ROOT / "code/output"
        parent.mkdir(exist_ok=True)
        cls.root = Path(tempfile.mkdtemp(prefix="m2_RAM_checker_synthetic_", dir=parent))
        cls.oracle = vectors.build(cls.root / "vectors")
        lines = ["META exact_score_uart_fulltop nominalPLL DVIstub"]
        rx_count = tx_count = 0
        for row in cls.oracle["cases"]:
            index = row["id"]
            lines.append(f"CASE {index} {row['op']}")
            if row["op"] == "S":
                lines.extend((f"RX {index} {row['request']}", f"TX {index} {row['response']}"))
                pulses = 0 if index == 12 else 1 if index >= 4 else 0
                lines.append(f"PUBLIC {index} {row['committed_valid']} {row['committed_count']} {row['score_id']} {pulses}")
                rx_count += len(bytes.fromhex(row["request"]))
                tx_count += len(bytes.fromhex(row["response"]))
        lines.append(f"END 600001 200001 801 101 12 {rx_count} {tx_count}")
        cls.lines = lines
        cls.results = []

    def run_case(self, name, lines, oracle=None, negative=False):
        folder = self.root / name
        folder.mkdir()
        capture = folder / "capture.txt"
        capture.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8", newline="\n")
        truth = folder / "oracle.json"
        truth.write_text(json.dumps(self.oracle if oracle is None else oracle), encoding="utf-8")
        command = [sys.executable, "-B", "-X", "utf8", str(CHECKER),
                   "--capture", str(capture), "--oracle", str(truth)]
        if negative:
            command.append("--negative")
        result = subprocess.run(command, capture_output=True, timeout=30)
        (folder / "stdout.bin").write_bytes(result.stdout)
        (folder / "stderr.bin").write_bytes(result.stderr)
        self.results.append({"name": name, "exit_code": result.returncode,
                             "capture_SHA256": hashlib.sha256(capture.read_bytes()).hexdigest(),
                             "oracle_SHA256": hashlib.sha256(truth.read_bytes()).hexdigest(),
                             "diagnostic": result.stdout.decode("utf-8").strip()})
        return result

    def test_positive_and_malformed(self):
        self.assertEqual(self.run_case("synthetic_positive", self.lines).returncode, 0)
        changed = list(self.lines)
        tx = next(i for i, row in enumerate(changed) if row.startswith("TX 0 "))
        raw = bytearray.fromhex(changed[tx].split()[2])
        raw[-1] ^= 1
        bad_crc = list(changed)
        bad_crc[tx] = "TX 0 " + raw.hex()
        raw = bytearray.fromhex(changed[tx].split()[2])
        raw[12] ^= 1
        raw[-2:] = vectors.crc(raw[2:-2]).to_bytes(2, "little")
        bad_command = list(changed)
        bad_command[tx] = "TX 0 " + raw.hex()
        bad_public = list(changed)
        public = next(i for i, row in enumerate(changed) if row.startswith("PUBLIC 4 "))
        bad_public[public] = "PUBLIC 4 1 2 102 1"
        bad_counts = list(changed)
        bad_counts[-1] = "END 600001 200001 801 101 11 1 1"
        cases = {"empty": [], "no_END": changed[:-1], "unknown": changed[:-1] + ["UNKNOWN 1", changed[-1]],
                 "after_END": changed + ["CASE 13 S"], "duplicate_RX": changed[:-1] + [changed[2], changed[-1]],
                 "missing_TX": changed[:tx] + changed[tx+1:], "bad_crc": bad_crc,
                 "valid_crc_wrong_command": bad_command, "bad_public": bad_public, "bad_counts": bad_counts}
        for name, lines in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.run_case(name, lines).returncode, 1)
        for name, field, value in (("schema_bool", "schema", True), ("count_float", "count", 13.0)):
            truth = json.loads(json.dumps(self.oracle))
            truth[field] = value
            self.assertEqual(self.run_case(name, changed, truth).returncode, 1)
        truth = json.loads(json.dumps(self.oracle))
        truth["cases"][0]["id"] = False
        self.assertEqual(self.run_case("id_bool", changed, truth).returncode, 1)

    @classmethod
    def tearDownClass(cls):
        (cls.root / "receipt.json").write_text(json.dumps({
            "scope": "SYNTHETIC checker inputs, not RTL capture or hardware proof",
            "cases": cls.results, "count": len(cls.results)}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print("SYNTHETIC_OUTPUT=" + str(cls.root), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
