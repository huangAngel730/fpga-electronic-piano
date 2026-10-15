"""Small SOFTWARE_FIXTURE packages: never genuine long-window captures."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import static_bundle as guard
import run_software


class StaticBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.prepared = self.root / "prepared"
        self.prepared.mkdir()

        def write(path, data=b"SOFTWARE_FIXTURE_ONLY\n"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return guard.identity(path)

        self.write = write
        control = write(self.prepared / "controls.hex", b"0123456789\n")
        ledger = write(self.prepared / "expected_publications.jsonl", b"fixture ledger\n")
        confirmation = write(self.root / "confirmation.md", b"fixture confirmation\n")
        write(self.prepared / "M1_INPUT_CONFIRMATION.md", b"fixture confirmation\n")
        for name in guard.PYTHON_NAMES:
            write(self.root / guard.BASE / name)
        for name in guard.TB_NAMES:
            write(self.root / guard.TB / name)
            write(self.prepared / name)
        suite = self.root / "tools"
        tools = dict(missing=[], requested_suite=str(suite), files=[
            write(suite / "bin/iverilog.exe"), write(suite / "bin/vvp.exe")])
        qualified = dict(status="TOOL_METADATA_PASS", after=tools,
                         steps=[dict(version="fixture compiler"),
                                dict(version="fixture runtime")])
        qpath = self.root / "qualification.json"
        qpath.write_text(json.dumps(qualified), encoding="utf-8")
        qualification = guard.identity(qpath)
        frozen, groups = {}, []
        names = sorted(guard.FROZEN_NAMES)
        for index, part in enumerate((names[:1], names[1:])):
            relative = f"archive{index}.zip"
            archive_path = self.root / relative
            members = {}
            with zipfile.ZipFile(archive_path, "x") as archive:
                for name in part:
                    member = "frozen/" + name
                    data = ("fixture " + name).encode("ascii")
                    archive.writestr(member, data)
                    spec = write(self.prepared / "readonly" / name, data)
                    members[member] = dict(bytes=len(data), sha256=spec["sha256"])
                    frozen[name] = dict(spec, archive=relative, member=member)
            groups.append(dict(path=relative,
                               sha256=guard.identity(archive_path)["sha256"], members=members))
        source_manifest = self.root / guard.SOURCE_MANIFEST
        source_manifest.parent.mkdir(parents=True, exist_ok=True)
        source_manifest.write_text(json.dumps(dict(raw_archive=groups[0],
                                                   readonly_archive=groups[1])), encoding="utf-8")
        sources = [self.root / guard.BASE / n for n in guard.PYTHON_NAMES]
        sources += [self.root / guard.TB / n for n in guard.TB_NAMES]
        sources += [source_manifest, Path(confirmation["path"]), qpath]
        python = write(self.root / "python.exe")
        self.proposal = dict(
            schema="T052_LONG_STATIC_PREPARATION_R01", plan=guard.PLAN,
            execution_authorized=False, phase="STATIC_PREPARATION_ONLY",
            actual_HDL_calls=0, actual_RTL_runs=0, actual_EDA_calls=0,
            PCM_math_verified=False, old_4207_completeness="UNKNOWN", rows=guard.ROWS,
            expected_end=dict(type="END", rows=guard.ROWS, accepted=8207,
                              published=8201, cancelled=6, open=0),
            proposed_limits_seconds=dict(compile=90, run=300, check=300, total=900),
            proposed_output_limit_bytes=1200 * (1 << 20),
            proposed_capture_limit_bytes=750 * (1 << 20),
            last_posedge_ns=170726710, finish_ns=170726711,
            simulation_timeout_ns=170726720,
            input=control, expected_ledger=ledger, m1_confirmation=confirmation,
            tool_qualification=qualification, tools=tools,
            tool_versions=["fixture compiler", "fixture runtime"],
            source_files={str(p): guard.identity(p) for p in sources},
            frozen_sources=frozen, python=python, cwd=str(self.prepared),
            compile_argv=[str(suite / "bin/iverilog.exe"), "-g2012", "-s", "tb_t052_long",
                          "-o", "long.vvp", "readonly/t052_polyphony_test_source.sv",
                          "readonly/dds_oscillator.sv", "readonly/pcm_mixer_4voice.sv",
                          "t052_long_observer.sv", "tb_t052_long.sv"],
            run_argv=[str(suite / "bin/vvp.exe"), "long.vvp"],
            check_argv=[python["path"], "-B", "-X", "utf8",
                        str(self.root / guard.BASE / "check_capture.py"),
                        "--capture", str(self.prepared), "--report",
                        str(self.prepared / "capture_review.json")])
        # Only this test fixture replaces artifact pins; CLI has no such override.
        pins = dict(CONTROL_BYTES=control["bytes"], CONTROL_SHA=control["sha256"],
                    LEDGER_SHA=ledger["sha256"], M1_SHA=confirmation["sha256"])
        patches = patch.multiple(guard, **pins)
        patches.start()
        self.addCleanup(patches.stop)

    def check(self):
        (self.prepared / "proposal.json").write_text(json.dumps(self.proposal), encoding="utf-8")
        return guard.check_prepared(self.prepared, self.root)

    def reject(self, diagnostic):
        with self.assertRaisesRegex(guard.BindingError, diagnostic):
            self.check()

    def test_matching_fixture_stays_locked(self):
        result = self.check()
        self.assertEqual(result["status"], "STATIC_IDENTITY_MATCH_ONLY")
        self.assertIs(result["execution_authorized"], False)
        self.assertIs(result["complete_T052"], False)
        self.assertIs(result["proposed_commands_executed"], False)

    def test_permission_claim_rejected(self):
        self.proposal["execution_authorized"] = True
        self.reject("EXECUTION_MUST_BE_LOCKED")

    def test_false_integer_is_not_zero(self):
        self.proposal["actual_RTL_runs"] = False
        self.reject("NONZERO_OR_INVALID_TOOL_CLAIM")

    def test_nonzero_hdl_call(self):
        self.proposal["actual_HDL_calls"] = 1
        self.reject("NONZERO_OR_INVALID_TOOL_CLAIM")

    def test_float_totals_rejected(self):
        self.proposal["expected_end"]["accepted"] = 8207.0
        self.reject("WRONG_STATIC_TOTALS")

    def test_budget_cannot_be_increased(self):
        self.proposal["proposed_limits_seconds"]["run"] = 600
        self.reject("BUDGET_CONTRACT_CHANGED")

    def test_capture_limit_cannot_be_increased(self):
        self.proposal["proposed_capture_limit_bytes"] += 1
        self.reject("WINDOW_OR_OUTPUT_LIMIT_CHANGED")

    def test_simulation_window_cannot_be_changed(self):
        self.proposal["simulation_timeout_ns"] += 20
        self.reject("WINDOW_OR_OUTPUT_LIMIT_CHANGED")

    def test_control_file_drift(self):
        Path(self.proposal["input"]["path"]).write_bytes(b"tampered")
        self.reject("FILE_IDENTITY_MISMATCH")

    def test_rehashed_wrong_control_rejected(self):
        self.proposal["input"] = self.write(self.prepared / "controls.hex", b"wrong plan")
        self.reject("FROZEN_CONTROL_CHANGED")

    def test_rehashed_wrong_ledger_rejected(self):
        self.proposal["expected_ledger"] = self.write(
            self.prepared / "expected_publications.jsonl", b"wrong ledger")
        self.reject("FROZEN_LEDGER_CHANGED")

    def test_missing_input(self):
        Path(self.proposal["input"]["path"]).unlink()
        with self.assertRaises(FileNotFoundError):
            self.check()

    def test_wrong_input_path(self):
        self.proposal["input"] = self.write(self.root / "other.hex", b"0123456789\n")
        self.reject("IDENTITY_WRONG_PATH")

    def test_float_size_rejected(self):
        self.proposal["input"]["bytes"] = float(self.proposal["input"]["bytes"])
        self.reject("IDENTITY_SIZE_TYPE")

    def test_source_drift(self):
        self.write(self.root / guard.BASE / "plan.py", b"changed source")
        self.reject("FILE_IDENTITY_MISMATCH")

    def test_missing_source(self):
        del self.proposal["source_files"][str(self.root / guard.BASE / "plan.py")]
        self.reject("SOURCE_CLOSURE_MISMATCH")

    def test_extra_source(self):
        extra = self.write(self.root / "extra.py")
        self.proposal["source_files"][extra["path"]] = extra
        self.reject("SOURCE_CLOSURE_MISMATCH")

    def test_tb_copy_drift(self):
        self.write(self.prepared / "t052_long_observer.sv", b"wrong observer")
        self.reject("TB_COPY_CHANGED")

    def test_frozen_file_drift(self):
        self.write(self.prepared / "readonly/sine_1024_8192.mem", b"wrong ROM")
        self.reject("FILE_IDENTITY_MISMATCH")

    def test_archive_drift(self):
        self.write(self.root / "archive0.zip", b"wrong archive")
        self.reject("ARCHIVE_SHA_MISMATCH")

    def test_wrong_frozen_mapping(self):
        self.proposal["frozen_sources"]["dds_oscillator.sv"]["member"] = "other.sv"
        self.reject("FROZEN_SOURCE_MAPPING")

    def test_duplicate_json_key(self):
        path = self.root / "bad.json"
        path.write_text('{"rows":1,"rows":2}', encoding="utf-8")
        with self.assertRaisesRegex(guard.BindingError, "DUPLICATE_JSON_KEY"):
            guard.load_json(path)

    def test_nonfinite_json(self):
        path = self.root / "bad.json"
        path.write_text('{"rows":NaN}', encoding="utf-8")
        with self.assertRaisesRegex(guard.BindingError, "NONFINITE_JSON"):
            guard.load_json(path)

    def test_tool_binary_drift(self):
        self.write(self.root / "tools/bin/vvp.exe", b"wrong runtime")
        self.reject("FILE_IDENTITY_MISMATCH")

    def test_incomplete_tool_inventory(self):
        self.proposal["tools"]["files"] = []
        self.reject("TOOL_INVENTORY_DISAGREES")

    def test_command_injection_is_only_rejected_data(self):
        self.proposal["compile_argv"].append("--other-source")
        self.reject("COMPILE_ARGV_CHANGED")

    def test_run_command_changed(self):
        self.proposal["run_argv"].append("--extra")
        self.reject("RUN_ARGV_CHANGED")

    def test_checker_command_changed(self):
        self.proposal["check_argv"][-1] = str(self.root / "other.json")
        self.reject("CHECK_ARGV_CHANGED")

    def test_cwd_changed(self):
        self.proposal["cwd"] = str(self.root)
        self.reject("CWD_CHANGED")

    def test_evidence_level_cannot_be_upgraded(self):
        self.proposal["PCM_math_verified"] = True
        self.reject("EVIDENCE_UPGRADE")

    def test_drift_during_read(self):
        original = guard.identity
        path = (self.prepared / "controls.hex").resolve()
        calls = 0

        def drifting(value):
            nonlocal calls
            result = original(value)
            if Path(value).resolve() == path:
                calls += 1
                if calls > 1:
                    result = copy.deepcopy(result)
                    result["sha256"] = "0" * 64
            return result

        with patch.object(guard, "identity", side_effect=drifting):
            self.reject("FILE_CHANGED_DURING_CHECK")

    def test_runner_refuses_existing_output(self):
        output = self.root / "code/output/existing"
        output.mkdir(parents=True)
        marker = output / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        with patch.object(run_software, "ROOT", self.root):
            with self.assertRaises(FileExistsError):
                run_software.run(output)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_runner_refuses_output_outside_scope(self):
        with patch.object(run_software, "ROOT", self.root):
            with self.assertRaisesRegex(ValueError, "OUTPUT_MUST_BE_IN_CODE_OUTPUT"):
                run_software.run(self.root / "not_output")
        self.assertFalse((self.root / "not_output").exists())

    def test_cli_refuses_existing_report(self):
        report = self.root / "existing.json"
        report.write_text("keep", encoding="utf-8")
        with patch("sys.argv", ["static_bundle.py", "--prepared", str(self.prepared),
                                "--report", str(report)]):
            with self.assertRaises(SystemExit) as raised:
                guard.main()
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(report.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main(verbosity=2)
