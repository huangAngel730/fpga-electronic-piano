"""Trusted bootstrap: externally SHA-check these bytes before compile/exec.

Only standard-library imports precede full capsule validation. The executor
must pin the reviewed plan SHA and this bootstrap's SHA outside the worktree.
No project import or HDL process occurs before the frozen capsule is checked.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import socket
import sys
import time


def bootstrap(plan_path, plan_sha, *, invoke=True, import_verify=False):
    started = time.monotonic()
    plan_path = Path(plan_path).resolve()
    raw = plan_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != plan_sha:
        raise ValueError("BOOTSTRAP_PLAN_SHA")

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("BOOTSTRAP_DUPLICATE_KEY")
            value[key] = item
        return value

    plan = json.loads(raw, object_pairs_hook=unique)
    if plan["hostname"] != socket.gethostname() or plan["total_seconds"] != 900:
        raise ValueError("BOOTSTRAP_MACHINE_OR_BUDGET")
    if Path(sys.executable).resolve() != Path(plan["tools"]["python"]).resolve():
        raise ValueError("BOOTSTRAP_PYTHON_IDENTITY")
    capsule = Path(plan["capsule_root"]).resolve()
    if capsule != plan_path.parent / "capsule":
        raise ValueError("BOOTSTRAP_CAPSULE_ROOT")
    actual_members = {path.relative_to(capsule).as_posix() for path in capsule.rglob("*")
                      if path.is_file()}
    if actual_members != set(plan["capsule_files"]):
        raise ValueError("BOOTSTRAP_CAPSULE_MEMBERS")
    for relative, expected in plan["capsule_files"].items():
        path = (capsule / relative).resolve()
        if Path(relative).is_absolute() or not path.is_relative_to(capsule):
            raise ValueError("BOOTSTRAP_CAPSULE_ESCAPE")
        if any(parent.is_symlink() for parent in (path, *path.parents)):
            raise ValueError("BOOTSTRAP_CAPSULE_SYMLINK")
        data = path.read_bytes()
        if len(data) != expected["bytes"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
            raise ValueError("BOOTSTRAP_CAPSULE_SHA:" + relative)
    worker = capsule / plan["worker"]
    if plan["worker"] not in plan["capsule_files"]:
        raise ValueError("BOOTSTRAP_WORKER_UNBOUND")
    if time.monotonic() - started >= 900:
        raise ValueError("BOOTSTRAP_TOTAL_BUDGET")
    if not invoke:
        return {"worker": str(worker), "started_monotonic": started,
                "scope": "SOFTWARE_GUARD_ONLY_NO_WORKER_EXECUTION"}
    if import_verify:
        sys.argv = [str(worker), "import-verify", "--plan", str(plan_path)]
    else:
        sys.argv = [str(worker), "execute", "--plan", str(plan_path),
                    "--reviewed-plan-sha", plan_sha, "--budget-start", str(started)]
    runpy.run_path(str(worker), run_name="__main__")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--plan-sha", required=True)
    parser.add_argument("--import-verify", action="store_true")
    args = parser.parse_args()
    bootstrap(args.plan, args.plan_sha, import_verify=args.import_verify)
