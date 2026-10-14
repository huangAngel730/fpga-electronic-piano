"""Only new loader contract guards; no HDL processes."""
import os
from pathlib import Path
import tempfile
import unittest

import a_harness as harness


class LoaderContractTests(unittest.TestCase):
    def make_plan(self, root):
        (root / "lib").mkdir()
        (root / "lib/test_runtime.dll").write_bytes(b"SOFTWARE_FIXTURE_NOT_A_DLL")
        (root / "environment.bat").write_text("SOFTWARE_FIXTURE_ONLY\n", encoding="ascii")
        return {"suite_root": str(root), "environment": harness.tool_environment(root),
                "tool_files": {str(path): harness.identity(path)
                               for path in (root / "lib/test_runtime.dll", root / "environment.bat")}}

    def test_loader_is_explicit_not_inherited_and_rejects_wrong_path(self):
        with tempfile.TemporaryDirectory(dir=harness.ROOT / "code/output") as temporary:
            root = Path(temporary)
            plan = self.make_plan(root)
            harness.validate_environment(plan)
            parts = plan["environment"]["PATH"].split(";")
            self.assertEqual(parts[:2], [str(root / "bin"), str(root / "lib")])
            self.assertEqual(len(parts), 4)
            self.assertEqual(plan["environment"]["YOSYSHQ_ROOT"], str(root) + "\\")
            plan["environment"]["PATH"] = "UNBOUND_OLD_MINGW_PATH"
            with self.assertRaisesRegex(ValueError, "TOOL_ENVIRONMENT"):
                harness.validate_environment(plan)

    def test_missing_lib_dependency_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=harness.ROOT / "code/output") as temporary:
            root = Path(temporary)
            plan = self.make_plan(root)
            del plan["tool_files"][str(root / "lib/test_runtime.dll")]
            with self.assertRaisesRegex(ValueError, "SUITE_DLL_UNBOUND"):
                harness.validate_environment(plan)


if __name__ == "__main__":
    unittest.main()
