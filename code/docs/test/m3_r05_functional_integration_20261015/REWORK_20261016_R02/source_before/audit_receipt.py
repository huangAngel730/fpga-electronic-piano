"""Verify original six streams / frozen source identities; never self-sign M2."""
import argparse
import json
from pathlib import Path
import sys

from common import R05_SHA, Refusal, identity, json_load, sha
from receipt_check import check_step
from runner import MODEL_2020


def check_identity(item, *, expected=None):
    if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}:
        raise Refusal("IDENTITY_FORMAT", repr(item))
    path = Path(item["path"])
    if expected is not None and path.resolve() != expected.resolve():
        raise Refusal("STREAM_LOCATION", str(path))
    if identity(path) != item:
        raise Refusal("FILE_SHA", str(path))
    return path.read_bytes()


def audit(path):
    path = Path(path).resolve()
    receipt = json_load(path.read_bytes())
    if receipt.get("schema") != "M3_R05_ISOLATED_RUN_V1":
        raise Refusal("RECEIPT_SCHEMA", "wrong R05 receipt")
    if receipt.get("input_archive", {}).get("sha256") != R05_SHA:
        raise Refusal("R05_SHA", "receipt points to another input")
    check_identity(receipt["input_archive"])
    if receipt.get("status") in ("BLOCKED_TOOL", "FAILED_STOP_NO_RETRY"):
        return {
            "status": receipt["status"], "functional_signoff": False,
            "functional_attempt_consumed": receipt.get("functional_attempt_consumed"),
            "functional_tool_count": receipt.get("functional_tool_count"),
            "board_release_allowed": False, "receipt_sha256": sha(path.read_bytes()),
            "per_request_deadline": "UNKNOWN_NO_PUBLIC_TRACE",
        }, 2
    if receipt.get("status") != "CONSISTENT_PENDING_M2":
        raise Refusal("NOT_A_COMPLETE_RUN", "no actual completed three-step result")
    if receipt.get("board_release_allowed") is not False:
        raise Refusal("RELEASE_CLAIM", "software cannot release board")
    if receipt.get("functional_attempt_consumed") is not True:
        raise Refusal("CONSUMPTION_MISSING", "no consumption marker")
    selected_versions = [
        item for item in receipt.get("version_calls", [])
        if item.get("before") == receipt.get("tool_before")
        and item.get("before") == item.get("after")
    ]
    if len(selected_versions) != 1 or len(selected_versions[0].get("calls", [])) != 3:
        raise Refusal("TOOL_VERSION_MISSING", "exact three tool versions required")
    for name, call in zip(("vlib", "vlog", "vsim"), selected_versions[0]["calls"]):
        if Path(call["argv"][0]).name.lower() != name + ".exe" or call["argv"][1:] != ["-version"]:
            raise Refusal("TOOL_VERSION_COMMAND", name)
        raw = check_identity(call["stdout"]) + check_identity(call["stderr"])
        if call.get("exit_code") != 0 or call.get("timeout") is not False or not MODEL_2020.search(raw.decode("utf-8")):
            raise Refusal("TOOL_VERSION_IDENTITY", name)
    marker = json_load(check_identity(receipt["consumption_marker"]))
    if marker["input_sha256"] != R05_SHA or Path(marker["output"]).resolve() != path.parent:
        raise Refusal("CONSUMPTION_IDENTITY", "marker does not bind this run")
    preflight = path.parent / "PREFLIGHT.json"
    if identity(preflight) != marker["preflight"]:
        raise Refusal("PREFLIGHT_SHA", "frozen plan differs")
    check_identity(receipt["authorization_reference"])
    check_identity(receipt["night_authorization_reference"])
    if not isinstance(receipt.get("machine"), str) or not receipt["machine"]:
        raise Refusal("MACHINE_MISSING", "empty machine")
    for before, after in (
        ("source_before", "source_after"), ("stage_input_before", "stage_input_after"),
        ("tool_before", "tool_after"),
    ):
        if not receipt.get(before) or receipt[before] != receipt.get(after):
            raise Refusal("IDENTITY_DRIFT", before)
        for item in receipt[before].values():
            check_identity(item)
    calls = receipt.get("functional_calls")
    if not isinstance(calls, list) or len(calls) != 3 or receipt.get("functional_tool_count") != 3:
        raise Refusal("MISSING_STEP", "vlib/vlog/vsim all required")
    summaries = []
    for name, call, argv in zip(("vlib", "vlog", "vsim"), calls, receipt["planned_argv"]):
        if call.get("argv") != argv or Path(argv[0]).name.lower() != name + ".exe":
            raise Refusal("COMMAND_IDENTITY", name)
        if Path(call["cwd"]).resolve() != Path(receipt["stage"]).resolve():
            raise Refusal("CWD_IDENTITY", name)
        if call.get("process_created") is not True or call.get("error") or call.get("log_limit_exceeded"):
            raise Refusal("TOOL_SUPERVISION", name)
        duration = call.get("elapsed_s")
        if type(duration) not in (int, float) or not 0 <= duration <= 300:
            raise Refusal("TOOL_BUDGET", name)
        stdout = check_identity(call["stdout"], expected=path.parent / "functional_logs" / (name + ".stdout.log"))
        stderr = check_identity(call["stderr"], expected=path.parent / "functional_logs" / (name + ".stderr.log"))
        summaries.append(check_step(name, stdout, stderr, call["exit_code"], call["timeout"]))
    duration = receipt.get("elapsed_s")
    if type(duration) not in (int, float) or not 0 <= duration < 900:
        raise Refusal("TOTAL_BUDGET", "900 seconds include collection")
    return {
        "status": "CONSISTENT_PENDING_M2", "functional_signoff": False,
        "board_release_allowed": False, "receipt_sha256": sha(path.read_bytes()),
        "steps": summaries, "dynamic_dependencies": "UNKNOWN_STATIC_INVENTORY_ONLY",
        "per_request_deadline": "UNKNOWN_NO_PUBLIC_TRACE",
        "analog_latency": "UNKNOWN_NOT_MEASURED",
        "limitation": "M2 must independently confirm original provenance and physical source binding.",
    }, 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("receipt", type=Path)
    args = p.parse_args()
    try:
        result, code = audit(args.receipt)
        print(json.dumps(result, ensure_ascii=False))
        return code
    except (Refusal, KeyError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "REJECTED", "diagnostic": getattr(exc, "code", "INPUT_ERROR"), "detail": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
