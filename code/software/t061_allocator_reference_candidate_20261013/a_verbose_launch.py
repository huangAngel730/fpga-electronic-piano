"""Pinned parent admission and hard watchdog for verbose compile-only work."""
import argparse
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import sys
import time


PINNED_EXEC = (
    "from pathlib import Path;import hashlib,sys;"
    "p=Path(sys.argv.pop(1));expected=sys.argv.pop(1);raw=p.read_bytes();"
    "assert hashlib.sha256(raw).hexdigest()==expected,'FROZEN_SCRIPT_SHA';"
    "sys.argv[0]=str(p);exec(compile(raw,str(p),'exec'),"
    "{'__name__':'__main__','__file__':str(p)})"
)
HELPERS = ("runner.py", "runner_tail_20261013.py", "windows_job.py",
           "supervisor_20261013.py")


def identity(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def collect_parent_identity():
    return {
        "pid": os.getpid(), "orig_argv": list(sys.orig_argv),
        "argv": list(sys.argv), "cwd": str(Path.cwd().resolve()),
        "python_path": str(Path(sys.executable).resolve()),
        "python": identity(Path(sys.executable).read_bytes()),
        "flags": {key: getattr(sys.flags, key) for key in
                  ("isolated", "no_site", "no_user_site",
                   "dont_write_bytecode", "utf8_mode")},
        "xoptions": dict(sys._xoptions),
    }


def validate_parent_runtime(manifest, manifest_sha, actual):
    assert Path(actual["cwd"]) == Path(manifest["cwd"]), "PARENT_ACTUAL_CWD"
    assert actual["flags"] == {key: 1 for key in
                               ("isolated", "no_site", "no_user_site",
                                "dont_write_bytecode", "utf8_mode")}, "PARENT_FLAGS"
    assert actual["xoptions"].get("utf8") is True, "PARENT_UTF8_OPTION"
    expected = manifest["parent_argv_prefix"] + [manifest_sha]
    assert len(actual["orig_argv"]) == len(expected), "PARENT_ARGV"
    assert Path(actual["orig_argv"][0]).resolve() == Path(expected[0]).resolve(), \
        "PARENT_ARGV_PYTHON"
    assert actual["orig_argv"][1:] == expected[1:], "PARENT_ARGV"
    python = manifest["python"]
    assert Path(actual["python_path"]) == Path(python["path"]), "PARENT_PYTHON"
    assert actual["python"] == {key: python[key]
                                for key in ("bytes", "sha256")}, \
        "PARENT_PYTHON_SHA"


def read_bound_sources(manifest):
    result = {}
    for name, expected in manifest["sources"].items():
        path = Path(name).resolve()
        raw = path.read_bytes()
        assert identity(raw) == expected, "PARENT_SOURCE_SHA:" + name
        result[path] = raw
    helpers = Path(manifest["helpers"]).resolve()
    expected_helpers = {helpers / name for name in HELPERS}
    assert {path.resolve() for path in helpers.rglob("*") if path.is_file()} \
        == expected_helpers, "PARENT_HELPER_MEMBERS"
    return result


def load_parent_helpers(raw_sources, helpers):
    """Load supervisor and nested imports from already authenticated bytes."""
    helpers = Path(helpers).resolve()
    raw_helpers = {path: raw for path, raw in raw_sources.items()
                   if path.parent == helpers}

    class RawLoader(importlib.abc.Loader):
        def __init__(self, path):
            self.path = path

        def create_module(self, spec):
            return None

        def exec_module(self, module):
            module.__file__ = str(self.path)
            exec(compile(raw_helpers[self.path], str(self.path), "exec"),
                 module.__dict__)

    def raw_spec(name, path):
        spec = importlib.util.spec_from_loader(name, RawLoader(path),
                                               origin=str(path))
        spec.has_location = True
        return spec

    class RawFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            source = helpers / (fullname + ".py")
            return raw_spec(fullname, source) if source in raw_helpers else None

    original = importlib.util.spec_from_file_location

    def pinned_file_spec(name, location, *args, **kwargs):
        path = Path(location).resolve()
        return raw_spec(name, path) if path in raw_helpers \
            else original(name, location, *args, **kwargs)

    finder = RawFinder()
    for path in raw_helpers:
        sys.modules.pop(path.stem, None)
    sys.meta_path.insert(0, finder)
    importlib.util.spec_from_file_location = pinned_file_spec
    try:
        path = helpers / "supervisor_20261013.py"
        spec = raw_spec("frozen_verbose_supervisor", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.meta_path.remove(finder)
        importlib.util.spec_from_file_location = original


def prepare(plan_path, config_path, destination, command_destination=None):
    plan_path, config_path, destination = map(
        lambda path: Path(path).resolve(),
        (plan_path, config_path, destination))
    command_destination = (Path(command_destination).resolve()
                           if command_destination else
                           destination.with_name("launch_command.json"))
    plan_raw = plan_path.read_bytes()
    config_raw = config_path.read_bytes()
    plan = json.loads(plan_raw)
    config = json.loads(config_raw)
    assert config["plan"] == identity(plan_raw), "CONFIG_PLAN_SHA"
    capsule = Path(plan["capsule_root"]).resolve()
    worker = capsule / plan["worker"]
    launcher = capsule / plan["launcher"]
    base_worker = capsule / plan["base_worker"]
    helpers = capsule / Path(plan["runner_tail"]).parent
    paths = [worker, launcher, base_worker,
             *(helpers / name for name in HELPERS), plan_path, config_path]
    source_files = {str(path.resolve()): identity(path.read_bytes())
                    for path in paths}
    for path in (worker, launcher, base_worker,
                 *(helpers / name for name in HELPERS)):
        relative = path.resolve().relative_to(capsule).as_posix()
        expected = plan["capsule_files"][relative]
        assert source_files[str(path.resolve())] == {
            key: expected[key] for key in ("bytes", "sha256")
        }, "PLAN_CAPSULE_SOURCE_SHA:" + relative
    python = plan["tools"]["python"]
    prefix = [python, "-I", "-S", "-B", "-X", "utf8", "-c", PINNED_EXEC]
    worker_argv = prefix + [str(worker), source_files[str(worker)]["sha256"],
                            "--config", str(config_path), "--config-sha",
                            identity(config_raw)["sha256"]]
    manifest = {
        "schema": "T061_N32_A_VERBOSE_LAUNCH_V1",
        "python": {"path": python, **plan["tool_files"][python]},
        "capsule": str(capsule), "cwd": str(capsule),
        "helpers": str(helpers),
        "plan": {"path": str(plan_path), **identity(plan_raw)},
        "config": {"path": str(config_path), **identity(config_raw)},
        "worker": {"path": str(worker), **source_files[str(worker)]},
        "launcher": {"path": str(launcher), **source_files[str(launcher)]},
        "sources": source_files,
        "worker_argv": worker_argv,
        "parent_argv_prefix": prefix + [
            str(launcher), source_files[str(launcher)]["sha256"],
            "execute", "--manifest", str(destination), "--manifest-sha"],
        "parent_output": config["execution_output"] + "_parent",
        "parent_entry": config["execution_output"] + "_parent.entry.json",
        "receipt_path": str(Path(config["execution_output"]) / "receipt.json"),
        "parent_total_seconds": 300, "worker_watchdog_seconds": 300,
        "compile_seconds": 90, "calls": 1, "automatic_retries": 0,
        "simulate_calls": 0, "EDA_calls": 0,
    }
    with destination.open("xb") as stream:
        stream.write(encoded(manifest))
    manifest_identity = identity(destination.read_bytes())
    command = {
        "schema": "T061_N32_A_VERBOSE_LAUNCH_COMMAND_V1",
        "status": "PREPARED_NOT_RUN",
        "argv": manifest["parent_argv_prefix"] + [manifest_identity["sha256"]],
        "cwd": manifest["cwd"],
        "launch_manifest": {"path": str(destination), **manifest_identity},
        "execution_outputs": [config["execution_output"],
                              manifest["parent_output"],
                              manifest["parent_entry"]],
    }
    with command_destination.open("xb") as stream:
        stream.write(encoded(command))
    return {"status": "FROZEN_VERBOSE_LAUNCH_NOT_RUN",
            "manifest": manifest_identity,
            "command": identity(command_destination.read_bytes())}


def execute(manifest_path, expected_sha):
    started = time.monotonic()
    manifest_path = Path(manifest_path).resolve()
    raw = manifest_path.read_bytes()
    assert identity(raw)["sha256"] == expected_sha, "LAUNCH_MANIFEST_SHA"
    manifest = json.loads(raw)
    assert manifest["schema"] == "T061_N32_A_VERBOSE_LAUNCH_V1"
    assert manifest["parent_total_seconds"] == 300 \
        and manifest["worker_watchdog_seconds"] == 300, "PARENT_LIMITS"
    assert manifest["calls"] == 1 and manifest["automatic_retries"] == 0 \
        and manifest["simulate_calls"] == 0 and manifest["EDA_calls"] == 0, \
        "PARENT_SCOPE"
    actual = collect_parent_identity()
    entry = {"status": "ADMISSION_REJECTED", "manifest": identity(raw),
             "actual_parent": actual}
    try:
        validate_parent_runtime(manifest, expected_sha, actual)
        assert Path(__file__).resolve() == Path(manifest["launcher"]["path"]), \
            "PARENT_SOURCE_PATH"
        raw_sources = read_bound_sources(manifest)
        plan = json.loads(raw_sources[Path(manifest["plan"]["path"]).resolve()])
        python = manifest["python"]
        assert python == {"path": plan["tools"]["python"],
                          **plan["tool_files"][plan["tools"]["python"]]}, \
            "CHILD_PYTHON_ADMISSION"
        entry["status"] = "ADMITTED"
    except Exception as error:
        entry["failure"] = str(error)
        with Path(manifest["parent_entry"]).open("xb") as stream:
            stream.write(encoded(entry))
        raise

    supervisor = load_parent_helpers(raw_sources, manifest["helpers"])
    original_budget = supervisor.runner.Budget
    original_identity = supervisor.runner.identity
    original_run = supervisor.runner._run_process
    python_path = Path(manifest["python"]["path"]).resolve()
    python_identity = {key: manifest["python"][key]
                       for key in ("bytes", "sha256")}

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
    sources = {str(path): identity(data) for path, data in raw_sources.items()}
    sources.update({str(manifest_path): identity(raw),
                    manifest["parent_entry"]: identity(encoded(entry)),
                    str(python_path): python_identity})
    result = supervisor.observe_run(
        manifest["parent_output"], manifest["worker_argv"],
        Path(manifest["capsule"]), manifest["receipt_path"], sources,
        total_seconds=300, step_seconds=300)
    return {"status": result["status"], "exit_code": result["exit_code"],
            "failure": result["failure"],
            "elapsed_seconds": result["elapsed_seconds"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    prepare_parser = sub.add_parser("prepare")
    for name in ("plan", "config", "destination", "command-destination"):
        prepare_parser.add_argument("--" + name, type=Path, required=True)
    execute_parser = sub.add_parser("execute")
    execute_parser.add_argument("--manifest", type=Path, required=True)
    execute_parser.add_argument("--manifest-sha", required=True)
    args = parser.parse_args()
    result = (prepare(args.plan, args.config, args.destination,
                      args.command_destination)
              if args.mode == "prepare"
              else execute(args.manifest, args.manifest_sha))
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(result.get("exit_code", 0))
