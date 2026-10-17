"""Bounded B1 metadata-gate CLI tests, separate original streams and identities."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import time

from check_observation_binding import DOC, ROOT, HERE, strict_json
from metadata_cases import prepare, save

HELPERS = ROOT / "code/software/m3_r05_functional_integration_20261015"
sys.path.insert(0, str(HELPERS))
from supervised_process import invoke  # noqa: E402


def identity(path):
    p = Path(path).resolve()
    raw = p.read_bytes()
    return {"path": str(p), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def runtime_files():
    home = Path(sys.executable).parent
    result = [Path(sys.executable)]
    result += list(home.glob("python*.dll")) + list(home.glob("vcruntime*.dll"))
    result += [home / "DLLs/_ctypes.pyd", home / "DLLs/_hashlib.pyd"]
    result += [home / ("Lib/" + name) for name in
               ("subprocess.py", "pathlib.py", "hashlib.py", "json/__init__.py", "json/decoder.py", "json/encoder.py")]
    return sorted(set(p for p in result if p.is_file()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, choices=(1, 2, 3, 4), required=True)
    args = ap.parse_args()
    assert len(list(DOC.glob("B1_ROUND_*_CONSUMED.json"))) < 4, "OWN_4_ROUND_LIMIT"
    previous = sorted(DOC.glob("B1_ROUND_*/RUN_RECEIPT.json"))
    assert not any(strict_json(p.read_bytes()).get("status") == "PASS_METADATA_GATE_ONLY_REAL_PRO_PENDING" for p in previous), "SUCCESS_STOP"
    if args.round > 1:
        assert previous and (DOC / f"REPAIR_{args.round:02d}.md").is_file(), "CONCRETE_REPAIR_REQUIRED"
    out = DOC / f"B1_ROUND_{args.round:02d}"
    out.mkdir(exist_ok=False)
    logs = out / "logs"
    logs.mkdir()
    start = time.monotonic()
    deadline = start + 85
    source = sorted(list(HERE.glob("*.py")) + [DOC / "OBSERVATION_CONTRACT.json", DOC / "START.md", DOC / "INPUT_IDENTITIES.json"] +
                    [HELPERS / name for name in ("common.py", "supervised_process.py", "windows_job.py")])
    inputs = strict_json((DOC / "INPUT_IDENTITIES.json").read_bytes())
    for entry in inputs["files"]:
        assert identity(entry["original"]["path"]) == entry["original"], "REFERENCED_INPUT_DRIFT"
    referenced_before = [identity(e["original"]["path"]) for e in inputs["files"]]
    before = [identity(p) for p in source]
    tools_before = [identity(p) for p in runtime_files()]
    snap = out / "source"
    snap.mkdir()
    snapshots = []
    for p, entry in zip(source, before):
        dst = snap / (entry["sha256"][:16] + "_" + p.name)
        shutil.copyfile(p, dst)
        assert identity(dst)["sha256"] == entry["sha256"]
        snapshots.append({"original": entry, "snapshot": identity(dst)})
    cases = prepare(out, strict_json((DOC / "OBSERVATION_CONTRACT.json").read_bytes()))
    save(out / "CASE_PLAN.json", {"scope": "METADATA_ONLY_NO_REAL_DUT_NO_CALENDAR",
        "cases": cases, "all_refusals_predeclared_before_first_process": True})
    fixture_before = [identity(p) for p in sorted((out / "inputs").rglob("*")) if p.is_file()]
    receipt = {"status": "PREPARING", "round": args.round, "started_utc": datetime.now(timezone.utc).isoformat(),
        "machine": platform.node(), "python_version": sys.version,
        "source_before": before, "tool_before": tools_before, "input_before": fixture_before,
        "referenced_input_before": referenced_before,
        "source_snapshots": snapshots, "calls": [], "cases": [], "consumed": False,
        "own_limit": 4, "B1_shared_limit": 6, "night5_reserved": 2, "group_limit_s": 90,
        "pro_dut_pass": False, "board_release_allowed": False,
        "ModelSim_Gowin_Icarus_hardware_calls": 0}
    save(out / "BEFORE.json", receipt)
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    code = 1

    def consumed(pid):
        if not receipt["consumed"]:
            save(DOC / f"B1_ROUND_{args.round:02d}_CONSUMED.json", {"pid": pid, "round": args.round,
                 "started_utc": datetime.now(timezone.utc).isoformat(), "own_limit": 4,
                 "shared_B1_limit": 6, "night5_reserved": 2, "restores_old_rounds": False})
            receipt["consumed"] = True

    def call(name, argv, expected, functional=True):
        began = datetime.now(timezone.utc).isoformat()
        save(out / (name + ".launch.json"), {"argv": list(map(str, argv)), "cwd": str(ROOT),
             "started_utc": began, "expected_exit": expected, "bounded_by_group_90s": True})
        result = invoke(argv, ROOT, logs, name, deadline, step_budget=85, environment=env,
                        on_created=consumed if functional else None)
        result.update(name=name, started_utc=began, ended_utc=datetime.now(timezone.utc).isoformat(), expected_exit=expected)
        receipt["calls"].append(result)
        save(out / (name + ".receipt.json"), result)
        assert not result["timeout"] and not result["error"] and not result["log_limit_exceeded"], "TOOL_FAILURE:" + name
        assert result["exit_code"] == expected, "UNEXPECTED_EXIT:" + name
        return result

    try:
        call("python_version", [sys.executable, "--version"], 0, False)
        for index, case in enumerate(cases):
            name = f"case_{index:02d}"
            report = out / (name + ".json")
            argv = [sys.executable, "-B", "-X", "utf8", str(HERE / "check_observation_binding.py"),
                    "--artifact-root", str(out / "inputs"), "--output", str(report)]
            if case["binding"]:
                argv += ["--binding", case["binding"]]
            if case["expected_sha256"]:
                argv += ["--expected-binding-sha256", case["expected_sha256"]]
            if case.get("contract"):
                argv += ["--contract", case["contract"]]
            command = call(name, argv, case["expected_exit"])
            result = strict_json(report.read_bytes())
            assert result["pro_dut_pass"] is False and result["board_release_allowed"] is False, "CLAIM_DRIFT"
            if case["expected_code"] is None:
                assert result["status"] == "METADATA_STRUCTURE_READY_PROVENANCE_AND_CALENDAR_PENDING", "SELFTEST_SCOPE"
                assert result["authority_verified"] is False and result["real_trace_calendar_checked"] is False, "SELFTEST_AUTHORITY"
            else:
                assert result["code"] == case["expected_code"], "REFUSAL_CODE:" + case["name"]
                assert result["first_difference"] == case["expected_first_difference"], "FIRST_DIFFERENCE:" + case["name"]
            receipt["cases"].append({"name": case["name"], "result": identity(report), "expected_exit": case["expected_exit"],
                "actual_exit": command["exit_code"], "code": result.get("code"), "first_difference": result.get("first_difference")})
        receipt["status"] = "PASS_METADATA_GATE_ONLY_REAL_PRO_PENDING"
        code = 0
    except Exception as error:
        receipt.update(status="FAILED_ORIGINALS_PRESERVED", first_failure=repr(error))
    receipt["source_after"] = [identity(p) for p in source]
    receipt["tool_after"] = [identity(p) for p in runtime_files()]
    receipt["input_after"] = [identity(p) for p in sorted((out / "inputs").rglob("*")) if p.is_file()]
    receipt["referenced_input_after"] = [identity(e["original"]["path"]) for e in inputs["files"]]
    if receipt["source_before"] != receipt["source_after"] or receipt["tool_before"] != receipt["tool_after"] or receipt["input_before"] != receipt["input_after"] or receipt["referenced_input_before"] != receipt["referenced_input_after"]:
        receipt.update(status="IDENTITY_DRIFT", preceding_failure=receipt.get("first_failure"))
        code = 1
    receipt.update(ended_utc=datetime.now(timezone.utc).isoformat(), elapsed_s=time.monotonic() - start, exit_code=code)
    save(out / "RUN_RECEIPT.json", receipt)
    print(json.dumps({"status": receipt["status"], "cases": len(receipt["cases"]),
                      "error": receipt.get("first_failure"), "seconds": receipt["elapsed_s"],
                      "receipt": identity(out / "RUN_RECEIPT.json")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
