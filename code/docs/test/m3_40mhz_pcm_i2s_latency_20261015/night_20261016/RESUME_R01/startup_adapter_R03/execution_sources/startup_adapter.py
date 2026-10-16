"""Strict FIX02 raw sidecar adapter; no cropping or invented known values."""
import json
from pathlib import Path
import re

from consume_capture import HEADER, parse_json, require, sha256
from startup_guards import BOUNDARY_FIELDS, binary_map, validate_selection


AUDIO_WIDTHS = {"rst_n": 1, "frame_tick": 1, "request_accept": 1, "request_id": 32,
                "commit": 1, "committed_id": 32, "left": 24, "right": 24,
                "clipped": 1, "pending": 1, "play_left": 24, "play_right": 24,
                "clip_count": 32, "underflow": 32, "bclk": 1, "ws": 1, "din": 1}
INPUT_WIDTHS = {"rst_n": 1, "midi_rx": 1, "event_valid": 1, "event_ready": 1,
                "event_data_binary": 64, "config_valid": 1, "config_ready": 1,
                "active_voice_count": 32}
POST_FIELDS = set("schema startup_unknown clock_hz clock_period_ps startup_edges "
                  "main_first_absolute_cycle main_first_relative_cycle main_first_time_ps "
                  "main_first_time_ns absolute_cycle_offset selection_predicate source_contract "
                  "startup_capture startup_inputs boundary_raw main_capture main_inputs "
                  "producer_receipt startup_has_xz prefix_contiguous early_business_accepts limits".split())
LIMITS = {"startup": "UNKNOWN_NOT_SIGNED", "first_valid": "UNKNOWN_NOT_EXPORTED",
          "analog_latency": "UNKNOWN_NOT_MEASURED", "board_release_allowed": False}


def check_schema(path, pinned_sha):
    require(sha256(path) == pinned_sha, "STARTUP_SCHEMA_SHA")
    schema = parse_json(Path(path).read_text(encoding="utf-8"))
    require(schema["startup_capture"]["binary_field_widths"] == AUDIO_WIDTHS
            and schema["startup_inputs"]["binary_field_widths"] == INPUT_WIDTHS
            and set(schema["boundary_raw_exact_keys"]) == BOUNDARY_FIELDS
            and set(schema["boundary_post_identity_keys"]) == POST_FIELDS
            and schema["boundary_schema"] == "M3_R05_SEGMENTED_BOUNDARY_V1",
            "STARTUP_SCHEMA_FIELDS_OR_WIDTHS")
    return schema


def read_prefix(path, widths, schema_name, *, audio):
    ticks, resets = [], []
    end = None
    last_time = -1
    with Path(path).open(encoding="utf-8") as stream:
        require(parse_json(stream.readline()) == {"kind": "HEADER", "schema": schema_name,
                                                  "clock_hz": 40000000}, "STARTUP_HEADER")
        for line in stream:
            require(end is None, "STARTUP_AFTER_END")
            row = parse_json(line)
            if row.get("kind") == "END":
                fields = {"kind", "absolute_edges", "main_first_absolute_cycle"} if audio else {"kind", "absolute_edges"}
                require(set(row) == fields and type(row["absolute_edges"]) is int
                        and row["absolute_edges"] == len(ticks), "STARTUP_END_COUNT")
                if audio:
                    require(type(row["main_first_absolute_cycle"]) is int
                            and row["main_first_absolute_cycle"] == len(ticks) + 1, "STARTUP_END_MAIN_BOUNDARY")
                end = row
                continue
            require(type(row.get("time_ps")) is int and row["time_ps"] >= last_time,
                    "STARTUP_RECORD_TIME_ORDER")
            last_time = row["time_ps"]
            if row.get("kind") == "STARTUP_RESET":
                require(audio and set(row) == {"kind", "absolute_cycle", "time_ps", "rst_n_binary"}
                        and type(row["absolute_cycle"]) is int and row["absolute_cycle"] == len(ticks),
                        "STARTUP_RESET_FIELDS_OR_POSITION")
                binary_map({"rst_n": row["rst_n_binary"]}, {"rst_n": 1})
                resets.append(row)
                continue
            require(row.get("kind") == "STARTUP_TICK"
                    and set(row) == set(widths) | {"kind", "absolute_cycle", "time_ps"}, "STARTUP_TICK_FIELDS")
            require(type(row["absolute_cycle"]) is int and row["absolute_cycle"] == len(ticks) + 1
                    and len(ticks) < 63, "STARTUP_ABSOLUTE_SEQUENCE")
            binary_map({k: row[k] for k in widths}, widths)
            ticks.append(row)
    require(end is not None, "STARTUP_END_MISSING")
    return ticks, resets


def first_main_rows(capture, inputs):
    with Path(capture).open(encoding="utf-8") as stream:
        require(parse_json(stream.readline()) == HEADER, "MAIN_HEADER")
        audio = parse_json(stream.readline())
    require(audio.get("kind") == "TICK" and audio.get("cycle") == 1
            and audio.get("epoch") == 0, "MAIN_FIRST_RECORD")
    with Path(inputs).open(encoding="utf-8") as stream:
        require(parse_json(stream.readline()) == {"kind": "HEADER", "schema": "M3_R05_INPUT_PRE_NBA_V1",
                                                  "clock_hz": 40000000}, "MAIN_INPUT_HEADER")
        initial = parse_json(stream.readline())
        require(initial.get("kind") == "INITIAL_INPUTS", "MAIN_INITIAL_INPUTS")
        first_input = None
        for line in stream:
            row = parse_json(line)
            if row.get("kind") == "TICK":
                first_input = row
                break
            require(row.get("kind") in ("MIDI_EDGE", "RAW_RESET_EDGE"), "MAIN_INPUT_PREFIX_KIND")
    require(first_input is not None and first_input["cycle"] == 1, "MAIN_FIRST_INPUT_RECORD")
    def as_binary(value, width):
        require(type(value) is int and -(1 << (width - 1)) <= value < (1 << width), "MAIN_BINARY_SOURCE_TYPE")
        return format(value & ((1 << width) - 1), f"0{width}b")
    audio_binary = {k: as_binary(audio[k], width) for k, width in AUDIO_WIDTHS.items()}
    input_binary = {}
    for key, width in INPUT_WIDTHS.items():
        if key == "event_data_binary":
            value = first_input["event_data_hex"]
            require(type(value) is str and re.fullmatch("[0-9a-fA-F]{16}", value), "MAIN_EVENT_HEX")
            input_binary[key] = format(int(value, 16), "064b")
        else:
            input_binary[key] = as_binary(first_input[key], width)
    require(audio["rst_n"] == first_input["rst_n"], "MAIN_FIRST_RESET_ALIGNMENT")
    return audio_binary, input_binary, first_input["time_ns"]


def validate_raw(startup_capture, startup_inputs, boundary_raw, main_capture, main_inputs):
    raw = parse_json(Path(boundary_raw).read_text(encoding="utf-8"))
    audio, resets = read_prefix(startup_capture, AUDIO_WIDTHS, "M3_R05_STARTUP_PUBLIC_BINARY_V1", audio=True)
    inputs, _ = read_prefix(startup_inputs, INPUT_WIDTHS, "M3_R05_STARTUP_INPUT_BINARY_V1", audio=False)
    require(len(audio) == len(inputs), "STARTUP_AUDIO_INPUT_COUNT")
    normalized = []
    for a, i in zip(audio, inputs):
        require(a["absolute_cycle"] == i["absolute_cycle"] and a["time_ps"] == i["time_ps"]
                and a["rst_n"] == i["rst_n"], "STARTUP_AUDIO_INPUT_ALIGNMENT")
        normalized.append({"absolute_cycle": a["absolute_cycle"], "time_ps": a["time_ps"],
                           "audio": {k: a[k] for k in AUDIO_WIDTHS},
                           "inputs": {k: i[k] for k in INPUT_WIDTHS}})
    first_audio, first_inputs, time_ns = first_main_rows(main_capture, main_inputs)
    result = validate_selection(normalized, first_audio, first_inputs, raw, AUDIO_WIDTHS, INPUT_WIDTHS, time_ns)
    for reset in resets:
        count = reset["absolute_cycle"]
        low = audio[count - 1]["time_ps"] if count else 0
        high = audio[count]["time_ps"] if count < len(audio) else raw["main_first_time_ps"]
        require(low <= reset["time_ps"] <= high, "STARTUP_RESET_TIME_OUTSIDE_EDGE_WINDOW")
    result["startup_resets"] = resets
    return result


def verify_post_run_links(boundary, receipt):
    for post_key, run_key in (("startup_capture", "STARTUP_CAPTURE.jsonl"),
                             ("startup_inputs", "STARTUP_INPUTS.jsonl"),
                             ("boundary_raw", "STARTUP_BOUNDARY_RAW.json"),
                             ("main_capture", "REAL_CAPTURE.jsonl"),
                             ("main_inputs", "REAL_INPUTS.jsonl")):
        post, run = boundary[post_key], receipt[run_key]
        require(set(post) == {"path", "bytes", "sha256"}
                and set(run) == {"path", "bytes", "sha256"}
                and Path(post["path"]).resolve() == Path(run["path"]).resolve()
                and post["bytes"] == run["bytes"] and post["sha256"] == run["sha256"],
                "STARTUP_POST_PRODUCER_RAW_IDENTITY")


def verify_segmented(boundary_path, boundary_sha, schema_path, schema_sha, receipt_path, capture, inputs):
    # Local import avoids the source-verification module's adapter import cycle.
    from consume_real import verify_identity
    check_schema(schema_path, schema_sha)
    require(sha256(boundary_path) == boundary_sha, "STARTUP_BOUNDARY_SHA")
    boundary = parse_json(Path(boundary_path).read_text(encoding="utf-8"))
    require(set(boundary) == POST_FIELDS and boundary["schema"] == "M3_R05_SEGMENTED_BOUNDARY_V1",
            "STARTUP_POST_BOUNDARY_FIELDS")
    require(boundary["startup_unknown"] is True and boundary["prefix_contiguous"] is True
            and boundary["clock_hz"] == 40000000 and boundary["clock_period_ps"] == 25000
            and type(boundary["early_business_accepts"]) is int and boundary["early_business_accepts"] == 0
            and boundary["limits"] == LIMITS, "STARTUP_SCOPE_OR_METADATA")
    paths = {key: verify_identity(boundary[key]) for key in ("startup_capture", "startup_inputs", "boundary_raw",
             "main_capture", "main_inputs", "producer_receipt", "source_contract")}
    require(paths["main_capture"].resolve() == Path(capture).resolve()
            and paths["main_inputs"].resolve() == Path(inputs).resolve()
            and paths["producer_receipt"].resolve() == Path(receipt_path).resolve(), "STARTUP_MAIN_RECEIPT_LINK")
    verify_post_run_links(boundary, parse_json(Path(receipt_path).read_text(encoding="utf-8")))
    raw = parse_json(paths["boundary_raw"].read_text(encoding="utf-8"))
    require(all(type(boundary[k]) is int and boundary[k] == raw[k] for k in BOUNDARY_FIELDS)
            and type(boundary["absolute_cycle_offset"]) is int
            and boundary["absolute_cycle_offset"] == raw["startup_edges"], "STARTUP_POST_RAW_FACTS")
    require(type(boundary["selection_predicate"]) is str and boundary["selection_predicate"], "STARTUP_SELECTION_LABEL")
    result = validate_raw(paths["startup_capture"], paths["startup_inputs"], paths["boundary_raw"], capture, inputs)
    require(type(boundary["startup_has_xz"]) is bool
            and boundary["startup_has_xz"] == (result["prefix_edges_with_unknown"] > 0), "STARTUP_UNKNOWN_METADATA")
    result.update(boundary_sha256=boundary_sha, schema_sha256=schema_sha,
                  raw_file_identities={key: boundary[key] for key in paths})
    return result
