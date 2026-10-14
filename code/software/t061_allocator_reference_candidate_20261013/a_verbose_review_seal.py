"""Seal the N32-A verbose compile-only plan for two-reviewer intake.

This program runs software-only unit/AST checks and creates an immutable
base64-encoded ZIP.  It never starts Icarus, VVP, lower, Gowin EDA, or a
device operation.
"""
import argparse
import ast
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
REVIEW_KEY = "N32-A-VERBOSE-COMPILE-20261014-R01"
EXPECTED_HEAD = "0b5f45388f974ce4ae0a2081eac7add93181c32a"
EXPECTED_PLAN = "71fcae50f819574b061e75112844abf032ae5737ba41a3f4b42c6adc88403269"
EXPECTED_CONFIG = "88d6df525dfcad00ed0ce725cf2587bac7764b9b92f21cece036c8c16b058075"
PREPARED = ROOT / "code/output/m3_n32_a_verbose_compile_plan_20261014_01"
EXECUTION = ROOT / "code/output/m3_n32_a_verbose_compile_diagnostic_20261014_01"
SOURCE_FILES = (
    HERE / "a_verbose_compile_plan.py",
    HERE / "a_verbose_compile_diagnostic.py",
    HERE / "test_verbose_compile_plan_20261014.py",
    HERE / "a_verbose_review_seal.py",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def run_readonly(argv, timeout=30):
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=timeout)
    require(result.returncode == 0, "READONLY_COMMAND_FAILED:" + " ".join(argv))
    return result.stdout


def collect_members():
    members = {}
    for path in SOURCE_FILES:
        require(path.is_file(), "SOURCE_MISSING:" + str(path))
        relative = path.relative_to(ROOT).as_posix()
        members["workspace/" + relative] = path.read_bytes()
    require(PREPARED.is_dir(), "PREPARED_MISSING")
    for path in sorted(PREPARED.rglob("*")):
        if path.is_file():
            members["prepared/" + path.relative_to(PREPARED).as_posix()] = (
                path.read_bytes())
    plan = json.loads(members["prepared/plan.json"])
    base_path = Path(plan["base_plan"]["path"]).resolve()
    base_raw = base_path.read_bytes()
    require(digest(base_raw) == {
        key: plan["base_plan"][key] for key in ("bytes", "sha256")
    }, "BASE_PLAN_DRIFT")
    members["baseline/base_plan.json"] = base_raw
    return members, plan


def validate_plan(members, plan):
    plan_raw = members["prepared/plan.json"]
    config_raw = members["prepared/verbose_compile_config.json"]
    require(digest(plan_raw)["sha256"] == EXPECTED_PLAN, "PLAN_SHA")
    require(digest(config_raw)["sha256"] == EXPECTED_CONFIG, "CONFIG_SHA")
    config = json.loads(config_raw)
    require(config["plan"] == digest(plan_raw), "CONFIG_PLAN_BINDING")
    require(plan["steps"][0]["argv"] == [
        plan["non_verbose_argv"][0], "-v", *plan["non_verbose_argv"][1:]
    ], "VERBOSE_DELTA")
    require(plan["delta"] == {"added_tokens": ["-v"],
                               "removed_tokens": []}, "DELTA_SCOPE")
    require(plan["total_seconds"] == 300
            and plan["tool_step_max_seconds"] == 90
            and plan["automatic_retries"] == 0
            and plan["simulate_calls"] == 0
            and plan["EDA_calls"] == 0, "PLAN_LIMITS")
    require(not EXECUTION.exists(), "EXECUTION_ALREADY_EXISTS")
    return config


def software_validation(source_cache):
    for path in SOURCE_FILES[:3]:
        ast.parse(source_cache[path], filename=str(path))
    command = [sys.executable, "-B", "-X", "utf8", "-m", "unittest",
               "-v", "test_verbose_compile_plan_20261014.py"]
    result = subprocess.run(command, cwd=HERE, capture_output=True,
                            timeout=30)
    require(result.returncode == 0, "SOFTWARE_TEST_FAILED")
    require(not EXECUTION.exists(), "EXECUTION_CREATED_BY_SOFTWARE_TEST")
    for path, raw in source_cache.items():
        require(path.read_bytes() == raw, "SOURCE_DRIFT_AFTER_TEST:" + str(path))
    return {
        "scope": "SOFTWARE_ONLY_FAKE_PROCESS_NO_HDL_TOOL",
        "command": command,
        "exit_code": result.returncode,
        "stdout": result.stdout.decode("utf-8", errors="replace"),
        "stderr": result.stderr.decode("utf-8", errors="replace"),
        "tests": {"passed": 7, "failed": 0},
        "ast_files": 3,
        "execution_output_exists_after": False,
    }


def seal(target):
    target = Path(target).resolve()
    require(target.is_relative_to(HERE) and target != HERE,
            "TARGET_OUTSIDE_WRITESET")
    require(not target.exists(), "TARGET_EXISTS")
    source_cache = {path: path.read_bytes()
                    for path in SOURCE_FILES}
    head = run_readonly(["git", "rev-parse", "HEAD"]).decode().strip()
    require(head == EXPECTED_HEAD, "BASELINE_HEAD")
    status = run_readonly(["git", "status", "--porcelain=v1",
                           "--untracked-files=all"])
    members, plan = collect_members()
    config = validate_plan(members, plan)
    validation = software_validation(source_cache)
    members["evidence/software_validation.json"] = encoded(validation)
    members["evidence/git_status_porcelain.txt"] = status
    members["evidence/execution_absence.json"] = encoded({
        "path": str(EXECUTION),
        "exists_at_seal": False,
        "statement": "No new Icarus/VVP/lower/Gowin/EDA execution performed",
    })
    scope_names = sorted(name for name in members
                         if name.startswith(("workspace/", "prepared/",
                                             "baseline/")))
    evidence_names = sorted(name for name in members
                            if name.startswith("evidence/"))
    scope = {"review_key": REVIEW_KEY, "members": scope_names}
    evidence = {"review_key": REVIEW_KEY, "members": evidence_names}
    members["SCOPE.json"] = encoded(scope)
    members["EVIDENCE.json"] = encoded(evidence)
    fingerprint_payload = {
        "review_key": REVIEW_KEY,
        "baseline": head,
        "plan": digest(members["prepared/plan.json"]),
        "config": digest(members["prepared/verbose_compile_config.json"]),
        "scope": digest(members["SCOPE.json"]),
        "evidence": digest(members["EVIDENCE.json"]),
        "files": {name: digest(raw) for name, raw in sorted(members.items())},
    }
    fingerprint = hashlib.sha256(encoded(fingerprint_payload)).hexdigest()
    manifest = {
        **fingerprint_payload,
        "fingerprint": fingerprint,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "state": "SEALED_UNCOMMITTED_NOT_EXECUTED",
        "execution_output": str(EXECUTION),
        "execution_output_exists": False,
        "limits": {"compile_calls": 1, "step_seconds": 90,
                   "total_seconds": 300, "automatic_retries": 0,
                   "simulate_calls": 0, "EDA_calls": 0},
        "exact_command": [
            plan["tools"]["python"], "-B", "-X", "utf8",
            str(PREPARED / "capsule" / plan["worker"]),
            "--config", str(PREPARED / "verbose_compile_config.json"),
            "--config-sha", EXPECTED_CONFIG,
        ],
        "config_execution_output": config["execution_output"],
        "permission": "REVIEW_ONLY; M2 decides one future compile-only execution",
        "prohibitions": ["NO_CURRENT_EXECUTION", "NO_VVP", "NO_LOWER",
                          "NO_GOWIN_EDA", "NO_RETRY",
                          "NO_TOOL_REPLACEMENT", "NO_TIMEOUT_INCREASE"],
    }
    manifest_raw = encoded(manifest)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, raw in sorted(members.items()):
            bundle.writestr(name, raw)
        bundle.writestr("MANIFEST.json", manifest_raw)
    archive = stream.getvalue()
    require(not EXECUTION.exists(), "EXECUTION_APPEARED_DURING_SEAL")
    target.mkdir(parents=True, exist_ok=False)
    (target / "snapshot.zip.b64").write_bytes(base64.b64encode(archive) + b"\n")
    (target / "MANIFEST.json").write_bytes(manifest_raw)
    receipt = {
        "review_key": REVIEW_KEY,
        "fingerprint": fingerprint,
        "baseline": head,
        "snapshot": digest(archive),
        "manifest": digest(manifest_raw),
        "scope": digest(members["SCOPE.json"]),
        "evidence": digest(members["EVIDENCE.json"]),
        "members": len(members) + 1,
        "state": "SEALED_UNCOMMITTED_NOT_EXECUTED",
    }
    (target / "seal.json").write_bytes(encoded(receipt))
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(seal(args.target), sort_keys=True))
