"""Production entry for one R13 backend streaming candidate run."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import traceback

import binding
import finalize
import resources
from stream_bridge import (Reject, identity, read_control,
                           read_descriptor_json, require, strict_child)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]
OUTPUT_ROOT = ROOT / "code/output/m3_backend_stream_r13_20261018"
CONTROL_FIELDS = {"schema", "run_id", "run_kind", "envelope_ref",
                  "dependencies_ref", "quota_bytes", "volume_policy",
                  "authority"}
_TEST_HOOK = None


def install_test_hook(hook_or_none) -> None:
    """Install the private B12 boundary callback without wrapping failures."""
    global _TEST_HOOK
    require(hook_or_none is None or callable(hook_or_none),
            "R13_ENTRY_TEST_HOOK")
    _TEST_HOOK = hook_or_none


def _event(name: str, payload: dict) -> None:
    if _TEST_HOOK is not None:
        _TEST_HOOK(name, payload)


def validate_control(value: dict) -> None:
    require(type(value) is dict and set(value) == CONTROL_FIELDS,
            "R13_CONTROL_FIELDS")
    require(value["schema"] == "M3_R13_BACKEND_CONTROL_V1",
            "R13_CONTROL_SCHEMA")
    require(value["run_kind"] in ("SYNTHETIC_SOFTWARE", "FORMAL_REAL"),
            "R13_RUN_KIND")
    require(value["volume_policy"] == "GZIP_32M_PARTS_IO_1M",
            "R13_VOLUME_POLICY")
    require(value["authority"] == {
        "execution_allowed": False, "real_verified": False,
        "math_verified": False, "board_release_allowed": False},
        "R13_FALSE_AUTHORITY")
    require(type(value["quota_bytes"]) is int and
            0 < value["quota_bytes"] <= resources.WORKSPACE_LIMIT,
            "R13_QUOTA")
    if value["run_kind"] == "FORMAL_REAL":
        # D4 has six mathematical outputs.  Its seven-input M1 consumer still
        # needs the signed streaming-index/reset projection adapter; do not
        # silently promote the software successor to a formal REAL run.
        raise Reject("R13_FORMAL_REAL_CONSUMER_ADAPTER_PENDING")


def run(control_path: Path, control_sha256: str, final_dir: Path) -> dict:
    require(sys.dont_write_bytecode and not sys.flags.optimize,
            "R13_REQUIRES_B_ASSERTIONS_ON")
    control_path = Path(control_path).resolve()
    initial = read_control(control_path, control_sha256)
    validate_control(initial["value"])
    control = initial["value"]
    # The worker configures the one process-wide budget from its consumed
    # admission before materializing this frozen-compatible backend control.
    budget = resources.get_budget()
    budget.check()
    final_dir = strict_child(OUTPUT_ROOT, final_dir)
    require(not final_dir.exists(), "R13_FINAL_EXISTS")
    # Frozen D4 records repo-relative paths in its descriptors.  Therefore it
    # must run at the final stable pathname; renaming a staging directory would
    # leave every recorded descriptor pointing at the vanished staging name.
    # Publication is the atomic COMPLETE.json marker, never directory presence.
    resources.accounting_mkdir(final_dir, parents=True, exist_ok=False)
    chain_dir = final_dir / "chain"
    started = datetime.now(timezone.utc).isoformat()
    try:
        before = resources.preflight(final_dir,
                                     full_window=control["run_id"] == "W01")
        require(before["decision"] == "GO", "R13_RESOURCE_PREFLIGHT")
        envelope_record = read_descriptor_json(control["envelope_ref"], ROOT)
        dependency_record = read_descriptor_json(control["dependencies_ref"], ROOT)
        envelope = envelope_record["value"]
        result = binding.run_frozen_chain(
            envelope, control["dependencies_ref"], chain_dir,
            control["quota_bytes"])
        _event("after_backend_before_final_verify", {
            "control_path": control_path, "control": control,
            "result": result, "final_dir": final_dir,
        })
        budget.check()
        # Freeze decisions came from initial.raw only; this second identity is
        # a terminal mutation guard, never a second parse/decision source.
        require(identity(control_path) == initial["stamp"],
                "R13_CONTROL_CHANGED_DURING_RUN")
        require(read_descriptor_json(control["envelope_ref"], ROOT)["stamp"] ==
                envelope_record["stamp"], "R13_ENVELOPE_CHANGED_DURING_RUN")
        require(read_descriptor_json(control["dependencies_ref"], ROOT)["stamp"] ==
                dependency_record["stamp"], "R13_DEPENDENCIES_CHANGED_DURING_RUN")
        audit = finalize.audit(result, ROOT, final_dir)
        after = resources.disk_snapshot(final_dir)
        require(after["tree_bytes"] <= resources.WORKSPACE_LIMIT and
                after["disk_free"] >= resources.END_RESERVE,
                "R13_FINAL_DISK_RESOURCE_LIMIT")
        completion = {"schema": "M3_R13_ATOMIC_COMPLETION_V1",
                      "status": "COMPLETE_SOFTWARE_ONLY",
                      "run_id": control["run_id"],
                      "started_utc": started,
                      "ended_utc": datetime.now(timezone.utc).isoformat(),
                      "control": {"path": str(control_path), **initial["stamp"]},
                      "envelope": envelope_record["stamp"],
                      "dependencies": dependency_record["stamp"],
                      "audit": audit,
                      "workspace_resources": after,
                      "volume_store": result["R13_volume_store"],
                      "accounting_before_completion": budget.receipt(),
                      "instantaneous_ABA_not_observable": True,
                      **{flag: False for flag in finalize.AUTHORITY_FLAGS}}
        finalize.atomic_json(final_dir / "COMPLETE.json", completion,
                             category="control")
        return completion
    except BaseException as error:
        failure = {"schema": "M3_R13_FAILURE_V1",
                   "status": "PARTIAL_FAILURE_OR_REJECT",
                   "started_utc": started,
                   "ended_utc": datetime.now(timezone.utc).isoformat(),
                   "error": type(error).__name__ + ":" + str(error),
                   "traceback": traceback.format_exc(),
                   "completion_written": False,
                   **{flag: False for flag in finalize.AUTHORITY_FLAGS}}
        failure_root = final_dir
        secondary_failures = []
        complete = failure_root / "COMPLETE.json"
        complete_exists = complete.exists()
        failure["completion_written"] = complete_exists
        if complete_exists:
            # A post-publication exception must never silently retract success.
            secondary_failures.append("COMPLETE_MARKER_ALREADY_PRESENT")
        if secondary_failures:
            failure["secondary_failures"] = secondary_failures
        try:
            failure["accounting_before_failure_record"] = budget.receipt()
        except BaseException as secondary:
            secondary_failures.append(type(secondary).__name__ + ":" +
                                      str(secondary))
        if secondary_failures:
            failure["secondary_failures"] = secondary_failures
        try:
            finalize.atomic_json(failure_root / "R13_FAILURE.json", failure,
                                 category="failure")
        except BaseException as secondary:
            secondary_failures.append(type(secondary).__name__ + ":" +
                                      str(secondary))
            budget.secondary(secondary)
        raise error.with_traceback(error.__traceback__)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control", required=True, type=Path)
    parser.add_argument("--control-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.control, args.control_sha256, args.output)
    print(json.dumps({"status": result["status"],
                      "real_verified": False,
                      "board_release_allowed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
