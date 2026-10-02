"""Regression for duplicated report rows; dedicated CDC path proof stays strict.

Uses the real generated report as baseline; injected parser rows are explicitly
synthetic negative cases, never timing evidence for the physical design.
"""
import argparse
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "code/scripts"))
from check_hdmi_link_report import ReportParser
from check_visual_full_path_report import check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    folder = parser.parse_args().folder
    pnr = folder / "impl/pnr"
    timing = (pnr / "audio_visual_coexistence_top_tr_content.html").read_text(encoding="utf-8").replace("u_visual/", "")
    pins = (pnr / "audio_visual_coexistence_top.rpt.txt").read_text(encoding="utf-8")
    source = ReportParser()
    source.feed(timing)
    pair = ("u_event_bridge/ack_meta_s0/Q", "u_event_bridge/ack_sync_s0/D")
    matches = [(section, row) for section, row in source.rows
               if section.startswith("Hold_Slack_Table") and len(row) >= 4
               and tuple(row[2:4]) == pair]
    if len(matches) < 2:
        raise AssertionError("this test requires the actual duplicate-report case")
    errors, _ = check(timing, pins)
    if errors:
        raise AssertionError("positive report rejected: " + str(errors))
    print("PASS dedicated + global report contain same positive pair")

    for kind in ("missing", "negative", "wrong_sink", "duplicate_in_dedicated", "inactive"):
        rows = deepcopy(source.rows)
        index = next(i for i, (section, row) in enumerate(rows)
                     if section == "Hold_Slack_Table1" and len(row) >= 4
                     and tuple(row[2:4]) == pair)
        if kind == "missing":
            rows.pop(index)  # all-clock table still contains the positive pair
        elif kind == "negative":
            rows[index][1][1] = "-0.001"
        elif kind == "wrong_sink":
            rows[index][1][3] = "u_event_bridge/other_s0/D"
        elif kind == "duplicate_in_dedicated":
            rows.insert(index, deepcopy(rows[index]))
        else:
            row = next(row for section, row in rows
                       if section == "SDC_Report" and len(row) == 3
                       and row[2].startswith("report_timing -hold -from [get_regs {u_event_bridge/ack_meta_s0}"))
            row[1] = "Inactived"
        fake = SimpleNamespace(rows=rows, feed=lambda text: None)
        with patch("check_visual_full_path_report.ReportParser", return_value=fake):
            errors, _ = check(timing, pins)
        if not any("second-stage" in error for error in errors):
            raise AssertionError("bad dedicated CDC report accepted: " + kind)
        print("PASS reject dedicated report", kind)
    print("PASS direct CDC report positive + 5 negatives")


if __name__ == "__main__":
    main()
