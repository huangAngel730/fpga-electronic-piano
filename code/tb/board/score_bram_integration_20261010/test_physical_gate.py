"""Synthetic native XML screening and incomplete-build refusal; no EDA."""
from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "code/scripts"))
import check_138k_score_bram_integration as gate


def fixture():
    root = ET.Element("Module", name="audio_visual_coexistence_top", T_Bsram="31", T_Ssram="89")
    for name, bs, ss in (("g_polyphonic.u_audio_core", 20, 32), ("u_waveform", 3, 0),
                          ("u_wave_bridge", 0, 28)):
        ET.SubElement(root, "SubModule", name=name, T_Bsram=str(bs), T_Ssram=str(ss))
    score = ET.SubElement(root, "SubModule", name="u_score_receiver", T_Bsram="8", T_Ssram="0",
                          T_Register="3392", T_Lut="3624")
    for i in range(8):
        ET.SubElement(score, "SubModule", name=f"byte_lanes[{i}].storage", T_Bsram="1(1)")
    return root, score


class NativeMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="m2_RAM_physical_synthetic_", dir=ROOT / "code/output"))
        cls.results = []

    def assess(self, name, root):
        path = self.root / (name + ".xml")
        path.write_bytes(ET.tostring(root, encoding="utf-8"))
        facts, count, errors = gate.xml_resource(path)
        self.results.append({"name": name, "errors": errors, "facts": facts, "total_BSRAM": count,
                             "report_SHA256": gate.parent.sha(path)})
        return errors

    def test_synthetic_mapping_and_mutants(self):
        root, score = fixture()
        self.assertEqual(self.assess("synthetic_resource_screen_positive", root), [])
        for case in ("zero_body", "missing_lane", "duplicate_lane", "extra_ssram", "over_FF", "over_LUT",
                     "added_DSP", "audio_changed", "root_total_changed", "duplicate_score"):
            root, score = fixture()
            if case == "zero_body":
                score[0].set("T_Bsram", "0")
            elif case == "missing_lane":
                score.remove(score[0])
            elif case == "duplicate_lane":
                ET.SubElement(score, "SubModule", **score[0].attrib)
            elif case == "extra_ssram":
                score.set("T_Ssram", "1")
                root.set("T_Ssram", "90")
            elif case == "over_FF":
                score.set("T_Register", "8193")
            elif case == "over_LUT":
                score.set("T_Lut", "8193")
            elif case == "added_DSP":
                score.set("T_MULT18X18", "1")
            elif case == "audio_changed":
                root[0].set("T_Bsram", "19")
            elif case == "root_total_changed":
                root.set("T_Bsram", "32")
            else:
                ET.SubElement(root, "SubModule", **score.attrib)
            with self.subTest(case=case):
                self.assertTrue(self.assess(case, root))

    def test_incomplete_actual_preparation_is_not_physical_pass(self):
        runs = gate.prepared.BUILD_ROOT / "runs"
        runs.mkdir(exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="no_tool_preflight_", dir=runs))
        gate.prepared.prepare(folder / "project")
        result = gate.review(folder)
        self.assertIs(result["passed"], False)
        self.assertIs(result["board_release_allowed"], False)
        self.assertTrue(any("build_receipt.json" in error for error in result["errors"]))
        (self.root / "no_build_receipt_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                                               encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        (cls.root / "receipt.json").write_text(json.dumps({
            "scope": "SYNTHETIC XML only; no synthesis/PnR/STA evidence",
            "cases": cls.results, "no_EDA_started": True}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print("SYNTHETIC_PHYSICAL_OUTPUT=" + str(cls.root), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
