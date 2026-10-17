"""R7 F/first-valid/A calendar candidate for R6-5.

L0 / NOT_RUN.  Reads the additive R6-3 R7 ledger and the unique canonical
FRAME_PLAN.  It never derives a frame schedule from observed rows and never
requires acceptance or M1 advance on the F edge.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


LEDGER_SCHEMA = "M3_R63_R07_INTAKE_REPORT_V1"
PLAN_SCHEMA = "M3_R06_UNIQUE_FRAME_PLAN_V1"
REPORT_SCHEMA = "M3_R65_R07_CALENDAR_REPORT_V1"
PLAN_FORMULA = (
    "n_k=ceil(128*k*2**32/659706977); "
    "cycle_k=release_cycle+n_k-1; k>=1"
)
PLAN_RULES_SHA256 = (
    "3c968a151b0b5369f9dd95465761b2d87449c29975b1fca914f81fc5cfd01560"
)
PLAN_PARAMETERS = {
    "acc_bits": 32,
    "phase_step": 659706977,
    "core_hz_candidate": 40000000,
    "half_bclk_toggles_per_frame": 128,
    "initial_state": {"accumulator": 0, "bclk": 0, "slot_count": 0},
}


class CalendarReject(ValueError):
    """Malformed or contradictory ledger/plan evidence."""


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CalendarReject("ROOT_NOT_OBJECT")
    return value


def _int(value: Any, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise CalendarReject(f"{label}_INVALID")
    return value


def _is_sha256(value: Any) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _plan_identity_payload(plan: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema", "formula", "rules_sha256", "input_sha256",
        "source_identities", "parameters", "epochs", "finish",
    }
    if not required.issubset(plan):
        raise CalendarReject("FRAME_PLAN_IDENTITY_FIELDS")
    return {key: plan[key] for key in (
        "schema", "formula", "rules_sha256", "input_sha256",
        "source_identities", "parameters", "epochs", "finish",
    )}


def _expected_cycles(
        plan: dict[str, Any]) -> tuple[dict[int, list[int]], dict[int, int]]:
    if plan.get("schema") != PLAN_SCHEMA or plan.get("independent_of_trace") is not True:
        raise CalendarReject("FRAME_PLAN_SCHEMA_OR_INDEPENDENCE")
    if (plan.get("formula") != PLAN_FORMULA
            or plan.get("rules_sha256") != PLAN_RULES_SHA256):
        raise CalendarReject("FRAME_PLAN_FROZEN_RULES")
    if not _is_sha256(plan.get("input_sha256")):
        raise CalendarReject("FRAME_PLAN_INPUT_SHA")
    source_identities = plan.get("source_identities")
    if not isinstance(source_identities, list) or not source_identities:
        raise CalendarReject("FRAME_PLAN_SOURCE_IDENTITIES")
    for index, source in enumerate(source_identities):
        if (not isinstance(source, dict)
                or set(source) != {"path", "sha256"}
                or not isinstance(source.get("path"), str)
                or not source["path"]
                or not _is_sha256(source.get("sha256"))):
            raise CalendarReject(f"FRAME_PLAN_SOURCE_IDENTITY_{index}")
    payload = _plan_identity_payload(plan)
    identity_sha = _sha256_bytes(_canonical_bytes(payload))
    if plan.get("canonical_identity_sha256") != identity_sha:
        raise CalendarReject("FRAME_PLAN_IDENTITY_SHA")
    if plan.get("canonical_plan_id") != f"sha256:{identity_sha}":
        raise CalendarReject("FRAME_PLAN_ID")

    parameters = plan.get("parameters")
    if not isinstance(parameters, dict) or parameters != PLAN_PARAMETERS:
        raise CalendarReject("FRAME_PLAN_PARAMETERS")
    acc_bits = _int(parameters.get("acc_bits"), "ACC_BITS", 1)
    phase_step = _int(parameters.get("phase_step"), "PHASE_STEP", 1)
    toggles = _int(parameters.get("half_bclk_toggles_per_frame"),
                   "TOGGLES_PER_FRAME", 1)
    initial = parameters.get("initial_state")
    if initial != {"accumulator": 0, "bclk": 0, "slot_count": 0}:
        raise CalendarReject("FRAME_PLAN_INITIAL_STATE")
    modulus = 1 << acc_bits

    expected: dict[int, list[int]] = {}
    window_end_exclusive: dict[int, int] = {}
    previous_stop = None
    epochs = plan.get("epochs")
    if not isinstance(epochs, list):
        raise CalendarReject("FRAME_PLAN_EPOCHS")
    for index, item in enumerate(epochs):
        if not isinstance(item, dict):
            raise CalendarReject(f"FRAME_PLAN_EPOCH_{index}_SHAPE")
        if set(item) != {
                "epoch", "window_kind", "reset_assert_cycle", "release_cycle",
                "stop_cycle", "cycles"}:
            raise CalendarReject(f"FRAME_PLAN_EPOCH_{index}_FIELDS")
        epoch = _int(item.get("epoch"), f"FRAME_PLAN_EPOCH_{index}")
        reset_cycle = _int(item.get("reset_assert_cycle"),
                           f"FRAME_PLAN_RESET_{index}")
        stop_cycle = _int(item.get("stop_cycle"),
                          f"FRAME_PLAN_STOP_{index}")
        kind = item.get("window_kind")
        cycles = item.get("cycles")
        if epoch != index or not isinstance(cycles, list):
            raise CalendarReject(f"FRAME_PLAN_EPOCH_{index}_ORDER")
        if previous_stop is not None and reset_cycle != previous_stop + 1:
            raise CalendarReject(f"FRAME_PLAN_EPOCH_{index}_GAP")
        if reset_cycle > stop_cycle:
            raise CalendarReject(f"FRAME_PLAN_EPOCH_{index}_WINDOW")
        if kind == "RESET_ONLY":
            if item.get("release_cycle") is not None or cycles:
                raise CalendarReject(f"FRAME_PLAN_EPOCH_{index}_RESET_ONLY")
            recalculated: list[int] = []
        elif kind == "ACTIVE":
            release = _int(item.get("release_cycle"),
                           f"FRAME_PLAN_RELEASE_{index}")
            if not (reset_cycle <= release <= stop_cycle):
                raise CalendarReject(f"FRAME_PLAN_EPOCH_{index}_WINDOW")
            recalculated = []
            frame_index = 1
            while True:
                numerator = toggles * frame_index * modulus
                edge = (numerator + phase_step - 1) // phase_step
                cycle = release + edge - 1
                if cycle > stop_cycle:
                    break
                recalculated.append(cycle)
                frame_index += 1
        else:
            raise CalendarReject(f"FRAME_PLAN_EPOCH_{index}_KIND")
        if cycles != recalculated:
            raise CalendarReject(f"FRAME_PLAN_EPOCH_{index}_FORMULA")
        expected[epoch] = list(cycles)
        window_end_exclusive[epoch] = stop_cycle + 1
        previous_stop = stop_cycle

    if not expected:
        raise CalendarReject("FRAME_PLAN_NO_EPOCHS")
    finish = plan.get("finish")
    last = epochs[-1]
    if finish != {"epoch": last["epoch"], "cycle": last["stop_cycle"]}:
        raise CalendarReject("FRAME_PLAN_FINISH")
    return expected, window_end_exclusive


def analyze(ledger: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    if ledger.get("schema") != LEDGER_SCHEMA:
        raise CalendarReject("LEDGER_SCHEMA")
    expected, window_end_exclusive = _expected_cycles(plan)
    pending_reasons = ledger.get("pending_reasons")
    if (not isinstance(pending_reasons, list)
            or any(not isinstance(item, str) for item in pending_reasons)):
        raise CalendarReject("LEDGER_PENDING_REASONS")
    pending = set(pending_reasons)
    if not isinstance(ledger.get("frames"), list):
        raise CalendarReject("LEDGER_FRAMES")
    if ledger.get("origin") not in {
            "SYNTHETIC_SCHEMA_FIXTURE", "HDL_PUBLIC_CAPTURE_UNVERIFIED"}:
        raise CalendarReject("LEDGER_ORIGIN")
    for key in ("transactions", "tx_samples", "raw_frame_cancels",
                "business_cancels"):
        if not isinstance(ledger.get(key), list):
            raise CalendarReject(f"LEDGER_{key.upper()}_LIST")

    observed: dict[int, list[int]] = {epoch: [] for epoch in expected}
    by_epoch: dict[int, list[dict[str, Any]]] = {epoch: [] for epoch in expected}
    for frame in ledger["frames"]:
        epoch = _int(frame.get("epoch"), "FRAME_EPOCH")
        if epoch not in expected:
            raise CalendarReject(f"FRAME_UNKNOWN_EPOCH_{epoch}")
        origin = frame.get("F")
        if not isinstance(origin, dict):
            raise CalendarReject("FRAME_F_MISSING")
        cycle = _int(origin.get("cycle"), "FRAME_F_CYCLE")
        observed[epoch].append(cycle)
        by_epoch[epoch].append(frame)

    for epoch in sorted(expected):
        if observed[epoch] != expected[epoch]:
            missing = sorted(set(expected[epoch]) - set(observed[epoch]))
            extra = sorted(set(observed[epoch]) - set(expected[epoch]))
            raise CalendarReject(
                f"FRAME_COVERAGE_EPOCH_{epoch}:missing={missing}:extra={extra}"
            )

    frame_results = []
    flat_cycles = [(epoch, cycle) for epoch in sorted(expected)
                   for cycle in expected[epoch]]
    next_frame = {
        key: (flat_cycles[index + 1][1]
              if index + 1 < len(flat_cycles)
              and flat_cycles[index + 1][0] == key[0] else None)
        for index, key in enumerate(flat_cycles)
    }
    for epoch in sorted(by_epoch):
        for frame in by_epoch[epoch]:
            f_cycle = frame["F"]["cycle"]
            first_valid = frame.get("first_valid")
            accept = frame.get("A")
            next_cycle = next_frame[(epoch, f_cycle)]
            window_end = (next_cycle if next_cycle is not None
                          else window_end_exclusive[epoch])
            result = {
                "epoch": epoch,
                "frame_ordinal": frame.get("frame_ordinal"),
                "F": frame["F"],
                "first_valid": first_valid,
                "A": accept,
                "req_id": frame.get("req_id"),
                "next_F_cycle": next_cycle,
                "window_end_exclusive": window_end,
                "advance": None,
            }
            fv_cycle = None
            if first_valid is None:
                pending.add("PENDING_FIRST_VALID")
            else:
                fv_cycle = _int(first_valid.get("cycle"), "FIRST_VALID_CYCLE")
                if fv_cycle < f_cycle or fv_cycle >= window_end:
                    raise CalendarReject("FIRST_VALID_OUTSIDE_FRAME_WINDOW")
            if accept is None:
                pending.add("PENDING_ACCEPT_A")
            else:
                a_cycle = _int(accept.get("cycle"), "ACCEPT_CYCLE")
                if fv_cycle is None or a_cycle < fv_cycle:
                    raise CalendarReject("ACCEPT_BEFORE_FIRST_VALID")
                if a_cycle >= window_end:
                    raise CalendarReject("ACCEPT_NOT_BEFORE_NEXT_FRAME")

            advances = frame.get("advance_observations")
            if (not isinstance(advances, list)
                    or any(not isinstance(item, dict) for item in advances)):
                raise CalendarReject("ADVANCE_LIST")
            matching = [item for item in advances
                        if item.get("req_id") == frame.get("req_id")]
            if accept is not None and not matching:
                pending.add("PENDING_M1_ADVANCE")
            elif len(matching) > 1:
                raise CalendarReject("DUPLICATE_M1_ADVANCE")
            elif matching:
                if accept is None:
                    raise CalendarReject("ADVANCE_WITHOUT_ACCEPT")
                advance = matching[0]
                advance_cycle = _int(advance.get("cycle"), "ADVANCE_CYCLE")
                if advance.get("mask") != 0xF:
                    raise CalendarReject("ADVANCE_MASK_NOT_1111")
                if advance_cycle < f_cycle or advance_cycle >= window_end:
                    raise CalendarReject("ADVANCE_OUTSIDE_FRAME_WINDOW")
                result["advance"] = advance
            frame_results.append(result)

    if ledger["business_cancels"]:
        raise CalendarReject("INVENTED_BUSINESS_CANCEL")
    if ledger.get("raw_frame_cancels"):
        pending.add("PENDING_TRANSACTION_CANCEL_RULE")
    if ledger.get("legacy_d3_projection_status") != "PENDING_UNSUPPORTED_PROFILE":
        raise CalendarReject("LEGACY_D3_PROFILE_MUST_REMAIN_PENDING")

    if ledger.get("origin") == "HDL_PUBLIC_CAPTURE_UNVERIFIED":
        pending.add("PENDING_SOURCE_PROVENANCE")
    if plan.get("authority") != "M2_FROZEN_FRAME_PLAN":
        pending.add("PENDING_FRAME_PLAN_ADMISSION")

    status = ("SYNTHETIC_MECHANICS_CANDIDATE" if not pending
              else sorted(pending)[0])
    return {
        "schema": REPORT_SCHEMA,
        "status": status,
        "capture_id": ledger.get("capture_id"),
        "frame_plan_id": plan.get("canonical_plan_id"),
        "frames": frame_results,
        "transactions": ledger.get("transactions", []),
        "tx_samples": ledger.get("tx_samples", []),
        "raw_frame_cancels": ledger.get("raw_frame_cancels", []),
        "business_cancels": ledger.get("business_cancels", []),
        "legacy_d3_projection_status": "PENDING_UNSUPPORTED_PROFILE",
        "pending_reasons": sorted(pending),
        "real_pro_calendar_pass": False,
        "board_release_allowed": False,
    }


def run_files(ledger_path: Path, plan_path: Path,
              output_path: Path) -> dict[str, Any]:
    report = analyze(_load_json(ledger_path), _load_json(plan_path))
    report["inputs"] = {
        "ledger": {"path": str(ledger_path), "sha256": _sha256_file(ledger_path)},
        "frame_plan": {"path": str(plan_path), "sha256": _sha256_file(plan_path)},
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8", newline="\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intake-ledger", required=True, type=Path)
    parser.add_argument("--frame-plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = run_files(args.intake_ledger, args.frame_plan, args.output)
    print(json.dumps({"status": report["status"],
                      "real_pro_calendar_pass": False}))
    return 0 if report["status"] == "SYNTHETIC_MECHANICS_CANDIDATE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
