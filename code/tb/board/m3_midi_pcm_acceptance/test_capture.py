"""Fail-closed tests of F evidence parsing; not additional RTL simulations."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def run_checks(capture, root, output):
    checker = load_module("f_capture_checker_test", root / "code/tb/board/m3_midi_pcm_acceptance/scoreboard.py")
    original = capture.read_text(encoding="ascii").splitlines()
    output.mkdir(exist_ok=False)
    reports = []
    variants = {"empty": [], "missing_end": original[:-1], "truncated": original[:100],
                "only_end": [original[-1]], "missing_scenario": [line for line in original if not line.endswith(" sample_edge")]}

    def altered(name, prefix, field, change):
        lines = original.copy()
        index = next(i for i, line in enumerate(lines) if line.startswith(prefix))
        fields = lines[index].split()
        fields[field] = change(fields[field])
        lines[index] = " ".join(fields)
        variants[name] = lines

    altered("wrong_pcm", "M ", 3, lambda word: f"{int(word, 16) ^ 1:06x}")
    altered("wrong_fcw", "F ", 7, lambda word: f"{int(word, 16) ^ 1:032x}")
    altered("wrong_frame", "M ", 2, lambda word: str(int(word) + 1))
    altered("unknown_value", "M ", 3, lambda word: "xxxxxx")
    altered("malformed", "M ", 0, lambda word: "UNKNOWN")
    for name, lines in variants.items():
        path = output / (name + ".capture")
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="ascii")
        try:
            checker.check_capture(path, root)
        except (AssertionError, ValueError, OSError) as error:
            reports.append({"name": name, "passed": True, "rejection": str(error)})
        else:
            raise AssertionError("capture false PASS: " + name)
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(root / "code/scripts/run_m3_midi_pcm_acceptance.py"),
             "--check-capture", str(path)], cwd=root, capture_output=True, timeout=30, check=False)
        (output / (name + ".log")).write_bytes(result.stdout + result.stderr)
        if result.returncode != 1:
            raise AssertionError("capture CLI did not return failure: " + name)
        reports[-1]["cli_exit_code"] = result.returncode
    # Missing source/ROM negatives run the actual preflight against a scratch
    # copy. They do not rename, delete or modify any production input.
    runner = load_module("f_preflight_test", root / "code/scripts/run_m3_midi_pcm_acceptance.py")
    contract_path = root / "code/docs/evidence/M3_E_F_mainline_contract_20261003.json"
    import json
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    for label, omitted in (("missing_rom", "code/model/generated/pitch_mod/sub_ratio_q16.mem"),
                           ("missing_source", "code/rtl/common/uart_rx.sv")):
        scratch = output / label
        for relative in contract["source_sha256"]:
            if relative != omitted:
                target = scratch / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / relative, target)
        runner.ROOT = scratch
        try:
            runner.validate_sources()
        except FileNotFoundError as error:
            if Path(error.filename).resolve() != (scratch / omitted).resolve():
                raise AssertionError("unrelated preflight failure: " + str(error)) from error
            reports.append({"name": label, "passed": True, "rejection": str(error)})
        else:
            raise AssertionError("missing input false PASS: " + label)
    return reports
