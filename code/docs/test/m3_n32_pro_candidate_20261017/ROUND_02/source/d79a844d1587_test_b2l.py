"""Preparation contract only: no audio simulation, EDA or production approval."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import b2l_prepare as prep


class PreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = tempfile.TemporaryDirectory(prefix="b2l_", dir=prep.ROOT / "code/output")
        cls.root = Path(cls.parent.name)
        # One expensive Git-source scan, cached only inside unit-test fixtures.
        cls.reference, cls.blobs = prep.generated(cls.root / "fixture", 8, 1)

    @classmethod
    def tearDownClass(cls):
        cls.parent.cleanup()

    def fixture(self, name):
        path = self.root / name
        with patch.object(prep, "generated", return_value=(self.reference, self.blobs)):
            prep.prepare(path, 8, 1)
        return path

    def verify_fixture(self, path):
        with patch.object(prep, "generated", return_value=(self.reference, self.blobs)):
            return prep.verify(path)

    def test_all_wrapper_parameters(self):
        for n in (4, 8, 16, 32):
            for r in (1, 64):
                text = prep.wrapper(n, r).decode()
                self.assertIn(f".N({n}), .RESPONSE({r})", text)
                self.assertIn(f"inject_tag({72+prep.slot_width(n)}'d0)", text)
                self.assertIn(".read_context(read_context)", text)
                self.assertIn(".inject_valid(1'b0)", text)

    def test_config_types_and_bounds(self):
        for n in (True, 0, 3, 64, "8"):
            with self.assertRaises(ValueError):
                prep.config(n, 1)
        for r in (True, 0, 65, "1", 1.0):
            with self.assertRaises(ValueError):
                prep.config(8, r)

    def test_input_pins_and_reversible_rom_relocation(self):
        self.assertEqual(len(self.reference["inputs"]), 22)
        self.assertTrue(all(p["original"]["pin_commit"] == prep.PIN
                            for p in self.reference["inputs"]))
        replacements = {p["staged"]: p["rom_path_replacements"]
                        for p in self.reference["inputs"] if p["rom_path_replacements"]}
        self.assertEqual(replacements, {
            "sources/adsr_piano_envelope.sv": 2,
            "sources/pitch_mod_fcw_pipeline.sv": 3,
            "sources/b2_audio_backend.sv": 4})

    def test_no_eda_authorization_or_project(self):
        self.assertFalse(self.reference["new_synthesis"])
        self.assertFalse(self.reference["representative_configuration_approved"])
        self.assertEqual(self.reference["physical_resources"], "UNKNOWN")
        self.assertFalse(any(Path(p).suffix in (".tcl", ".fs", ".gprj", ".cst")
                             for p in self.blobs))

    def test_clock_protection_not_relaxed(self):
        self.assertIn(b"-period 25.000", self.blobs["clock.sdc"])
        self.assertIn(b"-setup 1.000", self.blobs["clock.sdc"])
        self.assertIn(b"-hold 0.650", self.blobs["clock.sdc"])
        self.assertNotIn(b"false_path", self.blobs["clock.sdc"])

    def test_normal_and_refuse_overwrite(self):
        path = self.fixture("normal")
        self.assertEqual(self.verify_fixture(path)["status"], prep.STATUS)
        with self.assertRaisesRegex(ValueError, "REFUSE_EXISTING"):
            prep.prepare(path, 8, 1)

    def test_no_output_root_or_escape(self):
        for path in (prep.ROOT, prep.ROOT / "code/output", prep.ROOT / "code/output/../rtl"):
            with self.assertRaisesRegex(ValueError, "OUTPUT_OUTSIDE"):
                prep.destination(path)

    def test_unsafe_path(self):
        with self.assertRaisesRegex(ValueError, "UNSAFE_OUTPUT"):
            prep.destination(prep.ROOT / "code/output/bad[exec]")

    def test_artifact_tamper_rejected_even_if_manifest_resigned(self):
        path = self.fixture("tamper")
        target = path / (prep.TOP + ".sv")
        target.write_bytes(target.read_bytes().replace(b".N(8)", b".N(4)"))
        plan = json.loads((path / "plan.json").read_text())
        plan["artifacts"][target.name]["sha256"] = prep.digest(target.read_bytes())
        (path / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "PLAN_IDENTITY"):
            self.verify_fixture(path)

    def test_rom_tamper_and_missing_member(self):
        path = self.fixture("rom_bad")
        target = next((path / "rom").glob("*.mem"))
        target.write_bytes(target.read_bytes() + b"\n00\n")
        with self.assertRaisesRegex(ValueError, "ARTIFACT_IDENTITY:rom"):
            self.verify_fixture(path)
        target.unlink()
        with self.assertRaisesRegex(ValueError, "ARTIFACT_SET"):
            self.verify_fixture(path)

    def test_extra_project_rejected(self):
        path = self.fixture("extra")
        (path / "run.tcl").write_text("run all\n", encoding="ascii")
        with self.assertRaisesRegex(ValueError, "ARTIFACT_SET"):
            self.verify_fixture(path)

    def test_forged_authorization_and_bool_rejected(self):
        for field, value in (("representative_configuration_approved", True), ("schema", True)):
            path = self.fixture("forge_" + field)
            plan = json.loads((path / "plan.json").read_text())
            plan[field] = value
            (path / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "PLAN_IDENTITY"):
                self.verify_fixture(path)


if __name__ == "__main__":
    unittest.main()
