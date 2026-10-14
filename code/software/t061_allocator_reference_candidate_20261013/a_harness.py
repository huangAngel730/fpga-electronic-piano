"""Prepare and run only the reviewed, bounded N32-A allocator comparison."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from reference import (Allocator, ContractError, Edge, compare_records, exact_keys,
                       integer, read_jsonl, validate_snapshot)
from vectors import build_vectors, jsonl_bytes, vector_fingerprints

HELPERS = ROOT / "code/software/t052_runner_acceptance_candidate_20261012"
sys.path.insert(0, str(HELPERS))
from runner_tail_20261013 import Budget, _run_process, finalize_receipt
from runner import identity, load_json, require, safe_member, write_json

ORIGINAL = ROOT / "code/rtl/common/polyphony_scaling_candidate/b2c_voice_allocator.sv"
CANDIDATE = ROOT / "code/rtl/common/m3_n32_allocator_candidate_20261013/m3_balanced_voice_allocator.sv"
ORIGINAL_SHA = "9fec9f838a9ef333d01d1b79ecf77d137e41bc0c5e78a40d2820c37739506061"
SCHEMA = "T061_N32_A_REVIEWED_PLAN_V1"


def under_output(path, repo=None):
    path = Path(path).resolve()
    repo = Path(ROOT if repo is None else repo).resolve()
    require(path.is_relative_to(repo / "code/output") and path != repo / "code/output",
            "OUTPUT_OUTSIDE_CODE_OUTPUT")
    return path


def tb_text(n, rows):
    """Drive before edge; observe after NBA. Hierarchy is verification-only."""
    lines = [f"""`timescale 1ns/1ps
module tb_allocator;
localparam integer N={n}, SW=$clog2(N);
reg sys_clk=0, sys_rst_n=1, note_on=0, note_off=0;
reg [3:0] source_id=0, channel_id=0;
reg [7:0] midi_note=0;
reg [N-1:0] release_done=0;
wire [SW-1:0] oa, orl, ca, crl;
wire ov, orv, cv, crv;
integer fo, fc, j;
always #5 sys_clk=~sys_clk;
b2c_voice_allocator #(.N(N)) original(sys_clk,sys_rst_n,note_on,note_off,
source_id,channel_id,midi_note,release_done,oa,ov,orl,orv);
m3_balanced_voice_allocator #(.N(N)) candidate(sys_clk,sys_rst_n,note_on,note_off,
source_id,channel_id,midi_note,release_done,ca,cv,crl,crv);
task observe(input integer idx);
begin
$fwrite(fo,"{{\\\"index\\\":%0d,\\\"outputs\\\":{{\\\"allocated_slot\\\":%0d,\\\"slot_valid\\\":%0d,\\\"release_slot\\\":%0d,\\\"release_target_valid\\\":%0d}},\\\"slots\\\":[",idx,oa,ov,orl,orv);
$fwrite(fc,"{{\\\"index\\\":%0d,\\\"outputs\\\":{{\\\"allocated_slot\\\":%0d,\\\"slot_valid\\\":%0d,\\\"release_slot\\\":%0d,\\\"release_target_valid\\\":%0d}},\\\"slots\\\":[",idx,ca,cv,crl,crv);
for(j=0;j<N;j=j+1)begin
if(j>0)begin $fwrite(fo,","); $fwrite(fc,",");end
$fwrite(fo,"%0d",original.slots[j]); $fwrite(fc,"%0d",candidate.slots[j]);
end
$fwrite(fo,"]}}\\n"); $fwrite(fc,"]}}\\n");
end endtask
initial begin
fo=$fopen("original.jsonl","w"); fc=$fopen("candidate.jsonl","w");
if(!fo || !fc)$fatal(1,"CAPTURE_OPEN");
"""]
    for row in rows:
        edge = row["input"]
        lines.append("@(negedge sys_clk);")
        if row["inject_slots"] is not None:
            lines.append("// Verification-only arbitrary old state; not natural reachability.")
            for i, value in enumerate(row["inject_slots"]):
                lines.append(f"original.slots[{i}]={18+n.bit_length()-1}'d{value}; candidate.slots[{i}]={18+n.bit_length()-1}'d{value};")
        for signal, field in (("sys_rst_n", "rst_n"), ("note_on", "note_on"),
                              ("note_off", "note_off"), ("source_id", "source"),
                              ("channel_id", "channel"), ("midi_note", "note"),
                              ("release_done", "release_done")):
            lines.append(f"{signal}={edge[field]};")
        lines.append(f"@(posedge sys_clk); #1; observe({row['index']});")
    lines.extend(["$fclose(fo);$fclose(fc);$display(\"ALLOCATOR_CAPTURE_COMPLETE\");$finish;",
                  "end\nendmodule\n"])
    return "\n".join(lines)


def mutated(raw, mutation):
    if mutation == "priority":
        old = "(occupied && identity_match) ? 2'd0 :\n                                           (!occupied) ? 2'd1 : 2'd2"
        new = "(occupied && identity_match) ? 2'd1 :\n                                           (!occupied) ? 2'd0 : 2'd2"
    elif mutation == "tie":
        old, new = "select_index[L] <= select_index[R]", "select_index[L] >= select_index[R]"
    else:
        require(mutation == "none", "MUTATION_UNKNOWN")
        return raw
    text = raw.decode("utf-8")
    require(text.count(old) == 1, "MUTATION_SITE_NOT_UNIQUE")
    return text.replace(old, new).encode("utf-8")


def case_vectors(n, mutation):
    rows = build_vectors(n)
    if mutation == "none":
        return rows
    target = {"priority": "INJECT_match_over_idle", "tie": "INJECT_lru_tie_min_slot"}[mutation]
    selected = [rows[0], next(row for row in rows if row["label"] == target)]
    model = Allocator(n)
    result = []
    for index, row in enumerate(selected):
        if row["inject_slots"] is not None:
            model.load_slots(row["inject_slots"])
        result.append({**row, "index": index,
                       "expected": model.step(Edge.from_dict(row["input"], n))})
    return result


def tool_inventory(suite):
    suite = Path(suite).resolve()
    tools = {"python": Path(sys.executable).resolve(),
             "compile": suite / "bin/iverilog.exe", "simulate": suite / "bin/vvp.exe"}
    files = set(tools.values())
    files.update((suite / "bin").glob("*.dll"))
    files.update((suite / "lib").glob("*.dll"))
    files.add(suite / "environment.bat")
    files.update(path for path in (suite / "lib/ivl").rglob("*") if path.is_file())
    python_root = tools["python"].parent
    files.update(python_root.glob("*.dll"))
    for folder in (python_root / "Lib", python_root / "DLLs"):
        files.update(path for path in folder.rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts
                     and path.suffix.lower() != ".pyc")
    require(all(path.is_file() for path in tools.values()), "TOOL_MISSING")
    return {key: str(path) for key, path in tools.items()}, {
        str(path): identity(path) for path in sorted(files)}


def tool_environment(suite):
    """Bind only the required suite loader setup; do not run environment.bat.

    The original batch also updates a graphics loader cache. That unrelated
    executable is intentionally not invoked by this isolated audio test.
    """
    suite = Path(suite).resolve()
    windows = Path(os.environ["SYSTEMROOT"]).resolve()
    return {"PATH": ";".join(map(str, (suite / "bin", suite / "lib",
                                      windows / "System32", windows))),
            "YOSYSHQ_ROOT": str(suite) + "\\"}


def validate_environment(plan):
    suite = Path(plan["suite_root"])
    require(plan["environment"] == tool_environment(suite), "TOOL_ENVIRONMENT")
    require(str(suite / "environment.bat") in plan["tool_files"], "SUITE_ENV_SOURCE_UNBOUND")
    for path in (suite / "lib").glob("*.dll"):
        require(str(path) in plan["tool_files"], "SUITE_DLL_UNBOUND:" + str(path))


def prepare(output, execution_output, suite):
    output, execution_output = under_output(output), under_output(execution_output)
    require(not output.exists() and not execution_output.exists(), "OUTPUT_EXISTS")
    require(identity(ORIGINAL)["sha256"] == ORIGINAL_SHA, "ORIGINAL_IDENTITY")
    output.mkdir(parents=True)
    capsule = output / "capsule"
    capsule.mkdir()
    inputs = {}
    for path in sorted([*HERE.glob("*.py"), HERE / "README_A.md"]):
        inputs[str(path)] = identity(path)
    for name in ("runner.py", "runner_tail_20261013.py", "windows_job.py", "supervisor_20261013.py"):
        inputs[str(HELPERS / name)] = identity(HELPERS / name)
    inputs[str(ORIGINAL)], inputs[str(CANDIDATE)] = identity(ORIGINAL), identity(CANDIDATE)
    tools, tool_files = tool_inventory(suite)
    cases, steps = [], []
    for n, mutation in [(4, "none"), (8, "none"), (16, "none"), (32, "none"),
                        (32, "priority"), (32, "tie")]:
        name = f"N{n}_{mutation}"
        case = output / name
        case.mkdir()
        rows = case_vectors(n, mutation)
        # Mutation cases retain the complete input; checker requires the exact
        # first mismatching label and independently replays original capture.
        (case / "vectors.jsonl").write_bytes(jsonl_bytes(rows))
        (case / "tb.sv").write_text(tb_text(n, rows), encoding="utf-8", newline="\n")
        (case / "candidate.sv").write_bytes(mutated(CANDIDATE.read_bytes(), mutation))
        for path in sorted(case.iterdir()):
            inputs[str(path)] = identity(path)
        work = execution_output / "work" / name
        frozen_case = capsule / "cases" / name
        argv = {
            "compile": [tools["compile"], "-B", str(Path(suite).resolve() / "lib/ivl"),
                        "-g2012", "-s", "tb_allocator", "-o", "sim.vvp",
                        str(capsule / ORIGINAL.relative_to(ROOT)),
                        str(frozen_case / "candidate.sv"), str(frozen_case / "tb.sv")],
            "simulate": [tools["simulate"], "sim.vvp"],
            "check": [tools["python"], "-I", "-S", "-B", "-X", "utf8",
                      str(capsule / (HERE / "a_harness.py").relative_to(ROOT)),
                      "check", "--n", str(n), "--vectors", str(frozen_case / "vectors.jsonl"),
                      "--original", "original.jsonl", "--capture", "candidate.jsonl",
                      "--mutation", mutation],
        }
        cases.append({"name": name, "n": n, "mutation": mutation,
                      "prepared": str(case), "capsule": str(frozen_case),
                      "work": str(work), "edges": len(rows),
                      **vector_fingerprints(rows)})
        for kind in ("compile", "simulate", "check"):
            steps.append({"label": f"{name}_{kind}", "kind": kind, "argv": argv[kind],
                          "cwd": str(work), "timeout_seconds": 300, "calls": 1,
                          "expected_exit": 1 if kind == "check" and mutation != "none" else 0,
                          "marker": (f"ALLOC_{mutation.upper()}" if mutation != "none" else '"status": "PASS"')
                          if kind == "check" else ("ALLOCATOR_CAPTURE_COMPLETE" if kind == "simulate" else None)})
    capsule_files = {}
    for path, expected in inputs.items():
        source = Path(path)
        if source.parent.parent == output:
            relative = Path("cases") / source.parent.name / source.name
        else:
            relative = source.relative_to(ROOT)
        frozen_path = capsule / relative
        frozen_path.parent.mkdir(parents=True, exist_ok=True)
        raw = source.read_bytes()
        require({"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} == expected,
                "CAPSULE_COPY_DRIFT:" + path)
        with frozen_path.open("xb") as stream:
            stream.write(raw)
        capsule_files[relative.as_posix()] = {**expected, "source_provenance": path}
    plan = {"schema": SCHEMA, "hostname": socket.gethostname(), "repo": str(ROOT),
            "prepared": str(output), "execution_output": str(execution_output),
            "capsule_root": str(capsule), "capsule_files": capsule_files,
            "bootstrap": "code/software/t061_allocator_reference_candidate_20261013/a_bootstrap.py",
            "worker": "code/software/t061_allocator_reference_candidate_20261013/a_harness.py",
            "supervisor": "code/software/t052_runner_acceptance_candidate_20261012/supervisor_20261013.py",
            "total_seconds": 900, "tool_step_max_seconds": 300,
            "tools": tools, "tool_files": tool_files, "inputs": inputs,
            "suite_root": str(Path(suite).resolve()),
            "environment": tool_environment(suite),
            "cases": cases, "steps": steps, "seed": 0x3261,
            "status": "PREPARED_NOT_EXECUTED", "review_required": True,
            "lower_calls": 0, "tool_version_calls": 0, "EDA_calls": 0,
            "original_path_resolution": "Canonical source exact frozen SHA; old prepared copy absent.",
            "dependency_scope": "Conservative Python/IVL/suite DLL inventory; system OS loader files not claimed measured.",
            "T061_complete": False}
    bootstrap_code = (
        "import hashlib,pathlib,sys;"
        "p=pathlib.Path(sys.argv[1]);raw=p.read_bytes();"
        "assert hashlib.sha256(raw).hexdigest()==sys.argv[2],'TRUSTED_BOOTSTRAP_SHA';"
        "sys.argv=[str(p),'--plan',sys.argv[3],'--plan-sha',sys.argv[4]]+sys.argv[5:];"
        "exec(compile(raw,str(p),'exec'),{'__name__':'__main__','__file__':str(p)})"
    )
    plan["launch"] = {
        "argv_prefix": [tools["python"], "-I", "-S", "-B", "-X", "utf8", "-c", bootstrap_code,
                        str(capsule / plan["bootstrap"]), capsule_files[plan["bootstrap"]]["sha256"],
                        str(output / "plan.json")],
        "append_reviewed_plan_sha": True, "cwd": str(capsule), "calls": 1,
        "outer_supervisor_max_seconds": 900,
        "budget_contract": "Bootstrap monotonic start is carried into same-process worker total 900; outer observation is a watchdog, not an extra tool budget.",
    }
    launcher = "code/software/t061_allocator_reference_candidate_20261013/a_launch.py"
    launch_code = (
        "from pathlib import Path;import hashlib,sys;"
        "p=Path(sys.argv.pop(1));expected=sys.argv.pop(1);raw=p.read_bytes();"
        "assert hashlib.sha256(raw).hexdigest()==expected,'LAUNCHER_SHA';"
        "sys.argv[0]=str(p);exec(compile(raw,str(p),'exec'),"
        "{'__name__':'__main__','__file__':str(p)})"
    )
    plan["parent_launch"] = {
        "argv_prefix": [tools["python"], "-I", "-S", "-B", "-X", "utf8", "-c", launch_code,
                        str(capsule / launcher), capsule_files[launcher]["sha256"],
                        "--plan", str(output / "plan.json"),
                        "--bootstrap-sha", capsule_files[plan["bootstrap"]]["sha256"],
                        "--parent-output", str(execution_output) + "_parent", "--plan-sha"],
        "append_exact_reviewed_plan_sha": True,
        "budget_contract": "Parent budget begins at launcher entry, before validation/imports, and covers child plus collection and completion; no extra work budget.",
    }
    write_json(output / "plan.json", plan)
    return plan


def verify(plan_path):
    plan_path = Path(plan_path).resolve()
    plan = load_json(plan_path)
    require(plan["schema"] == SCHEMA and plan["total_seconds"] == 900
            and plan["tool_step_max_seconds"] == 300, "PLAN_CONTRACT")
    require(plan["hostname"] == socket.gethostname(), "MACHINE_IDENTITY")
    validate_environment(plan)
    require(Path(plan["prepared"]).resolve() == plan_path.parent, "PREPARED_PATH")
    under_output(plan["prepared"], plan["repo"])
    under_output(plan["execution_output"], plan["repo"])
    capsule = Path(plan["capsule_root"]).resolve()
    require(capsule == plan_path.parent / "capsule", "CAPSULE_ROOT")
    require(plan["launch"]["cwd"] == str(capsule), "LAUNCH_CWD")
    actual_members = {path.relative_to(capsule).as_posix() for path in capsule.rglob("*")
                      if path.is_file()}
    require(actual_members == set(plan["capsule_files"]), "CAPSULE_MEMBERS")
    require(len(plan["steps"]) == 18 and len(plan["cases"]) == 6, "STEP_COUNT")
    for relative, expected in plan["capsule_files"].items():
        path = safe_member(capsule, relative)
        require(identity(path) == {key: expected[key] for key in ("bytes", "sha256")},
                "CAPSULE_DRIFT:" + relative)
    for path, expected in plan["tool_files"].items():
        require(identity(path) == expected, "INPUT_OR_TOOL_DRIFT:" + path)
    original_relative = "code/rtl/common/polyphony_scaling_candidate/b2c_voice_allocator.sv"
    require(plan["capsule_files"][original_relative]["sha256"] == ORIGINAL_SHA, "ORIGINAL_IDENTITY")
    for case in plan["cases"]:
        require(case["n"] in (4, 8, 16, 32), "PARAMETER_SCOPE")
        expected_cwd = Path(plan["execution_output"]) / "work" / case["name"]
        require(case["work"] == str(expected_cwd), "CASE_CWD")
        require(case["capsule"] == str(capsule / "cases" / case["name"]), "CASE_CAPSULE")
    for step in plan["steps"]:
        require(step["calls"] == 1 and step["timeout_seconds"] == 300, "STEP_CONTRACT")
        require(step["argv"][0] in plan["tools"].values(), "STEP_TOOL")
    return plan


def import_verify(plan_path):
    """Software-only entry through the actual bootstrap/import chain."""
    plan = verify(plan_path)
    capsule = Path(plan["capsule_root"])
    import importlib
    modules = {"worker": Path(__file__).resolve()}
    for name in ("reference", "vectors", "runner_tail_20261013", "runner", "windows_job"):
        modules[name] = Path(importlib.import_module(name).__file__).resolve()
    observed = {}
    for name, path in modules.items():
        require(path.is_relative_to(capsule), "IMPORT_OUTSIDE_CAPSULE:" + name)
        relative = path.relative_to(capsule).as_posix()
        require(relative in plan["capsule_files"], "IMPORT_NOT_BOUND:" + name)
        expected = plan["capsule_files"][relative]
        require(identity(path) == {key: expected[key] for key in ("bytes", "sha256")},
                "IMPORT_IDENTITY:" + name)
        observed[name] = {"path": str(path), **identity(path)}
    require(ROOT == capsule, "SOFTWARE_WORKER_NOT_FROM_CAPSULE")
    return {"status": "SOFTWARE_IMPORT_VERIFY_PASS", "imports": observed,
            "HDL_calls": 0, "actual_execution_receipt": False}


def check(n, vectors_path, original_path, capture_path, mutation):
    vectors = read_jsonl(vectors_path)
    original, capture = read_jsonl(original_path), read_jsonl(capture_path)
    original_result = compare_records(vectors, original, n)
    if mutation == "none":
        result = compare_records(vectors, capture, n)
        require(capture == original, "ORIGINAL_CANDIDATE_PAIR")
        return {**result, "original": original_result}
    # First full independent oracle rejection must occur in a declared target.
    require(len(capture) == len(vectors), "MUTATION_CAPTURE_TRUNCATED")
    for index, record in enumerate(capture):
        exact_keys(record, ("index", "outputs", "slots"), "capture")
        integer(record["index"], index, index, "capture.index")
        validate_snapshot({key: record[key] for key in ("outputs", "slots")}, n)
    try:
        compare_records(vectors, capture, n)
    except ContractError as error:
        first = next((i for i, (a, b) in enumerate(zip(original, capture)) if a != b), None)
        require(first is not None, "MUTATION_NO_DIFFERENCE")
        label = vectors[first]["label"]
        require(capture[first]["outputs"]["allocated_slot"] != original[first]["outputs"]["allocated_slot"],
                "MUTATION_WRONG_FIELD")
        # Exact labels are supplied by the independent input generator.
        allowed = {"priority": {"INJECT_match_over_idle"},
                   "tie": {"INJECT_lru_tie_min_slot"}}[mutation]
        require(label in allowed, "MUTATION_WRONG_CASE:" + label)
        return {"status": "EXPECTED_REJECTION", "diagnostic": "ALLOC_" + mutation.upper(),
                "oracle_diagnostic": str(error), "edge": first, "label": label,
                "original": original_result}
    require(False, "MUTATION_FALSE_ACCEPT")


def execute(plan_path, reviewed_plan_sha, budget_start=None):
    budget = Budget(900)
    require(budget_start is not None and 0 <= budget.elapsed() + budget.started - budget_start < 900,
            "FROZEN_BOOTSTRAP_REQUIRED")
    budget.started = budget_start
    plan_path = Path(plan_path).resolve()
    require(identity(plan_path)["sha256"] == reviewed_plan_sha, "REVIEWED_PLAN_SHA")
    plan = verify(plan_path)
    require(ROOT == Path(plan["capsule_root"]).resolve(), "WORKER_NOT_FROM_CAPSULE")
    output = under_output(plan["execution_output"], plan["repo"])
    require(not output.exists(), "ATTEMPT_ALREADY_EXISTS")
    output.mkdir(parents=True)
    write_json(output / "attempt.json", {"plan": identity(plan_path), "hostname": socket.gethostname(),
                                         "automatic_retries": 0})
    receipt = {"status": "FAIL_PARTIAL", "exit_code": 1, "failure": None,
               "plan": identity(plan_path), "steps": [], "T061_complete": False,
               "EDA_calls": 0, "automatic_retries": 0}
    try:
        frozen = {}
        for relative, expected in plan["capsule_files"].items():
            budget.remaining(300)
            path = safe_member(ROOT, relative)
            raw = Path(path).read_bytes()
            require({"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} ==
                    {key: expected[key] for key in ("bytes", "sha256")},
                    "FREEZE_DRIFT:" + relative)
            frozen[relative] = raw
        for case in plan["cases"]:
            work = Path(case["work"])
            work.mkdir(parents=True)
        for step in plan["steps"]:
            require(budget.remaining(300) == 300, "INSUFFICIENT_REMAINING_STEP_BUDGET")
            saved_environment = {key: os.environ.get(key) for key in plan["environment"]}
            try:
                os.environ.update(plan["environment"])
                result = _run_process(output, step["label"], step["argv"],
                                      Path(step["cwd"]), step["timeout_seconds"], budget)
            finally:
                for key, value in saved_environment.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
            result["environment"] = plan["environment"]
            receipt["steps"].append(result)
            require(not result["timed_out"] and result["launch_error"] is None,
                    "STEP_TIMEOUT_OR_LAUNCH:" + step["label"])
            require(result["exit_code"] == step["expected_exit"], "STEP_EXIT:" + step["label"])
            raw = (output / (step["label"] + ".stdout.bin")).read_bytes()
            require(step["marker"] is None or step["marker"].encode() in raw,
                    "STEP_DIAGNOSTIC:" + step["label"])
        receipt["artifacts"] = {}
        for path in sorted(output.rglob("*")):
            budget.remaining(300)
            if path.is_file():
                receipt["artifacts"][path.relative_to(output).as_posix()] = identity(path)
        # Bundle before the final budget check, never after a success receipt.
        with zipfile.ZipFile(output / "evidence.zip", "x", zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(output.rglob("*")):
                budget.remaining(300)
                if path.is_file() and path.name != "evidence.zip":
                    bundle.write(path, path.relative_to(output).as_posix())
            for relative, raw in frozen.items():
                budget.remaining(300)
                bundle.writestr("capsule/" + relative, raw)
            bundle.write(plan_path, "plan.json")
        receipt["bundle"] = identity(output / "evidence.zip")
        verify(plan_path)
        receipt["identities_after"] = {relative: identity(safe_member(ROOT, relative))
                                       for relative in plan["capsule_files"]}
        receipt["tool_identities_after"] = {path: identity(path) for path in plan["tool_files"]}
        receipt.update(status="ALLOCATOR_COMPARISON_AND_MUTATIONS_PASS", exit_code=0)
    except Exception as error:
        receipt["failure"] = type(error).__name__ + ":" + str(error)
    return finalize_receipt(output / "receipt.json", receipt, budget)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--execution-output", required=True, type=Path)
    p.add_argument("--suite", required=True, type=Path)
    p = sub.add_parser("verify")
    p.add_argument("--plan", required=True, type=Path)
    p = sub.add_parser("import-verify")
    p.add_argument("--plan", required=True, type=Path)
    p = sub.add_parser("execute")
    p.add_argument("--plan", required=True, type=Path)
    p.add_argument("--reviewed-plan-sha", required=True)
    p.add_argument("--budget-start", required=True, type=float)
    p = sub.add_parser("check")
    p.add_argument("--n", required=True, type=int)
    for name in ("vectors", "original", "capture"):
        p.add_argument("--" + name, required=True, type=Path)
    p.add_argument("--mutation", required=True, choices=("none", "priority", "tie"))
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare(args.output, args.execution_output, args.suite)
            print(json.dumps({"status": "PREPARED_NOT_EXECUTED"}))
        elif args.command == "verify":
            verify(args.plan)
            print(json.dumps({"status": "STATIC_VERIFY_PASS"}))
        elif args.command == "import-verify":
            print(json.dumps(import_verify(args.plan), sort_keys=True))
        elif args.command == "execute":
            result = execute(args.plan, args.reviewed_plan_sha, args.budget_start)
            print(json.dumps(result))
            return result["exit_code"]
        else:
            result = check(args.n, args.vectors, args.original, args.capture, args.mutation)
            print(json.dumps(result, sort_keys=True))
            return 0 if result["status"] == "PASS" else 1
    except Exception as error:
        print(json.dumps({"status": "FAIL", "diagnostic": type(error).__name__ + ":" + str(error)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
