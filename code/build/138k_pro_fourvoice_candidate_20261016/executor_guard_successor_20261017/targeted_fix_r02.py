"""Two new fault-injection cases for the ownership-before-metadata repair."""

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
    inputs["targeted_script"] = executor.identity(Path(__file__))
    return inputs


def main():
    start = time.monotonic()
    group_deadline = start + 90
    output = executor.EVIDENCE / "RUN_02"
    output.mkdir(exist_ok=False)
    expected = executor.snapshot()
    before = frozen_inputs()
    scope = executor.EVIDENCE / "LOCAL_EXECUTION_SCOPE_R02.json"
    record = {"schema": "m2_executor_guard_targeted_repair_v1", "result": "FAIL_PARTIAL",
        "created_utc": datetime.now(timezone.utc).isoformat(), "maximum_seconds": 90,
        "level": "L1_SOFTWARE_FAULT_INJECTION_ONLY", "inputs_before": before,
        "scope_identity": executor.identity(scope), "cases": [], "error": None,
        "p7_state": "BLOCKED_EXECUTOR_GUARD", "board_release_allowed": False,
        "not_run": ["RUN_01 rerun", "P7", "HDL", "RTL simulation", "EDA", "hardware"]}
    executor.write_json(output / "PRELAUNCH.json", record)
    original_write_json = executor.write_json
    original_attach = None
    try:
        policy = json.loads(scope.read_text(encoding="utf-8"))
        require(policy["maximum_group_seconds"] == 90 and policy["targeted_groups_allowed"] == 1,
                "R02_SCOPE_MISMATCH")
        # Fail the first post-attachment launch-metadata write. Per-case START and
        # terminal receipt writes stay enabled to preserve both raw streams.
        def injected_write_failure(path, value):
            if Path(path).name == "LAUNCHED_ATTACHED.json":
                raise OSError("INJECTED_LAUNCH_METADATA_WRITE_FAILURE")
            return original_write_json(path, value)

        executor.write_json = injected_write_failure
        case = executor.run_software_case("metadata_write_failure", "timeout_tree", output,
            expected, group_deadline, 4, 1048576)
        executor.write_json = original_write_json
        require(case["error"] is not None and "INJECTED_LAUNCH_METADATA_WRITE_FAILURE" in case["error"],
                "METADATA_FAILURE_NOT_INJECTED")
        require(case["job_attached_successfully"] and case["root_handle_signaled"],
                "METADATA_FAILURE_OWNERSHIP_OR_TERMINATION")
        require(case["cleanup"]["mechanism"] == "KILL_ON_JOB_CLOSE"
                and case["inputs_unchanged"], "METADATA_FAILURE_CLEANUP_OR_IDENTITY")
        require(set(case["logs"]) == {"stdout.raw", "stderr.raw"}, "METADATA_FAILURE_RAW_STREAMS_MISSING")
        record["cases"].append({"case": "metadata_write_failure", "result": "PASS_EXPECTED_FAULT",
                                  "receipt": str(output / "metadata_write_failure/RECEIPT.json")})

        # Replace only the helper entry on this new Job instance. It raises
        # before assignment, exercising cleanup via the current Popen handle.
        original_job_init = executor.OwnedJob.__init__
        def injected_init(self):
            original_job_init(self)
            def reject_attachment(process):
                raise OSError("INJECTED_FAILURE_BEFORE_JOB_ATTACHMENT")
            self.job.attach_and_resume = reject_attachment

        original_attach = original_job_init
        executor.OwnedJob.__init__ = injected_init
        case = executor.run_software_case("before_attachment_failure", "normal", output,
            expected, group_deadline, 4, 1048576)
        executor.OwnedJob.__init__ = original_job_init
        original_attach = None
        require(case["error"] is not None and "INJECTED_FAILURE_BEFORE_JOB_ATTACHMENT" in case["error"],
                "ATTACHMENT_FAILURE_NOT_INJECTED")
        require(not case["job_attached_successfully"] and case["root_handle_signaled"],
                "UNATTACHED_ROOT_NOT_TERMINATED")
        require(case["unattached_handle_cleanup"] == "Popen.kill_and_wait_current_handle"
                and case["root_exit_code"] is not None, "OWN_POPEN_HANDLE_CLEANUP_NOT_PROVEN")
        require(case["inputs_unchanged"] and set(case["logs"]) == {"stdout.raw", "stderr.raw"},
                "ATTACHMENT_FAILURE_IDENTITY_OR_STREAMS")
        record["cases"].append({"case": "before_attachment_failure", "result": "PASS_EXPECTED_FAULT",
                                  "receipt": str(output / "before_attachment_failure/RECEIPT.json")})
        require(time.monotonic() <= group_deadline, "GROUP_DEADLINE_EXCEEDED")
        require(frozen_inputs() == before, "PRE_POST_SOURCE_IDENTITY_CHANGED")
        record["result"] = "PASS_TWO_TARGETED_SOFTWARE_FAULTS"
    except Exception as error:
        record["error"] = type(error).__name__ + ": " + str(error)
    finally:
        executor.write_json = original_write_json
        if original_attach is not None:
            executor.OwnedJob.__init__ = original_attach
        record["inputs_after"] = frozen_inputs()
        record["inputs_unchanged"] = record["inputs_before"] == record["inputs_after"]
        record["elapsed_seconds"] = round(time.monotonic() - start, 6)
        record["exit_code"] = 0 if record["result"] == "PASS_TWO_TARGETED_SOFTWARE_FAULTS" else 1
        executor.write_json(output / "RECEIPT.json", record)
        print(json.dumps({key: record[key] for key in ("result", "level", "elapsed_seconds", "exit_code", "error")}))
    return record["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
