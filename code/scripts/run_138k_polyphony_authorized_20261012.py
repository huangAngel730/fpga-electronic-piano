"""One trusted user-authorized synthesis attempt; original receipt stays locked.

Specific approval: 2026-10-12, exact prepared N32/R1, run syn only, 900 seconds,
new output, no retry, PnR, STA or device operations. This is a separate successor
entry, not an edit to V0282's frozen receipt or V0287's locked CLI.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import run_138k_polyphony_synthesis_once as controller

ROOT = controller.prepared.ROOT
PROJECT = ROOT / "code/build/138k_polyphony_resource/prepared/N32_R1_20261011_01"
OUTPUT = ROOT / "code/output/M2_N32R1_authorized_syn_20261012_01"
AUTH_DIR = ROOT / "code/build/138k_polyphony_resource/authorization_20261012"
CONTROLLER_SHA = "735b00911b3c0aa96997a9a02fef1c81da5fadc9ee09388bb5c15859ad5ecabe"
FROZEN_SHA = "883297182d9705788d5d04855b597ad8620ab2b1b8ca38727a8b06492a0454e9"
TOOL_SHA = "4c172d4c0d2a4c7ef5c764d091a315cbcde2127573554bfd7d09ac6f2e5ea535"
AUTH_TEXT = "允许M2对已准备的精确N32/R1资源工程执行一次仅综合，总上限900秒，使用全新结果目录，失败不自动重试；不包含PnR、STA或设备操作。"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_scope():
    if digest(Path(controller.__file__)) != CONTROLLER_SHA:
        raise ValueError("EXACT_ORIGINAL_CONTROLLER_SHA")
    if digest(PROJECT / "frozen_receipt.json") != FROZEN_SHA:
        raise ValueError("EXACT_ORIGINAL_FROZEN_SHA")
    record = controller.prepared.verify(PROJECT)
    if record["configuration"] != dict(N=32, response=1, profile="audio_and_public_read_no_injection"):
        raise ValueError("EXACT_N32_R1_PROFILE")
    if record["synthesis_authorized"] is not False:
        raise ValueError("OLD_RECEIPT_PERMISSION_CHANGED")
    if record["tool"]["identities"]["shell"]["sha256"] != TOOL_SHA:
        raise ValueError("EXACT_GW_SH_SHA")
    if OUTPUT.exists():
        raise ValueError("REFUSE_EXISTING_ATTEMPT")
    if (AUTH_DIR / "consumed.json").exists():
        raise ValueError("ONE_APPROVAL_ALREADY_CONSUMED_NO_RETRY")
    return record


def approval_record(record):
    return dict(schema=1, user_instruction=AUTH_TEXT, instruction_source="Human user instruction in this chat on 2026-10-12",
                project=str(PROJECT), output=str(OUTPUT), configuration=record["configuration"],
                original_frozen_sha256=FROZEN_SHA, original_controller_sha256=CONTROLLER_SHA,
                successor_entry_sha256=digest(Path(__file__)), tool_sha256=TOOL_SHA,
                attempt_count_allowed=1, total_seconds=900, stage="run syn only",
                retry=False, PnR=False, STA=False, device=False,
                original_frozen_permission_modified=False)


def execute():
    start = time.monotonic()
    record = verify_scope()
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    approval = approval_record(record)
    controller.write_new(AUTH_DIR / "consumed.json", dict(
        approval=approval, consumed_at_UTC=datetime.now(timezone.utc).isoformat(),
        state="reserved_before_tool_start_even_failure_consumes_attempt"))
    remaining = 900 - (time.monotonic() - start)
    if remaining <= 0:
        raise ValueError("AUTHORIZATION_PREFLIGHT_BUDGET_EXHAUSTED_NO_RETRY")
    # Only this exact authenticated successor may cross the private test seam.
    # No arbitrary project, tool, timeout or stub parameters are accepted.
    result = controller._execute_one(PROJECT, OUTPUT, authorized=True,
                                     timeout_seconds=remaining)
    controller.write_new(OUTPUT / "authorization_receipt.json", dict(
        approval=approval, total_elapsed_seconds=time.monotonic()-start,
        tool_runs=result["tool_runs"], tool_exit=result.get("tool_exit_code"),
        controller_exit=result["exit_code"], timed_out=result["timed_out"],
        original_frozen_sha_after=digest(PROJECT / "frozen_receipt.json"),
        command=[sys.executable, *sys.argv], emergency_timeout_cleanup_may_follow_deadline=True,
        new_resource_admission=False, physical_STA=False, board_release_allowed=False))
    print(json.dumps({k:result.get(k) for k in (
        "status","exit_code","tool_runs","tool_exit_code","timed_out","diagnostic")},ensure_ascii=False))
    return result["exit_code"]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args()
    try:
        if args.execute:
            return execute()
        record=verify_scope()
        print(json.dumps(dict(status="EXACT_APPROVED_SUCCESSOR_PREFLIGHT", approval=approval_record(record)),ensure_ascii=False,indent=2))
        return 0
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        print(json.dumps(dict(status="REJECT_OR_FAILURE_NO_RETRY",diagnostic=str(error)),ensure_ascii=False))
        return 1


if __name__=="__main__": raise SystemExit(main())
