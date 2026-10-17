"""R06 TX/clock/reset checker over canonical public observations.

The checker never infers TX identity from PCM equality or from a commit.  A
TX frame is identified only by the explicit TX-adoption sidecar and is checked
against an independent transaction/adoption calendar and PCM oracle.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


CANONICAL_FIELDS = (
    "cycle", "epoch", "rst_n", "frame_tick", "event_valid",
    "event_ready", "event_data", "apply_valid", "apply_event_seq",
    "apply_data", "occupied_mask", "releasing_mask", "note_on_mask",
    "note_off_mask", "retire_mask", "slot_sources", "slot_channels",
    "slot_notes", "slot_generations", "req_valid", "req_ready",
    "req_id", "advance_mask", "advance_frame_req_id", "result_valid",
    "result_ready", "result_id", "result_left", "result_right",
    "result_clip_mask", "commit", "commit_id", "commit_left",
    "commit_right", "commit_clip", "cancel", "cancel_reason",
    "config_valid", "config_ready", "config_payload",
    "effect_input_valid", "effect_input_ready", "effect_input_id",
    "effect_input_left", "effect_input_right", "effect_input_clip_mask",
    "tx_sample_valid", "tx_frame_id", "tx_req_id", "tx_left",
    "tx_right", "tx_clip", "tx_hold", "tx_startup_zero", "bclk", "ws",
    "din", "pll_locked", "audio_stable", "pa_en", "finish",
)
TRACE_FIELDS = set(CANONICAL_FIELDS) | {"time_ps"}
INTEGER_FIELDS = TRACE_FIELDS - {"cancel_reason", "config_payload"}
BIT_FIELDS = {
    "rst_n", "frame_tick", "event_valid", "event_ready", "apply_valid",
    "req_valid", "req_ready", "result_valid", "result_ready", "commit",
    "cancel", "config_valid", "config_ready", "effect_input_valid",
    "effect_input_ready", "tx_sample_valid", "tx_clip", "tx_hold",
    "tx_startup_zero", "bclk", "ws", "din", "pll_locked",
    "audio_stable", "pa_en", "finish",
}
PCM24_FIELDS = {
    "result_left", "result_right", "commit_left", "commit_right",
    "effect_input_left", "effect_input_right", "tx_left", "tx_right",
}


class Reject(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


class Pending(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Reject("JSON_OBJECT_REQUIRED", str(path))
    return value


def load_trace(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                raise Reject("BLANK_TRACE_LINE", str(line_number))
            row = json.loads(line)
            if not isinstance(row, dict):
                raise Reject("TRACE_ROW_OBJECT", str(line_number))
            missing = sorted(TRACE_FIELDS - set(row))
            unknown = sorted(set(row) - TRACE_FIELDS)
            if missing:
                raise Reject("MISSING_TRACE_FIELD", f"line={line_number}:{missing}")
            if unknown:
                raise Reject("UNKNOWN_TRACE_FIELD", f"line={line_number}:{unknown}")
            row["__line"] = line_number
            rows.append(row)
    if not rows:
        raise Reject("EMPTY_TRACE")
    return rows


def integer(row: dict[str, Any], field: str) -> int:
    value = row[field]
    if isinstance(value, bool):
        return int(value)
    if not isinstance(value, int):
        raise Reject("UNKNOWN_OR_NONINTEGER", f"line={row['__line']},field={field}")
    return value


def load_decoder(path: Path, expected_sha256: str):
    if sha256(path) != expected_sha256:
        raise Reject("PIN_DECODER_IDENTITY")
    spec = importlib.util.spec_from_file_location("m3_r06_pinned_decoder", path)
    if spec is None or spec.loader is None:
        raise Reject("PIN_DECODER_LOAD")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if sha256(path) != expected_sha256:
        raise Reject("PIN_DECODER_CHANGED")
    return module


def validate_authority(binding: dict[str, Any], calendar: dict[str, Any],
                       frame_plan: dict[str, Any], oracle: dict[str, Any]) -> str:
    if binding.get("schema") != "M3_R06_TX_CLOCK_RESET_BINDING_V1":
        raise Reject("BINDING_SCHEMA")
    mode = binding.get("mode")
    if mode == "SYNTHETIC_SELFTEST_ONLY":
        expected = {
            "trace_authority": "SYNTHETIC_FIXTURE",
            "tx_sidecar_authority": "SYNTHETIC_EXPLICIT_SIDECAR",
            "pins_authority": "SYNTHETIC_PIN_STREAM",
            "timebase_authority": "SYNTHETIC_40MHZ_TIMEBASE",
            "finish_authority": "SYNTHETIC_EXPLICIT_FINISH",
        }
        pass_status = "PASS_SYNTHETIC_FIXTURE_ONLY"
    elif mode == "REAL_PUBLIC_TRACE":
        expected = {
            "trace_authority": "REAL_PUBLIC_TRACE",
            "tx_sidecar_authority": "M2_FROZEN_TX_SIDECAR",
            "pins_authority": "REAL_PUBLIC_PINS",
            "timebase_authority": "REAL_CAPTURE_TIMEBASE",
            "finish_authority": "M2_FROZEN_FINISH",
        }
        pass_status = "PASS_REAL_PUBLIC_TRACE"
    else:
        raise Pending("PENDING_TRACE_AUTHORITY")
    pending_codes = {
        "trace_authority": "PENDING_TRACE_AUTHORITY",
        "tx_sidecar_authority": "PENDING_TX_SIDECAR",
        "pins_authority": "PENDING_PUBLIC_PINS",
        "timebase_authority": "PENDING_TIMEBASE",
        "finish_authority": "PENDING_FINISH_CONTRACT",
    }
    for key, value in expected.items():
        if binding.get(key) != value:
            raise Pending(pending_codes[key])
    if calendar.get("schema") != "M3_R06_TX_TRANSACTION_CALENDAR_V1":
        raise Pending("PENDING_EVENT_CALENDAR")
    if calendar.get("authority") not in {
        "SYNTHETIC_INDEPENDENT_CALENDAR", "M3_R6_5_REAL_LEDGER"
    } or not calendar.get("independent_of_trace"):
        raise Pending("PENDING_EVENT_CALENDAR")
    if not calendar.get("tx_selection_plan_authoritative"):
        raise Pending("PENDING_TX_SELECTION_PLAN")
    if frame_plan.get("schema") != "M3_R06_TX_FRAME_PLAN_V1" or not frame_plan.get(
        "independent_of_trace"
    ):
        raise Pending("PENDING_FRAME_PLAN")
    if frame_plan.get("authority") not in {
        "SYNTHETIC_INDEPENDENT_PLAN", "M2_FROZEN_FRAME_PLAN"
    }:
        raise Pending("PENDING_FRAME_PLAN")
    if oracle.get("schema") != "M3_R06_PCM24_ORACLE_V1" or oracle.get(
        "authority"
    ) not in {"SYNTHETIC_INDEPENDENT_ORACLE", "M1_READONLY_GOLDEN"}:
        raise Pending("PENDING_PCM_ORACLE")
    return pass_status


def verify_input_hashes(binding: dict[str, Any], paths: dict[str, Path]) -> None:
    declared = binding.get("inputs_sha256")
    if not isinstance(declared, dict):
        raise Reject("INPUT_SHA_TABLE")
    for name, path in paths.items():
        if declared.get(name) != sha256(path):
            raise Reject("INPUT_SHA_MISMATCH", name)


def analyze(binding: dict[str, Any], calendar: dict[str, Any],
            frame_plan: dict[str, Any], oracle: dict[str, Any],
            rows: list[dict[str, Any]], decoder_module) -> dict[str, Any]:
    status = validate_authority(binding, calendar, frame_plan, oracle)
    clock_hz = binding.get("clock_hz")
    if clock_hz != 40_000_000 or binding.get("sample_phase") != "SYS_POSEDGE_PRE_NBA":
        raise Reject("CLOCK_OR_SAMPLE_PHASE")
    if binding.get("serial_format") != "PT8211_32BIT_SLOT_LSBJ16_WS_LOW_RIGHT_HIGH_LEFT":
        raise Reject("SERIAL_FORMAT")
    if binding.get("pcm24_to_pcm16") != "SATURATE((PCM24+128)//256)":
        raise Reject("QUANTIZATION_CONTRACT")

    prior_cycle = None
    prior_time = None
    for row in rows:
        for field in INTEGER_FIELDS:
            integer(row, field)
        if any(integer(row, field) not in (0, 1) for field in BIT_FIELDS):
            raise Reject("BIT_RANGE", str(row["__line"]))
        if any(not -(1 << 23) <= integer(row, field) < (1 << 23)
               for field in PCM24_FIELDS):
            raise Reject("PCM24_RANGE", str(row["__line"]))
        cycle = integer(row, "cycle")
        time_ps = integer(row, "time_ps")
        if prior_cycle is not None:
            if cycle != prior_cycle + 1:
                raise Reject("CYCLE_GAP_OR_DUPLICATE", str(cycle))
            if time_ps - prior_time != 25_000:
                raise Reject("TIMEBASE_NOT_40MHZ", str(cycle))
        prior_cycle, prior_time = cycle, time_ps

    expected_transactions = {}
    for item in calendar.get("transactions", []):
        required = {"epoch", "req_id", "request_cycle", "result_cycle",
                    "commit_cycle", "cancel_cycle"}
        if set(item) != required:
            raise Reject("CALENDAR_TRANSACTION_FIELDS")
        key = (item["epoch"], item["req_id"])
        if key in expected_transactions:
            raise Reject("CALENDAR_DUPLICATE_TRANSACTION", str(key))
        done = item["result_cycle"] if item["result_cycle"] is not None else item["cancel_cycle"]
        if done is None or done - item["request_cycle"] >= 833:
            raise Reject("INTERNAL_COMPLETION_AGE_NOT_LT_833", str(key))
        if item["commit_cycle"] is not None and item["result_cycle"] is None:
            raise Reject("CALENDAR_COMMIT_WITHOUT_RESULT", str(key))
        expected_transactions[key] = item

    tx_plan = {}
    for item in calendar.get("tx_expectations", []):
        required = {"epoch", "cycle", "kind", "req_id"}
        if set(item) != required or item["kind"] not in {"STARTUP", "NEW", "HOLD"}:
            raise Reject("TX_EXPECTATION_FIELDS")
        key = (item["epoch"], item["cycle"])
        if key in tx_plan:
            raise Reject("TX_EXPECTATION_DUPLICATE", str(key))
        if item["kind"] == "STARTUP" and item["req_id"] is not None:
            raise Reject("TX_EXPECTATION_STARTUP_ID")
        if item["kind"] != "STARTUP" and not isinstance(item["req_id"], int):
            raise Reject("TX_EXPECTATION_ID")
        tx_plan[key] = item

    golden = {}
    for item in oracle.get("records", []):
        if set(item) != {"epoch", "req_id", "left", "right", "clip"}:
            raise Reject("ORACLE_FIELDS")
        key = (item["epoch"], item["req_id"])
        if key in golden:
            raise Reject("ORACLE_DUPLICATE_ID", str(key))
        decoder_module.quantize(item["left"])
        decoder_module.quantize(item["right"])
        if item["clip"] not in (0, 1):
            raise Reject("ORACLE_CLIP", str(key))
        golden[key] = item

    expected_frames = {
        item["epoch"]: item["cycles"] for item in frame_plan.get("epochs", [])
    }
    observed_frames: dict[int, list[int]] = {}
    public: dict[tuple[int, int], dict[str, Any]] = {}
    live_key = None
    pin_ledger: dict[tuple[int, int], dict[str, Any]] = {}
    pins = decoder_module.PinDecoder(pin_ledger)
    adopted = set()
    held: dict[str, Any] | None = None
    tx_records = []
    finish_rows = []
    reset_truncated = []
    previous_epoch = rows[0]["epoch"]

    for row in rows:
        cycle = integer(row, "cycle")
        epoch = integer(row, "epoch")
        if epoch < previous_epoch or epoch > previous_epoch + 1:
            raise Reject("EPOCH_SEQUENCE", f"{previous_epoch}->{epoch}")
        if epoch != previous_epoch and integer(row, "rst_n"):
            raise Reject("EPOCH_CHANGE_WITHOUT_RESET", str(cycle))
        previous_epoch = epoch

        if not integer(row, "rst_n"):
            if integer(row, "pa_en") or integer(row, "bclk") or integer(row, "ws") or integer(row, "din"):
                raise Reject("RESET_NOT_SERIAL_SILENT", str(cycle))
            if integer(row, "tx_sample_valid"):
                raise Reject("TX_VALID_DURING_RESET", str(cycle))
            if live_key is not None:
                expected = expected_transactions.get(live_key)
                if expected is None or expected["cancel_cycle"] != cycle:
                    raise Reject("RESET_OPEN_TRANSACTION_NOT_DECLARED", str(live_key))
                public[live_key]["state"] = "RESET_CANCELED"
                live_key = None
            if pins.bits or pins.right_half:
                reset_truncated.append({"epoch": epoch, "cycle": cycle,
                                        "status": "RESET_TRUNCATED_UNKNOWN"})
            held = None
        if (not integer(row, "pll_locked") or not integer(row, "audio_stable")) and integer(row, "pa_en"):
            raise Reject("PA_ENABLED_WHILE_UNSAFE", str(cycle))

        request = integer(row, "req_valid") and integer(row, "req_ready")
        result = integer(row, "result_valid") and integer(row, "result_ready")
        if request:
            key = (epoch, integer(row, "req_id"))
            expected = expected_transactions.get(key)
            if live_key is not None or expected is None or expected["request_cycle"] != cycle:
                raise Reject("REQUEST_NOT_IN_CALENDAR", str(key))
            live_key = key
            public[key] = {"epoch": epoch, "req_id": key[1],
                           "request_cycle": cycle, "state": "REQUESTED"}
            pin_ledger[key] = {"epoch": epoch, "request_id": key[1],
                               "request_cycle": cycle}
        if result:
            key = (epoch, integer(row, "result_id"))
            expected = expected_transactions.get(key)
            if live_key != key or expected is None or expected["result_cycle"] != cycle:
                raise Reject("RESULT_NOT_IN_CALENDAR", str(key))
            public[key]["result_cycle"] = cycle
            public[key]["completion_age"] = cycle - public[key]["request_cycle"]
            if public[key]["completion_age"] >= 833:
                raise Reject("INTERNAL_COMPLETION_AGE_NOT_LT_833", str(key))
            public[key]["state"] = "RETURNED"
        if integer(row, "commit"):
            key = (epoch, integer(row, "commit_id"))
            expected = expected_transactions.get(key)
            if live_key != key or expected is None or expected["commit_cycle"] != cycle:
                raise Reject("COMMIT_NOT_IN_CALENDAR", str(key))
            if public[key]["state"] != "RETURNED":
                raise Reject("COMMIT_BEFORE_RESULT", str(key))
            value = golden.get(key)
            if value is None or (integer(row, "commit_left"), integer(row, "commit_right"),
                                 integer(row, "commit_clip")) != (
                    value["left"], value["right"], value["clip"]):
                raise Reject("COMMIT_ORACLE_MISMATCH", str(key))
            public[key]["commit_cycle"] = cycle
            public[key]["state"] = "COMMITTED_NOT_YET_TX"
            live_key = None
        if integer(row, "cancel"):
            if live_key is None:
                raise Reject("CANCEL_WITHOUT_OPEN_TRANSACTION", str(cycle))
            expected = expected_transactions[live_key]
            if expected["cancel_cycle"] != cycle:
                raise Reject("CANCEL_NOT_IN_CALENDAR", str(live_key))
            public[live_key]["cancel_cycle"] = cycle
            public[live_key]["completion_age"] = cycle - public[live_key]["request_cycle"]
            if public[live_key]["completion_age"] >= 833:
                raise Reject("INTERNAL_COMPLETION_AGE_NOT_LT_833", str(live_key))
            public[live_key]["state"] = "CANCELED"
            live_key = None

        try:
            pins.observe(row)
        except (ValueError, KeyError) as exc:
            raise Reject("PIN_" + str(exc), f"epoch={epoch},cycle={cycle}") from exc

        if integer(row, "frame_tick"):
            observed_frames.setdefault(epoch, []).append(cycle)
            if not integer(row, "tx_sample_valid"):
                raise Reject("FRAME_WITHOUT_TX_ADOPTION", f"{epoch}:{cycle}")
            expected_tx = tx_plan.get((epoch, cycle))
            if expected_tx is None:
                raise Reject("TX_ADOPTION_NOT_PLANNED", f"{epoch}:{cycle}")
            startup = bool(integer(row, "tx_startup_zero"))
            hold = bool(integer(row, "tx_hold"))
            if startup:
                if expected_tx["kind"] != "STARTUP" or hold or integer(row, "tx_req_id") != 0:
                    raise Reject("STARTUP_ZERO_ID_OR_FLAGS", f"{epoch}:{cycle}")
                if any(integer(row, field) for field in ("tx_left", "tx_right", "tx_clip")):
                    raise Reject("STARTUP_ZERO_DATA", f"{epoch}:{cycle}")
                selected = {"epoch": epoch, "cycle": cycle,
                            "frame_id": integer(row, "tx_frame_id"),
                            "request_id": None, "left": 0, "right": 0,
                            "clip": 0, "kind": "STARTUP"}
                held = None
            else:
                key = (epoch, integer(row, "tx_req_id"))
                if expected_tx["req_id"] != key[1]:
                    raise Reject("TX_ID_NOT_IN_SELECTION_PLAN", str(key))
                value = golden.get(key)
                if value is None:
                    raise Reject("TX_ID_WITHOUT_ORACLE", str(key))
                if (integer(row, "tx_left"), integer(row, "tx_right"),
                        integer(row, "tx_clip")) != (
                        value["left"], value["right"], value["clip"]):
                    raise Reject("TX_PCM_OR_CLIP_MISMATCH", str(key))
                if hold:
                    if expected_tx["kind"] != "HOLD" or held is None or (
                        held["request_id"], held["left"], held["right"], held["clip"]
                    ) != (key[1], value["left"], value["right"], value["clip"]):
                        raise Reject("HOLD_NOT_EXACT_INHERITANCE", str(key))
                else:
                    if expected_tx["kind"] != "NEW" or key in adopted:
                        raise Reject("NEW_TX_ADOPTION_MISMATCH", str(key))
                    record = public.get(key)
                    if record is None or record["state"] != "COMMITTED_NOT_YET_TX" or record[
                        "commit_cycle"
                    ] >= cycle:
                        raise Reject("TX_BEFORE_EXPLICIT_COMMIT", str(key))
                    adopted.add(key)
                    record["state"] = "TX_ADOPTED"
                    record["tx_cycle"] = cycle
                    record["request_to_tx_cycles"] = cycle - record["request_cycle"]
                selected = {"epoch": epoch, "cycle": cycle,
                            "frame_id": integer(row, "tx_frame_id"),
                            "request_id": key[1], "left": value["left"],
                            "right": value["right"], "clip": value["clip"],
                            "kind": "HOLD" if hold else "NEW"}
                held = selected
            tx_records.append(selected)
            pins.current_sample = {
                "cycle": cycle, "epoch": epoch, "left": selected["left"],
                "right": selected["right"], "id": selected["request_id"],
                "frame": selected["frame_id"],
            }
        elif integer(row, "tx_sample_valid"):
            raise Reject("TX_VALID_OFF_FRAME", f"{epoch}:{cycle}")

        if integer(row, "finish"):
            finish_rows.append({"epoch": epoch, "cycle": cycle})

    for key, expected in expected_transactions.items():
        actual = public.get(key)
        if actual is None:
            raise Reject("MISSING_CALENDAR_TRANSACTION", str(key))
        if expected["commit_cycle"] is not None and "commit_cycle" not in actual:
            raise Reject("MISSING_COMMIT", str(key))
        if expected["cancel_cycle"] is not None and actual["state"] not in {"CANCELED", "RESET_CANCELED"}:
            raise Reject("MISSING_CANCEL", str(key))

    for epoch in sorted(set(expected_frames) | set(observed_frames)):
        expected = expected_frames.get(epoch, [])
        observed = observed_frames.get(epoch, [])
        if observed != expected:
            missing = sorted(set(expected) - set(observed))
            extra = sorted(set(observed) - set(expected))
            code = "MISSING_FRAME_AFTER_IDLE_OR_CANCEL" if missing else "DUPLICATE_OR_EXTRA_FRAME"
            raise Reject(code, f"epoch={epoch},missing={missing},extra={extra}")
        gaps = [b - a for a, b in zip(observed, observed[1:])]
        if any(gap not in (833, 834) for gap in gaps):
            raise Reject("FRAME_INTERVAL_NOT_833_OR_834", str(epoch))
        for offset in range(max(0, len(gaps) - 2)):
            if sum(gaps[offset:offset + 3]) != 2500:
                raise Reject("FRAME_48K_DISTRIBUTION", str(epoch))

    if len(finish_rows) != 1:
        raise Reject("MISSING_OR_DUPLICATE_FINISH", str(len(finish_rows)))
    if finish_rows[0] != frame_plan.get("finish"):
        raise Reject("FINISH_MISMATCH", str(finish_rows[0]))
    if live_key is not None or any(item["state"] in {
        "REQUESTED", "RETURNED", "COMMITTED_NOT_YET_TX"
    } for item in public.values()):
        raise Reject("FINISH_WITH_UNFINISHED_TRANSACTION")
    if pins.bits or pins.right_half:
        raise Reject("FINISH_WITH_PARTIAL_SERIAL")

    complete_frames = pins.frames
    if not complete_frames:
        raise Reject("NO_COMPLETE_SERIAL_FRAME")
    complete_by_id = {(frame["epoch"], frame["request_id"])
                      for frame in complete_frames if frame["request_id"] is not None}
    for key, item in public.items():
        if item["state"] == "TX_ADOPTED":
            item["serial_disposition"] = (
                "COMPLETE" if key in complete_by_id else "RESET_TRUNCATED_UNKNOWN"
            )
    observed_gaps = [b["cycle"] - a["cycle"] for a, b in zip(tx_records, tx_records[1:])
                     if a["epoch"] == b["epoch"]]
    elapsed_ps = sum(gap * 25_000 for gap in observed_gaps)
    measured_rate = (len(observed_gaps) * 1_000_000_000_000 / elapsed_ps
                     if elapsed_ps else None)
    if measured_rate is None or not 47_990 <= measured_rate <= 48_010:
        raise Reject("TIMESTAMP_SAMPLE_RATE_NOT_48K", str(measured_rate))

    return {
        "schema": "M3_R06_TX_CLOCK_RESET_REPORT_V1",
        "status": status,
        "real_pro_tx_pass": status == "PASS_REAL_PUBLIC_TRACE",
        "clock_hz": clock_hz,
        "timestamp_sample_rate_hz": measured_rate,
        "bclk_per_lrclk_rising_edges": 64,
        "serial_format": binding["serial_format"],
        "quantization": binding["pcm24_to_pcm16"],
        "transactions": [public[key] for key in sorted(public)],
        "tx_adoptions": tx_records,
        "serial_frames": complete_frames,
        "serial_half_frames": pins.halves,
        "reset_truncated_unknown": reset_truncated,
        "finish": finish_rows[0],
        "counts": {
            "rows": len(rows), "frames": len(tx_records),
            "complete_serial_frames": len(complete_frames),
            "transactions": len(public), "startup_frames": sum(
                item["kind"] == "STARTUP" for item in tx_records),
            "hold_frames": sum(item["kind"] == "HOLD" for item in tx_records),
        },
        "claims": {
            "commit_is_tx_adoption": False,
            "pcm_equality_used_for_identity": False,
            "eof_is_finish": False,
            "wav_rate_used_as_fpga_lrclk": False,
            "analog_audio_verified": False,
            "board_release_allowed": False,
        },
    }


def run_files(paths: dict[str, Path], decoder_path: Path, decoder_sha: str,
              output: Path) -> tuple[int, dict[str, Any]]:
    identities = {name: {"path": str(path), "sha256": sha256(path)}
                  for name, path in paths.items()}
    try:
        binding = load_json(paths["binding"])
        verify_input_hashes(binding, {name: path for name, path in paths.items()
                                     if name != "binding"})
        module = load_decoder(decoder_path, decoder_sha)
        report = analyze(binding, load_json(paths["calendar"]),
                         load_json(paths["frame_plan"]), load_json(paths["oracle"]),
                         load_trace(paths["trace"]), module)
        code = 0
    except Pending as exc:
        report = {"schema": "M3_R06_TX_CLOCK_RESET_REPORT_V1",
                  "status": exc.code, "detail": exc.detail,
                  "real_pro_tx_pass": False}
        code = 3
    except (Reject, ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        diagnostic = exc.code if isinstance(exc, Reject) else str(exc)
        detail = exc.detail if isinstance(exc, Reject) else ""
        report = {"schema": "M3_R06_TX_CLOCK_RESET_REPORT_V1",
                  "status": "REJECT", "error": diagnostic, "detail": detail,
                  "real_pro_tx_pass": False}
        code = 2
    report["inputs"] = identities
    report["pin_decoder"] = {"path": str(decoder_path), "sha256": decoder_sha}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return code, report


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("binding", "calendar", "frame-plan", "oracle", "trace"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--decoder", required=True, type=Path)
    parser.add_argument("--decoder-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    paths = {"binding": args.binding, "calendar": args.calendar,
             "frame_plan": args.frame_plan, "oracle": args.oracle,
             "trace": args.trace}
    code, report = run_files(paths, args.decoder, args.decoder_sha256, args.output)
    print(json.dumps({"status": report["status"],
                      "error": report.get("error"), "exit_code": code}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
