"""One bounded synthetic software group for M3-R6-6."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from fixtures import binding as make_binding
from fixtures import build_documents
from tx_clock_reset_checker import Pending, Reject, analyze, load_decoder, run_files


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def save_trace(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, separators=(",", ":")) + "\n")


def mutation_hash(binding: dict[str, Any], calendar: dict[str, Any],
                  frame_plan: dict[str, Any], oracle: dict[str, Any],
                  rows: list[dict[str, Any]]) -> str:
    packed = json.dumps({"binding": binding, "calendar": calendar,
                         "frame_plan": frame_plan, "oracle": oracle,
                         "rows": rows}, sort_keys=True, separators=(",", ":"))
    return digest_bytes(packed.encode("utf-8"))


def apply_mutation(name: str, binding: dict[str, Any], calendar: dict[str, Any],
                   frame_plan: dict[str, Any], oracle: dict[str, Any],
                   rows: list[dict[str, Any]]) -> None:
    if name == "none":
        return
    if name == "pending_tx_sidecar":
        binding["tx_sidecar_authority"] = "MISSING"
        return
    if name == "pending_public_pins":
        binding["pins_authority"] = "MISSING"
        return
    if name == "pending_timebase":
        binding["timebase_authority"] = "WAV_HEADER_NOT_FPGA_TIMEBASE"
        return
    if name == "pending_event_calendar":
        calendar["authority"] = "MISSING"
        return
    if name == "pending_pcm_oracle":
        oracle["authority"] = "MISSING"
        return
    if name == "pending_frame_plan":
        frame_plan["authority"] = "MISSING"
        return
    if name == "pending_finish_eof":
        binding["finish_authority"] = "EOF_ONLY"
        next(row for row in rows if row["finish"])["finish"] = 0
        return
    if name == "startup_has_request_id":
        next(row for row in rows if row["tx_startup_zero"])["tx_req_id"] = 9
        return
    if name == "hold_clip_changed":
        row = next(row for row in rows if row["tx_hold"])
        row["tx_clip"] ^= 1
        return
    if name == "commit_marked_as_tx":
        row = next(row for row in rows if row["commit"] and not row["frame_tick"])
        row.update({"tx_sample_valid": 1, "tx_frame_id": 99,
                    "tx_req_id": row["commit_id"], "tx_left": row["commit_left"],
                    "tx_right": row["commit_right"], "tx_clip": row["commit_clip"]})
        return
    if name == "same_pcm_wrong_id":
        target = next(item for item in calendar["tx_expectations"]
                      if item["epoch"] == 1 and item["kind"] == "NEW"
                      and item["req_id"] == 1)
        row = next(row for row in rows if row["epoch"] == 1
                   and row["cycle"] == target["cycle"])
        row["tx_req_id"] = 0
        return
    if name == "internal_age_833":
        item = next(item for item in calendar["transactions"]
                    if item["result_cycle"] is not None)
        item["result_cycle"] = item["request_cycle"] + 833
        item["commit_cycle"] = item["result_cycle"] + 1
        return
    if name == "missing_frame_after_cancel":
        cancel = next(item for item in calendar["transactions"]
                      if item["cancel_cycle"] is not None and item["result_cycle"] is None
                      and item["epoch"] == 0)
        epoch_plan = next(item for item in frame_plan["epochs"]
                          if item["epoch"] == cancel["epoch"])
        after = next(cycle for cycle in epoch_plan["cycles"] if cycle > cancel["cancel_cycle"])
        epoch_plan["cycles"][epoch_plan["cycles"].index(after)] = after + 1
        return
    if name == "duplicate_frame_plan":
        epoch_plan = next(item for item in frame_plan["epochs"] if len(item["cycles"]) > 2)
        epoch_plan["cycles"].insert(2, epoch_plan["cycles"][1])
        return
    if name == "reset_pin_not_silent":
        next(row for row in rows if not row["rst_n"] and row["cycle"] > 1)["din"] = 1
        return
    if name == "pa_enabled_before_lock":
        next(row for row in rows if row["rst_n"] and not row["pll_locked"])["pa_en"] = 1
        return
    if name == "serial_bit_corruption":
        first_new = next(item for item in calendar["tx_expectations"]
                         if item["kind"] == "NEW")
        start = first_new["cycle"] + 80
        falling = None
        for index in range(1, len(rows)):
            if rows[index]["cycle"] < start:
                continue
            if rows[index - 1]["bclk"] == 1 and rows[index]["bclk"] == 0:
                falling = index
                break
        if falling is None:
            raise AssertionError("no falling edge for mutation")
        next_falling = next(index for index in range(falling + 1, len(rows))
                            if rows[index - 1]["bclk"] == 1
                            and rows[index]["bclk"] == 0)
        for index in range(falling, next_falling):
            rows[index]["din"] ^= 1
        return
    if name == "finish_with_unconsumed_commit":
        item = next(item for item in calendar["transactions"]
                    if item["epoch"] == 0 and item["req_id"] == 0)
        cutoff = item["commit_cycle"]
        del rows[next(index for index, row in enumerate(rows)
                      if row["cycle"] == cutoff) + 1:]
        for row in rows:
            row["finish"] = int(row["cycle"] == cutoff)
        calendar["transactions"] = [item]
        calendar["tx_expectations"] = [tx for tx in calendar["tx_expectations"]
                                       if tx["epoch"] == 0 and tx["cycle"] < cutoff]
        frame_plan["epochs"] = [{"epoch": 0, "cycles": [
            cycle for cycle in frame_plan["epochs"][0]["cycles"] if cycle < cutoff
        ]}]
        frame_plan["finish"] = {"epoch": 0, "cycle": cutoff}
        oracle["records"] = [record for record in oracle["records"]
                             if record["epoch"] == 0 and record["req_id"] == 0]
        return
    if name == "duplicate_finish":
        next(row for row in rows if row["epoch"] == 2
             and row["cycle"] == rows[-1]["cycle"] - 1)["finish"] = 1
        return
    raise AssertionError(name)


def evaluate(decoder, binding: dict[str, Any], calendar: dict[str, Any],
             frame_plan: dict[str, Any], oracle: dict[str, Any],
             rows: list[dict[str, Any]]) -> tuple[int, dict[str, Any]]:
    try:
        report = analyze(binding, calendar, frame_plan, oracle, rows, decoder)
        return 0, report
    except Pending as exc:
        return 3, {"status": exc.code, "detail": exc.detail}
    except Reject as exc:
        return 2, {"status": "REJECT", "error": exc.code, "detail": exc.detail}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--decoder", required=True, type=Path)
    parser.add_argument("--decoder-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cases = json.loads(args.cases.read_text(encoding="utf-8"))["cases"]
    decoder = load_decoder(args.decoder, args.decoder_sha256)
    base_calendar, base_frame_plan, base_oracle, base_rows = build_documents()

    valid_dir = args.output / "valid_synthetic"
    valid_dir.mkdir()
    save_json(valid_dir / "calendar.json", base_calendar)
    save_json(valid_dir / "frame_plan.json", base_frame_plan)
    save_json(valid_dir / "oracle.json", base_oracle)
    save_trace(valid_dir / "trace.jsonl", base_rows)
    input_sha = {
        name: hashlib.sha256((valid_dir / filename).read_bytes()).hexdigest()
        for name, filename in {"calendar": "calendar.json",
                               "frame_plan": "frame_plan.json",
                               "oracle": "oracle.json",
                               "trace": "trace.jsonl"}.items()
    }
    base_binding = make_binding(input_sha)
    save_json(valid_dir / "binding.json", base_binding)
    paths = {"binding": valid_dir / "binding.json",
             "calendar": valid_dir / "calendar.json",
             "frame_plan": valid_dir / "frame_plan.json",
             "oracle": valid_dir / "oracle.json", "trace": valid_dir / "trace.jsonl"}
    valid_code, valid_report = run_files(
        paths, args.decoder, args.decoder_sha256, valid_dir / "report.json"
    )

    results = []
    for case in cases:
        if case["mutation"] == "none":
            code, report = valid_code, valid_report
        else:
            binding = copy.deepcopy(base_binding)
            calendar = copy.deepcopy(base_calendar)
            frame_plan = copy.deepcopy(base_frame_plan)
            oracle = copy.deepcopy(base_oracle)
            rows = copy.deepcopy(base_rows)
            apply_mutation(case["mutation"], binding, calendar, frame_plan, oracle, rows)
            code, report = evaluate(decoder, binding, calendar, frame_plan, oracle, rows)
            save_json(args.output / "cases" / f"{case['name']}.json", {
                "schema": "M3_R06_TX_CLOCK_RESET_CASE_RESULT_V1",
                "name": case["name"], "mutation": case["mutation"],
                "mutated_input_sha256": mutation_hash(
                    binding, calendar, frame_plan, oracle, rows
                ),
                "exit_code": code, "report": report,
            })
        ok = code == case["exit"] and report.get("status") == case.get(
            "status", "REJECT"
        )
        if "error" in case:
            ok = ok and report.get("error") == case["error"]
        if "error_prefix" in case:
            ok = ok and str(report.get("error", "")).startswith(case["error_prefix"])
        results.append({"name": case["name"], "exit_code": code,
                        "status": report.get("status"),
                        "error": report.get("error"), "matched": ok})

    if not all(item["matched"] for item in results):
        status = "FAIL"
        exit_code = 1
    else:
        status = "PASS"
        exit_code = 0
    summary = {
        "schema": "M3_R06_TX_CLOCK_RESET_SELFTEST_V1",
        "status": status, "cases": len(results),
        "matched": sum(item["matched"] for item in results),
        "synthetic_passes": sum(item["status"] == "PASS_SYNTHETIC_FIXTURE_ONLY"
                                for item in results),
        "pending_cases": sum(str(item["status"]).startswith("PENDING_")
                             for item in results),
        "rejected_cases": sum(item["status"] == "REJECT" for item in results),
        "real_trace_cases": 0, "hdl_sim_eda_hardware_calls": 0,
        "results": results,
    }
    save_json(args.output / "summary.json", summary)
    print(json.dumps(summary))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
