"""Identity/overwrite checks only; never start RTL or FPGA tools."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "code/scripts/prepare_138k_score_bram_integration.py"
SPEC = importlib.util.spec_from_file_location("ram_prepare", SCRIPT)
prep = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prep)


def digest_tree(path):
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob("*") if p.is_file()}


class PrepareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prep.BUILD_ROOT.mkdir(parents=True, exist_ok=True)
        cls.root = Path(tempfile.mkdtemp(prefix="identity_tests_", dir=prep.BUILD_ROOT))
        cls.source_hashes = digest_tree(prep.SCOPE)
        cls.source_hashes[str(SCRIPT)] = hashlib.sha256(SCRIPT.read_bytes()).hexdigest()

    def fresh(self, name):
        path = self.root / name
        prep.prepare(path)
        return path

    def cli(self, path, check=False):
        command = [sys.executable, "-B", "-X", "utf8", str(SCRIPT), "--output", str(path)]
        if check:
            command.append("--check")
        result = subprocess.run(command, capture_output=True, timeout=30)
        stem = path.name + ("_check" if check else "_prepare")
        (self.root / (stem + ".stdout.bin")).write_bytes(result.stdout)
        (self.root / (stem + ".stderr.bin")).write_bytes(result.stderr)
        return result

    def test_exact_scope_and_parent_preservation(self):
        out = self.fresh("positive")
        data, _, gprj, tcl, _ = prep.inputs(out)
        previous, _, _, previous_tcl, _ = prep.base.inputs(out)
        allowed = {"sources/audio_visual_coexistence_top.sv", "sources/score_transfer_candidate.sv"}
        for key, raw in previous.items():
            if key not in allowed:
                self.assertEqual(data[key], raw, key)
        top = "sources/audio_visual_coexistence_top.sv"
        self.assertEqual(data[top].replace(b"score_transfer_bram_candidate #",
                                          b"score_transfer_candidate #"), previous[top])
        self.assertNotIn("sources/score_transfer_candidate.sv", data)
        self.assertEqual(len(data), 62)
        self.assertEqual(len(ET.fromstring(gprj).find("FileList")), 53)
        self.assertEqual(tcl, previous_tcl)
        self.assertEqual(self.cli(out, check=True).returncode, 0)
        record = json.loads((out / "frozen_receipt.json").read_bytes())
        for field in ("fulltop_simulation_completed", "ready_for_PnR", "physical_STA_passed",
                      "board_release_allowed", "programmed", "playback_connected"):
            self.assertIs(record[field], False)

    def test_refuse_overwrite_and_scope_escape(self):
        out = self.fresh("overwrite")
        before = digest_tree(out)
        result = self.cli(out)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"REFUSE_OVERWRITE", result.stderr)
        self.assertEqual(digest_tree(out), before)
        for path in (prep.BUILD_ROOT, ROOT / "code/output/not_a_ram_build"):
            with self.assertRaises(ValueError):
                prep.guard(path)

    def test_mutated_inputs(self):
        changes = {
            "lane": "sources/score_byte_lane.sv",
            "receiver": "sources/score_transfer_bram_candidate.sv",
            "top": "sources/audio_visual_coexistence_top.sv",
            "rom": "rom/piano_band_4x256_8191.mem",
            "cst": "constraints/audio_visual.cst",
            "sdc": "constraints/audio_visual_hold055.sdc",
        }
        for name, relative in changes.items():
            with self.subTest(name=name):
                out = self.fresh("mutate_" + name)
                path = out / "inputs" / relative
                path.write_bytes(path.read_bytes() + b"\nIDENTITY_CORRUPTION\n")
                result = self.cli(out, check=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"EXACT62_INPUTS_OR_HIDDEN_FILE", result.stderr)
        for name in ("extra", "missing"):
            with self.subTest(name=name):
                out = self.fresh("mutate_" + name)
                path = out / "inputs/sources/score_byte_lane.sv"
                if name == "missing":
                    path.unlink()
                else:
                    (out / "inputs/.hidden.v").write_bytes(b"extra hidden input")
                result = self.cli(out, check=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"EXACT62_INPUTS_OR_HIDDEN_FILE", result.stderr)

    def test_project_and_receipt_corruption(self):
        for field, value in (("physical_STA_passed", True), ("board_release_allowed", True),
                             ("ready_for_PnR", True), ("fulltop_simulation_completed", True),
                             ("device", {"name": "wrong_device"}), ("input_count", 61),
                             ("parent", "wrong_parent"), ("inputs", {})):
            with self.subTest(field=field):
                out = self.fresh("receipt_" + field)
                path = out / "frozen_receipt.json"
                record = json.loads(path.read_bytes())
                record[field] = value
                path.write_text(json.dumps(record), encoding="utf-8")
                result = self.cli(out, check=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"EXACT_RAM_FROZEN_RECEIPT", result.stderr)
        for name in ("duplicate_project_entry", "run_tcl"):
            with self.subTest(name=name):
                out = self.fresh(name)
                if name == "run_tcl":
                    (out / "run.tcl").write_bytes(b"run all; changed options")
                else:
                    path = out / prep.PROJECT
                    tree = ET.fromstring(path.read_bytes())
                    files = tree.find("FileList")
                    ET.SubElement(files, "File", **files[0].attrib)
                    path.write_bytes(ET.tostring(tree, encoding="utf-8"))
                result = self.cli(out, check=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"EXACT_PROJECT_OPTIONS", result.stderr)

    @classmethod
    def tearDownClass(cls):
        now = digest_tree(prep.SCOPE)
        now[str(SCRIPT)] = hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
        if now != cls.source_hashes:
            raise AssertionError("PREPARATION_SOURCE_CHANGED")
        print("EVIDENCE_OUTPUT=" + str(cls.root), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
