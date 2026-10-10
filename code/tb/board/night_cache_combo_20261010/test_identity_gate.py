"""Preparation/source and synthetic mapping admission only; never EDA."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "code/scripts"))
import prepare_138k_night_cache_combo as prep
import check_138k_night_cache_combo as gate


class ComboTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prep.BUILD_ROOT.mkdir(exist_ok=True)
        cls.root = Path(tempfile.mkdtemp(prefix="identity_tests_", dir=prep.BUILD_ROOT))
        cls.results = []

    def fresh(self, name):
        folder = self.root / name
        prep.prepare(folder)
        return folder

    def test_changes_are_exact(self):
        folder = self.fresh("positive")
        new = prep.inputs(folder)[0]
        old = prep.repair.frozen_parent_inputs(folder)[0]
        changed = {name for name in old if old[name] != new[name]}
        self.assertEqual(changed, {"sources/midi_event_parser.sv", "sources/score_byte_lane.sv",
                                  "sources/score_transfer_bram_candidate.sv", "constraints/audio_visual_hold055.sdc"})
        self.assertTrue(new["constraints/audio_visual_hold055.sdc"].startswith(old["constraints/audio_visual_hold055.sdc"]))
        self.assertEqual(new["constraints/audio_visual.cst"], old["constraints/audio_visual.cst"])
        record = prep.validate(folder)
        self.assertEqual(record["expected_score_BSRAM"], 9)
        self.assertFalse(record["physical_STA_passed"])
        self.assertFalse(record["board_release_allowed"])

    def test_damage_and_overwrite(self):
        for index, relative in enumerate(("sources/midi_event_parser.sv", "sources/score_byte_lane.sv",
                                          "sources/score_transfer_bram_candidate.sv", "constraints/audio_visual_hold055.sdc",
                                          "constraints/audio_visual.cst", "rom/piano_band_4x256_8191.mem")):
            folder = self.fresh("damage_" + str(index))
            path = folder / "inputs" / relative
            path.write_bytes(path.read_bytes() + b"\nwrong\n")
            with self.assertRaisesRegex(ValueError, "EXACT62"):
                prep.validate(folder)
            self.results.append(relative)
        for key, value in (("physical_STA_passed", True), ("physical_STA_passed", 0),
                           ("input_count", 62.0), ("prepare_script_sha256", "wrong")):
            folder = self.fresh("receipt_" + key + "_" + type(value).__name__)
            p = folder / "frozen_receipt.json"
            data = json.loads(p.read_bytes())
            data[key] = value
            p.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "RECEIPT_BYTES"):
                prep.validate(folder)
            self.results.append(key + "_" + type(value).__name__)
        with self.assertRaises(ValueError):
            prep.guard(ROOT / "code/output/wrong_combo_scope")
        with self.assertRaisesRegex(ValueError, "OVERWRITE"):
            prep.prepare(self.root / "positive")

    def test_native_mapping_screen_synthetic(self):
        def fixture():
            root = ET.Element("Module", name="audio_visual_coexistence_top", T_Bsram="32", T_Ssram="89")
            for name, bs, ss in (("g_polyphonic.u_audio_core", 20, 32), ("u_waveform", 3, 0), ("u_wave_bridge", 0, 28)):
                ET.SubElement(root, "SubModule", name=name, T_Bsram=str(bs), T_Ssram=str(ss))
            score = ET.SubElement(root, "SubModule", name="u_score_receiver", T_Register="1316", T_Lut="2147",
                                  T_Bsram="9", T_Ssram="0")
            for name in [f"byte_lanes[{i}].storage" for i in range(8)] + ["request_history"]:
                ET.SubElement(score, "SubModule", name=name, T_Bsram="1(1)")
            return root, score
        for name in ("positive", "missing_history", "history_zero", "duplicate_lane", "wrong_total", "old8RAM"):
            root, score = fixture()
            if name == "missing_history":
                score.remove(score[-1])
            elif name == "history_zero":
                score[-1].set("T_Bsram", "0")
            elif name == "duplicate_lane":
                ET.SubElement(score, "SubModule", **score[0].attrib)
            elif name == "wrong_total":
                root.set("T_Bsram", "31")
            elif name == "old8RAM":
                score.set("T_Bsram", "8")
                root.set("T_Bsram", "31")
            path = self.root / ("synthetic_" + name + ".xml")
            path.write_bytes(ET.tostring(root))
            _, _, errors = gate.xml_resource(path)
            self.assertEqual(not errors, name == "positive")
            self.results.append("SYNTHETIC_XML_" + name)

    @classmethod
    def tearDownClass(cls):
        (cls.root / "test_receipt.json").write_text(json.dumps({
            "scope": "software identity and synthetic native mapping screen, not actual STA",
            "cases": cls.results, "new_EDA_runs": 0}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print("COMBO_IDENTITY_TEST_OUTPUT=" + str(cls.root), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
