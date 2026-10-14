"""Pure-software structural guards for b_harness; starts no HDL process."""
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import b_harness as harness
import b_delivery


class HarnessStructureTests(unittest.TestCase):
    def test_exact_case_matrix(self):
        self.assertEqual(
            harness.CASES,
            (
                ("normal_long", None, 1, 0,
                 "N32_B_R1_EVENT_AUDIO_PASS_T061_PARTIAL"),
                ("wrong_id", "B_N32_MUTANT_RESULT_ID", 0, 1,
                 "RESULT_ID_LEDGER"),
                ("wrong_pcm", "B_N32_MUTANT_PCM", 0, 1,
                 "RESULT_PCM_LEDGER"),
                ("wrong_clipped", "B_N32_MUTANT_CLIPPED", 0, 1,
                 "RESULT_CLIPPED_LEDGER"),
            ),
        )

    def test_sources_are_unique_and_complete(self):
        resolved = [path.resolve() for path in harness.HDL_SOURCES]
        self.assertEqual(len(resolved), len(set(resolved)))
        names = {path.name for path in resolved}
        for required in (
            "m3_balanced_voice_allocator.sv", "b_n32_event_router.sv",
            "b_n32_event_audio_prom.sv", "b_n32_r1_wrapper.sv",
            "tb_b2d_event_audio.sv", "b_n32_observer.sv",
            "tb_b_n32_r1.sv", "prim_sim.v",
        ):
            self.assertIn(required, names)

    def test_all_snapshot_inputs_exist(self):
        for path in harness.HDL_SOURCES + harness.SUPPORT_INPUTS:
            self.assertTrue(path.is_file(), str(path))

    def test_delivery_scope_includes_b_sources_and_generator(self):
        authored = set(b_delivery._authored_files())
        for path in (
            harness.B_RTL / "b_n32_event_router.sv",
            harness.B_RTL / "b_n32_event_audio_prom.sv",
            harness.B_RTL / "b_n32_r1_wrapper.sv",
            harness.B_RTL / "b_n32_c_interface.json",
            harness.HERE / "b_harness.py",
            harness.HERE / "b_delivery.py",
            harness.HERE / "b_n32_check.py",
        ):
            self.assertIn(path.resolve(), {item.resolve() for item in authored})
        self.assertEqual(len(b_delivery.BASE), 40)
        self.assertIn(
            harness.HERE / "test_b_loader_contract.py",
            {item.resolve() for item in authored},
        )

    def test_compiler_capsule_uses_copied_executables_and_plugins(self):
        with tempfile.TemporaryDirectory(dir=harness.ROOT / "code/output") as raw:
            root = Path(raw)
            suite = root / "suite"
            prepared = root / "prepared"
            for relative, payload in (
                ("bin/iverilog.exe", b"compile"),
                ("bin/vvp.exe", b"simulate"),
                ("bin/runtime.dll", b"dll"),
                ("lib/libgcc_s_seh-1.dll", b"gcc"),
                ("lib/libstdc++-6.dll", b"stdc++"),
                ("lib/libwinpthread-1.dll", b"pthread"),
                ("lib/ivl/plugin.vpi", b"plugin"),
            ):
                path = suite / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
            prepared.mkdir()
            origin_tools = {
                "python": str(Path(harness.sys.executable).resolve()),
                "compile": str((suite / "bin/iverilog.exe").resolve()),
                "simulate": str((suite / "bin/vvp.exe").resolve()),
            }
            origin_files = {
                str(path.resolve()): harness.identity(path)
                for path in suite.rglob("*") if path.is_file()
            }
            origin_files[origin_tools["python"]] = harness.identity(
                origin_tools["python"]
            )
            tools, files, compiler_lib = harness.copy_compiler_capsule(
                prepared, suite, origin_tools, origin_files
            )
            capsule = (prepared / "tools/iverilog").resolve()
            self.assertTrue(Path(tools["compile"]).is_relative_to(capsule))
            self.assertTrue(Path(tools["simulate"]).is_relative_to(capsule))
            self.assertTrue(compiler_lib.is_relative_to(capsule))
            self.assertIn(str((capsule / "lib/ivl/plugin.vpi").resolve()), files)
            for name in harness.COMPILER_RUNTIME_DLLS:
                copied = (capsule / "lib" / name).resolve()
                self.assertIn(str(copied), files)
                self.assertEqual(harness.identity(copied), files[str(copied)])
            self.assertEqual(
                harness.compiler_environment(capsule),
                {
                    "PATH": os.pathsep.join((str(capsule / "bin"),
                                              str(capsule / "lib"))),
                    "YOSYSHQ_ROOT": str(capsule),
                },
            )

    def test_tool_inventory_binds_lib_runtime_dlls_without_environment_bat(self):
        with tempfile.TemporaryDirectory(dir=harness.ROOT / "code/output") as raw:
            suite = Path(raw) / "suite"
            for relative, payload in (
                ("bin/iverilog.exe", b"compile"),
                ("bin/vvp.exe", b"simulate"),
                ("bin/tool.dll", b"bin"),
                ("lib/libgcc_s_seh-1.dll", b"gcc"),
                ("lib/libstdc++-6.dll", b"stdc++"),
                ("lib/libwinpthread-1.dll", b"pthread"),
                ("lib/ivl/ivl.exe", b"ivl"),
                ("environment.bat", b"must not run or copy"),
            ):
                path = suite / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
            _, inventory = harness.tool_inventory(suite)
            for name in harness.COMPILER_RUNTIME_DLLS:
                self.assertIn(str((suite / "lib" / name).resolve()), inventory)
            self.assertNotIn(str((suite / "environment.bat").resolve()), inventory)

    def test_child_loader_environment_is_exact_and_parent_is_restored(self):
        environment = {
            "PATH": "C:\\sealed\\bin;C:\\sealed\\lib",
            "YOSYSHQ_ROOT": "C:\\sealed",
        }
        before = {key: os.environ.get(key)
                  for key in harness.TOOL_ENVIRONMENT_KEYS}
        observed = {}

        def fake_run(*args):
            observed.update({key: os.environ.get(key)
                             for key in harness.TOOL_ENVIRONMENT_KEYS})
            return {"exit_code": 0}

        with mock.patch.object(harness, "_run_process", side_effect=fake_run):
            result = harness._run_process_with_environment(
                Path("unused"), "label", ["tool"], Path("unused"), 1,
                object(), environment,
            )
        self.assertEqual(result, {"exit_code": 0})
        self.assertEqual(observed, environment)
        self.assertEqual(
            {key: os.environ.get(key) for key in harness.TOOL_ENVIRONMENT_KEYS},
            before,
        )
        with self.assertRaisesRegex(ValueError, "TOOL_ENVIRONMENT_KEYS"):
            harness._run_process_with_environment(
                Path("unused"), "label", ["tool"], Path("unused"), 1,
                object(), {**environment, "EXTRA": "forbidden"},
            )

    def test_isolated_process_loads_harness_helpers_from_capsule(self):
        with tempfile.TemporaryDirectory(dir=harness.ROOT / "code/output") as raw:
            root = Path(raw)
            snapshot = root / "snapshot"
            harness_dir = snapshot / harness.HERE.relative_to(harness.ROOT)
            helper_dir = snapshot / harness.HELPERS.relative_to(harness.ROOT)
            harness_dir.mkdir(parents=True)
            helper_dir.mkdir(parents=True)
            shutil.copy2(harness.HERE / "b_harness.py", harness_dir)
            shutil.copy2(harness.HERE / "b_progress.py", harness_dir)
            for name in ("runner.py", "runner_tail_20261013.py", "windows_job.py"):
                shutil.copy2(harness.HELPERS / name, helper_dir)

            poison = root / "poison"
            poison.mkdir()
            (poison / "runner.py").write_text(
                "raise RuntimeError('ACTIVE_OR_PYTHONPATH_RUNNER_USED')\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = str(poison)
            result = subprocess.run(
                [harness.sys.executable, "-I", "-S", "-B", "-X", "utf8",
                 str(harness_dir / "b_harness.py"), "--repo-root",
                 str(harness.ROOT), "--help"],
                cwd=root, env=env, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("reviewed active repository root", result.stdout)
            self.assertNotIn("ACTIVE_OR_PYTHONPATH_RUNNER_USED",
                             result.stdout + result.stderr)

    def test_no_lower_or_eda_process_is_constructed(self):
        tree = ast.parse(Path(harness.__file__).read_text(encoding="utf-8"))
        literals = {node.value for node in ast.walk(tree)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        self.assertNotIn("lower", {value.lower() for value in literals})
        self.assertNotIn("gowin", {value.lower() for value in literals})
        self.assertNotIn("yosys", {value.lower() for value in literals})

    def test_all_frozen_authorities_exist_and_match(self):
        for path, expected in harness.AUTHORITY_SHA.items():
            self.assertTrue(path.is_file(), str(path))
            self.assertEqual(harness.identity(path)["sha256"], expected, str(path))

    def test_output_guard_rejects_root_and_escape(self):
        for path in (harness.ROOT, harness.ROOT / "code/output",
                     harness.ROOT.parent / "escape"):
            with self.assertRaisesRegex(ValueError, "OUTPUT_OUTSIDE_CODE_OUTPUT"):
                harness.under_output(path)

    def test_output_root_is_not_redirected(self):
        lexical = (harness.ROOT / "code/output").absolute()
        self.assertTrue(lexical.is_dir())
        self.assertFalse(lexical.is_symlink())
        self.assertEqual(lexical.resolve(), lexical)

    def test_active_harness_cannot_execute_formal_plan(self):
        self.assertFalse(harness.SNAPSHOT_MODE)
        with self.assertRaisesRegex(ValueError,
                                    "EXECUTE_REQUIRES_SNAPSHOT_CAPSULE"):
            harness.execute(Path("unused.json"), "0" * 64,
                            "0" * 64, "0" * 64,
                            "T061-N32-A-RESULT-TEST")

    def test_step_binding_rejects_active_repository_input(self):
        records = [
            {
                "origin": str(path.resolve()),
                "snapshot": harness.snapshot_name(path),
            }
            for path in (
                list(dict.fromkeys(
                    harness.HDL_SOURCES
                    + [harness.HERE / "b_n32_check.py",
                       harness.FROZEN / "include/sine_table.svh"]
                ))
            )
        ]
        snapshot = {
            str(Path(row["origin"]).resolve()): str(
                Path("C:/sealed/snapshot") / row["snapshot"]
            )
            for row in records
        }
        hdl = [snapshot[str(path.resolve())] for path in harness.HDL_SOURCES]
        checker = snapshot[str((harness.HERE / "b_n32_check.py").resolve())]
        include_dir = str(Path(snapshot[
            str((harness.FROZEN / "include/sine_table.svh").resolve())
        ]).parent)
        plan = {
            "prepared": "C:/sealed",
            "compiler_lib": "C:\\sealed\\tools\\iverilog\\lib\\ivl",
            "inputs": records,
            "steps": [
                {"label": "compile", "kind": "compile",
                 "argv": ["iverilog", "-B",
                          "C:\\sealed\\tools\\iverilog\\lib\\ivl",
                          "-I", include_dir, *hdl]},
                {"label": "check", "kind": "check",
                 "argv": ["python", checker]},
            ],
        }
        harness._validate_step_snapshot_binding(plan)
        plan["steps"][0]["argv"][-1] = str(harness.HDL_SOURCES[-1].resolve())
        with self.assertRaisesRegex(ValueError, "ACTIVE_REPOSITORY_INPUT"):
            harness._validate_step_snapshot_binding(plan)

    def test_c_interface_manifest_matches_wrapper_and_source_order(self):
        manifest_path = harness.B_RTL / "b_n32_c_interface.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        wrapper = (harness.B_RTL / "b_n32_r1_wrapper.sv").read_text(
            encoding="utf-8"
        )
        required = (
            "event_valid", "event_ready", "event_data",
            "control_snapshot_valid", "control_snapshot_ready",
            "control_snapshot_id", "control_snapshot_value",
            "sample_valid", "sample_ready", "sample_id",
            "result_valid", "result_ready", "result_id", "left", "right",
            "clipped", "backend_release_done_valid",
            "backend_release_done_ready", "backend_release_done_slot",
            "backend_release_done_generation", "read_valid", "read_ready",
            "read_out_valid", "read_slot", "read_context", "cancel",
            "aborted", "abort_reason", "idle", "fault", "occupied",
            "releasing", "sources", "channels", "notes", "generations",
        )
        for name in required:
            self.assertIn(name, wrapper)
        for section in (
            "clock_reset_cancel_semantics", "public_read_timing",
            "control_snapshot_timing", "control_release_timing",
            "backend_release_done_timing", "audio_state_encoding",
            "router_state_encoding", "compile_contract", "compile_order",
        ):
            self.assertIn(section, manifest)

        def portable(path):
            path = path.resolve()
            if path.is_relative_to(harness.ROOT.resolve()):
                return path.relative_to(harness.ROOT).as_posix()
            return path.as_posix()

        expected = [portable(path) for path in harness.HDL_SOURCES[:20]]
        self.assertEqual(manifest["compile_order"][:20], expected)
        self.assertEqual(manifest["compile_order"][20], "<C testbench last>")


if __name__ == "__main__":
    unittest.main()
