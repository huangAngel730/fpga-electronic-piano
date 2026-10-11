"""Fault-oriented checks of the preparation gate; no FPGA tool execution."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import prepare_138k_polyphony_resource as prep
import preflight_138k_polyphony_synthesis as entry
import inspect_polyphony_synthesis_report as reports


class ExactProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prep.BUILD_ROOT.mkdir(parents=True, exist_ok=True)
        cls.parent = tempfile.TemporaryDirectory(prefix="identity_test_", dir=prep.BUILD_ROOT)
        cls.base = Path(cls.parent.name)
        cls.payload, cls.record = prep.expected(cls.base / "fixture")

    @classmethod
    def tearDownClass(cls):
        cls.parent.cleanup()

    def fixture(self, name):
        target = self.base / name
        with patch.object(prep, "expected", return_value=(self.payload, self.record)):
            prep.prepare(target)
        return target

    def check(self, target):
        with patch.object(prep, "expected", return_value=(self.payload, self.record)):
            return prep.verify(target)

    def test_refuse_existing_without_overwrite(self):
        target = self.fixture("existing")
        before = (target / prep.PROJECT).read_bytes()
        with self.assertRaisesRegex(ValueError, "REFUSE_EXISTING_PROJECT"):
            prep.prepare(target)
        self.assertEqual(before, (target / prep.PROJECT).read_bytes())

    def test_project_redirect_and_resign_not_accepted(self):
        target = self.fixture("redirect")
        project = target / prep.PROJECT
        project.write_bytes(project.read_bytes().replace(b"GW5AST-138C", b"GW5AST-138B"))
        record = copy.deepcopy(self.record)
        record["artifacts"][prep.PROJECT]["sha256"] = prep.digest(project.read_bytes())
        (target / "frozen_receipt.json").write_bytes(prep.canonical(record))
        with self.assertRaisesRegex(ValueError, "CANONICAL_FROZEN_RECEIPT"):
            self.check(target)

    def test_run_all_with_forged_receipt_rejected(self):
        target = self.fixture("all")
        tcl = target / "run_synthesis_only.tcl"
        tcl.write_bytes(tcl.read_bytes().replace(b"run syn", b"run all"))
        with self.assertRaisesRegex(ValueError, "PROJECT_ARTIFACT_IDENTITY"):
            self.check(target)

    def test_bool_authorization_and_float_schema_rejected(self):
        for name, key, value in (("authorized", "synthesis_authorized", True),
                                 ("float", "schema", 1.0)):
            target = self.fixture(name)
            record = copy.deepcopy(self.record)
            record[key] = value
            (target / "frozen_receipt.json").write_bytes(prep.canonical(record))
            with self.assertRaisesRegex(ValueError, "CANONICAL_FROZEN_RECEIPT"):
                self.check(target)

    def test_unlisted_pin_or_generated_report_rejected(self):
        target = self.fixture("extra")
        (target / "unapproved.cst").write_bytes(b"IO_LOC clk A1;\n")
        with self.assertRaisesRegex(ValueError, "EXACT_PROJECT_FILE_SET"):
            self.check(target)

    def test_output_escape_and_tcl_metacharacters_rejected(self):
        for target in (prep.BUILD_ROOT, prep.ROOT / "code/rtl", self.base / "bad[exec]"):
            with self.assertRaises(ValueError):
                prep.destination(target)

    def test_execute_flag_cannot_call_preflight_or_tools(self):
        with patch("sys.argv", ["entry", "--project", str(self.base), "--execute"]), \
                patch.object(entry, "preflight", side_effect=AssertionError("must not run")):
            self.assertEqual(entry.main(), 1)

    def test_absent_resource_is_unknown_and_counts_not_added(self):
        path = self.base / "synthetic_report.xml"
        path.write_bytes(b'<R name="top" T_Register="12" T_Bsram="1(1)"><N name="leaf" Register="12" MULT9="4"/></R>')
        result = reports.inspect(path)
        self.assertEqual(result["hierarchy"][0]["resources"]["Register"], 12)
        self.assertEqual(result["hierarchy"][0]["resources"]["Bsram"], 1)
        self.assertIsNone(result["hierarchy"][0]["resources"]["DSP"])
        self.assertIsNone(result["hierarchy"][0]["resources"]["Logic"])
        self.assertFalse(result["resource_admission"])
        self.assertEqual(result["hierarchy"][1]["other_operator_attributes"], {"MULT9": "4"})

    def test_bad_count_and_nonresource_xml_rejected(self):
        for value in ("-1", "NaN", "12.0", "2(foo)"):
            with self.assertRaises(ValueError):
                reports.count(value)
        path = self.base / "empty_report.xml"
        path.write_bytes(b"<R/>")
        with self.assertRaisesRegex(ValueError, "NO_RESOURCE_ROWS"):
            reports.inspect(path)


if __name__ == "__main__":
    unittest.main()
