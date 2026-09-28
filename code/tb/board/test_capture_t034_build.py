#!/usr/bin/env python3
"""Regression for T034 report verification; no vendor tool required."""
import sys
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from capture_t034_formal_build import cst_pins, verify_build  # noqa: E402

CST = ('IO_LOC "midi_rx" R17;\n'
       'IO_PORT "midi_rx" IO_TYPE=LVCMOS33 PULL_MODE=UP BANK_VCCIO=3.3;\n')
REPORT = ('  <Tool Version>: V1.9.11.03 Education\n'
          '  <Part Number>: GW5AT-LV60PG484AC1/I0\n'
          '7. Pinout by Port Name\n'
          'midi_rx | - | R17/6 | Y | in | site | cfg | LVCMOS33 | OFF | UP | '
          'OFF | ON | OFF | SLOW | OFF | OFF | OFF | 3.3 | MEDIUM\n'
          '8. All Package Pins\n')
INFO = {"resources": {"Logic": 5, "Register": 5}, "worst_ns": {"Setup": 1.0}}


class TestCapture(TestCase):
    def test_expected_port(self):
        with patch("capture_t034_formal_build.verify", return_value=([], INFO.copy())):
            info = verify_build("timing", REPORT, CST)
        self.assertEqual(info["pins"]["midi_rx"]["ball"], "R17")

    def test_pin_mismatch_rejected(self):
        with patch("capture_t034_formal_build.verify", return_value=([], INFO.copy())):
            with self.assertRaisesRegex(ValueError, "CST=R18 PnR=R17"):
                verify_build("timing", REPORT, CST.replace("R17", "R18"))

    def test_negative_timing_rejected(self):
        with patch("capture_t034_formal_build.verify",
                   return_value=(["Hold negative slack: -0.01 ns"], INFO.copy())):
            with self.assertRaisesRegex(ValueError, "Hold negative slack"):
                verify_build("timing", REPORT, CST)

    def test_missing_pin_rejected(self):
        with patch("capture_t034_formal_build.verify", return_value=([], INFO.copy())):
            with self.assertRaisesRegex(ValueError, "missing"):
                verify_build("timing", REPORT.replace("midi_rx |", "other |"), CST)

    def test_duplicate_constraint_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate IO_LOC"):
            cst_pins(CST + 'IO_LOC "midi_rx" Y12;\n')


if __name__ == "__main__":
    main()
