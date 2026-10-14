"""Isolated software tests for the T052 observer-repair execution envelope."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "t052_observer_repair_successor_20261014.py"


def load_controller():
    spec = importlib.util.spec_from_file_location("t052_observer_repair_tested", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def file_spec(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


class ObserverRepairEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.controller = load_controller()

    def test_bootstrap_sources_compile(self):
        compile(self.controller.BOOTSTRAP_CODE, "controller-bootstrap", "exec")
        compile(self.controller.CHECKER_BOOTSTRAP_CODE, "checker-bootstrap", "exec")

    def test_bound_json_uses_the_hashed_buffer(self):
        with tempfile.TemporaryDirectory(
                dir=self.controller.ROOT / "code/output") as directory:
            path = Path(directory) / "control.json"
            raw = b'{"value":1}\n'
            path.write_bytes(raw)
            value, identity, captured = self.controller.read_bound_json(
                path, hashlib.sha256(raw).hexdigest())
            self.assertEqual(value, {"value": 1})
            self.assertEqual(captured, raw)
            self.assertEqual(identity["bytes"], len(raw))
            with self.assertRaisesRegex(ValueError, "BOUND_JSON_SHA"):
                self.controller.read_bound_json(path, "0" * 64)

    def test_canonical_json_bytes_reject_equivalent_reformatting(self):
        value = {"z": 1, "a": "observer"}
        canonical = self.controller.canonical_json_bytes(value)
        reformatted = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.assertEqual(json.loads(canonical), json.loads(reformatted))
        self.assertNotEqual(canonical, reformatted)
        self.assertEqual(
            canonical,
            b'{\n  "a": "observer",\n  "z": 1\n}\n',
        )

    def test_archive_container_identity_is_not_member_identity(self):
        with tempfile.TemporaryDirectory(
                dir=self.controller.ROOT / "code/output") as directory:
            archive_path = Path(directory) / "sources.zip"
            member = b"module frozen; endmodule\n"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("dut.sv", member)
                archive.writestr("rom.mem", b"00\n")
            manifest = {"sources": {
                "dut": {"path": str(archive_path), "member": "dut.sv",
                        "bytes": len(member),
                        "sha256": hashlib.sha256(member).hexdigest()},
                "rom": {"path": str(archive_path), "member": "rom.mem",
                        "bytes": 3,
                        "sha256": hashlib.sha256(b"00\n").hexdigest()},
            }}
            containers = self.controller.source_container_identities(manifest)
            expected = file_spec(archive_path)
            self.assertEqual(containers, {str(archive_path.resolve()): {
                "bytes": expected["bytes"], "sha256": expected["sha256"]}})
            self.assertNotEqual(expected["sha256"],
                                hashlib.sha256(member).hexdigest())

    def test_checker_bootstrap_executes_pinned_input_buffers(self):
        with tempfile.TemporaryDirectory(
                dir=self.controller.ROOT / "code/output") as directory:
            root = Path(directory)
            checker = root / "checker.py"
            calendar = root / "calendar.py"
            manifest = root / "manifest.json"
            plan = root / "plan.jsonl"
            receipt = root / "receipt.json"
            tracks = {name: root / f"{name}.jsonl" for name in
                      ("controls", "observations", "publications", "resets")}
            calendar.write_text("VALUE = 17\n", encoding="utf-8")
            plan.write_text('{"edge":0}\n', encoding="utf-8")
            receipt.write_text('{"status":"PASS"}\n', encoding="utf-8")
            for path in tracks.values():
                path.write_text('{"row":0}\n', encoding="utf-8")
            manifest.write_text(json.dumps({"plan": file_spec(plan)}) + "\n",
                                encoding="utf-8")
            checker.write_text(
                "import importlib.util, pathlib, sys\n"
                "def main():\n"
                " a=sys.argv[1:]; paths=[]\n"
                " for z in ('--manifest','--plan','--receipt','--controls',"
                "'--observations','--publications','--resets'):\n"
                "  paths.append(pathlib.Path(a[a.index(z)+1]).resolve())\n"
                " if any(p.read_bytes()!=p.read_bytes() for p in paths): return 8\n"
                " cp=pathlib.Path(a[a.index('--calendar')+1]).resolve()\n"
                " s=importlib.util.spec_from_file_location('calendar_test',cp)\n"
                " m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n"
                " return 0 if m.VALUE==17 else 9\n",
                encoding="utf-8",
            )
            checker_identity = file_spec(checker)
            manifest_sha = file_spec(manifest)["sha256"]
            receipt_sha = file_spec(receipt)["sha256"]
            original_checker = self.controller.CHECKER
            original_manifest = self.controller.MANIFEST
            try:
                self.controller.CHECKER = checker
                self.controller.MANIFEST = manifest
                argv = [str(self.controller.PYTHON), "-I", "-S", "-B", "-X",
                        "utf8", str(checker), "actual",
                        "--manifest", str(manifest.resolve()),
                        "--manifest-sha", manifest_sha,
                        "--plan", str(plan.resolve()),
                        "--receipt", str(receipt.resolve()),
                        "--receipt-sha", receipt_sha,
                        "--calendar", str(calendar.resolve())]
                for name, path in tracks.items():
                    argv.extend(["--" + name, str(path.resolve())])
                pinned = self.controller.checker_bootstrap_argv(
                    argv, checker_identity, calendar, calendar.read_bytes(),
                    manifest.read_bytes())
                result = subprocess.run(pinned, capture_output=True, text=True,
                                        encoding="utf-8", timeout=15, check=False)
            finally:
                self.controller.CHECKER = original_checker
                self.controller.MANIFEST = original_manifest
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
