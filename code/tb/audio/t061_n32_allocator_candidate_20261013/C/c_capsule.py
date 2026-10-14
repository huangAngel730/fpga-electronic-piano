"""N32-C source capsule, one-attempt execution and evidence sealing.

Only isolated Icarus simulation is supported. The accepted B source capsule is
the immutable prerequisite. C gets its own plan, expected input and evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
SOURCE_ROOT = HERE.parents[4]
sys.path.insert(0, str(HERE))
from c_process import identity, run_step, write_json

C_SOFTWARE = "code/software/t061_n32_stress_plan_candidate_20261013"
C_TB = "code/tb/audio/t061_n32_allocator_candidate_20261013/C"
B_PASS = "N32_B_R1_EVENT_AUDIO_AND_MUTANTS_PASS_T061_PARTIAL"


def require(test, message):
    if not test:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def within_output(root, target):
    base = (root / "code/output").resolve()
    target = Path(target).absolute()
    require(target != base and target.is_relative_to(base), "C_OUTPUT_SCOPE")
    for component in (target, *target.parents):
        if component.exists():
            require(not component.is_symlink()
                    and not getattr(component.stat(), "st_file_attributes", 0) & 0x400,
                    "C_OUTPUT_REPARSE")
        if component == base:
            break
    return target


def prepare(args):
    root = SOURCE_ROOT
    prepared = within_output(root, args.prepared)
    output = within_output(root, args.output)
    require(not prepared.exists() and not output.exists(), "C_NEW_OUTPUT_REQUIRED")
    bplan = read_json(root / "code/output/n32b03/plan.json")
    bseal_path = root / "code/tb/audio/t061_n32_allocator_candidate_20261013/B/SEALED_RESULT_R01/seal.json"
    bseal = read_json(bseal_path)
    require(bseal["status"] == B_PASS, "C_B_PASS_REQUIRED")
    require(identity(bseal_path)["sha256"] == args.b_seal_sha, "C_B_EXTERNAL_PIN")
    bmanifest = bseal_path.parent / "MANIFEST.json"
    require(identity(bmanifest) == bseal["manifest"], "C_B_MANIFEST_IDENTITY")
    bfiles = read_json(bmanifest)["files"]
    require(identity(root/"code/output/n32b03/plan.json") == bfiles["prepared/plan.json"],
            "C_B_PLAN_SEALED_IDENTITY")
    breceipt = root / "code/output/n32br04/receipt.json"
    require(identity(breceipt) == bfiles["evidence/continuation/receipt.json"],
            "C_B_RECEIPT_SEALED_IDENTITY")
    require(read_json(breceipt)["status"] == B_PASS
            and read_json(breceipt)["base_plan"] == identity(root/"code/output/n32b03/plan.json"),
            "C_B_RECEIPT_NOT_PASS")
    before = {}
    prepared.mkdir()
    snapshot = prepared / "snapshot"
    inputs = []

    def copy_one(origin, relative, expected=None):
        origin = Path(origin).resolve()
        relative = Path(relative)
        require(not relative.is_absolute() and ".." not in relative.parts,
                "C_SNAPSHOT_MEMBER")
        target = snapshot / relative
        require(not target.exists(), "C_SNAPSHOT_COLLISION:" + str(relative))
        actual = identity(origin)
        require(expected is None or actual == expected, "C_INPUT_DRIFT:" + str(origin))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
        require(identity(target) == actual, "C_COPY_DRIFT")
        inputs.append({"origin": str(origin), "snapshot": relative.as_posix(), **actual})
        before[str(origin)] = actual

    # Every B dependency is copied from the already bound B capsule, including
    # mathematical models, ROMs, vendor model and process ownership helper.
    for row in bplan["inputs"]:
        copy_one(Path(bplan["prepared"]) / "snapshot" / row["snapshot"],
                 row["snapshot"], {k: row[k] for k in ("bytes", "sha256")})
    for relative in (C_SOFTWARE, C_TB):
        for origin in sorted((root / relative).rglob("*")):
            if args.profile == "full-v6" and any(part.startswith("SEALED_") for part in origin.parts):
                continue  # Historical archives are evidence, not FULL execution dependencies.
            if origin.is_file() and "__pycache__" not in origin.parts:
                copy_one(origin, origin.relative_to(root))
    for origin in sorted(args.assets.rglob("*")):
        if origin.is_file():
            copy_one(origin, Path("assets") / origin.relative_to(args.assets))
    asset_receipt = read_json(snapshot/"assets/asset_build_receipt.json")
    require(asset_receipt["status"] == "PASS_INDEPENDENT_EXPECTED_BEFORE_RTL"
            and asset_receipt["sources_before"] == asset_receipt["sources_after"],
            "C_EXPECTED_BUILD_NOT_BOUND")
    for origin, expected in asset_receipt["sources_before"].items():
        rel = Path(origin).relative_to(root)
        require(identity(snapshot/rel) == expected, "C_EXPECTED_GENERATOR_SNAPSHOT_DRIFT:"+str(rel))
    for name, expected in asset_receipt["artifacts"].items():
        require(identity(snapshot/"assets"/name) == expected, "C_EXPECTED_ASSET_DRIFT:"+name)
    for name, origin in (("b_seal.json", bseal_path), ("b_manifest.json", bmanifest),
                         ("b_receipt.json", breceipt)):
        copy_one(origin, Path("dependency") / name)
    compile_sources = []
    for path in bplan["steps"][0]["argv"]:
        p = Path(path)
        if p.suffix in (".sv", ".v") and str(p).startswith(str(Path(bplan["prepared"]) / "snapshot")):
            rel = p.relative_to(Path(bplan["prepared"]) / "snapshot")
            if "tb" not in rel.parts:
                compile_sources.append(str(snapshot / rel))
    include = snapshot / "code/rtl/138K_try/hold_trials_20261005/L_locations_guard065/include"
    compiler = bplan["tools"]["compile"]
    image = output / "work/sim.vvp"
    work = output / "work"
    version = "v6" if args.profile in ("suffix-v6", "full-v6") else "v4"
    require(asset_receipt.get("profile", "v4") == args.profile, "C_ASSET_PROFILE")
    checker = snapshot / C_SOFTWARE / ("check_full_v6.py" if args.profile == "full-v6"
                                       else "check_"+version+".py")
    top = "tb_c_n32_r1_"+version
    tb = snapshot / C_TB / (top+".sv")
    compile_argv = [compiler, "-B", bplan["compiler_lib"], "-g2012", "-I", str(include),
                    "-I", str(snapshot / "assets"), "-s", top, "-o", str(image),
                    *compile_sources, str(tb)]
    steps = [
        {"name": "compile", "argv": compile_argv, "cwd": str(work),
         "timeout_seconds": 300, "expected_exit": 0},
        {"name": "simulate", "argv": [bplan["tools"]["simulate"], str(image),
             "+C4_PLAN_MEM="+str(snapshot/"assets"/("c_plan_"+version+".mem"))],
         "cwd": str(work), "timeout_seconds": 86400, "expected_exit": 0},
        {"name": "check", "argv": [sys.executable, "-I", "-S", "-B", "-X", "utf8",
             str(checker), "--input", str(output / "simulate.stdout.bin"),
             "--plan", str(snapshot / "assets"/("plan_"+version+".jsonl")),
             "--expected", str(snapshot / "assets"/("expected_"+version+".jsonl")),
             "--output", str(output / "report.json")],
         "cwd": str(work), "timeout_seconds": 86400, "expected_exit": 0},
    ]
    mutation_args = list(steps[-1]["argv"])
    mutation_args[mutation_args.index("--output")+1] = str(output/"mutation_report.json")
    mutation_args.append("--mutations-only")
    steps.append({"name": "mutations", "argv": mutation_args, "cwd": str(work),
                  "timeout_seconds": 86400, "expected_exit": 0})
    plan = {"schema": "T061_N32_C_CAPSULE_V4", "review_key": args.review_key,
            "profile": args.profile,
            "hostname": socket.gethostname(), "repo": str(root),
            "prepared": str(prepared), "output": str(output), "inputs": inputs,
            "b_seal": identity(bseal_path), "b_review_key": bseal["review_key"],
            "b_snapshot": bseal["snapshot"], "tools": bplan["tools"],
            "tool_files": bplan["tool_files"], "environment": bplan["environment"],
            "steps": steps, "automatic_retries": 0, "EDA_calls": 0,
            "budget": {"compile_seconds": 300, "step_seconds": 86400,
                       "total_seconds": 345600, "stall_seconds": 300},
            "execution_authority": "USER_20261014_C_TAKEOVER_AND_EXTEND_WHILE_PROGRESSING",
            "execution_profile": "HOST_PROCESS_OWNED_JOB;CODEX_ESCALATED_LAUNCH",
            "intermediate_review": "USER_WAIVED;ROOT_AND_SUBAGENTS_SELF_REVIEW",
            "T061_complete": False}
    if args.profile == "full-v6":
        require(read_json(snapshot/"assets/asset_build_receipt.json")["profile"] == "full-v6",
                "C_FULL_ASSETS_REQUIRED")
        plan["execution_authority"] = "USER_20261014_C_FULL_CONTINUOUS_COMPLETION_SELFTEST_AND_PUBLISH"
    if args.reuse_run is not None:
        prior_output = within_output(root, args.reuse_run)
        prior_receipt_path = prior_output / "receipt.json"
        prior_receipt = read_json(prior_receipt_path)
        prior_plan_path = Path(prior_receipt["prepared_plan_path"])
        require(identity(prior_plan_path) == prior_receipt["plan"], "C_REUSE_PLAN_PIN")
        prior_plan = read_json(prior_plan_path)
        simulation = [s for s in prior_receipt["steps"] if s["name"] == "simulate"]
        require(len(simulation) == 1 and simulation[0]["exit_code"] == 0
                and not simulation[0]["timeout"] and simulation[0]["failure"] is None,
                "C_REUSE_REQUIRES_COMPLETED_SIMULATION")
        raw_capture = prior_output / "simulate.stdout.bin"
        require(identity(raw_capture) == simulation[0]["stdout"], "C_REUSE_CAPTURE_PIN")
        old_sources = {r["snapshot"]: {k: r[k] for k in ("bytes", "sha256")}
                       for r in prior_plan["inputs"]}
        if args.profile == "full-v6":
            sys.path.insert(0, str(root/C_SOFTWARE))
            from full_reuse_guard import qualify, unchanged_normal_functions
            new_sources = {r["snapshot"]: {k: r[k] for k in ("bytes", "sha256")} for r in inputs}
            proof = qualify(prior_plan, prior_receipt, read_json(prior_output/"report.json"),
                            read_json(prior_output/"mutation_report.json"), old_sources,
                            new_sources, plan["tool_files"])
            old_checker = Path(prior_plan["prepared"])/"snapshot"/C_SOFTWARE/"check_full_v6.py"
            unchanged_normal_functions(old_checker.read_bytes(), (snapshot/C_SOFTWARE/"check_full_v6.py").read_bytes())
            plan["full_reuse_qualification"] = proof
        for row in inputs:
            rel = Path(row["snapshot"])
            if rel.suffix in (".sv", ".v", ".svh", ".mem") or rel.name in (
                    "plan_v4.jsonl", "plan_v6.jsonl", "expected_v6.jsonl"):
                require(old_sources.get(row["snapshot"]) == {k: row[k] for k in ("bytes", "sha256")},
                        "C_REUSE_STIMULUS_OR_HDL_DRIFT:" + row["snapshot"])
        plan["reused_simulation"] = {"receipt_path": str(prior_receipt_path),
            "receipt": identity(prior_receipt_path), "capture_path": str(raw_capture),
            "capture": identity(raw_capture), "status": "REUSED_COMPLETED_RTL_CAPTURE_ONLY",
            "origin_profile": prior_plan.get("profile"),
            "origin_report": identity(prior_output/"report.json")}
        for check_step in steps[-2:]:
            check_step["argv"][check_step["argv"].index("--input")+1] = str(raw_capture)
        plan["steps"] = steps[-2:]
    write_json(prepared / "plan.json", plan)
    return {"status": "C_PREPARED", "plan": identity(prepared / "plan.json")}


def verify(plan, snapshot):
    require(plan["schema"] == "T061_N32_C_CAPSULE_V4", "C_SCHEMA")
    require(plan["hostname"] == socket.gethostname(), "C_MACHINE_DRIFT")
    require(plan["automatic_retries"] == 0 and plan["EDA_calls"] == 0, "C_SCOPE")
    for row in plan["inputs"]:
        expected = {k: row[k] for k in ("bytes", "sha256")}
        require(identity(snapshot / row["snapshot"]) == expected,
                "C_SNAPSHOT_DRIFT:" + row["snapshot"])
        require(identity(row["origin"]) == expected, "C_ORIGIN_DRIFT:" + row["origin"])
    for path, expected in plan["tool_files"].items():
        require(identity(path) == expected, "C_TOOL_DRIFT:" + path)
    capsule = Path(plan["tools"]["compile"]).parent.parent
    actual_dlls = {str(p.resolve()) for directory in (capsule/"bin", capsule/"lib")
                   for p in directory.glob("*.dll") if p.is_file()}
    pinned_dlls = {str(Path(p).resolve()) for p in plan["tool_files"]
                   if Path(p).suffix.lower() == ".dll"
                   and Path(p).parent in (capsule/"bin", capsule/"lib")}
    require(actual_dlls == pinned_dlls, "C_LOADER_DLL_CLOSURE_DRIFT")


def execute(args):
    require(identity(args.plan)["sha256"] == args.plan_sha, "C_PLAN_PIN")
    plan = read_json(args.plan)
    snapshot = Path(plan["prepared"]) / "snapshot"
    require(Path(__file__).resolve() == snapshot / C_TB / "c_capsule.py",
            "C_EXECUTE_FROZEN_CAPSULE_ONLY")
    require(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode,
            "C_PYTHON_ISOLATION")
    require(Path(sys.executable).resolve() == Path(plan["tools"]["python"]).resolve(),
            "C_PYTHON_TOOL_IDENTITY")
    output = within_output(Path(plan["repo"]), plan["output"])
    require(not output.exists(), "C_ATTEMPT_ALREADY_CONSUMED")
    output.mkdir()
    started = time.monotonic()
    budget = plan["budget"]["total_seconds"]

    def remaining():
        return budget - (time.monotonic()-started)

    receipt = {"schema": "T061_N32_C_RECEIPT_V4", "status": "FAIL_PARTIAL", "exit_code": 1,
        "review_key": plan["review_key"], "plan": identity(args.plan),
        "prepared_plan_path": str(args.plan.resolve()),
        "machine": {"hostname": socket.gethostname(), "os": platform.platform(),
                    "arch": platform.machine()}, "steps": [], "failure": None,
        "automatic_retries": 0, "EDA_calls": 0, "T061_complete": False}
    write_json(output / "attempt.json", {"plan": receipt["plan"], "consumed": True,
                                         "authority": plan["execution_authority"]})
    try:
        verify(plan, snapshot)
        if "reused_simulation" in plan:
            reused = plan["reused_simulation"]
            require(identity(reused["receipt_path"]) == reused["receipt"]
                    and identity(reused["capture_path"]) == reused["capture"], "C_REUSED_EVIDENCE_DRIFT")
            receipt["reused_simulation"] = reused
            if plan.get("profile") == "full-v6":
                require(plan["full_reuse_qualification"]["execution_mode"] == "RTL_REUSED_NO_NEW_SIMULATION",
                        "C_FULL_REUSE_QUALIFICATION_REQUIRED")
                receipt["full_reuse_qualification"] = plan["full_reuse_qualification"]
                receipt["execution_mode"] = "RTL_REUSED_NO_NEW_SIMULATION"
        (output / "work").mkdir()
        helpers = snapshot / "code/software/t052_runner_acceptance_candidate_20261012"
        for step in plan["steps"]:
            require(remaining() > 0, "C_TOTAL_BUDGET")
            result = run_step(step, output, plan["environment"], helpers, remaining)
            receipt["steps"].append(result)
            require(not result["timeout"] and result["failure"] is None
                    and result["exit_code"] == step["expected_exit"],
                    "C_STEP_FAILED:" + step["name"])
        report = read_json(output / "report.json")
        require(report.get("status") == "N32_C_STRESS_PASS_T061_PARTIAL", "C_CHECKER_NOT_PASS")
        if plan.get("profile") == "full-v6":
            require(report.get("single_continuous_full_C_run") is True
                    and report.get("complete_C_capture") is True
                    and report.get("capture_composition") is False, "C_FULL_REPORT_SCOPE")
        mutations = read_json(output/"mutation_report.json")
        require(mutations.get("status") == "N32_C_MUTATIONS_PASS"
                and mutations.get("rejected", 0) >= 10, "C_MUTATIONS_NOT_PASS")
        if plan.get("profile") == "full-v6":
            require(mutations.get("profile") == "FULL_C00_C09_SINGLE_CONTINUOUS_CAPTURE"
                    and mutations.get("rejected") == 24, "C_FULL_MUTATION_SCOPE")
        verify(plan, snapshot)
        receipt["inputs_after"] = {r["snapshot"]: identity(snapshot/r["snapshot"])
                                    for r in plan["inputs"]}
        receipt["tools_after"] = plan["tool_files"]
        receipt["artifacts"] = {}
        for path in sorted(output.rglob("*")):
            require(remaining() > 0, "C_BUDGET_ARTIFACT_COLLECTION")
            if path.is_file():
                receipt["artifacts"][path.relative_to(output).as_posix()] = identity(path)
        receipt.update(status="N32_C_STRESS_PASS_T061_PARTIAL", exit_code=0)
    except Exception as error:
        receipt["failure"] = type(error).__name__ + ":" + str(error)
    # A failed run retains its actual after-identities too. Evidence persistence
    # never restores PASS and is not another execution attempt.
    if "inputs_after" not in receipt:
        receipt["inputs_after"] = {}
        receipt["tools_after"] = {}
        for row in plan["inputs"]:
            try:
                receipt["inputs_after"][row["snapshot"]] = identity(snapshot/row["snapshot"])
            except OSError as error:
                receipt["inputs_after"][row["snapshot"]] = {"error": str(error)}
        for path in plan["tool_files"]:
            try:
                receipt["tools_after"][path] = identity(path)
            except OSError as error:
                receipt["tools_after"][path] = {"error": str(error)}
    receipt["elapsed_seconds"] = time.monotonic()-started
    if remaining() <= 0:
        receipt.update(status="FAIL_PARTIAL", exit_code=1, failure="C_TOTAL_BUDGET_BEFORE_RECEIPT")
    write_json(output / "receipt.json", receipt)
    if remaining() <= 0:
        receipt.update(status="FAIL_PARTIAL", exit_code=1, failure="C_TOTAL_BUDGET_AFTER_RECEIPT")
        write_json(output / "receipt.json", receipt, exclusive=False)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    p = subs.add_parser("prepare")
    p.add_argument("--prepared", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--assets", type=Path, required=True)
    p.add_argument("--b-seal-sha", required=True)
    p.add_argument("--review-key", required=True)
    p.add_argument("--reuse-run", type=Path)
    p.add_argument("--profile", choices=("v4", "suffix-v6", "full-v6"), default="v4")
    p = subs.add_parser("execute")
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--plan-sha", required=True)
    args = parser.parse_args()
    try:
        result = prepare(args) if args.command == "prepare" else execute(args)
        print(json.dumps({k: result[k] for k in ("status", "exit_code", "failure", "plan") if k in result}))
        return result.get("exit_code", 0)
    except Exception as error:
        print(json.dumps({"status": "FAIL_PARTIAL", "failure": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
