"""Identity and append-only constraint checks; no RTL/EDA tools."""
from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "code/scripts"))
import prepare_138k_score_bram_timing_repair as prep


class RepairPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prep.BUILD_ROOT.mkdir(exist_ok=True)
        cls.root = Path(tempfile.mkdtemp(prefix="identity_tests_", dir=prep.BUILD_ROOT))
        cls.results = []

    def new(self, name):
        out = self.root / name
        prep.prepare(out)
        return out

    def test_only_parser_and_append_SDC_changed(self):
        out = self.new("positive")
        old = prep.parent.inputs(out)[0]
        data, _, project, tcl = prep.inputs(out)
        changes = {name for name in old if old[name] != data[name]}
        self.assertEqual(changes, {"sources/midi_event_parser.sv", "constraints/audio_visual_hold055.sdc"})
        key = "constraints/audio_visual_hold055.sdc"
        self.assertTrue(data[key].startswith(old[key]))
        added = data[key][len(old[key]):].decode("utf-8")
        self.assertEqual(added.count("set_min_delay "), 1)
        self.assertEqual(added.count("report_timing "), 2)
        self.assertNotIn("set_false_path", added)
        self.assertNotIn("set_clock_uncertainty", added)
        self.assertEqual(len(ET.fromstring(project).find("FileList")), 53)
        self.assertEqual(len(data), 62)
        receipt = prep.validate(out)
        self.assertFalse(receipt["physical_STA_passed"])
        self.assertFalse(receipt["ready_for_PnR"])

    def test_damage_and_overwrite_refused(self):
        for i, rel in enumerate(("sources/midi_event_parser.sv", "sources/score_transfer_bram_candidate.sv",
                                "rom/sine_1024_8192.mem", "constraints/audio_visual.cst",
                                "constraints/audio_visual_hold055.sdc")):
            out = self.new("bad_input_" + str(i))
            path = out / "inputs" / rel
            path.write_bytes(path.read_bytes() + b"\nchanged\n")
            with self.assertRaisesRegex(ValueError, "EXACT62"):
                prep.validate(out)
            self.results.append(rel)
        for field, value in (("physical_STA_passed", True), ("physical_STA_passed", 0),
                             ("input_count", 62.0), ("prepare_script_sha256", "wrong")):
            out = self.new("bad_receipt_" + field + "_" + type(value).__name__)
            path = out / "frozen_receipt.json"
            record = json.loads(path.read_bytes())
            record[field] = value
            path.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "RECEIPT_BYTES"):
                prep.validate(out)
            self.results.append(field + "_" + type(value).__name__)
        out = self.new("overwrite")
        with self.assertRaisesRegex(ValueError, "REFUSE_OVERWRITE"):
            prep.prepare(out)
        with self.assertRaises(ValueError):
            prep.guard(ROOT / "code/output/outside_repair")

    @classmethod
    def tearDownClass(cls):
        (cls.root / "test_receipt.json").write_text(json.dumps({
            "scope": "repair preparation identity only", "damaged_cases": cls.results,
            "new_EDA_calls": 0}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("REPAIR_PREPARATION_TEST_OUTPUT=" + str(cls.root), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
