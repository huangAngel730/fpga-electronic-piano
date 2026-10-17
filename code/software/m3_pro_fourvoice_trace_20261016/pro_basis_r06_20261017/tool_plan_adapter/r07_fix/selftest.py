"""One targeted R6-4 repair group. Never invokes the original seven-case suite."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

import consumer as c


def check(ok, message):
    if not ok:
        raise AssertionError(message)


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, indent=2)
        f.write("\n")


def rel(path):
    return path.relative_to(c.ROOT).as_posix()


def test_mutation(plan, mutation):
    if mutation == "argv_arguments":
        plan["argv"][1:] = ["-c", "print('MUST_NOT_RUN')"]
    elif mutation == "argv_worker":
        plan["argv"][4] = str(c.HERE / "selftest.py")
    elif mutation == "argv_python":
        plan["argv"][0] = str(Path(sys.executable).with_name("pythonw.exe"))
    elif mutation == "cwd":
        plan["cwd"] = str(c.ROOT)
    elif mutation == "output_dir":
        plan["output_dir"] = str(c.DOC / "RUN_01/redirected_output")
    elif mutation == "consumption_marker":
        plan["consumption_marker"] = str(c.DOC / "RUN_01/redirected_marker.json")
    elif mutation == "timeout_seconds":
        plan["timeout_seconds"] = 59
    elif mutation == "inputs":
        plan["inputs"] = plan["inputs"][:-1]
    elif mutation == "helper_identity":
        next(i for i in plan["inputs"] if i["role"] == "dependencies")["sha256"] = "0" * 64
    elif mutation == "spec_identity":
        plan["spec"]["sha256"] = "0" * 64
    elif mutation == "runtime_identity":
        plan["fixture_runtime"]["python_dll"]["sha256"] = "0" * 64
    elif mutation == "unknown_field":
        plan["extra_permission"] = True
    else:
        values = {"mode": "REAL_TOOL_REQUEST", "approved": True, "status": "APPROVED",
                  "fixture_authority": "CALLER_AUTHORIZED", "tool_kind": "CALLER_TOOL",
                  "real_tool_launch_route_present": True, "fixed_cwd": False}
        plan[mutation] = values[mutation]


def main():
    run = c.DOC / "RUN_01"
    products = run / "products"
    products.mkdir(exist_ok=False)
    cases = c.parse((c.DOC / "CASE_SPEC.json").read_bytes())["plan_mutations"]
    template = c.parse((c.DOC / "BASE_SPEC.json").read_bytes())
    records = []

    def bound(name):
        spec_path, plan_path = products / (name + ".spec.json"), products / (name + ".plan.json")
        spec = copy.deepcopy(template)
        spec["output_dir"] = rel(products / (name + ".output"))
        spec["consumption_marker"] = rel(products / (name + ".consumed.json"))
        save(spec_path, spec)
        sh = c.identity(spec_path)["sha256"]
        plan = c.rebuild(rel(spec_path), sh)
        return spec_path, plan_path, sh, plan

    def record(name, result):
        records.append({"name": name, **result})
        save(products / (name + ".result.json"), records[-1])

    # New control proves full rebuilding + immediate guard actually reached the
    # fixed worker. It is not a replay of the old seven scenarios.
    sp, pp, sh, plan = bound("rebuilt_consumer_control")
    save(pp, plan)
    binding = (rel(pp), c.identity(pp)["sha256"], rel(sp), sh)
    result = c.run_fixture(*binding)
    validation = result["consumer_fix"]["pre_spawn_validation"]
    check(result["result"] == "PASS_SOFTWARE_FIXTURE_ONLY" and
          result["consumer_fix"]["actual_fixture_launches"] == 1 and
          set(validation["compared_fields"]) == set(plan) and
          validation["pinned_spec_sha256"] == sh, "REBUILD_AND_IMMEDIATE_GUARD_CONTROL")
    record("rebuilt_consumer_control", {"expected": "FIXED_WORKER_WITH_NEW_GUARD", "actual": "PASS", "fixture_launches": 1})

    for mutation in cases:
        sp, pp, sh, plan = bound("forged_" + mutation)
        test_mutation(plan, mutation)
        save(pp, plan)
        binding = (rel(pp), c.identity(pp)["sha256"], rel(sp), sh)
        outcomes = []
        for function in (c.audit, c.run_fixture):
            try:
                function(*binding)
            except c.Refusal as error:
                check(str(error).startswith(("PLAN_FIELD_MISMATCH:", "PLAN_FIELDS_MISMATCH")), "FORGED_PLAN_REJECTION_REASON")
                outcomes.append(str(error))
            else:
                raise AssertionError("FORGED_REHASHED_PLAN_ACCEPTED:" + mutation)
        spec = c.parse(sp.read_bytes())
        check(not (c.ROOT / spec["output_dir"]).exists() and
              not (c.ROOT / spec["consumption_marker"]).exists(), "FORGED_PLAN_NO_SIDE_EFFECTS")
        record("forged_" + mutation, {"expected": "REJECT_BOTH_AUDIT_AND_CONSUME", "actual": outcomes,
                                     "recomputed_plan_sha256": binding[1], "fixture_launches": 0})

    # Spec altered as well: rewriting the plan's own identity must not replace
    # the independently frozen spec digest passed to the consumer.
    sp, pp, sh, plan = bound("spec_and_plan_rehashed")
    (products / "spec_and_plan_rehashed.original_spec.json").write_bytes(sp.read_bytes())
    changed = c.parse(sp.read_bytes())
    changed["timeout_seconds"] = 6
    sp.write_text(json.dumps(changed) + "\n", encoding="utf-8", newline="\n")
    plan["spec"] = c.identity(sp)
    plan["timeout_seconds"] = 6
    save(pp, plan)
    try:
        c.run_fixture(rel(pp), c.identity(pp)["sha256"], rel(sp), sh)
    except c.Refusal as error:
        check(str(error) == "PINNED_SPEC_SHA_MISMATCH", "INDEPENDENT_SPEC_PIN")
    else:
        raise AssertionError("REHASHED_SPEC_ACCEPTED")
    record("spec_and_plan_rehashed", {"actual": "PINNED_SPEC_SHA_MISMATCH", "fixture_launches": 0})

    # Isolate final guard arguments without launching a worker/Job.
    for field in ("argv", "cwd", "shell"):
        sp, pp, sh, plan = bound("spawn_argument_" + field)
        save(pp, plan)
        guard = c.SpawnGuard((rel(pp), c.identity(pp)["sha256"], rel(sp), sh))
        argv = list(plan["argv"])
        kwargs = {"cwd": plan["cwd"], "stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE,
                  "stderr": subprocess.PIPE, "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | 4}
        expected = {"argv": "SPAWN_ARGV_MISMATCH", "cwd": "SPAWN_ARGUMENT_BINDING", "shell": "SPAWN_ARGUMENT_FIELDS"}[field]
        if field == "argv":
            argv[-1] = "error"
        elif field == "cwd":
            kwargs["cwd"] = str(c.ROOT)
        else:
            kwargs["shell"] = True
        try:
            guard.Popen(argv, **kwargs)
        except c.Refusal as error:
            check(str(error) == expected, "SPAWN_ARGUMENT_REJECTION")
        else:
            raise AssertionError("SPAWN_ARGUMENT_CHANGED_ACCEPTED")
        check(guard.processes == 0, "SPAWN_ARGUMENT_NO_PROCESS")
        record("spawn_argument_" + field, {"actual": expected, "fixture_launches": 0})

    # Alter the plan after the initial consume audit, precisely when legacy
    # would load its Job. Dummy close-only object never creates a Job/process.
    sp, pp, sh, plan = bound("late_plan_tamper")
    save(pp, plan)
    original_plan = products / "late_plan_tamper.original_plan.json"
    original_plan.write_bytes(pp.read_bytes())
    first_binding_sha = c.identity(pp)["sha256"]
    original_loader = c.load_legacy
    module = original_loader()

    class CloseOnly:
        def close(self):
            pass

    def late_load_job():
        altered = copy.deepcopy(plan)
        altered["argv"][1:] = ["-c", "print('MUST_NOT_RUN')"]
        pp.write_text(json.dumps(altered) + "\n", encoding="utf-8", newline="\n")
        return CloseOnly()

    module.load_job = late_load_job
    c.load_legacy = lambda: module
    try:
        result = c.run_fixture(rel(pp), c.identity(pp)["sha256"], rel(sp), sh)
    finally:
        c.load_legacy = original_loader
    check(result["result"] == "FAIL_PARTIAL" and
          result["consumer_fix"]["actual_fixture_launches"] == 0 and
          "PLAN_SHA_MISMATCH" in result["error"], "LATE_PLAN_RECHECK")
    record("late_plan_tamper", {"actual": "PRE_SPAWN_PLAN_SHA_MISMATCH", "fixture_launches": 0,
                              "original_plan": c.identity(original_plan), "mutated_plan": c.identity(pp),
                              "first_binding_sha256": first_binding_sha,
                              "job_policy": "TEST_INJECTED_CLOSE_ONLY_NO_NEW_TREE_PROOF"})

    # Real CLI boundaries for the new required independent spec pin and
    # recomputed-SHA forged argv. No other old CLI scenarios are replayed.
    cli = []
    for name, sp, pp, sh in (("forged_argv_arguments", products / "forged_argv_arguments.spec.json", products / "forged_argv_arguments.plan.json", None),
                             ("spec_and_plan_rehashed", products / "spec_and_plan_rehashed.spec.json", products / "spec_and_plan_rehashed.plan.json", sh)):
        if name == "spec_and_plan_rehashed":
            pinned_sha = c.digest((products / "spec_and_plan_rehashed.original_spec.json").read_bytes())
        else:
            pinned_sha = c.identity(sp)["sha256"]
        argv = [sys.executable, "-I", "-S", "-B", str(c.HERE / "consumer.py"), "run-fixture",
                "--plan", rel(pp), "--sha256", c.identity(pp)["sha256"], "--spec", rel(sp), "--spec-sha256", pinned_sha]
        start_utc, started = datetime.now(timezone.utc).isoformat(), time.monotonic()
        proc = subprocess.Popen(argv, cwd=c.ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        timeout = False
        cleanup_timeout = False
        try:
            out, err = proc.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            timeout = True
            proc.kill()
            try:
                out, err = proc.communicate(timeout=3)
            except subprocess.TimeoutExpired as error:
                cleanup_timeout = True
                out, err = error.output or b"", error.stderr or b""
        item = {"argv": argv, "cwd": str(c.ROOT), "pid": proc.pid, "start_utc": start_utc,
                "end_utc": datetime.now(timezone.utc).isoformat(), "elapsed_s": time.monotonic() - started,
                "exit_code": proc.returncode, "timeout": timeout, "cleanup_timeout": cleanup_timeout}
        for label, data in (("stdout", out), ("stderr", err)):
            path = products / (name + ".CLI." + label + ".raw")
            path.write_bytes(data)
            item[label] = c.identity(path)
        save(products / (name + ".CLI.json"), item)
        check(not timeout and not cleanup_timeout and proc.returncode == 2 and not err and
              c.parse(out)["process_launches"] == 0, "CLI_REJECT_BEFORE_WORKER")
        cli.append(item)
    summary = {"status": "PASS_TARGETED_CONSUMER_REPAIR_ONLY", "new_cases": len(records),
               "new_positive_control": 1, "negative_cases": len(records) - 1,
               "cli_rejections_exit2": len(cli), "fixed_worker_launches": 1,
               "old_seven_cases_replayed": 0, "real_tool_launches": 0,
               "HDL_EDA_hardware": 0, "tree_timeout_overflow_qualification": "NOT_EXTENDED",
               "board_release_allowed": False}
    save(products / "SUMMARY.json", summary)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
