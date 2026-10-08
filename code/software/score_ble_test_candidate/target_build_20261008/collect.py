"""Capture target preparation, runner tests and repository gate; seal two handoffs.

No business source edits, installations, dependency downloads or device access.
Evidence writes are confined to new output and target_build_20261008 docs.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import zipfile

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("target_run", HERE / "run.py")
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)
DOCS = RUN.ROOT / "code/docs/hardware/score_ble_v1/target_build_20261008"


def execute(out):
    if out.exists() or not out.is_relative_to((RUN.ROOT / "code/output").resolve()) or not out.name.startswith("m3_t059_target_"):
        raise ValueError("require fresh code/output/m3_t059_target_* output")
    out.mkdir(parents=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    # Child-only Python override; never replace system Java/Python or use setx.
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    commands = RUN.Commands(out, env, 3600)
    result = {"steps": commands.steps, "status": "FAIL", "target_builds": "NOT_EXECUTED_MISSING_ENVIRONMENT"}
    try:
        for name in ("run.py", "test_run.py", "collect.py"):
            shutil.copyfile(HERE / name, out / name)
        commands.run("runner_selftest", [sys.executable, "-B", "-X", "utf8", HERE / "test_run.py"], limit=120)
        print("runner_selftest PASS (6 infrastructure tests)", flush=True)
        for stage in ("preflight", "c3", "apk"):
            stage_out = out / ("m3_t059_target_" + stage)
            try:
                commands.run(stage, [sys.executable, "-B", "-X", "utf8", HERE / "run.py", stage,
                                     "--output", stage_out, "--timeout", "120"], limit=180)
            except ValueError:
                if commands.steps[-1]["exit_code"] != 2 or commands.steps[-1]["timed_out"]:
                    raise
            receipt = json.loads((stage_out / "receipt.json").read_text(encoding="utf-8"))
            if receipt["status"] != "BLOCKED_MISSING_ENVIRONMENT" or receipt["target_build_passed"]:
                raise ValueError("this capture is only for current missing-environment preparation")
            print(stage + " BLOCKED_MISSING_ENVIRONMENT exit2; no target compilation", flush=True)
        # Capture current worktree input identity, not just Git blobs (CRLF can differ).
        names = commands.run("tracked_gate_files", ["git", "-c", "core.quotepath=false", "ls-files", "-z"]).split("\x00")
        before = {name: RUN.digest(RUN.ROOT / name) for name in names if name}
        extra = {p.relative_to(RUN.ROOT).as_posix(): RUN.digest(p) for p in HERE.glob("*.py")}
        RUN.dump(out / "gate_inputs.json", {"tracked": before, "new_runner": extra})
        print("repository_gate START (no new FPGA functionality build)", flush=True)
        commands.run("repository_gate", ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                     RUN.ROOT / "code/scripts/check_repo.ps1"], limit=1200)
        gate_text = (out / "logs/repository_gate/stdout.log").read_text(encoding="utf-8", errors="replace")
        if gate_text.count("[PASS]") != 9 or "All repository checks passed." not in gate_text:
            raise ValueError("GATE_NINE_PASS_REQUIRED")
        if any(not (RUN.ROOT / name).is_file() or RUN.digest(RUN.ROOT / name) != sha
               for name, sha in {**before, **extra}.items()):
            raise ValueError("GATE_INPUT_MUTATED")
        result.update(status="PREPARATION_CAPTURED", gate_pass_count=9, gate_inputs_unchanged=True,
                      gate_tracked_inputs=len(before), runner_tests=6)
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    finally:
        RUN.dump(out / "execution.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return int(result["status"] == "FAIL")


def seal(out):
    execution = json.loads((out / "execution.json").read_text(encoding="utf-8"))
    if execution["status"] != "PREPARATION_CAPTURED":
        raise ValueError("cannot seal failed capture as preparation success")
    for stage in ("c3", "apk"):
        doc = DOCS / stage
        if (doc / "evidence").exists():
            raise ValueError("refuse evidence overwrite")
        evidence = doc / "evidence"
        evidence.mkdir(parents=True)
        stage_out = out / ("m3_t059_target_" + stage)
        stage_receipt = json.loads((stage_out / "receipt.json").read_text(encoding="utf-8"))
        paths = [out / "execution.json", out / "gate_inputs.json", out / "run.py", out / "test_run.py", out / "collect.py"]
        paths.extend(p for p in stage_out.rglob("*") if p.is_file())
        paths.extend(p for label in (stage, "runner_selftest", "repository_gate")
                     for p in (out / "logs" / label).rglob("*") if p.is_file())
        manifest = {}
        for path in paths:
            relative = path.relative_to(out).as_posix()
            carrier = relative.replace("/", "__") + ".gz.b64"
            raw = path.read_bytes()
            encoded = base64.b64encode(gzip.compress(raw, mtime=0)) + b"\n"
            (evidence / carrier).write_bytes(encoded)
            manifest[relative] = {"bytes": len(raw), "sha256": RUN.digest(path),
                                  "carrier": carrier, "carrier_sha256": RUN.digest(evidence / carrier)}
        RUN.dump(evidence / "manifest.json", manifest)
        report = {
            "stage": stage, "status": "PREPARATION_ONLY_BLOCKED_ENVIRONMENT",
            "business_base": stage_receipt["commit"], "new_function_commit": None,
            "missing": stage_receipt["missing"][stage], "source_config_sha256": stage_receipt["source_config_sha256"],
            "configuration_check": stage_receipt["configuration_check"],
            "source_config_unchanged": stage_receipt["source_config_unchanged"],
            "target_compiler_invoked": False, "target_artifacts": [],
            "runner_selftest": "6/6; infrastructure tests only", "repository_gate": "9/9, exit0",
            "installed": False, "downloaded": False, "device_operations": False,
            "complete_t059_passed": False,
        }
        RUN.dump(doc / "RESULT.json", report)
        archive = out / ("M3_T059_" + stage.upper() + "_构建条件与实测准备_20261008.zip")
        members = [p for folder in (HERE, DOCS) for p in folder.rglob("*")
                   if p.is_file() and "__pycache__" not in p.parts
                   and not p.is_relative_to(DOCS / ("apk" if stage == "c3" else "c3"))]
        with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as package:
            hashes = {}
            for path in sorted(members):
                relative = path.relative_to(RUN.ROOT).as_posix()
                package.write(path, relative)
                hashes[relative] = RUN.digest(path)
            package.writestr("CONTENTS_SHA256.json", json.dumps(hashes, ensure_ascii=False, indent=2) + "\n")
        with zipfile.ZipFile(archive) as package:
            if package.testzip():
                raise ValueError("package CRC failure")
        print(json.dumps({"stage": stage, "package": str(archive), "bytes": archive.stat().st_size,
                          "sha256": RUN.digest(archive)}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("execute", "seal"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if args.mode == "execute":
        return execute(out)
    seal(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
