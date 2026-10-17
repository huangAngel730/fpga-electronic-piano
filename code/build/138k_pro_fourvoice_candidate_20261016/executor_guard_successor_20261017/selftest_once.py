"""One <=90 second software-only group; exclusive output preserves all failures."""

from datetime import datetime, timezone
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import time

from owned_executor import (DUMMY, HERE, PYTHON, ROOT, run_software_case, snapshot,
                            validate_argv, write_json)
import owned_executor

EVIDENCE = ROOT / "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/executor_guard_successor_20261017"


def require(value, reason):
    if not value:
        raise AssertionError(reason)


def main():
    started = time.monotonic()
    deadline = started + 90
    output = EVIDENCE / "RUN_01"
    output.mkdir(exist_ok=False)
    planned = json.loads((EVIDENCE / "LOCAL_EXECUTION_SCOPE.json").read_text(encoding="utf-8"))
    expected = snapshot()
    receipt = {"schema": "m2_executor_guard_software_group_v1", "result": "FAIL_PARTIAL",
        "created_utc": datetime.now(timezone.utc).isoformat(), "maximum_seconds": 90,
        "group_number": 1, "level": "L1_SOFTWARE_PROCESS_CONTROL_ONLY",
        "p7_state": "BLOCKED_EXECUTOR_GUARD", "board_release_allowed": False,
        "source_identity": expected, "scope_identity": {
            "sha256": hashlib.sha256((EVIDENCE / "LOCAL_EXECUTION_SCOPE.json").read_bytes()).hexdigest()},
        "cases": [], "error": None, "not_run": ["P7", "HDL compilation", "RTL simulation", "EDA", "hardware"]}
    write_json(output / "START.json", receipt)
    try:
        require(planned["maximum_group_seconds"] == 90 and planned["groups_allowed"] == 1,
                "SCOPE_OR_BUDGET_CHANGED")
        cases = [("normal_exit0", "normal", 4, 1048576),
                 ("error_exit7", "error7", 4, 1048576),
                 ("timeout_parent_child_grandchild", "timeout_tree", 2.5, 1048576),
                 ("parent_exit_child_grandchild", "parent_exit_tree", 4, 1048576),
                 ("observed_log_limit", "overflow", 4, 65536)]
        for label, mode, seconds, log_limit in cases:
            result = run_software_case(label, mode, output, expected, deadline, seconds, log_limit)
            receipt["cases"].append({"case": label, "receipt": str(output / label / "RECEIPT.json")})
            write_json(output / "GROUP_PROGRESS.json", receipt)
            require(result["error"] is None, label + ": " + str(result["error"]))
            require(result["inputs_unchanged"] and result["group_deadline_kept"], label + ": identity/deadline")
            raw_out = (output / label / "stdout.raw").read_bytes()
            raw_err = (output / label / "stderr.raw").read_bytes()
            if mode in {"normal", "error7"}:
                require(result["root_exit_code"] == (7 if mode == "error7" else 0), label + ": exit")
                require((b"DUMMY_EXIT7_STDOUT" if mode == "error7" else b"DUMMY_NORMAL_STDOUT") in raw_out,
                        label + ": stdout")
                require((b"DUMMY_EXIT7_STDERR" if mode == "error7" else b"DUMMY_NORMAL_STDERR") in raw_err,
                        label + ": stderr")
                require(not result["timed_out"] and not result["log_limit_observed"], label + ": bounds")
            elif mode in {"timeout_tree", "parent_exit_tree"}:
                require((output / label / "grandchild.ready").exists(), label + ": grandchild missing")
                require(result["owned_members_captured"] >= 2, label + ": tree not observed")
                require(len(result["owned_handles_after_wait"]) >= 2 and all(
                    item["terminated"] for item in result["owned_handles_after_wait"]), label + ": owned handles")
                require(result["timed_out"] == (mode == "timeout_tree"), label + ": timeout")
                require(not (output / label / "ESCAPED_GRANDCHILD.txt").exists(), label + ": escaped grandchild")
                if mode == "parent_exit_tree":
                    require(result["root_exit_code"] == 0 and result["cleanup"]["mechanism"] == "KILL_ON_JOB_CLOSE",
                            label + ": parent/close semantics")
            else:
                require(result["log_limit_observed"] and not result["timed_out"], label + ": overflow not detected")
                require(result["cleanup"]["mechanism"] == "TerminateJobObject", label + ": cleanup")
            receipt["cases"][-1]["result"] = "PASS_SOFTWARE_ONLY"
        denied = []
        for argv in [["iverilog.exe", "-g2012", "unapproved.sv"],
                     ["gw_sh.exe", "unapproved.tcl"],
                     [str(PYTHON), "-I", "-S", "-B", str(DUMMY), "unknown"]]:
            try:
                validate_argv(argv)
            except PermissionError as error:
                denied.append({"argv": argv, "error": str(error), "process_launches": 0})
            else:
                raise AssertionError("UNAPPROVED_COMMAND_WAS_ACCEPTED")
        write_json(output / "DENIED_COMMANDS.json", denied)
        cli_stdout = io.StringIO()
        old_argv = list(sys.argv)
        try:
            sys.argv = [str(HERE / "owned_executor.py"), "iverilog.exe", "unapproved.sv"]
            with contextlib.redirect_stdout(cli_stdout):
                cli_exit = owned_executor.main()
        finally:
            sys.argv = old_argv
        (output / "cli_denial.stdout.raw").write_text(cli_stdout.getvalue(), encoding="utf-8")
        (output / "cli_denial.stderr.raw").write_bytes(b"")
        cli_record = json.loads(cli_stdout.getvalue())
        require(cli_exit == 2 and cli_record["process_launches"] == 0,
                "CLI_DID_NOT_DENY_UNAPPROVED_TOOL")
        write_json(output / "CLI_DENIAL_RECEIPT.json", {"exit_code": cli_exit,
                    "observed": cli_record, "actual_unapproved_process_launches": 0})
        receipt["cases"].append({"case": "deny_unapproved_tool", "result": "PASS_SOFTWARE_ONLY",
                                  "denials": len(denied), "process_launches": 0})
        require(snapshot() == expected and time.monotonic() < deadline, "FINAL_IDENTITY_OR_DEADLINE")
        receipt["result"] = "PASS_SOFTWARE_ONLY"
    except Exception as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)
    finally:
        receipt["elapsed_seconds"] = round(time.monotonic() - started, 6)
        receipt["exit_code"] = 0 if receipt["result"] == "PASS_SOFTWARE_ONLY" else 1
        write_json(output / "RECEIPT.json", receipt)
        print(json.dumps({key: receipt[key] for key in ("result", "level", "elapsed_seconds", "exit_code", "error")}))
    return receipt["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
