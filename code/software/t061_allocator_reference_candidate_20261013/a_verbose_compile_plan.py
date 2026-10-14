"""Prepare one reviewed verbose compile-only successor without running HDL tools.

The successor reuses the exact frozen N4 source bytes and the same Icarus
executable from a prior plan.  Its only compiler-argv delta is one ``-v``
token, used to expose the internal Icarus stage commands in captured logs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import socket
import types


SCHEMA = "T061_N32_A_VERBOSE_COMPILE_PLAN_V1"
CONFIG_SCHEMA = "T061_N32_A_VERBOSE_COMPILE_CONFIG_V1"
WORKER = (
    "code/software/t061_allocator_reference_candidate_20261013/"
    "a_verbose_compile_diagnostic.py"
)
LAUNCHER = (
    "code/software/t061_allocator_reference_candidate_20261013/"
    "a_verbose_launch.py"
)
BASE_WORKER = (
    "code/software/t061_allocator_reference_candidate_20261013/"
    "a_compile_diagnostic.py"
)
RUNNER = "code/software/t052_runner_acceptance_candidate_20261012/runner.py"
RUNNER_TAIL = (
    "code/software/t052_runner_acceptance_candidate_20261012/"
    "runner_tail_20261013.py"
)
WINDOWS_JOB = (
    "code/software/t052_runner_acceptance_candidate_20261012/windows_job.py"
)
SUPERVISOR = (
    "code/software/t052_runner_acceptance_candidate_20261012/"
    "supervisor_20261013.py"
)
OLD_ALLOCATOR = (
    "code/rtl/common/polyphony_scaling_candidate/b2c_voice_allocator.sv"
)
N4_CANDIDATE = "cases/N4_none/candidate.sv"
N4_TB = "cases/N4_none/tb.sv"
COPIED_MEMBERS = (BASE_WORKER, RUNNER, RUNNER_TAIL, WINDOWS_JOB, SUPERVISOR,
                  OLD_ALLOCATOR, N4_CANDIDATE, N4_TB)
NEW_MEMBERS = (WORKER, LAUNCHER)


def identity_bytes(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def identity(path):
    return identity_bytes(Path(path).read_bytes())


def require(condition, diagnostic):
    if not condition:
        raise ValueError(diagnostic)


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def insert_verbose(base_argv):
    """Return the one-token argv successor and reject ambiguous inputs."""
    require(isinstance(base_argv, list) and len(base_argv) >= 4,
            "BASE_ARGV_INVALID")
    require(all(isinstance(item, str) for item in base_argv),
            "BASE_ARGV_TYPE")
    require("-v" not in base_argv and "-V" not in base_argv,
            "BASE_ALREADY_VERBOSE")
    return [base_argv[0], "-v", *base_argv[1:]]


def _copy_bound(base_plan, relative, capsule):
    base_capsule = Path(base_plan["capsule_root"]).resolve()
    source = (base_capsule / relative).resolve()
    require(source.is_relative_to(base_capsule) and source.is_file(),
            "BASE_MEMBER_MISSING:" + relative)
    expected = base_plan["capsule_files"].get(relative)
    require(expected is not None, "BASE_MEMBER_UNBOUND:" + relative)
    raw = source.read_bytes()
    observed = identity_bytes(raw)
    require(observed == {key: expected[key] for key in ("bytes", "sha256")},
            "BASE_MEMBER_DRIFT:" + relative)
    target = capsule / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(raw)
    return {**observed, "source_provenance": str(source)}


def build(base_plan_path, expected_base_sha, prepared, execution_output,
          repo=None):
    """Create a new plan/config and capsule, but never start a tool process."""
    base_plan_path = Path(base_plan_path).resolve()
    prepared = Path(prepared).resolve()
    execution_output = Path(execution_output).resolve()
    repo = Path(repo).resolve() if repo else Path(__file__).resolve().parents[3]
    require(not prepared.exists(), "PREPARED_EXISTS")
    require(not execution_output.exists(), "EXECUTION_OUTPUT_EXISTS")
    require(prepared.is_relative_to(repo / "code/output"), "PREPARED_SCOPE")
    require(execution_output.is_relative_to(repo / "code/output"),
            "EXECUTION_SCOPE")

    raw = base_plan_path.read_bytes()
    base_identity = identity_bytes(raw)
    require(base_identity["sha256"] == expected_base_sha, "BASE_PLAN_SHA")
    base_plan = json.loads(raw)
    require(base_plan["hostname"] == socket.gethostname(), "BASE_MACHINE")
    require(len(base_plan["steps"]) >= 1, "BASE_STEP_MISSING")
    base_step = base_plan["steps"][0]
    require(base_step["kind"] == "compile", "BASE_NOT_COMPILE")
    require(base_step["argv"][0] == base_plan["tools"]["compile"],
            "BASE_TOOL_MISMATCH")
    base_sources = [OLD_ALLOCATOR, N4_CANDIDATE, N4_TB]
    base_expected_sources = [
        str((Path(base_plan["capsule_root"]) / item).resolve())
        for item in base_sources
    ]
    require(base_step["argv"][-3:] == base_expected_sources,
            "BASE_N4_SOURCE_ORDER")

    capsule = prepared / "capsule"
    capsule.mkdir(parents=True)
    capsule_files = {
        relative: _copy_bound(base_plan, relative, capsule)
        for relative in COPIED_MEMBERS
    }
    for relative in NEW_MEMBERS:
        source = repo / relative
        require(source.is_file(), "NEW_MEMBER_MISSING:" + relative)
        target = capsule / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        capsule_files[relative] = {
            **identity(target), "source_provenance": str(source)
        }

    replacement_sources = [str((capsule / item).resolve())
                           for item in base_sources]
    non_verbose_argv = [*base_step["argv"][:-3], *replacement_sources]
    verbose_argv = insert_verbose(non_verbose_argv)
    require(verbose_argv[0] == base_step["argv"][0], "TOOL_CHANGED")
    require(verbose_argv[2:] == non_verbose_argv[1:], "NON_VERBOSE_DELTA")
    step = {
        "label": "N4_verbose_compile_only",
        "kind": "compile",
        "argv": verbose_argv,
        "cwd": str(execution_output / "work"),
        "timeout_seconds": 90,
        "calls": 1,
        "expected_exit": 0,
        "marker": None,
    }
    plan = {
        "schema": SCHEMA,
        "hostname": base_plan["hostname"],
        "repo": str(repo),
        "prepared": str(prepared),
        "execution_output": str(execution_output),
        "capsule_root": str(capsule),
        "capsule_files": capsule_files,
        "worker": WORKER,
        "launcher": LAUNCHER,
        "base_worker": BASE_WORKER,
        "runner_tail": RUNNER_TAIL,
        "base_plan": {**base_identity, "path": str(base_plan_path)},
        "base_step_argv": base_step["argv"],
        "non_verbose_argv": non_verbose_argv,
        "delta": {"added_tokens": ["-v"], "removed_tokens": []},
        "N4_sources": {
            item: {key: capsule_files[item][key]
                   for key in ("bytes", "sha256")}
            for item in base_sources
        },
        "total_seconds": 300,
        "tool_step_max_seconds": 90,
        "automatic_retries": 0,
        "simulate_calls": 0,
        "EDA_calls": 0,
        "tools": {
            "python": base_plan["tools"]["python"],
            "compile": base_plan["tools"]["compile"],
        },
        "tool_files": base_plan["tool_files"],
        "environment": base_plan["environment"],
        "steps": [step],
        "purpose": (
            "One new compile-only diagnostic after two 0xC0000005 exits; "
            "capture Icarus internal stage commands with -v only"
        ),
        "prohibitions": [
            "NO_VVP", "NO_LOWER", "NO_GOWIN_EDA", "NO_RETRY",
            "NO_TOOL_REPLACEMENT", "NO_TIMEOUT_INCREASE",
        ],
    }
    plan_path = prepared / "plan.json"
    write_json(plan_path, plan)
    plan_identity = identity(plan_path)
    config = {
        "schema": CONFIG_SCHEMA,
        "hostname": plan["hostname"],
        "plan_path": str(plan_path),
        "plan": plan_identity,
        "worker": identity(capsule / WORKER),
        "execution_output": str(execution_output),
        "step": step,
        "environment": plan["environment"],
        "total_seconds": 300,
        "step_seconds": 90,
        "calls": 1,
        "automatic_retries": 0,
        "simulate_calls": 0,
        "EDA_calls": 0,
    }
    config_path = prepared / "verbose_compile_config.json"
    write_json(config_path, config)
    launcher_path = capsule / LAUNCHER
    launcher_raw = launcher_path.read_bytes()
    require(identity_bytes(launcher_raw)
            == {key: capsule_files[LAUNCHER][key]
                for key in ("bytes", "sha256")}, "LAUNCHER_COPY_SHA")
    launcher = types.ModuleType("t061_n32_a_verbose_launch_prepare")
    launcher.__file__ = str(launcher_path)
    exec(compile(launcher_raw, str(launcher_path), "exec"), launcher.__dict__)
    launch_path = prepared / "verbose_launch.json"
    command_path = prepared / "launch_command.json"
    launch_result = launcher.prepare(plan_path, config_path, launch_path,
                                     command_path)
    return {
        "status": "PREPARED_VERBOSE_COMPILE_ONLY_NOT_RUN",
        "plan": plan_identity,
        "config": identity(config_path),
        "launch": launch_result["manifest"],
        "launch_command": launch_result["command"],
        "prepared": str(prepared),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-plan", type=Path, required=True)
    parser.add_argument("--base-plan-sha", required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--execution-output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.base_plan, args.base_plan_sha, args.prepared,
                           args.execution_output), sort_keys=True))
