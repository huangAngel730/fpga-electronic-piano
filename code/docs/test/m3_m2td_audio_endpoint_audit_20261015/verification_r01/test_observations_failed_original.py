"""Independent known-value and raw-byte checks of offline observations."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
import zipfile

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("extractor", ROOT / "inspect_original.py")
extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)


class ObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.obs = json.loads((ROOT / "observed_r03/observations.json").read_bytes())
        cls.target = json.loads((ROOT / "targets.json").read_bytes())
        with zipfile.ZipFile(extractor.ZIP) as z:
            cls.raw = z.read("pnr/timing.html")
            cls.names = z.namelist()

    def test_original_sha_literal(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), "524cea6ebb93eca719c5aa86cd6413129299ac2c9da78467ac7709cdf4e8ec62")

    def test_original_member_set_no_netlist(self):
        self.assertEqual(len(self.names), 15)
        self.assertFalse(any(n.endswith(".vg") for n in self.names))

    def test_selected_raw_bytes(self):
        for p in self.obs["selected_paths"]:
            loc = p["raw_location"]
            blob = self.raw[loc["byte_start_inclusive"]:loc["byte_end_exclusive"]]
            self.assertEqual(hashlib.sha256(blob).hexdigest(), loc["fragment_sha256"])
            for key in ("from_node", "to_node", "from_clock", "to_clock", "slack_ns"):
                self.assertIn(p[key].encode(), blob)

    def test_independent_known_row_offsets(self):
        self.assertEqual([(p["raw_location"]["byte_start_inclusive"], p["raw_location"]["byte_end_exclusive"])
                          for p in self.obs["selected_paths"]],
                         [(81940, 82251), (82253, 82612), (82614, 82973), (82975, 83334), (33223, 33494)])

    def test_known_slacks_and_clocks(self):
        self.assertEqual([p["slack_ns"] for p in self.obs["selected_paths"]], ["0.000"] * 4 + ["1.736"])
        for p in self.obs["selected_paths"]:
            self.assertEqual((p["from_clock"], p["to_clock"]), ("sys_clk:[R]", "sys_clk:[R]"))

    def test_known_true_audio_sample_path(self):
        p = self.obs["selected_paths"][1]
        self.assertEqual(p["from_node"], "g_polyphonic.u_audio_core/u_chain/u_audio/u_bank/g_lane[2].u_voice/u_piano/phase_acc_30_s0/Q")
        self.assertEqual(p["to_node"], "g_polyphonic.u_audio_core/u_chain/u_audio/u_bank/g_lane[2].u_voice/u_piano/u_table/rom_data_rom_data_0_0_s/AD[10]")
        self.assertEqual(p["analysis"], "Hold")

    def test_routed_locations_literal(self):
        self.assertEqual([p["routed_node_locations"][0]["physical_location"] for p in self.obs["selected_paths"][:4]],
                         ["R48C105[0][A]", "R53C106[2][A]", "R83C117[2][A]", "R86C122[0][A]"])

    def test_detail_byte_fragments_all_retained(self):
        for p in self.obs["selected_paths"]:
            self.assertEqual(len(p["detail_candidates"]), 1)
            loc = p["detail_candidates"][0]
            blob = self.raw[loc["byte_start_inclusive"]:loc["byte_end_exclusive"]]
            path = ROOT / "observed_r03/fragments" / (loc["anchor"] + "_byte" + str(loc["byte_start_inclusive"]) + ".html")
            self.assertEqual(path.read_bytes(), blob)

    def test_unknown_not_inferred_from_absence(self):
        self.assertEqual(self.obs["base_name_search"], {"base_s1": 0, "base_s2": 0})
        pair = self.target["requested_register_pair"]
        self.assertIsNone(pair["synthesis_cell_from"])
        self.assertIsNone(pair["routed_cell_to"])
        self.assertTrue(pair["same_pair_setup_hold"].startswith("UNKNOWN"))

    def test_no_acceptance_upgrade(self):
        self.assertFalse(self.obs["board_release_allowed"])
        self.assertFalse(self.target["board_release_allowed"])
        self.assertFalse(self.target["new_sta_executed"])
        for target in self.target["targets"]:
            self.assertEqual(target["required_analyses"], ["Setup", "Hold"])
            self.assertEqual(len(target["observed_analyses"]), 1)
            self.assertEqual(target["exact_pair_both_analyses"], "UNKNOWN")

    def test_malformed_actual_cell_style(self):
        self.assertEqual(extractor.cells("<tr><td>1</td><td>40.000\n<td>0.000</td></tr>"), ["1", "40.000", "0.000"])

    def test_refuse_existing_output(self):
        with self.assertRaisesRegex(ValueError, "fresh"):
            extractor.inspect(ROOT / "observed_r03")

    def test_refuse_out_of_write_set(self):
        with self.assertRaisesRegex(ValueError, "fresh"):
            extractor.inspect(ROOT.parent / "DO_NOT_CREATE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
