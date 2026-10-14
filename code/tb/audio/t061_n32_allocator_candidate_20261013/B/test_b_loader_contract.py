"""Directed software-only counterexamples for the N32-B loader contract."""
import base64
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

import b_delivery
import b_harness


class LoaderContractTests(unittest.TestCase):
    def _copy_fake_capsule(self, root):
        suite = root / "suite"
        prepared = root / "prepared"
        for relative, payload in (
            ("bin/iverilog.exe", b"compile"),
            ("bin/vvp.exe", b"simulate"),
            ("bin/runtime.dll", b"bin-runtime"),
            ("lib/libgcc_s_seh-1.dll", b"gcc"),
            ("lib/libstdc++-6.dll", b"stdc++"),
            ("lib/libwinpthread-1.dll", b"pthread"),
            ("lib/ivl/ivl.exe", b"ivl"),
        ):
            path = suite / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        prepared.mkdir()
        origin_tools = {
            "python": str(Path(b_harness.sys.executable).resolve()),
            "compile": str((suite / "bin/iverilog.exe").resolve()),
            "simulate": str((suite / "bin/vvp.exe").resolve()),
        }
        origin_files = {
            str(path.resolve()): b_harness.identity(path)
            for path in suite.rglob("*") if path.is_file()
        }
        origin_files[origin_tools["python"]] = b_harness.identity(
            origin_tools["python"]
        )
        tools, files, _ = b_harness.copy_compiler_capsule(
            prepared, suite, origin_tools, origin_files
        )
        capsule = Path(tools["compile"]).resolve().parent.parent
        return capsule, files

    def _write_fake_evidence(self, evidence_root, source):
        source = source.resolve()
        relative = source.relative_to(b_harness.ROOT).as_posix()
        raw = source.read_bytes()
        rows = b_delivery._binding_rows({relative: raw})
        binding_sha = b_delivery._binding_sha(rows)
        inputs_raw = b_delivery.encode({
            "binding_sha256": binding_sha,
            "files": rows,
        })
        snapshot = evidence_root / "snapshot" / relative
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(raw)
        snapshot_here = (
            evidence_root / "snapshot"
            / b_delivery.HERE.relative_to(b_harness.ROOT)
        )
        command = {
            "argv": [
                b_harness.sys.executable, "-B", "-X", "utf8", "-m",
                "unittest", "test_b_loader_contract.py",
            ],
            "cwd": str(snapshot_here),
            "timeout_seconds": 120,
            "input_binding_sha256": binding_sha,
            "automatic_retries": 0,
            "HDL_tool_calls": 0,
            "EDA_calls": 0,
            "environment_bat_invoked": False,
        }
        command_raw = b_delivery.encode(command)
        stdout = b""
        stderr = b"Ran directed tests: OK\n"
        receipt = {
            "schema": "T061_N32_B_LOADER_SOFTWARE_EVIDENCE_V2",
            "status": "PASS",
            "exit_code": 0,
            "timed_out": False,
            "stdout": b_delivery.digest(stdout),
            "stderr": b_delivery.digest(stderr),
            "command": b_delivery.digest(command_raw),
            "inputs": b_delivery.digest(inputs_raw),
            "input_binding_sha256": binding_sha,
            "inputs_before_sha256": binding_sha,
            "inputs_after_sha256": binding_sha,
            "python": {
                "path": b_harness.sys.executable,
                **b_harness.identity(b_harness.sys.executable),
            },
            "automatic_retries": 0,
            "HDL_tool_calls": 0,
            "EDA_calls": 0,
            "environment_bat_invoked": False,
        }
        evidence_root.mkdir(parents=True, exist_ok=True)
        (evidence_root / "command.json").write_bytes(command_raw)
        (evidence_root / "inputs.json").write_bytes(inputs_raw)
        (evidence_root / "stdout.bin").write_bytes(stdout)
        (evidence_root / "stderr.bin").write_bytes(stderr)
        (evidence_root / "receipt.json").write_bytes(
            b_delivery.encode(receipt)
        )
        return relative, raw, snapshot

    def test_unlisted_dll_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=b_harness.HERE) as raw:
            capsule, files = self._copy_fake_capsule(Path(raw))
            b_harness.validate_compiler_dll_closure(capsule, files)
            (capsule / "bin/injected.dll").write_bytes(b"unreviewed")
            with self.assertRaisesRegex(ValueError,
                                        "COMPILER_DLL_CLOSURE_DRIFT"):
                b_harness.validate_compiler_dll_closure(capsule, files)

    def test_deleted_or_unbound_dll_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=b_harness.HERE) as raw:
            capsule, files = self._copy_fake_capsule(Path(raw))
            missing = (capsule / "lib/libwinpthread-1.dll").resolve()
            missing.unlink()
            with self.assertRaisesRegex(ValueError,
                                        "COMPILER_DLL_CLOSURE_DRIFT"):
                b_harness.validate_compiler_dll_closure(capsule, files)

        with tempfile.TemporaryDirectory(dir=b_harness.HERE) as raw:
            capsule, files = self._copy_fake_capsule(Path(raw))
            unbound = str((capsule / "lib/libstdc++-6.dll").resolve())
            files = {name: value for name, value in files.items()
                     if name != unbound}
            with self.assertRaisesRegex(ValueError,
                                        "COMPILER_DLL_CLOSURE_DRIFT"):
                b_harness.validate_compiler_dll_closure(capsule, files)

    def test_loader_environment_restores_after_child_exception(self):
        environment = {
            "PATH": "C:\\sealed\\bin;C:\\sealed\\lib",
            "YOSYSHQ_ROOT": "C:\\sealed",
        }
        before = {key: os.environ.get(key)
                  for key in b_harness.TOOL_ENVIRONMENT_KEYS}
        observed = {}

        def fail(*args):
            observed.update({key: os.environ.get(key)
                             for key in b_harness.TOOL_ENVIRONMENT_KEYS})
            raise RuntimeError("synthetic-child-failure")

        with mock.patch.object(b_harness, "_run_process", side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, "synthetic-child-failure"):
                b_harness._run_process_with_environment(
                    Path("unused"), "label", ["tool"], Path("unused"), 1,
                    object(), environment,
                )
        self.assertEqual(observed, environment)
        self.assertEqual(
            {key: os.environ.get(key)
             for key in b_harness.TOOL_ENVIRONMENT_KEYS},
            before,
        )

    def test_old_pass_after_source_change_is_rejected(self):
        tested = {"B/b_harness.py": b"tested", "B/test.py": b"test"}
        rows = b_delivery._binding_rows(tested)
        b_delivery.validate_loader_input_binding(rows, tested)
        changed = dict(tested)
        changed["B/b_harness.py"] = b"changed-after-pass"
        with self.assertRaisesRegex(ValueError,
                                    "LOADER_INPUT_IDENTITY_DRIFT"):
            b_delivery.validate_loader_input_binding(rows, changed)

    def test_receipt_or_raw_log_tamper_is_rejected(self):
        command = b"{\"argv\":[]}\n"
        inputs = b"{\"files\":[]}\n"
        stdout = b""
        stderr = b"Ran directed tests: OK\n"
        receipt = {
            "schema": "T061_N32_B_LOADER_SOFTWARE_EVIDENCE_V2",
            "status": "PASS",
            "exit_code": 0,
            "timed_out": False,
            "HDL_tool_calls": 0,
            "EDA_calls": 0,
            "environment_bat_invoked": False,
            "command": b_delivery.digest(command),
            "inputs": b_delivery.digest(inputs),
            "stdout": b_delivery.digest(stdout),
            "stderr": b_delivery.digest(stderr),
        }
        b_delivery.validate_loader_receipt_raw(
            receipt, command, inputs, stdout, stderr
        )
        with self.assertRaisesRegex(ValueError, "LOADER_STDERR_DRIFT"):
            b_delivery.validate_loader_receipt_raw(
                receipt, command, inputs, stdout, stderr + b"tamper"
            )
        changed_receipt = json.loads(json.dumps(receipt))
        changed_receipt["status"] = "FAIL_PARTIAL"
        with self.assertRaisesRegex(ValueError, "LOADER_EVIDENCE_NOT_PASS"):
            b_delivery.validate_loader_receipt_raw(
                changed_receipt, command, inputs, stdout, stderr
            )

    def test_actual_seal_rejects_unlisted_snapshot_file(self):
        output_parent = b_harness.ROOT / "code/output"
        output_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output_parent) as output_raw:
            with tempfile.TemporaryDirectory(dir=b_harness.HERE) as target_raw:
                output_root = Path(output_raw)
                source = output_root / "tested.py"
                source.write_bytes(b"tested")
                evidence = output_root / "evidence"
                self._write_fake_evidence(evidence, source)
                (evidence / "snapshot/unlisted.py").write_bytes(b"unlisted")
                target = Path(target_raw) / "sealed"
                with mock.patch.object(
                        b_delivery, "_loader_review_inputs",
                        return_value=[source]), mock.patch.object(
                        b_delivery, "_authored_files",
                        return_value=[source]), mock.patch.object(
                        b_delivery, "binary_diff",
                        return_value=(b"patch", {"path": "fake"})):
                    with self.assertRaisesRegex(
                            ValueError, "LOADER_SNAPSHOT_SET_DRIFT"):
                        b_delivery.seal_loader_review(
                            evidence, target, "T061-N32-B-LOADER-TEST"
                        )

    def test_actual_seal_archives_validated_cache_not_later_disk_change(self):
        output_parent = b_harness.ROOT / "code/output"
        output_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output_parent) as output_raw:
            with tempfile.TemporaryDirectory(dir=b_harness.HERE) as target_raw:
                output_root = Path(output_raw)
                source = output_root / "tested.py"
                source.write_bytes(b"tested")
                evidence = output_root / "evidence"
                relative, tested, snapshot = self._write_fake_evidence(
                    evidence, source
                )
                target = Path(target_raw) / "sealed"
                original_reader = b_delivery._read_loader_evidence

                def read_then_mutate(path):
                    result = original_reader(path)
                    snapshot.write_bytes(b"changed-after-validation")
                    return result

                with mock.patch.object(
                        b_delivery, "_loader_review_inputs",
                        return_value=[source]), mock.patch.object(
                        b_delivery, "_authored_files",
                        return_value=[source]), mock.patch.object(
                        b_delivery, "binary_diff",
                        return_value=(b"patch", {"path": "fake"})), \
                        mock.patch.object(
                            b_delivery, "_read_loader_evidence",
                            side_effect=read_then_mutate):
                    b_delivery.seal_loader_review(
                        evidence, target, "T061-N32-B-LOADER-TEST"
                    )
                archive = base64.b64decode(
                    (target / "snapshot.zip.b64").read_bytes()
                )
                with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
                    archived = bundle.read("evidence/snapshot/" + relative)
                self.assertEqual(archived, tested)
                self.assertNotEqual(archived, snapshot.read_bytes())


if __name__ == "__main__":
    unittest.main()
