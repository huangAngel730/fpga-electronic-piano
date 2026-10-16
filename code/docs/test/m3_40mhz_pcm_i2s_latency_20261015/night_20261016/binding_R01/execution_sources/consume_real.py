"""Require A's exact real-run receipt before attributing a raw trace to R05.

Never runs the producer or any simulator. Hashes are integrity/provenance
links, not signatures or an independent guarantee that a forged run occurred.
"""
import argparse
import json
from pathlib import Path
import re

from consume_capture import analyze, parse_json, require, sha256


R05_SHA = "dcf15f5d3ded1a0b160f55eab43066c728f80b3c329c44ea9f099c63f178696a"
TX_SHA = "6c703e31064e5943df4e310b3baddd8935362a1c028828d8e11f8f3c016267ad"


def verify_identity(item):
    require(type(item) is dict and all(k in item for k in ("path", "bytes", "sha256")),
            "IDENTITY_FIELDS")
    path = Path(item["path"])
    require(type(item["bytes"]) is int and path.is_file()
            and path.stat().st_size == item["bytes"] and sha256(path) == item["sha256"],
            "IDENTITY_BYTES_OR_SHA")
    return path


def verify_receipt(path, pinned_sha):
    require(sha256(path) == pinned_sha, "PRODUCER_RECEIPT_SHA")
    receipt = parse_json(Path(path).read_text(encoding="utf-8"))
    require(receipt.get("schema") == "M3_R05_NIGHT_OBSERVATION_RUN_V1"
            and receipt.get("status") == "REAL_CAPTURE_TOOL_PASS_PENDING_INDEPENDENT_VALIDATION"
            and type(receipt.get("exit_code")) is int and receipt["exit_code"] == 0,
            "PRODUCER_RUN_NOT_SUCCESSFUL")
    require(receipt.get("capture_origin") == "REAL_MODELSIM_R05_UART_MIDI_BOARD_PUBLIC_PORTS"
            and receipt.get("functional_attempt_consumed") is True,
            "PRODUCER_ORIGIN_OR_CONSUMPTION")
    require(receipt.get("board_release_allowed") is False, "BOARD_RELEASE_SCOPE")
    for before, after in (("source_before", "source_after"), ("stage_before", "stage_after"),
                          ("tool_before", "tool_after")):
        require(type(receipt.get(before)) is dict and receipt[before]
                and receipt[before] == receipt.get(after), "PRODUCER_IDENTITY_CHANGED")
    require(receipt.get("elapsed_s", float("inf")) <= 900, "PRODUCER_ROUND_BUDGET")
    calls = receipt.get("functional_calls")
    require(type(calls) is list and len(calls) == 3, "PRODUCER_THREE_TOOL_CALLS")
    stage = Path(receipt["stage"])
    expected_args = (("work",), ("-sv", "+incdir+include", "-f", "compile.f"),
                     ("-c", "work.tb_m2_m1td_real_chain", "-do", "run -all; quit -f"))
    for name, call, arguments in zip(("vlib", "vlog", "vsim"), calls, expected_args):
        require(type(call.get("exit_code")) is int and call["exit_code"] == 0
                and call.get("timeout") is False and call.get("error") is None
                and call.get("log_limit_exceeded") is False, "PRODUCER_TOOL_FAILED")
        tool = verify_identity(receipt["tool_before"][name + ".exe"])
        require(call.get("argv") == [str(tool), *arguments]
                and Path(call["cwd"]).resolve() == stage.resolve(), "PRODUCER_ARGV_OR_CWD")
        require(call.get("process_created") is True and 0 <= call.get("elapsed_s", 301) <= 300
                and call.get("step_budget_s") <= 300, "PRODUCER_PROCESS_OR_BUDGET")
        for stream_name in ("stdout", "stderr"):
            raw = verify_identity(call[stream_name]).read_text(encoding="utf-8", errors="replace")
            require(not re.search(r"(?im)^\s*(?:#\s*)?(?:\*\*\s*)?(?:error|fatal|failure)\s*:", raw),
                    "PRODUCER_LOG_ERROR")
            require(all(int(number) == 0 for number in re.findall(r"(?i)\berrors\s*:\s*(\d+)", raw)),
                    "PRODUCER_LOG_ERRORS_NONZERO")
            if name == "vsim" and stream_name == "stdout":
                require(bool(re.search(r"(?m)^\s*(?:#\s*)?PASS tb_m2_m1td_real_chain\b", raw)),
                        "PRODUCER_PASS_MISSING")
    binding_path = verify_identity(receipt["frozen_input_binding"])
    binding = parse_json(binding_path.read_text(encoding="utf-8"))
    require(binding.get("zip_sha256") == R05_SHA, "FROZEN_R05_ZIP_IDENTITY")
    stage_items = receipt["stage_before"]
    tx = stage_items.get("sources/i2s_tx.sv")
    require(tx is not None and tx.get("sha256") == TX_SHA, "TRANSMITTER_SOURCE_IDENTITY")
    originals = binding["compile_units"] + [dict(item, member=member)
                 for member, item in binding["rom_members"].items()]
    for item in originals:
        member = item["member"].removeprefix("inputs/")
        if member == "sources/m2_fourvoice_timbre_delay_board_top.sv":
            continue  # The separately frozen observation-only board copy.
        require(member in stage_items and stage_items[member]["sha256"] == item["sha256"],
                "FROZEN_ALGORITHM_OR_ROM_CHANGED")
    for relative, item in stage_items.items():
        path_item = stage / relative
        require(path_item.is_file() and path_item.stat().st_size == item["bytes"]
                and sha256(path_item) == item["sha256"], "STAGED_SOURCE_BYTES_CHANGED")
    for relative, item in receipt["source_before"].items():
        snapshot = Path(path).parent / "execution_sources" / relative
        require(snapshot.is_file() and snapshot.stat().st_size == item["bytes"]
                and sha256(snapshot) == item["sha256"], "EXECUTED_SOURCE_SNAPSHOT")
    consumed = Path(path).parent.parent / (Path(path).parent.name + "_CONSUMED.json")
    marker = parse_json(consumed.read_text(encoding="utf-8"))
    require(Path(marker["output"]).resolve() == Path(path).parent.resolve()
            and marker.get("new_batch_only") is True and type(marker.get("pid")) is int
            and marker["pid"] > 0, "PRODUCER_CONSUMPTION_MARKER")
    preflight = parse_json(verify_identity(marker["preflight"]).read_text(encoding="utf-8"))
    require(preflight["source_before"] == receipt["source_before"]
            and preflight["stage_before"] == stage_items
            and preflight["tool_before"] == receipt["tool_before"], "PREFLIGHT_RUN_IDENTITY")
    return receipt


def verify_inputs(inputs_path, capture_path, expected_sha):
    require(sha256(inputs_path) == expected_sha, "INPUT_CAPTURE_SHA")
    fields = set("kind cycle time_ns rst_n midi_rx event_valid event_ready event_data_hex "
                 "config_valid config_ready active_voice_count".split())
    flags = "rst_n midi_rx event_valid event_ready config_valid config_ready".split()
    cycle = 0
    previous_time = None
    events = []
    edges = []
    end_seen = False
    with Path(capture_path).open(encoding="utf-8") as cap:
        def audio_ticks():
            for line in cap:
                record = parse_json(line)
                if record.get("kind") == "TICK":
                    yield record
        audio = audio_ticks()
        with Path(inputs_path).open(encoding="utf-8") as stream:
            require(parse_json(stream.readline()) == {"kind": "HEADER",
                "schema": "M3_R05_INPUT_PRE_NBA_V1", "clock_hz": 40000000}, "INPUT_HEADER")
            for line in stream:
                require(not end_seen, "INPUT_AFTER_END")
                row = parse_json(line)
                if row.get("kind") == "END":
                    require(row == {"kind": "END", "cycle": cycle}, "INPUT_END_COUNT")
                    end_seen = True
                    continue
                if row.get("kind") in ("MIDI_EDGE", "RAW_RESET_EDGE"):
                    require(set(row) == {"kind", "time_ns", "value"}
                            and type(row["time_ns"]) is int and row["time_ns"] >= 0
                            and type(row["value"]) is int and row["value"] in (0, 1), "RAW_INPUT_EDGE")
                    edges.append(row)
                    continue
                require(row.get("kind") == "TICK" and set(row) == fields, "INPUT_TICK_FIELDS")
                require(all(type(row[k]) is int for k in fields - {"kind", "event_data_hex"}), "INPUT_X_OR_TYPE")
                cycle += 1
                require(row["cycle"] == cycle and all(row[k] in (0, 1) for k in flags), "INPUT_ORDER_OR_BITS")
                require(row["time_ns"] >= 0 and (previous_time is None
                        or row["time_ns"] - previous_time == 25), "INPUT_40MHZ_TIMEBASE")
                previous_time = row["time_ns"]
                require(type(row["event_data_hex"]) is str
                        and re.fullmatch(r"[0-9a-fA-F]{16}", row["event_data_hex"])
                        and 0 <= row["active_voice_count"] <= 4, "INPUT_EVENT_OR_VOICE_RANGE")
                other = next(audio, None)
                require(other is not None and other["cycle"] == cycle
                        and other["rst_n"] == row["rst_n"], "INPUT_AUDIO_TICK_ALIGNMENT")
                if row["rst_n"] and row["event_valid"] and row["event_ready"]:
                    events.append({"epoch": other["epoch"], "cycle": cycle,
                                   "time_ns": row["time_ns"], "event_data_hex": row["event_data_hex"]})
        require(end_seen and next(audio, None) is None, "INPUT_AUDIO_LENGTH_OR_END")
    require(sha256(inputs_path) == expected_sha, "INPUT_CHANGED_DURING_READ")
    return {"input_sha256": expected_sha, "ticks": cycle, "accepted_events": events,
            "raw_edges": edges, "input_to_analog_latency": "UNKNOWN_NOT_MEASURED",
            "event_to_audible_pcm": "UNKNOWN_NO_AUDIO_GOLDEN_CAUSALITY"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--producer-receipt", type=Path, required=True)
    parser.add_argument("--receipt-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "REFUSE_OVERWRITE")
    try:
        receipt = verify_receipt(args.producer_receipt, args.receipt_sha256)
        capture = verify_identity(receipt["REAL_CAPTURE.jsonl"])
        inputs = verify_identity(receipt["REAL_INPUTS.jsonl"])
        result = analyze(capture, receipt["REAL_CAPTURE.jsonl"]["sha256"])
        result["input_timeline"] = verify_inputs(inputs, capture, receipt["REAL_INPUTS.jsonl"]["sha256"])
        result["evidence_kind"] = "A_REAL_MODELSIM_R05_WITH_VERIFIED_RECEIPT_LINKS"
        result["producer_receipt_sha256"] = args.receipt_sha256
        code = 0
    except (ValueError, OSError, UnicodeError, KeyError, TypeError) as exc:
        result = {"passed": False, "diagnostic": str(exc), "board_release_allowed": False}
        code = 1
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"passed": result["passed"], "diagnostic": result.get("diagnostic"),
                      "evidence_kind": result.get("evidence_kind")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
