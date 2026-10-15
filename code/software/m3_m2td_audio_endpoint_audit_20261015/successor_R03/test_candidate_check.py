"""Pure software tests for the new literal-selector successor, synthetic only."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("candidate_check", Path(__file__).with_name("check_candidate_report.py"))
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)
parser = check.load_parser()


def fixture():
    # Synthetic records test predicate logic; never an original STA report.
    target = {"id": "SYNTHETIC_ONLY", "from_node": "exact/lane[3]/reg/Q", "to_node": "exact/memory/AD[7]"}
    rows = []
    for kind in ("setup", "hold"):
        command = "Report Command:report_timing -" + kind + " -from [get_regs {exact/lane[3]/reg}] -to [get_pins {exact/memory/AD[7]}] -max_paths 1 -max_common_paths 1"
        rows.append({"From Node": target["from_node"], "To Node": target["to_node"],
                     "From Clock": "sys_clk:[R]", "To Clock": "sys_clk:[R]", "analysis": kind,
                     "command": command, "Path Slack": "0.125", "Data Delay": "1.000", "Path Number": "1",
                     "Relation": "25.000" if kind == "setup" else "0.000", "Clock Skew": "0.000",
                     "row_span": {"SYNTHETIC": True}, "table_span": {"SYNTHETIC": True}})
    parsed = {"metadata": {"Tool Version": "V1.9.11.03 Education", "Part Number": "GW5AST-LV138PG484AC1/I0"},
              "clocks": {"sys_clk": {"period_ns": "25.000", "frequency_mhz": "40.000", "objects": "u_visual/u_video_pll/PLLA_inst/CLKOUT2"}},
              "paths": rows}
    return parsed, [target]


class CandidatePredicateTests(unittest.TestCase):
    def reject_change(self, modify, code):
        data, targets = fixture()
        modify(data)
        with self.assertRaisesRegex((ValueError, parser.AuditError), code):
            check.check_paths(data, targets, parser)

    def test_synthetic_literal_brackets_complete(self):
        data, targets = fixture()
        self.assertEqual(len(check.check_paths(data, targets, parser)), 2)

    def test_missing_endpoint(self):
        self.reject_change(lambda d: d.update(paths=[]), "ENDPOINT_ABSENT")

    def test_unrelated_audio_path(self):
        self.reject_change(lambda d: [r.update({"From Node": "unrelated/audio/Q"}) for r in d["paths"]], "ENDPOINT_ABSENT")

    def test_only_hold(self):
        self.reject_change(lambda d: d.update(paths=d["paths"][1:]), "DIRECTED_SETUP_ABSENT")

    def test_only_setup(self):
        self.reject_change(lambda d: d.update(paths=d["paths"][:1]), "DIRECTED_HOLD_ABSENT")

    def test_summary_command_cannot_replace_directed(self):
        self.reject_change(lambda d: d["paths"][0].update(command="report_timing -setup -from_clock [get_clocks {sys_clk}]"), "DIRECTED_SETUP_ABSENT")

    def test_wildcard_cannot_replace_literal_brackets(self):
        self.reject_change(lambda d: d["paths"][0].update(command=d["paths"][0]["command"].replace("lane[3]", "lane*")), "DIRECTED_SETUP_ABSENT")

    def test_inactive_row(self):
        self.reject_change(lambda d: d["paths"][0].update({"Clock Skew": "inactive"}), "INACTIVE_PAIR")

    def test_wrong_pair_clock(self):
        self.reject_change(lambda d: d["paths"][0].update({"To Clock": "video_pixel:[R]"}), "PAIR_CLOCK")

    def test_negative_slack(self):
        self.reject_change(lambda d: d["paths"][1].update({"Path Slack": "-0.001"}), "PAIR_TIMING_VALUE")

    def test_nan_slack(self):
        self.reject_change(lambda d: d["paths"][1].update({"Path Slack": "NaN"}), "slack: 'NaN'")

    def test_wrong_period(self):
        self.reject_change(lambda d: d["clocks"]["sys_clk"].update(period_ns="20.000"), "CLOCK_40MHZ")

    def test_wrong_tool_version(self):
        self.reject_change(lambda d: d["metadata"].update({"Tool Version": "V1.9.12"}), "REPORT_TOOL_OR_DEVICE")

    def test_wrong_clock_object(self):
        self.reject_change(lambda d: d["clocks"]["sys_clk"].update(objects="inactive"), "CLOCK_OBJECT")

    def test_actual_original_parser_command_prefix(self):
        import zipfile
        original = check.REPO / "code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_整机PnR_STA_20261015.zip"
        with zipfile.ZipFile(original) as z:
            real = parser.parse_report(z.read("pnr/timing.html"))
        self.assertGreater(len(real["paths"]), 0)
        self.assertTrue(all(r["command"].startswith("Report Command:report_timing ") for r in real["paths"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
