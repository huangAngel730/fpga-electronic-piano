"""One new BaseException fault injection, with independent source pre/post seal."""

from datetime import datetime, timezone
import json
from pathlib import Path
import time

import owned_executor as executor


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def frozen_inputs():
    inputs = executor.snapshot()
    inputs["r03_targeted_script"] = executor.identity(Path(__file__))
    return inputs


def main():
    started = time.monotonic()
    group_deadline = started + 90
    output = executor.EVIDENCE / "RUN_03"
    output.mkdir(exist_ok=False)
    expected = executor.snapshot()
    before = frozen_inputs()
    scope = executor.EVIDENCE / "LOCAL_EXECUTION_SCOPE_R03.json"
    record = {"schema": "m2_executor_guard_baseexception_repair_v1", "result": "FAIL_PARTIAL",
        "created_utc": datetime.now(timezone.utc).isoformat(), "maximum_seconds": 90,
        "level": "L1_ONE_SOFTWARE_BASEEXCEPTION_FAULT_ONLY", "inputs_before": before,
        "scope_identity": executor.identity(scope), "case": "keyboard_interrupt_before_attachment",
        "error": None, "base_exception_propagated": False,
        "p7_state": "BLOCKED_EXECUTOR_GUARD", "board_release_allowed": False,
        "not_run": ["R01 rerun", "R02 rerun", "P7", "HDL", "RTL simulation", "EDA", "hardware"]}
    executor.write_json(output / "PRELAUNCH.json", record)
    original_init = executor.OwnedJob.__init__
    try:
        policy = json.loads(scope.read_text(encoding="utf-8"))
        require(policy["maximum_group_seconds"] == 90 and policy["targeted_groups_allowed"] == 1,
                "R03_SCOPE_MISMATCH")
        def injected_init(self):
            original_init(self)
            def interrupted_attachment(process):
                raise KeyboardInterrupt("INJECTED_KEYBOARD_INTERRUPT_BEFORE_JOB_ATTACHMENT")
            self.job.attach_and_resume = interrupted_attachment
        executor.OwnedJob.__init__ = injected_init
        try:
            executor.run_software_case("keyboard_interrupt_before_attachment", "timeout_tree", output,
                expected, group_deadline, 4, 1048576)
        except KeyboardInterrupt as interruption:
            require("INJECTED_KEYBOARD_INTERRUPT_BEFORE_JOB_ATTACHMENT" in str(interruption),
                    "WRONG_BASEEXCEPTION_PROPAGATED")
            record["base_exception_propagated"] = True
        else:
            raise AssertionError("BASEEXCEPTION_WAS_SWALLOWED")
        finally:
            executor.OwnedJob.__init__ = original_init
        folder = output / "keyboard_interrupt_before_attachment"
        case = json.loads((folder / "RECEIPT.json").read_text(encoding="utf-8"))
        require(case["base_exception_re_raised"] and case["error"].startswith("KeyboardInterrupt:"),
                "BASEEXCEPTION_RECEIPT_NOT_HONEST")
        require(not case["job_attached_successfully"] and case["root_handle_signaled"],
                "UNATTACHED_ROOT_HANDLE_NOT_SIGNALED")
        require(case["unattached_handle_cleanup"] == "Popen.kill_and_wait_current_handle"
                and case["root_exit_code"] is not None, "CURRENT_HANDLE_CLEANUP_NOT_PROVEN")
        require(case["owned_handles_after_wait"] == [], "UNEXPECTED_JOB_DESCENDANTS")
        require(set(case["logs"]) == {"stdout.raw", "stderr.raw"}, "RAW_STREAMS_MISSING")
        require((folder / "stdout.raw").read_bytes() == b"" and (folder / "stderr.raw").read_bytes() == b"",
                "SUSPENDED_FIXTURE_EXECUTED")
        require(not (folder / "child.ready").exists() and not (folder / "grandchild.ready").exists()
                and not list(folder.glob("ESCAPED_*")), "UNATTACHED_FIXTURE_ESCAPED")
        require(case["inputs_unchanged"] and case["group_deadline_kept"], "CASE_IDENTITY_OR_DEADLINE")
        require(frozen_inputs() == before and time.monotonic() < group_deadline,
                "GROUP_PRE_POST_IDENTITY_OR_DEADLINE")
        record["root_handle_signaled"] = True
        record["fixture_descendant_or_escape_markers"] = 0
        record["case_receipt"] = str(folder / "RECEIPT.json")
        record["result"] = "PASS_ONE_TARGETED_BASEEXCEPTION_FAULT"
    except Exception as error:
        record["error"] = type(error).__name__ + ": " + str(error)
    finally:
        executor.OwnedJob.__init__ = original_init
        record["inputs_after"] = frozen_inputs()
        record["inputs_unchanged"] = record["inputs_before"] == record["inputs_after"]
        record["elapsed_seconds"] = round(time.monotonic() - started, 6)
        record["exit_code"] = 0 if record["result"] == "PASS_ONE_TARGETED_BASEEXCEPTION_FAULT" else 1
        executor.write_json(output / "RECEIPT.json", record)
        print(json.dumps({key: record[key] for key in ("result", "level", "elapsed_seconds", "exit_code", "error")}))
    return record["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
