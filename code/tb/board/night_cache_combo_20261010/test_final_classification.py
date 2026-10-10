"""Synthetic classifier regression: exact MIDI20 only, never EDA."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "code/scripts"))
import check_138k_night_cache_combo_final as final


def fixture():
    root = ET.Element("Module", name="audio_visual_coexistence_top", T_Bsram="32", T_Ssram="86")
    for name, bs, ss in (("g_polyphonic.u_audio_core", 20, 32), ("u_waveform", 3, 0),
                          ("u_wave_bridge", 0, 28), ("u_midi_input", 0, 20)):
        ET.SubElement(root, "SubModule", name=name, T_Bsram=str(bs), T_Ssram=str(ss))
    score = ET.SubElement(root, "SubModule", name="u_score_receiver", T_Bsram="9", T_Ssram="0",
                          T_Register="1309", T_Lut="2646")
    for name in [f"byte_lanes[{i}].storage" for i in range(8)] + ["request_history"]:
        ET.SubElement(score, "SubModule", name=name, T_Bsram="1(1)")
    return root, score


class FinalClassificationTests(unittest.TestCase):
    def test_exact_mapping_and_damage(self):
        root = Path(tempfile.mkdtemp(prefix="m2_combo_final_classifier_", dir=ROOT / "code/output"))
        results = []
        for case in ("positive", "MIDI21", "MIDI_BSRAM1", "old_total89", "missing_cache", "body0",
                     "scoreSSRAM1", "audio_changed", "MIDI_DSP1"):
            tree, score = fixture()
            if case == "MIDI21":
                tree[3].set("T_Ssram", "21")
                tree.set("T_Ssram", "87")
            elif case == "MIDI_BSRAM1":
                tree[3].set("T_Bsram", "1")
                tree.set("T_Bsram", "33")
            elif case == "old_total89":
                tree.set("T_Ssram", "89")
            elif case == "missing_cache":
                score.remove(score[-1])
            elif case == "body0":
                score[0].set("T_Bsram", "0")
            elif case == "scoreSSRAM1":
                score.set("T_Ssram", "1")
                tree.set("T_Ssram", "87")
            elif case == "audio_changed":
                tree[0].set("T_Bsram", "19")
            elif case == "MIDI_DSP1":
                tree[3].set("T_MULT18X18", "1")
            path = root / (case + ".xml")
            path.write_bytes(ET.tostring(tree))
            _, _, errors = final.final_resource(path)
            self.assertEqual(not errors, case == "positive")
            results.append({"case": case, "errors": errors})
        (root / "receipt.json").write_text(json.dumps({
            "scope": "SYNTHETIC resource classification only, no timing or EDA proof",
            "cases": results, "new_EDA_runs": 0}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print("FINAL_CLASSIFICATION_TEST_OUTPUT=" + str(root), flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
