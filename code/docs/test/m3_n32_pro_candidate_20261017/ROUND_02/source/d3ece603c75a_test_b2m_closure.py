"""New closure-only selftests, not the old twelve math tests."""

import io
import json
from pathlib import Path
import sys
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import b2m_closure as closure


class ClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = closure.new_payload()

    def test_nine_actual_local_imports(self):
        graph = closure.static_import_closure(self.payload)
        self.assertEqual(set(graph), set(closure.MODULES))
        self.assertIn("strict_capture", graph["b2c_router_model"])
        self.assertIn("envelope_model", graph["b2m_check"])

    def test_original_and_supplementary_provenance(self):
        expected, reused = closure.baseline(self.payload["historical/B2M_original.zip"],
                                           self.payload["historical/M2_RAW_EVIDENCE.zip"])
        self.assertEqual(len(expected), 17)  # nine sources, five ROMs, three captures
        self.assertEqual(reused["status"], "REUSED")
        self.assertEqual(reused["new_math_replays"], 0)
        self.assertEqual(reused["original_missing_dependency_measurement"],
                         "NOT_RETROACTIVELY_CREATED")

    def test_valid_static_package(self):
        raw, manifest = closure.encode(self.payload)
        closure.validate(closure.unzip(raw), manifest)

    def test_resigned_other_math_source(self):
        bad = dict(self.payload)
        bad[closure.MODULES["b2m_check"]] += b"\n# altered\n"
        _, manifest = closure.encode(bad)
        with self.assertRaisesRegex(ValueError, "B2M_CLOSURE_PINNED_IDENTITY"):
            closure.validate(bad, manifest)

    def test_resigned_capture_change(self):
        bad = dict(self.payload)
        bad["captures/N4_R1.capture"] += b"\n"
        _, manifest = closure.encode(bad)
        with self.assertRaisesRegex(ValueError, "B2M_CLOSURE_PINNED_IDENTITY"):
            closure.validate(bad, manifest)

    def test_resigned_reused_claim(self):
        bad = dict(self.payload)
        reused = json.loads(bad["REUSED.json"])
        reused["new_math_replays"] = 3
        bad["REUSED.json"] = json.dumps(reused).encode()
        _, manifest = closure.encode(bad)
        with self.assertRaisesRegex(ValueError, "B2M_CLOSURE_REUSED_BINDING"):
            closure.validate(bad, manifest)

    def test_resigned_historical_anchor(self):
        bad = dict(self.payload)
        bad["historical/M2_RAW_EVIDENCE.zip"] += b"changed"
        _, manifest = closure.encode(bad)
        with self.assertRaisesRegex(ValueError, "B2M_CLOSURE_ANCHOR_SHA"):
            closure.validate(bad, manifest)

    def test_zip_path_escape(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("../escape.py", b"pass")
        with self.assertRaisesRegex(ValueError, "B2M_CLOSURE_PATH"):
            closure.unzip(stream.getvalue())


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(
        ClosureTests))
    print(json.dumps(dict(exit_code=0 if result.wasSuccessful() else 1,
                         tests_run=result.testsRun, old_math_tests_executed=False)))
    raise SystemExit(0 if result.wasSuccessful() else 1)
