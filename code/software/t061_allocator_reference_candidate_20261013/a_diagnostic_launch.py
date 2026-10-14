"""Frozen parent-owned 300-second watchdog for the one-step diagnostic."""
import argparse
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import sys
import time


def identity(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


PINNED_EXEC = (
    "from pathlib import Path;import hashlib,sys;"
    "p=Path(sys.argv.pop(1));expected=sys.argv.pop(1);raw=p.read_bytes();"
    "assert hashlib.sha256(raw).hexdigest()==expected,'FROZEN_SCRIPT_SHA';"
    "sys.argv[0]=str(p);exec(compile(raw,str(p),'exec'),"
    "{'__name__':'__main__','__file__':str(p)})"
)


def collect_parent_identity():
    return {"pid": os.getpid(), "orig_argv": list(sys.orig_argv), "argv": list(sys.argv),
            "cwd": str(Path.cwd().resolve()), "python_path": str(Path(sys.executable).resolve()),
            "python": identity(Path(sys.executable).read_bytes()),
            "flags": {key: getattr(sys.flags, key) for key in
                      ("isolated", "no_site", "no_user_site", "dont_write_bytecode", "utf8_mode")},
            "xoptions": dict(sys._xoptions)}


def validate_parent_runtime(manifest, manifest_sha, actual):
    assert Path(actual["cwd"]) == Path(manifest["cwd"]), "PARENT_ACTUAL_CWD"
    assert actual["flags"] == {key: 1 for key in
                               ("isolated", "no_site", "no_user_site", "dont_write_bytecode", "utf8_mode")}, "PARENT_FLAGS"
    assert actual["xoptions"].get("utf8") is True, "PARENT_UTF8_OPTION"
    expected = manifest["parent_argv_prefix"] + [manifest_sha]
    assert len(actual["orig_argv"]) == len(expected), "PARENT_ARGV"
    assert Path(actual["orig_argv"][0]).resolve() == Path(expected[0]).resolve(), "PARENT_ARGV_PYTHON"
    assert actual["orig_argv"][1:] == expected[1:], "PARENT_ARGV"
    python = manifest["python"]
    assert Path(actual["python_path"]) == Path(python["path"]), "PARENT_PYTHON"
    assert actual["python"] == {key: python[key] for key in ("bytes", "sha256")}, "PARENT_PYTHON_SHA"


def read_parent_helpers(manifest, helpers):
    names = ("runner.py", "runner_tail_20261013.py", "windows_job.py", "supervisor_20261013.py")
    expected_paths = {helpers / name for name in names}
    assert {p.resolve() for p in helpers.rglob("*") if p.is_file()} == expected_paths, "PARENT_HELPER_MEMBERS"
    result = {}
    for path in expected_paths:
        raw = path.read_bytes()
        assert identity(raw) == manifest["sources"][str(path)], "PARENT_HELPER_SHA"
        result[path] = raw
    return result


def load_parent_helpers(raw_helpers, helpers):
    """Load the exact verified bytes, including explicit nested file imports."""
    class RawLoader(importlib.abc.Loader):
        def __init__(self, path):
            self.path = path

        def create_module(self, spec):
            return None

        def exec_module(self, module):
            module.__file__ = str(self.path)
            exec(compile(raw_helpers[self.path], str(self.path), "exec"), module.__dict__)

    def raw_spec(name, path):
        spec = importlib.util.spec_from_loader(name, RawLoader(path), origin=str(path))
        spec.has_location = True
        return spec

    class RawFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            source = helpers / (fullname + ".py")
            return raw_spec(fullname, source) if source in raw_helpers else None

    original = importlib.util.spec_from_file_location

    def pinned_file_spec(name, location, *args, **kwargs):
        path = Path(location).resolve()
        return raw_spec(name, path) if path in raw_helpers else original(name, location, *args, **kwargs)

    finder = RawFinder()
    for path in raw_helpers:
        sys.modules.pop(path.stem, None)
    sys.meta_path.insert(0, finder)
    importlib.util.spec_from_file_location = pinned_file_spec
    try:
        spec = raw_spec("frozen_diagnostic_supervisor", helpers / "supervisor_20261013.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.meta_path.remove(finder)
        importlib.util.spec_from_file_location = original


def prepare(plan_path, config_path, destination):
    plan_path, config_path, destination = map(lambda p: Path(p).resolve(),
                                             (plan_path, config_path, destination))
    plan_raw, config_raw = plan_path.read_bytes(), config_path.read_bytes()
    plan, config = json.loads(plan_raw), json.loads(config_raw)
    assert config["plan"] == identity(plan_raw)
    capsule = Path(plan["capsule_root"])
    worker = capsule / "code/software/t061_allocator_reference_candidate_20261013/a_compile_diagnostic.py"
    launcher = capsule / "code/software/t061_allocator_reference_candidate_20261013/a_diagnostic_launch.py"
    helpers = capsule / "code/software/t052_runner_acceptance_candidate_20261012"
    paths = [worker, launcher, *(helpers / name for name in
             ("runner.py", "runner_tail_20261013.py", "windows_job.py", "supervisor_20261013.py"))]
    source_files = {str(path): identity(path.read_bytes()) for path in paths}
    source_files.update({str(plan_path): identity(plan_raw), str(config_path): identity(config_raw)})
    prefix = [plan["tools"]["python"], "-I", "-S", "-B", "-X", "utf8", "-c", PINNED_EXEC]
    manifest = {"schema": "T061_N32_A_DIAGNOSTIC_LAUNCH_V1",
                "python": {"path": plan["tools"]["python"],
                           **plan["tool_files"][plan["tools"]["python"]]},
                "capsule": str(capsule), "cwd": str(capsule),
                "plan": {"path": str(plan_path), **identity(plan_raw)},
                "config": {"path": str(config_path), **identity(config_raw)},
                "worker": {"path": str(worker), **source_files[str(worker)]},
                "launcher": {"path": str(launcher), **source_files[str(launcher)]},
                "sources": source_files,
                "worker_argv": prefix + [str(worker), source_files[str(worker)]["sha256"],
                                          "execute", "--config", str(config_path),
                                          "--config-sha", identity(config_raw)["sha256"]],
                "parent_argv_prefix": prefix + [str(launcher), source_files[str(launcher)]["sha256"],
                                                 "execute", "--manifest", str(destination), "--manifest-sha"],
                "append_reviewed_manifest_sha": True,
                "parent_output": config["execution_output"] + "_parent",
                "parent_entry": config["execution_output"] + "_parent.entry.json",
                "receipt_path": str(Path(config["execution_output"]) / "receipt.json"),
                "parent_total_seconds": 300, "worker_watchdog_seconds": 300,
                "compile_seconds": 90, "calls": 1, "automatic_retries": 0}
    with destination.open("xb") as stream:
        stream.write(encoded(manifest))
    return {"status": "FROZEN_DIAGNOSTIC_LAUNCH_NOT_RUN", "manifest": identity(encoded(manifest))}


def execute(manifest_path, expected_sha):
    started = time.monotonic()
    manifest_path = Path(manifest_path).resolve()
    raw = manifest_path.read_bytes()
    assert identity(raw)["sha256"] == expected_sha, "LAUNCH_MANIFEST_SHA"
    manifest = json.loads(raw)
    assert manifest["schema"] == "T061_N32_A_DIAGNOSTIC_LAUNCH_V1"
    assert manifest["parent_total_seconds"] == 300 and manifest["worker_watchdog_seconds"] == 300
    assert manifest["calls"] == 1 and manifest["automatic_retries"] == 0
    actual = collect_parent_identity()
    entry = {"status": "ADMISSION_REJECTED", "manifest": identity(raw), "actual_parent": actual}
    try:
        validate_parent_runtime(manifest, expected_sha, actual)
        assert Path(__file__).resolve() == Path(manifest["launcher"]["path"]), "PARENT_SOURCE_PATH"
        entry["status"] = "ADMITTED"
    except Exception as error:
        entry["failure"] = str(error)
        with Path(manifest["parent_entry"]).open("xb") as stream:
            stream.write(encoded(entry))
        raise
    capsule = Path(manifest["capsule"]).resolve()
    assert Path(manifest["cwd"]).resolve() == capsule, "PARENT_CWD"
    helpers = capsule / "code/software/t052_runner_acceptance_candidate_20261012"
    plan_raw = Path(manifest["plan"]["path"]).read_bytes()
    assert identity(plan_raw) == {key: manifest["plan"][key] for key in ("bytes", "sha256")}, "PARENT_PLAN_SHA"
    plan = json.loads(plan_raw)
    assert manifest["python"] == {"path": plan["tools"]["python"],
                                  **plan["tool_files"][plan["tools"]["python"]]}, "CHILD_PYTHON_ADMISSION"
    raw_helpers = read_parent_helpers(manifest, helpers)
    supervisor = load_parent_helpers(raw_helpers, helpers)
    original_budget = supervisor.runner.Budget
    original_identity = supervisor.runner.identity
    original_run = supervisor.runner._run_process
    python_path = Path(manifest["python"]["path"]).resolve()
    python_identity = {key: manifest["python"][key] for key in ("bytes", "sha256")}
    assert Path(manifest["worker_argv"][0]).resolve() == python_path, "CHILD_PYTHON_PATH"

    def admitted_identity(path):
        observed = original_identity(path)
        if Path(path).resolve() == python_path:
            assert observed == python_identity, "CHILD_PYTHON_SHA"
        return observed

    def admitted_run(output, label, argv, cwd, timeout, budget):
        assert Path(argv[0]).resolve() == python_path, "CHILD_PYTHON_PATH"
        admitted_identity(python_path)
        return original_run(output, label, argv, cwd, timeout, budget)

    supervisor.runner.identity = admitted_identity
    supervisor.runner._run_process = admitted_run

    class ParentBudget(original_budget):
        def __init__(self, seconds):
            super().__init__(seconds)
            self.started = started

    supervisor.runner.Budget = ParentBudget
    with Path(manifest["parent_entry"]).open("xb") as stream:
        stream.write(encoded(entry))
    sources = {**manifest["sources"], str(manifest_path): identity(raw),
               manifest["parent_entry"]: identity(encoded(entry)),
               str(python_path): python_identity}
    result = supervisor.observe_run(manifest["parent_output"], manifest["worker_argv"],
                                    capsule, manifest["receipt_path"], sources,
                                    total_seconds=300, step_seconds=300)
    return {"status": result["status"], "exit_code": result["exit_code"],
            "failure": result["failure"], "elapsed_seconds": result["elapsed_seconds"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("prepare")
    for name in ("plan", "config", "destination"):
        p.add_argument("--" + name, type=Path, required=True)
    p = sub.add_parser("execute")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--manifest-sha", required=True)
    args = parser.parse_args()
    result = (prepare(args.plan, args.config, args.destination) if args.mode == "prepare"
              else execute(args.manifest, args.manifest_sha))
    print(json.dumps(result))
    raise SystemExit(result.get("exit_code", 0))
