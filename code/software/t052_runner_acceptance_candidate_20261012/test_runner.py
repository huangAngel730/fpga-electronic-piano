"""Software fake-tool qualification for the independent T052 runner."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from runner import identity, load_json, run, write_json  # noqa: E402

EVIDENCE = None


FAKE_TOOL = r'''import pathlib, subprocess, sys, time
mode = sys.argv[1] if len(sys.argv) > 1 else "version"
if mode == "version":
    print("T052_FAKE_TOOL 1.0")
elif mode == "compile":
    pathlib.Path("compiled.fake").write_bytes(b"compiled-this-run")
elif mode == "simulate":
    pathlib.Path("tb_t052_polyphony.capture").write_bytes(b"new capture\n")
    pathlib.Path("tb_t052_requests.log").write_bytes(b"new requests\n")
    print("PASS: fake simulation only")
elif mode == "check":
    pathlib.Path("checked.fake").write_bytes(b"checked-this-run")
    print("CHECK_OK")
elif mode == "pass_nonzero":
    print("PASS: text cannot override exit")
    raise SystemExit(7)
elif mode == "no_artifact":
    print("PASS: but no artifact")
elif mode == "timeout_tree":
    child = "import time,pathlib;time.sleep(1.5);pathlib.Path('orphan.txt').write_text('bad')"
    process = subprocess.Popen([sys.executable, "-I", "-S", "-B", "-c", child])
    print("partial parent=" + str(process.pid), flush=True)
    pathlib.Path("partial.capture").write_bytes(b"partial")
    time.sleep(10)
else:
    raise SystemExit(9)
'''


def fixture(root, simulate="simulate", sim_timeout=4, missing_rom=False):
    inputs = root / "inputs"
    inputs.mkdir()
    members = {
        "dut.sv": ("DUT", b"dut"),
        "tb.sv": ("TB", b"tb"),
        "rom.mem": ("ROM", b"rom"),
        "checker.py": ("CHECKER", b"checker"),
        "fake_tool.py": ("SUPPORT", FAKE_TOOL.encode("utf-8")),
    }
    if missing_rom:
        members.pop("rom.mem")
    entries = []
    for name, (role, raw) in members.items():
        path = inputs / name
        path.write_bytes(raw)
        entries.append({"path": name, "role": role, **identity(path)})
    python = Path(sys.executable).resolve()
    tool = {"path": str(python), **identity(python), "version_args": ["--version"]}
    config = {
        "schema": "T052_RUNNER_ACCEPTANCE_V1",
        "profile": "SOFTWARE_FAKE_TOOLS_ONLY_OR_EXPLICIT_FUTURE_TOOL",
        "input_root": str(inputs),
        "total_seconds": 20,
        "critical_artifacts": ["tb_t052_polyphony.capture", "tb_t052_requests.log"],
        "tools": {"python": tool},
        "inputs": entries,
        "steps": [
            {"label": "compile", "kind": "compile", "tool": "python",
             "args": ["fake_tool.py", "compile"], "timeout_seconds": 3,
             "expected_artifacts": ["compiled.fake"], "required_marker": None},
            {"label": "simulate", "kind": "simulate", "tool": "python",
             "args": ["fake_tool.py", simulate], "timeout_seconds": sim_timeout,
             "expected_artifacts": ["tb_t052_polyphony.capture",
                                    "tb_t052_requests.log"],
             "required_marker": "PASS:"},
            {"label": "check", "kind": "check", "tool": "python",
             "args": ["fake_tool.py", "check"], "timeout_seconds": 3,
             "expected_artifacts": ["checked.fake"], "required_marker": "CHECK_OK"},
        ],
    }
    path = root / "config.json"
    write_json(path, config)
    return path


class RunnerTests(unittest.TestCase):
    def case(self, name):
        path = EVIDENCE / name
        path.mkdir()
        return path

    def test_success_requires_all_three_steps_and_new_artifacts(self):
        case = self.case("success")
        result = run(fixture(case), case / "out")
        self.assertEqual(result["status"], "JOINT_COMPILE_SIMULATE_CHECK_PASS")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["automatic_retries"], 0)
        self.assertEqual(result["produced_by"]["tb_t052_polyphony.capture"]["step"],
                         "simulate")
        self.assertEqual(result["inputs_before"], result["inputs_after"])
        self.assertEqual(result["tools_before"], result["tools_after"])

    def test_pass_text_with_nonzero_exit_is_rejected(self):
        case = self.case("pass_text_nonzero")
        result = run(fixture(case, "pass_nonzero"), case / "out")
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("STEP_EXIT_NONZERO:simulate", result["failure"])
        self.assertFalse((case / "out/check.stdout.bin").exists())

    def test_zero_exit_without_artifacts_is_rejected(self):
        case = self.case("missing_artifact")
        result = run(fixture(case, "no_artifact"), case / "out")
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("STEP_ARTIFACT_MISSING", result["failure"])

    def test_missing_rom_still_writes_receipt(self):
        case = self.case("missing_rom")
        result = run(fixture(case, missing_rom=True), case / "out")
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("REQUIRED_INPUT_ROLE_MISSING", result["failure"])
        self.assertTrue((case / "out/receipt.json").is_file())

    def test_missing_tool_still_writes_receipt(self):
        case = self.case("missing_tool")
        config = fixture(case)
        value = load_json(config)
        value["tools"]["python"]["path"] = str(case / "absent.exe")
        config.unlink()
        write_json(config, value)
        result = run(config, case / "out")
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("TOOL_MISSING_OR_RELATIVE", result["failure"])

    def test_missing_dependency_still_writes_receipt(self):
        case = self.case("missing_dependency")
        config = fixture(case)
        (case / "inputs/fake_tool.py").unlink()
        result = run(config, case / "out")
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("INPUT_MISSING:fake_tool.py", result["failure"])
        self.assertTrue((case / "out/receipt.json").is_file())

    def test_stale_capture_cannot_be_an_input(self):
        case = self.case("stale_capture")
        config = fixture(case)
        value = load_json(config)
        stale = case / "inputs/tb_t052_polyphony.capture"
        stale.write_bytes(b"old")
        value["inputs"].append({"path": stale.name, "role": "SUPPORT", **identity(stale)})
        config.unlink()
        write_json(config, value)
        result = run(config, case / "out")
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("STALE_CRITICAL_INPUT", result["failure"])

    def test_timeout_preserves_partial_and_stops_owned_child(self):
        case = self.case("timeout_tree")
        result = run(fixture(case, "timeout_tree", 0.35), case / "out")
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("STEP_TIMEOUT_OR_LAUNCH", result["failure"])
        step = load_json(case / "out/simulate.receipt.json")
        self.assertTrue(step["timed_out"])
        self.assertIn(b"partial parent=", (case / "out/simulate.stdout.bin").read_bytes())
        self.assertIn("partial.capture", result["visible_artifacts"])
        subprocess.run([sys.executable, "-I", "-S", "-B", "-c",
                        "import time;time.sleep(1.8)"], cwd=case / "out/work",
                       timeout=3, check=True)
        self.assertFalse((case / "out/work/orphan.txt").exists())

    def test_output_overwrite_and_v5_caps_are_rejected(self):
        case = self.case("overwrite_caps")
        config = fixture(case)
        existing = case / "existing"
        existing.mkdir()
        with self.assertRaisesRegex(ValueError, "OUTPUT_EXISTS_REFUSE_OVERWRITE"):
            run(config, existing)
        value = load_json(config)
        value["steps"][0]["timeout_seconds"] = 301
        config.unlink()
        write_json(config, value)
        result = run(config, case / "out")
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("STEP_LIMIT_EXCEEDS_V5:compile", result["failure"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    EVIDENCE = args.evidence_dir.resolve()
    if EVIDENCE.exists():
        raise ValueError("EVIDENCE_OUTPUT_EXISTS")
    EVIDENCE.mkdir(parents=True)
    unittest.main(argv=[sys.argv[0], *remaining])
