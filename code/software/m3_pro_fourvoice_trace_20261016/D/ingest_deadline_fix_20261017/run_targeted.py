"""One bounded D3 deadline regression group; synthetic software inputs only.

This script is deliberately independent of all historical runners and budgets.
It creates RUN_01 once, freezes inputs, and launches only the fixed Python intake
entrypoints. It does not invoke acquisition, RTL, EDA, or device tools.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / (
    "code/docs/test/m3_pro_fourvoice_trace_20261016/D/"
    "ingest_deadline_fix_20261017/RUN_01"
)
OLD_SOURCE = HERE / "before_ingest.py"
NEW_SOURCE = HERE.parent / "ingest/ingest.py"
DECODER = ROOT / (
    "code/software/m3_40mhz_pcm_i2s_latency_20261015/"
    "night_20261016/RESUME_R02/consume_capture.py"
)
COUNTEREXAMPLE = ROOT / (
    "code/docs/test/m2_pro_offline_review_20261017/D3_COUNTEREXAMPLE.json"
)
OLD_SOURCE_SHA = "3217f97e57daec534306a213c64566fa111e3116f15a15967ca881847c218e07"
DECODER_SHA = "da91462e8421719e09ffab60d7bbe38d4ee05ac1793ea70e1f09c7a69ccda0cb"
CASE_TIMEOUT_SECONDS = 5.0
GROUP_TIMEOUT_SECONDS = 90.0
CONTRACT = {
    "schema": "M3_PRO_OBSERVER_REQUIREMENTS_V1",
    "package": "FPG676",
    "clock_hz": 40000000,
    "sampling_phase": "SYS_EDGE_ORDERED_EVENTS_V1",
    "pa_active": 1,
    "identity_only": True,
}


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def identity(path: Path) -> dict:
    path = path.resolve(strict=True)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}


def sources() -> dict:
    return {
        "harness": identity(Path(__file__)),
        "python": identity(Path(sys.executable)),
        "old_source": identity(OLD_SOURCE),
        "new_source": identity(NEW_SOURCE),
        "decoder": identity(DECODER),
        "original_counterexample": identity(COUNTEREXAMPLE),
    }


def event(kind: str, cycle: int, epoch: int = 0, **values: int) -> dict:
    return {"kind": kind, "cycle": cycle, "epoch": epoch, **values}


def calendar(requests: list[dict]) -> dict:
    return {
        "schema": "M3_PRO_INTAKE_CALENDAR_V1",
        "provenance": "SYNTHETIC_FIXTURE",
        "requests": requests,
    }


def request(req_id: int, cycle: int) -> dict:
    return {"epoch": 0, "req_id": req_id, "cycle": cycle, "lane_mask": 15}


def case(name: str, rows: list[dict], requests: dict, failure: str | None = None,
         *, baseline: bool = False) -> dict:
    return {
        "name": name,
        "trace": rows,
        "calendar": requests,
        "expected_exit_code": 0 if failure is None else 1,
        "expected_first_failure": failure,
        "baseline_known_bug": baseline,
        "source": str(OLD_SOURCE if baseline else NEW_SOURCE),
    }


def build_cases(original: dict) -> list[dict]:
    """Exactly 24 new cases plus the original old-source counterexample."""
    original_rows = copy.deepcopy(original["trace"])
    original_calendar = copy.deepcopy(original["calendar"])
    cases = [case(
        "00_old_original_counterexample", original_rows, original_calendar,
        baseline=True,
    )]
    # Original first-transaction prefix ends with RETURN. The positive boundary
    # cases move only RETURN to request age 832, preserving FRAME 833/834.
    normal_prefix = copy.deepcopy(original_rows[:12])
    normal_prefix[-1]["cycle"] = 10 + 832
    one_calendar = calendar([request(7, 10)])
    for gap in (833, 834):
        rows = copy.deepcopy(normal_prefix)
        if gap == 834:
            rows.extend([
                event("PA", 10 + 833, rst_n=1, stable=1, pa_en=1),
                event("PA", 10 + 834, rst_n=1, stable=1, pa_en=1),
            ])
        rows.extend([
            event("FRAME", 10 + gap, frame_id=1),
            event("CONSUME", 10 + gap, req_id=7, frame_id=1),
            event("END", 11 + gap),
        ])
        cases.append(case(f"normal_consume_age{gap}", rows, one_calendar))

    # Prefix is copied from the original counterexample through the second
    # REQUEST. State variations add ACCEPT/four lane ticks/RETURN as needed.
    def second_prefix(state: str) -> list[dict]:
        lengths = {"REQUESTED": 16, "ACCEPTED": 21, "RETURNED": 22}
        return copy.deepcopy(original_rows[:lengths[state]])

    two_calendar = copy.deepcopy(original_calendar)
    for state in ("REQUESTED", "ACCEPTED", "RETURNED"):
        rows = second_prefix(state)
        rows.extend([
            event("CANCEL", 1677 + 832, req_id=8),
            event("END", 1677 + 833),
        ])
        cases.append(case(f"cancel832_{state.lower()}", rows, two_calendar))
        rows = second_prefix(state)
        rows.extend([
            event("RESET", 1677 + 832, epoch=1),
            event("END", 1677 + 833, epoch=1),
        ])
        cases.append(case(f"reset832_{state.lower()}", rows, two_calendar))

    for state in ("REQUESTED", "ACCEPTED", "RETURNED"):
        rows = second_prefix(state)
        rows.append(event("CANCEL", 1677 + 833, req_id=8))
        if state == "REQUESTED":
            # If a same-edge cleanup were wrongly accepted, this later FRAME
            # would conceal the missing deadline. Cleanup must reject first.
            rows.append(event("FRAME", 1677 + 833, frame_id=3))
        rows.append(event("END", 1677 + 833))
        cases.append(case(
            f"cancel833_{state.lower()}", rows, two_calendar,
            "CANCEL_AFTER_UNOBSERVED_DEADLINE",
        ))
        rows = second_prefix(state)
        rows.append(event("RESET", 1677 + 833, epoch=1))
        if state == "REQUESTED":
            rows.append(event("FRAME", 1677 + 833, epoch=1, frame_id=0))
        rows.append(event("END", 1677 + 833, epoch=1))
        cases.append(case(
            f"reset833_{state.lower()}", rows, two_calendar,
            "RESET_AFTER_UNOBSERVED_DEADLINE",
        ))

    for age, state in ((834, "ACCEPTED"), (835, "RETURNED")):
        rows = second_prefix(state)
        rows.extend([
            event("CANCEL", 1677 + age, req_id=8),
            event("END", 1677 + age + 1),
        ])
        # This exact age835 RETURNED case is also the original counterexample.
        if age == 835:
            assert rows == original_rows
            assert two_calendar == original_calendar
        cases.append(case(
            f"cancel{age}_{state.lower()}", rows, two_calendar,
            "CANCEL_AFTER_UNOBSERVED_DEADLINE",
        ))
        rows = second_prefix(state)
        rows.extend([
            event("RESET", 1677 + age, epoch=1),
            event("END", 1677 + age + 1, epoch=1),
        ])
        cases.append(case(
            f"reset{age}_{state.lower()}", rows, two_calendar,
            "RESET_AFTER_UNOBSERVED_DEADLINE",
        ))

    for age in (833, 834):
        rows = second_prefix("ACCEPTED")
        rows.extend([
            event("RETURN", 1677 + age, req_id=8, left=0, right=0),
            event("END", 1677 + age + 1),
        ])
        cases.append(case(
            f"return_age{age}", rows, two_calendar,
            "RETURN_AFTER_UNOBSERVED_DEADLINE",
        ))
    rows = second_prefix("RETURNED")
    rows.append(event("END", 1677 + 835))
    cases.append(case("end835_pending", rows, two_calendar, "UNFINISHED_TRANSACTION"))
    for kind, failure in (
        ("CANCEL", "CANCEL_AFTER_DUE_FRAME"),
        ("RESET", "RESET_UNCONSUMED_DUE_FRAME"),
        ("END", "UNFINISHED_TRANSACTION"),
    ):
        rows = second_prefix("RETURNED")
        rows.append(event("FRAME", 1677 + 833, frame_id=3))
        if kind == "CANCEL":
            rows.append(event(kind, 1677 + 833, req_id=8))
            rows.append(event("END", 1677 + 833))
        elif kind == "RESET":
            rows.append(event(kind, 1677 + 833, epoch=1))
            rows.append(event("END", 1677 + 833, epoch=1))
        else:
            rows.append(event(kind, 1677 + 833))
        cases.append(case(f"due_frame_then_{kind.lower()}", rows, two_calendar, failure))
    assert len(cases) == 25
    assert sum(c["baseline_known_bug"] for c in cases) == 1
    assert sum(c["expected_exit_code"] == 0 and not c["baseline_known_bug"] for c in cases) == 8
    assert sum(c["expected_exit_code"] == 1 for c in cases) == 16
    assert len({c["name"] for c in cases}) == 25
    return cases


def make_fixture(item: dict) -> dict:
    case_dir = OUTPUT / item["name"]
    case_dir.mkdir()
    inputs = case_dir / "inputs"
    inputs.mkdir()
    # These payloads are intentionally marked placeholders. They establish file
    # identity only and cannot be interpreted as Pro RTL, ROM, or M1 golden data.
    (inputs / "source.txt").write_text(
        "SYNTHETIC_FIXTURE_PLACEHOLDER; NOT_PRO_RTL; NOT_M1_GOLDEN\n",
        encoding="utf-8", newline="\n",
    )
    (inputs / "rom.txt").write_text(
        "SYNTHETIC_FIXTURE_PLACEHOLDER; NOT_PRO_ROM; NOT_M1_GOLDEN\n",
        encoding="utf-8", newline="\n",
    )
    write_json(inputs / "contract.json", CONTRACT)
    write_json(inputs / "calendar.json", item["calendar"])
    (inputs / "trace.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in item["trace"]),
        encoding="utf-8", newline="\n",
    )
    roles = {
        "source": "source.txt", "rom": "rom.txt", "contract": "contract.json",
        "calendar": "calendar.json", "trace": "trace.jsonl",
    }
    artifacts = []
    for role, filename in roles.items():
        path = inputs / filename
        artifacts.append({
            "role": role, "path": filename,
            "bytes": path.stat().st_size, "sha256": sha(path),
        })
    manifest = {
        "schema": "M3_PRO_INTAKE_V1", "provenance": "SYNTHETIC_FIXTURE",
        "clock_hz": 40000000, "sampling_phase": "SYS_EDGE_ORDERED_EVENTS_V1",
        "package": "FPG676", "artifacts": artifacts,
    }
    manifest_path = inputs / "manifest.json"
    write_json(manifest_path, manifest)
    argv = [
        sys.executable, "-B", "-X", "utf8", item["source"],
        str(manifest_path), "--sha256", sha(manifest_path),
    ]
    # Only this Python executable and one of these two pinned script paths can
    # be launched. Neither audited entrypoint creates child processes.
    assert Path(argv[0]).resolve() == Path(sys.executable).resolve()
    assert Path(argv[4]).resolve() in {OLD_SOURCE.resolve(), NEW_SOURCE.resolve()}
    return {
        **{k: v for k, v in item.items() if k not in ("trace", "calendar")},
        "argv": argv, "cwd": str(ROOT),
        "inputs": {p.name: identity(p) for p in sorted(inputs.iterdir())},
    }


def run_case(item: dict, group_started: float) -> dict:
    case_dir = OUTPUT / item["name"]
    record = {
        **item, "started_utc": utc(), "timeout": False,
        "case_timeout_seconds": CASE_TIMEOUT_SECONDS,
        "group_timeout_seconds": GROUP_TIMEOUT_SECONDS,
        "execution_scope": "L1_SYNTHETIC_SOFTWARE_ONLY",
        "pro_dut_pass": False, "board_release_allowed": False,
    }
    write_json(case_dir / "COMMAND.json", record)
    remaining = GROUP_TIMEOUT_SECONDS - (time.monotonic() - group_started)
    if remaining <= 0:
        raise RuntimeError("GROUP_BUDGET_EXHAUSTED_BEFORE_LAUNCH")
    started = time.monotonic()
    with (case_dir / "stdout.raw").open("wb", buffering=0) as stdout:
        with (case_dir / "stderr.raw").open("wb", buffering=0) as stderr:
            process = subprocess.Popen(
                item["argv"], cwd=ROOT, stdin=subprocess.DEVNULL,
                stdout=stdout, stderr=stderr, shell=False,
            )
            try:
                exit_code = process.wait(timeout=min(CASE_TIMEOUT_SECONDS, remaining))
            except subprocess.TimeoutExpired:
                record["timeout"] = True
                process.kill()
                exit_code = process.wait(timeout=CASE_TIMEOUT_SECONDS)
            finally:
                # Keep ownership cleanup on non-ordinary exceptions as well.
                # This is the Popen object created above, never a looked-up PID.
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=CASE_TIMEOUT_SECONDS)
    record.update({
        "finished_utc": utc(), "elapsed_seconds": time.monotonic() - started,
        "actual_exit_code": exit_code,
        "stdout": identity(case_dir / "stdout.raw"),
        "stderr": identity(case_dir / "stderr.raw"),
    })
    stdout_text = (case_dir / "stdout.raw").read_text(encoding="utf-8")
    stderr_text = (case_dir / "stderr.raw").read_text(encoding="utf-8")
    try:
        result = json.loads(stdout_text if exit_code == 0 else stderr_text)
        record["actual_json"] = result
        record["actual_first_failure"] = result.get("first_failure")
        proper_claims = (
            result.get("pro_dut_pass") is False
            and result.get("board_release_allowed") is False
        )
        if item["expected_exit_code"] == 0:
            content_matches = (
                result.get("status") == "INTAKE_FIXTURE_PASS"
                and result.get("provenance") == "SYNTHETIC_FIXTURE"
                and result.get("level") == "L1" and not stderr_text
            )
        else:
            content_matches = (
                result.get("status") == "REJECT" and not stdout_text
                and result.get("first_failure") == item["expected_first_failure"]
            )
        record["expectation_met"] = bool(
            not record["timeout"] and proper_claims and content_matches
            and exit_code == item["expected_exit_code"]
        )
    except (ValueError, TypeError, AttributeError) as exc:
        record["expectation_met"] = False
        record["output_parse_error"] = repr(exc)
    record["input_identities_unchanged"] = item["inputs"] == {
        p.name: identity(p) for p in sorted((case_dir / "inputs").iterdir())
    }
    record["expectation_met"] = bool(
        record["expectation_met"] and record["input_identities_unchanged"]
    )
    record["status"] = (
        "KNOWN_BUG_REPRODUCED" if item["baseline_known_bug"] and record["expectation_met"]
        else "PASS" if record["expectation_met"] else "FAIL"
    )
    write_json(case_dir / "RECEIPT.json", record)
    return record


def main() -> int:
    if OUTPUT.exists():
        print("RUN_01_ALREADY_EXISTS; no modification or launch", file=sys.stderr)
        return 2
    OUTPUT.mkdir(parents=True)
    started_utc = utc()
    started = time.monotonic()
    results = []
    before = None
    failure = None
    try:
        before = sources()
        if before["old_source"]["sha256"] != OLD_SOURCE_SHA:
            raise RuntimeError("OLD_SOURCE_IDENTITY_MISMATCH")
        if before["decoder"]["sha256"] != DECODER_SHA:
            raise RuntimeError("DECODER_IDENTITY_MISMATCH")
        if before["new_source"]["sha256"] == OLD_SOURCE_SHA:
            raise RuntimeError("NEW_SOURCE_IS_UNMODIFIED_OLD_VERSION")
        original = json.loads(COUNTEREXAMPLE.read_text(encoding="utf-8"))
        if original["source_sha256"] != OLD_SOURCE_SHA:
            raise RuntimeError("COUNTEREXAMPLE_SOURCE_IDENTITY_MISMATCH")
        items = [make_fixture(item) for item in build_cases(original)]
        write_json(OUTPUT / "PRELAUNCH.json", {
            "status": "FROZEN_BEFORE_FIRST_LAUNCH", "utc": utc(),
            "cwd": str(ROOT), "sources": before, "cases": items,
            "new_cases": 24, "new_positive": 8, "new_rejections": 16,
            "baseline_known_bug": 1, "planned_cli_launches": 25,
            "group_timeout_seconds": GROUP_TIMEOUT_SECONDS,
            "case_timeout_seconds": CASE_TIMEOUT_SECONDS,
            "provenance": "SYNTHETIC_FIXTURE",
            "pro_dut_pass": False, "board_release_allowed": False,
        })
        for item in items:
            # Freeze source equality at every boundary, not just at group end.
            if sources() != before:
                raise RuntimeError("SOURCE_CHANGED_BEFORE_CASE_" + item["name"])
            results.append(run_case(item, started))
            if sources() != before:
                raise RuntimeError("SOURCE_CHANGED_AFTER_CASE_" + item["name"])
    except BaseException as exc:
        failure = {"type": type(exc).__name__, "message": str(exc)}
        (OUTPUT / "HARNESS_FAILURE.txt").write_text(
            traceback.format_exc(), encoding="utf-8", newline="\n",
        )
    try:
        after = sources()
        unchanged = before is not None and before == after
    except (OSError, ValueError) as exc:
        after, unchanged = {"identity_error": repr(exc)}, False
    elapsed = time.monotonic() - started
    passed = (
        failure is None and unchanged and len(results) == 25
        and all(item["expectation_met"] for item in results)
        and elapsed <= GROUP_TIMEOUT_SECONDS
    )
    write_json(OUTPUT / "POST.json", {
        "utc": utc(), "sources": after, "sources_unchanged": unchanged,
        "pro_dut_pass": False, "board_release_allowed": False,
    })
    receipt = {
        "status": "PASS" if passed else "FAIL",
        "scope_result": "24_TARGETED_AND_OLD_BUG_REPRODUCED",
        "exit_code": 0 if passed else 1,
        "started_utc": started_utc, "finished_utc": utc(),
        "elapsed_seconds": elapsed,
        "level": "L1_SYNTHETIC_SOFTWARE_DEADLINE_ONLY",
        "new_cases": 24, "new_positive": 8, "new_rejections": 16,
        "baseline_known_bug": 1, "actual_cli_launches": len(results),
        "group_timeout_seconds": GROUP_TIMEOUT_SECONDS,
        "case_timeout_seconds": CASE_TIMEOUT_SECONDS,
        "sources_unchanged": unchanged, "harness_failure": failure,
        "pro_dut_pass": False, "board_release_allowed": False,
        "results": results,
    }
    write_json(OUTPUT / "RECEIPT.json", receipt)
    print(json.dumps({
        "status": receipt["status"], "exit_code": receipt["exit_code"],
        "elapsed_seconds": elapsed, "actual_cli_launches": len(results),
        "receipt": str(OUTPUT / "RECEIPT.json"),
        "pro_dut_pass": False, "board_release_allowed": False,
    }, ensure_ascii=False))
    return receipt["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
