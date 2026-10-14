"""Source-bound software qualification; never invokes HDL/EDA tools.

Only a new, plan-bound capsule copy is tested. Qualification is not a
diagnostic compile attempt and cannot restore a consumed execution permit.
"""
import argparse
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import types
import unittest


GENERATOR = "code/software/t061_allocator_reference_candidate_20261013/a_qualify_diagnostic.py"
SOFTWARE = "code/software/t061_allocator_reference_candidate_20261013"
HELPERS = "code/software/t052_runner_acceptance_candidate_20261012"
TEST_MODULES = ("test_compile_diagnostic_guards", "test_diagnostic_launch_20261014",
                "test_delivery_binding_20261014")
HELPER_NAMES = ("runner.py", "runner_tail_20261013.py", "windows_job.py", "supervisor_20261013.py")
PINNED_EXEC = (
    "from pathlib import Path;import hashlib,sys;"
    "p=Path(sys.argv.pop(1));sha=sys.argv.pop(1);raw=p.read_bytes();"
    "assert hashlib.sha256(raw).hexdigest()==sha,'QUALIFICATION_GENERATOR_SHA';"
    "sys.argv[0]=str(p);exec(compile(raw,str(p),'exec'),"
    "{'__name__':'__main__','__file__':str(p)})"
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def remaining(started, cap=90):
    left = 300 - (time.monotonic() - started)
    require(left > 0, "QUALIFICATION_TOTAL_BUDGET")
    return min(float(cap), left)


def member(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    require(not Path(relative).is_absolute() and path != root and path.is_relative_to(root),
            "QUALIFICATION_MEMBER_ESCAPE")
    require(not any(item.is_symlink() for item in (path, *path.parents)),
            "QUALIFICATION_SYMLINK")
    return path


def load_manifest(path, expected_sha):
    raw = Path(path).read_bytes()
    require(identity(raw)["sha256"] == expected_sha, "QUALIFICATION_MANIFEST_SHA")
    value = json.loads(raw)
    require(value["schema"] == "T061_N32_A_DIAGNOSTIC_QUALIFICATION_V1",
            "QUALIFICATION_MANIFEST_SCHEMA")
    return value, raw


def source_bytes(manifest):
    frozen = Path(manifest["frozen_root"]).resolve()
    actual = {path.relative_to(frozen).as_posix() for path in frozen.rglob("*")
              if path.is_file()}
    require(actual == set(manifest["sources"]), "QUALIFICATION_FROZEN_MEMBERS")
    result = {}
    for relative, expected in manifest["sources"].items():
        raw = member(frozen, relative).read_bytes()
        require(identity(raw) == {key: expected[key] for key in ("bytes", "sha256")},
                "QUALIFICATION_SOURCE_SHA:" + relative)
        result[relative] = raw
    return result


def load_supervisor(manifest):
    frozen = Path(manifest["frozen_root"])
    helpers = frozen / HELPERS
    relative = SOFTWARE + "/a_diagnostic_launch.py"
    launcher_path = frozen / relative
    raw = launcher_path.read_bytes()
    require(identity(raw) == {key: manifest["sources"][relative][key]
                             for key in ("bytes", "sha256")}, "QUALIFICATION_LOADER_SHA")
    loader = types.ModuleType("qualification_verified_raw_loader")
    loader.__file__ = str(launcher_path)
    exec(compile(raw, str(launcher_path), "exec"), loader.__dict__)
    helper_manifest = {"sources": {
        str(frozen / relative): {key: value[key] for key in ("bytes", "sha256")}
        for relative, value in manifest["sources"].items()}}
    raw_helpers = loader.read_parent_helpers(helper_manifest, helpers)
    module = loader.load_parent_helpers(raw_helpers, helpers)
    for name in ("runner", "runner_tail_20261013", "windows_job"):
        loaded = importlib.import_module(name)
        require(Path(loaded.__file__).resolve().is_relative_to(helpers),
                "QUALIFICATION_HELPER_IMPORT:" + name)
    return module


def run_tests(manifest_path, expected_sha):
    """Child entry: run only exact frozen new software tests, not caller exits."""
    manifest, manifest_raw = load_manifest(manifest_path, expected_sha)
    frozen = Path(manifest["frozen_root"]).resolve()
    require(Path.cwd().resolve() == frozen, "QUALIFICATION_CHILD_CWD")
    require(Path(__file__).resolve() == frozen / GENERATOR,
            "QUALIFICATION_CHILD_GENERATOR_PATH")
    python = manifest["python"]
    require(Path(sys.executable).resolve() == Path(python["path"]).resolve(),
            "QUALIFICATION_CHILD_PYTHON")
    require(identity(Path(sys.executable).read_bytes()) ==
            {key: python[key] for key in ("bytes", "sha256")},
            "QUALIFICATION_CHILD_PYTHON_SHA")
    before = source_bytes(manifest)
    sys.path.insert(0, str(frozen / SOFTWARE))
    modules = [importlib.import_module(name) for name in TEST_MODULES]
    for module in modules:
        require(Path(module.__file__).resolve() == frozen / SOFTWARE / (module.__name__ + ".py"),
                "QUALIFICATION_TEST_IMPORT")
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(module)
                               for module in modules)
    discovered = suite.countTestCases()
    require(discovered > 0, "QUALIFICATION_NO_TESTS")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    after = source_bytes(manifest)
    require(after == before, "QUALIFICATION_CHILD_SOURCE_DRIFT")
    require(Path(manifest_path).read_bytes() == manifest_raw, "QUALIFICATION_CHILD_MANIFEST_DRIFT")
    success = result.wasSuccessful() and result.testsRun == discovered and not result.skipped
    receipt = {"schema": "T061_N32_A_DIAGNOSTIC_SOFTWARE_TEST_RESULT_V1",
               "status": "SOFTWARE_TEST_PASS" if success else "FAIL_PARTIAL",
               "exit_code": 0 if success else 1,
               "tests_discovered": discovered, "tests_run": result.testsRun,
               "failures": len(result.failures), "errors": len(result.errors),
               "skipped": len(result.skipped), "manifest": identity(manifest_raw),
               "sources_before": {key: identity(raw) for key, raw in before.items()},
               "sources_after": {key: identity(raw) for key, raw in after.items()},
               "test_modules": list(TEST_MODULES), "HDL_calls": 0, "EDA_calls": 0,
               "scope": "NEW_DIAGNOSTIC_GUARDS_SOFTWARE_ONLY"}
    with Path(manifest["child_receipt"]).open("xb") as stream:
        stream.write(encoded(receipt))
    return receipt


def qualify(plan_path, expected_sha, output):
    """Copy bound raw bytes and observe one real isolated software child."""
    started = time.monotonic()
    plan_path, output = Path(plan_path).resolve(), Path(output).resolve()
    raw = plan_path.read_bytes()
    require(identity(raw)["sha256"] == expected_sha, "QUALIFICATION_PLAN_SHA")
    plan = json.loads(raw)
    require(not output.exists(), "QUALIFICATION_OUTPUT_EXISTS")
    require(output.is_relative_to(Path(plan["repo"]).resolve() / "code/output"),
            "QUALIFICATION_OUTPUT_SCOPE")
    capsule = Path(plan["capsule_root"]).resolve()
    actual = {path.relative_to(capsule).as_posix() for path in capsule.rglob("*")
              if path.is_file()}
    require(actual == set(plan["capsule_files"]), "QUALIFICATION_PLAN_MEMBERS")
    output.mkdir()
    frozen = output / "frozen"
    frozen.mkdir()
    sources = {}
    for relative, expected in plan["capsule_files"].items():
        remaining(started)
        source = member(capsule, relative)
        bound = source.read_bytes()
        require(identity(bound) == {key: expected[key] for key in ("bytes", "sha256")},
                "QUALIFICATION_PLAN_SOURCE_SHA:" + relative)
        target = member(frozen, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(bound)
        sources[relative] = {**identity(bound), "plan_capsule_source": str(source),
                             "source_provenance": expected.get("source_provenance")}
    require(GENERATOR in sources, "QUALIFICATION_GENERATOR_UNBOUND")
    require(identity(Path(__file__).read_bytes()) ==
            {key: sources[GENERATOR][key] for key in ("bytes", "sha256")},
            "QUALIFICATION_ACTIVE_GENERATOR_NOT_PLAN_BYTES")
    (frozen / "code/output").mkdir(parents=True, exist_ok=True)
    python_path = Path(plan["tools"]["python"]).resolve()
    require(Path(sys.executable).resolve() == python_path, "QUALIFICATION_PARENT_PYTHON")
    python_identity = identity(python_path.read_bytes())
    require(python_identity == plan["tool_files"][str(python_path)],
            "QUALIFICATION_PYTHON_PLAN_SHA")
    child = output / "child"
    child.mkdir()
    manifest_path = output / "qualification_manifest.json"
    child_receipt = child / "receipt.json"
    argv_prefix = [str(python_path), "-I", "-S", "-B", "-X", "utf8", "-c", PINNED_EXEC,
                   str(frozen / GENERATOR), sources[GENERATOR]["sha256"], "run-tests",
                   "--manifest", str(manifest_path), "--manifest-sha"]
    manifest = {"schema": "T061_N32_A_DIAGNOSTIC_QUALIFICATION_V1",
                "plan": {"path": str(plan_path), **identity(raw)},
                "sources": sources, "frozen_root": str(frozen),
                "python": {"path": str(python_path), **python_identity},
                "generator": GENERATOR, "test_modules": list(TEST_MODULES),
                "argv_prefix": argv_prefix, "append_manifest_sha": True,
                "cwd": str(frozen), "child_receipt": str(child_receipt),
                "parent_output": str(output / "parent"),
                "total_seconds": 300, "step_seconds": 90,
                "automatic_retries": 0, "HDL_calls": 0, "EDA_calls": 0}
    manifest_raw = encoded(manifest)
    with manifest_path.open("xb") as stream:
        stream.write(manifest_raw)
    supervisor = load_supervisor(manifest)
    original_budget = supervisor.runner.Budget

    class QualificationBudget(original_budget):
        def __init__(self, seconds):
            super().__init__(seconds)
            self.started = started

    supervisor.runner.Budget = QualificationBudget
    snapshot = {str(frozen / relative): {key: value[key] for key in ("bytes", "sha256")}
                for relative, value in sources.items()}
    snapshot.update({str(manifest_path): identity(manifest_raw), str(plan_path): identity(raw)})
    require(remaining(started) == 90, "QUALIFICATION_INSUFFICIENT_CHILD_BUDGET")
    observed = supervisor.observe_run(output / "parent", argv_prefix + [identity(manifest_raw)["sha256"]],
                                      frozen, child_receipt, snapshot,
                                      total_seconds=300, step_seconds=90)
    if observed["exit_code"] != 0:
        return {"status": "FAIL_PARTIAL", "exit_code": 1,
                "failure": observed["failure"], "output": str(output)}
    verified = validate_qualification(output)
    return {"status": "SOURCE_BOUND_SOFTWARE_QUALIFICATION_PASS", "exit_code": 0,
            "tests_run": verified["receipt"]["tests_run"], "output": str(output),
            "manifest": identity(manifest_raw), "HDL_calls": 0, "EDA_calls": 0}


def validate_qualification(output, archived_sources=None):
    """Return validated immutable bytes; never accept a caller-supplied exit.

    A sealer passes its final capsule-relative bytes as archived_sources.
    Every tested member must match exactly; returned source_bytes are safe
    to archive without reopening the active workspace after validation.
    """
    output = Path(output).resolve()
    manifest_path = output / "qualification_manifest.json"
    manifest_raw = manifest_path.read_bytes()
    manifest, _ = load_manifest(manifest_path, identity(manifest_raw)["sha256"])
    require(manifest["test_modules"] == list(TEST_MODULES), "QUALIFICATION_TEST_SCOPE")
    require(manifest["total_seconds"] == 300 and manifest["step_seconds"] == 90,
            "QUALIFICATION_LIMITS")
    frozen = Path(manifest["frozen_root"])
    require(frozen.resolve() == output / "frozen", "QUALIFICATION_FROZEN_ROOT")
    require(Path(manifest["child_receipt"]).resolve() == output / "child/receipt.json"
            and Path(manifest["parent_output"]).resolve() == output / "parent"
            and Path(manifest["cwd"]).resolve() == frozen.resolve(),
            "QUALIFICATION_EVIDENCE_PATHS")
    bound = source_bytes(manifest)
    supervisor = load_supervisor(manifest)
    snapshot = {str(frozen / relative): identity(raw) for relative, raw in bound.items()}
    snapshot.update({str(manifest_path): identity(manifest_raw),
                     manifest["plan"]["path"]: {key: manifest["plan"][key] for key in ("bytes", "sha256")}})
    verified = supervisor.require_supervisor(
        output / "child", output / "parent/observation.json",
        manifest["argv_prefix"] + [identity(manifest_raw)["sha256"]], snapshot,
        expected_cwd=frozen, expected_total=300, expected_step=90)
    bound_plan = json.loads(verified["files"][manifest["plan"]["path"]])
    require({relative: identity(raw) for relative, raw in bound.items()} ==
            {relative: {key: value[key] for key in ("bytes", "sha256")}
             for relative, value in bound_plan["capsule_files"].items()},
            "QUALIFICATION_PLAN_SOURCE_BINDING")
    require(manifest["python"] == {"path": bound_plan["tools"]["python"],
                                    **bound_plan["tool_files"][bound_plan["tools"]["python"]]},
            "QUALIFICATION_PLAN_PYTHON_BINDING")
    receipt = json.loads(verified["files"][str((output / "child/receipt.json").resolve())])
    require(receipt["schema"] == "T061_N32_A_DIAGNOSTIC_SOFTWARE_TEST_RESULT_V1"
            and receipt["status"] == "SOFTWARE_TEST_PASS"
            and type(receipt["exit_code"]) is int and receipt["exit_code"] == 0,
            "QUALIFICATION_TEST_RESULT")
    require(type(receipt["tests_run"]) is int and receipt["tests_run"] > 0
            and receipt["tests_run"] == receipt["tests_discovered"]
            and receipt["failures"] == receipt["errors"] == receipt["skipped"] == 0,
            "QUALIFICATION_TEST_COUNTS")
    expected_sources = {relative: identity(raw) for relative, raw in bound.items()}
    require(receipt["sources_before"] == receipt["sources_after"] == expected_sources
            and receipt["manifest"] == identity(manifest_raw)
            and receipt["test_modules"] == list(TEST_MODULES), "QUALIFICATION_TEST_BINDING")
    if archived_sources is not None:
        require(set(bound) <= set(archived_sources), "QUALIFICATION_ARCHIVE_MISSING_SOURCE")
        for relative, raw in bound.items():
            require(archived_sources[relative] == raw,
                    "QUALIFICATION_ARCHIVE_SOURCE_MISMATCH:" + relative)
    evidence = {str(manifest_path): manifest_raw, **verified["files"]}
    return {"receipt": receipt, "source_bytes": bound, "evidence_bytes": evidence,
            "manifest": manifest, "observation": verified["record"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    prepare = modes.add_parser("qualify")
    prepare.add_argument("--plan", required=True, type=Path)
    prepare.add_argument("--plan-sha", required=True)
    prepare.add_argument("--output", required=True, type=Path)
    child = modes.add_parser("run-tests")
    child.add_argument("--manifest", required=True, type=Path)
    child.add_argument("--manifest-sha", required=True)
    args = parser.parse_args()
    result = (qualify(args.plan, args.plan_sha, args.output) if args.mode == "qualify"
              else run_tests(args.manifest, args.manifest_sha))
    print(json.dumps({key: value for key, value in result.items() if key not in
                      ("sources_before", "sources_after")}))
    raise SystemExit(result["exit_code"])
