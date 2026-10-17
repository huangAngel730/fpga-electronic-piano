"""R6-4 narrow consumer repair. Fixed software worker only; never real tools.

The original adapter is read-only. Its fixture lifecycle remains limited to
its existing evidence; this repair does not qualify it as a real executor.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/tool_plan_adapter/r07_fix"
TRUST_PATH = DOC / "TRUST.json"
TRUST_SHA = "94787764d99e0f609136b08f743c3cc5d5ecc0509c821e28d302986929ba799c"
PLAN_SCHEMA = "M3_R6_R07_FIXED_BOUND_TOOL_PLAN_V1"


class Refusal(ValueError):
    pass


def need(ok, code):
    if not ok:
        raise Refusal(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(path):
    path = Path(path)
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw), "sha256": digest(raw)}


def pairs(items):
    out = {}
    for key, value in items:
        need(key not in out, "DUPLICATE_JSON_KEY")
        out[key] = value
    return out


def parse(raw):
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(Refusal("NONFINITE_JSON")))


def canonical(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))


def no_alias(path):
    for part in (path, *path.parents):
        need(not part.is_symlink() and not part.is_junction(), "SYMLINK_OR_JUNCTION")


def repo_file(value, scope=None):
    path = Path(value)
    need(not path.is_absolute() and not path.drive and ".." not in path.parts,
         "CANONICAL_REPO_PATH_REQUIRED")
    absolute = ROOT / path
    no_alias(absolute)
    absolute = absolute.resolve()
    need(absolute.is_relative_to(ROOT), "PATH_ESCAPE")
    if scope is not None:
        need(absolute.is_relative_to(scope), "CANDIDATE_PATH_SCOPE")
    return absolute


def pinned_runtime():
    no_alias(TRUST_PATH)
    raw = TRUST_PATH.read_bytes()
    need(digest(raw) == TRUST_SHA, "TRUST_MANIFEST_CHANGED")
    pins = parse(raw)
    for item in pins.values():
        no_alias(Path(item["path"]))
        need(identity(item["path"]) == item, "FIXED_RUNTIME_CHANGED")
    need(str(Path(sys.executable).resolve()) == pins["python"]["path"], "FIXED_PYTHON_REQUIRED")
    return pins


def load_legacy():
    pins = pinned_runtime()
    spec = importlib.util.spec_from_file_location("r07_readonly_legacy", pins["legacy"]["path"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Only the candidate evidence root changes; original source is untouched.
    module.DOCS = DOC
    return module


def rebuild(spec_name, spec_sha):
    path = repo_file(spec_name, DOC / "RUN_01")
    raw = path.read_bytes()
    need(digest(raw) == spec_sha, "PINNED_SPEC_SHA_MISMATCH")
    spec = parse(raw)
    if spec.get("mode") != "SOFTWARE_FIXTURE":
        raise PermissionError("REAL_TOOL_ROUTE_DISABLED")
    # Inspect lexical paths before the legacy normalizer resolves them.
    for name in ("cwd", "output_dir", "consumption_marker"):
        repo_file(spec[name])
    for role in ("sources", "roms", "testbenches", "dependencies"):
        for item in spec[role]:
            repo_file(item["path"])
    pins = pinned_runtime()
    legacy = load_legacy()
    plan = legacy.normalize_spec(spec, path)
    need(plan["cwd"] == str(HERE), "FIXED_CWD_REQUIRED")
    by_role = {role: {item["path"] for item in plan["inputs"] if item["role"] == role}
               for role in ("sources", "roms", "testbenches", "dependencies")}
    tb = ROOT / "code/tb/board/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/tool_plan_adapter"
    for role, filename in (("sources", "fixture_source.sv"), ("roms", "fixture_rom.hex"),
                           ("testbenches", "fixture_tb.sv")):
        need(by_role[role] == {str(tb / filename)}, "FIXED_INPUT_ROLE_REQUIRED")
    dependencies = {pins[k]["path"] for k in ("legacy", "worker", "job_helper")}
    dependencies.add(str(Path(__file__).resolve()))
    need(by_role["dependencies"] == dependencies, "FIXED_HELPERS_REQUIRED")
    output, marker = Path(plan["output_dir"]), Path(plan["consumption_marker"])
    need(not marker.is_relative_to(output) and not output.is_relative_to(marker), "OUTPUT_MARKER_OVERLAP")
    need(identity(path) == plan["spec"] and digest(path.read_bytes()) == spec_sha, "SPEC_CHANGED_DURING_REBUILD")
    plan.update(schema=PLAN_SCHEMA, consumer_fix="SPEC_REBUILD_AND_IMMEDIATE_SPAWN_GUARD",
                fixture_runtime=pins, fixed_cwd=True)
    return plan


def audit(plan_name, plan_sha, spec_name, spec_sha):
    path = repo_file(plan_name, DOC / "RUN_01")
    raw = path.read_bytes()
    need(digest(raw) == plan_sha, "PLAN_SHA_MISMATCH")
    plan = parse(raw)
    rebuilt = rebuild(spec_name, spec_sha)
    need(set(plan) == set(rebuilt), "PLAN_FIELDS_MISMATCH")
    for name in rebuilt:
        need(canonical(plan[name]) == canonical(rebuilt[name]), "PLAN_FIELD_MISMATCH:" + name)
    need(digest(path.read_bytes()) == plan_sha, "PLAN_CHANGED_DURING_AUDIT")
    return rebuilt, {"result": "AUDIT_OK_NOT_APPROVAL", "plan": identity(path),
                     "pinned_spec_sha256": spec_sha, "compared_fields": sorted(rebuilt),
                     "real_tool_launches": 0}


class SpawnGuard:
    def __init__(self, binding):
        self.binding = binding
        self.validation = None
        self.processes = 0

    def __getattr__(self, name):
        return getattr(subprocess, name)

    def Popen(self, argv, **kwargs):  # noqa: N802 - legacy API name
        plan, validation = audit(*self.binding)
        need(canonical(argv) == canonical(plan["argv"]), "SPAWN_ARGV_MISMATCH")
        allowed = {"cwd", "stdin", "stdout", "stderr", "creationflags"}
        need(set(kwargs) == allowed, "SPAWN_ARGUMENT_FIELDS")
        need(kwargs["cwd"] == plan["cwd"] and kwargs["stdin"] == subprocess.DEVNULL and
             kwargs["stdout"] == subprocess.PIPE and kwargs["stderr"] == subprocess.PIPE and
             kwargs["creationflags"] == (subprocess.CREATE_NEW_PROCESS_GROUP | 4), "SPAWN_ARGUMENT_BINDING")
        output, marker = Path(plan["output_dir"]), Path(plan["consumption_marker"])
        no_alias(output)
        no_alias(marker)
        need(output.is_dir() and not any(output.iterdir()), "SPAWN_OUTPUT_NOT_EXCLUSIVE_EMPTY")
        claim = parse(marker.read_bytes())
        need(set(claim) == {"schema", "state", "plan_sha256", "pid", "created_utc"} and
             claim["schema"] == "M3_R6_TOOL_PLAN_CONSUMPTION_V1" and claim["state"] == "CLAIMED" and
             type(claim["pid"]) is int and claim["pid"] == os.getpid() and
             claim["plan_sha256"] == self.binding[1], "SPAWN_CONSUMPTION_CLAIM")
        self.validation = validation
        kwargs["creationflags"] |= subprocess.CREATE_NO_WINDOW
        pinned_runtime()
        process = subprocess.Popen(argv, **kwargs)
        self.processes += 1
        self.validation = {**validation, "pid": process.pid, "creationflags": kwargs["creationflags"]}
        return process


def run_fixture(plan_name, plan_sha, spec_name, spec_sha):
    binding = (plan_name, plan_sha, spec_name, spec_sha)
    audit(*binding)  # Refuse forged content before output/claim/Job creation.
    legacy = load_legacy()
    legacy.audit = lambda p, h: audit(p, h, spec_name, spec_sha)
    guard = SpawnGuard(binding)
    legacy.subprocess = guard
    result = legacy.run_fixture(plan_name, plan_sha)
    result["consumer_fix"] = {"pinned_spec_sha256": spec_sha, "pre_spawn_validation": guard.validation,
                              "actual_fixture_launches": guard.processes, "real_tool_launches": 0,
                              "tree_timeout_overflow_qualification": "NOT_EXTENDED_NOT_REAL_EXECUTOR"}
    legacy.write_json_exclusive(Path(result["output_dir"]) / "CONSUMER_RECEIPT.json", result)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("assemble", "audit", "run-fixture"))
    for name in ("spec", "spec-sha256", "plan"):
        ap.add_argument("--" + name, required=True)
    ap.add_argument("--sha256")
    args = ap.parse_args()
    try:
        if args.command == "assemble":
            plan = rebuild(args.spec, args.spec_sha256)
            destination = repo_file(args.plan, DOC / "RUN_01")
            with destination.open("x", encoding="utf-8", newline="\n") as f:
                json.dump(plan, f, indent=2)
                f.write("\n")
            result, code = {"result": "BOUND_NOT_APPROVED", "plan": identity(destination)}, 0
        else:
            need(args.sha256 is not None, "PLAN_SHA_REQUIRED")
            if args.command == "audit":
                _, result = audit(args.plan, args.sha256, args.spec, args.spec_sha256)
                code = 0
            else:
                result = run_fixture(args.plan, args.sha256, args.spec, args.spec_sha256)
                code = 0 if result["result"] == "PASS_SOFTWARE_FIXTURE_ONLY" else 1
    except PermissionError as error:
        result, code = {"result": "REFUSED", "reason": str(error), "process_launches": 0}, 4
    except Exception as error:
        result, code = {"result": "REFUSED", "reason": str(error), "process_launches": 0}, 2
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
