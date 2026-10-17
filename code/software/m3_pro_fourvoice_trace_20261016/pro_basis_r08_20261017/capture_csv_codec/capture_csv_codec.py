"""Lossless CSV codec for the frozen R7-A public-row profile."""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
from typing import Any, Iterable, Iterator, TextIO


ROW_SCHEMA = "M3_R7A_PUBLIC_ROW_V1"
EXT_SCHEMA = "M3_R7A_TX_EXTENSION_V1"
FIELDS = (
    "cycle", "epoch", "rst_n", "frame_tick", "event_valid", "event_ready",
    "event_data", "apply_valid", "apply_event_seq", "apply_data",
    "occupied_mask", "releasing_mask", "note_on_mask", "note_off_mask",
    "retire_mask", "slot_sources", "slot_channels", "slot_notes",
    "slot_generations", "req_valid", "req_ready", "req_id", "advance_mask",
    "advance_frame_req_id", "result_valid", "result_ready", "result_id",
    "result_left", "result_right", "result_clip_mask", "commit", "commit_id",
    "commit_left", "commit_right", "commit_clip", "cancel", "cancel_reason",
    "config_valid", "config_ready", "config_payload", "effect_input_valid",
    "effect_input_ready", "effect_input_id", "effect_input_left",
    "effect_input_right", "effect_input_clip_mask", "tx_sample_valid",
    "tx_frame_id", "tx_req_id", "tx_left", "tx_right", "tx_clip", "tx_hold",
    "tx_startup_zero", "bclk", "ws", "din", "pll_locked", "audio_stable",
    "pa_en", "finish",
)
SOURCE = ("raw_sha256", "reset_edges_sha256", "line", "cycle", "epoch",
          "time_ps", "sampling_phase")
EXTENSIONS = ("schema", "obs_core_clk", "obs_polyphonic_valid",
              "obs_tx_metadata_valid", "obs_tx_req_id_valid",
              "obs_tx_clip_mask", "obs_metadata_error",
              "obs_frame_id_overflow", "uart_tx", "raw_tx_req_id_bits")
HEADER = (("schema", "capture_id", "origin")
          + tuple(f"source.{name}" for name in SOURCE)
          + tuple(f"fields.{name}" for name in FIELDS)
          + tuple(f"extensions.{name}" for name in EXTENSIONS)
          + ("missing_reasons", "events"))


class CodecReject(ValueError):
    pass


def validate_row(row: dict[str, Any]) -> None:
    if set(row) != {"schema", "capture_id", "origin", "source", "fields",
                    "extensions", "missing_reasons", "events"}:
        raise CodecReject("ROW_SHAPE")
    if row["schema"] != ROW_SCHEMA:
        raise CodecReject("ROW_SCHEMA")
    if not all(isinstance(row[key], dict)
               for key in ("source", "fields", "extensions", "missing_reasons")):
        raise CodecReject("OBJECT_SHAPE")
    if not isinstance(row["events"], list):
        raise CodecReject("EVENTS_SHAPE")
    if set(row["source"]) != set(SOURCE):
        raise CodecReject("SOURCE_PROFILE")
    if set(row["fields"]) != set(FIELDS):
        raise CodecReject("FIELD_PROFILE_61_REQUIRED")
    if (set(row["extensions"]) != set(EXTENSIONS)
            or row["extensions"].get("schema") != EXT_SCHEMA):
        raise CodecReject("TX_EXTENSION_PROFILE")


def write_rows(rows: Iterable[dict[str, Any]], stream: TextIO) -> int:
    """Write validated rows without materializing the input or output."""
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(HEADER)
    count = 0
    for row in rows:
        validate_row(row)
        values = [row["schema"], row["capture_id"], row["origin"]]
        values += [row["source"][name] for name in SOURCE]
        values += [row["fields"][name] for name in FIELDS]
        values += [row["extensions"][name] for name in EXTENSIONS]
        values += [row["missing_reasons"], row["events"]]
        writer.writerow([json.dumps(value, ensure_ascii=False,
                                    separators=(",", ":")) for value in values])
        count += 1
    if count == 0:
        raise CodecReject("EMPTY_INPUT")
    return count


def encode_rows(rows: Iterable[dict[str, Any]]) -> str:
    """Small-fixture convenience wrapper around :func:`write_rows`."""
    stream = io.StringIO(newline="")
    write_rows(rows, stream)
    return stream.getvalue()


def iter_decode(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    """Yield one validated row at a time from a physical-line iterator."""
    reader = csv.reader(lines)
    try:
        header = tuple(next(reader))
    except StopIteration as exc:
        raise CodecReject("EMPTY_CSV") from exc
    if header != HEADER:
        raise CodecReject("CSV_HEADER_PROFILE")
    count = 0
    for line, cells in enumerate(reader, 2):
        if len(cells) != len(HEADER):
            raise CodecReject(f"CSV_COLUMN_COUNT_LINE_{line}")
        try:
            values = [json.loads(cell) for cell in cells]
        except json.JSONDecodeError as exc:
            raise CodecReject(f"CSV_JSON_LINE_{line}") from exc
        offset = 0
        outer = dict(zip(("schema", "capture_id", "origin"), values[:3]))
        offset = 3
        outer["source"] = dict(zip(SOURCE, values[offset:offset + len(SOURCE)]))
        offset += len(SOURCE)
        outer["fields"] = dict(zip(FIELDS, values[offset:offset + len(FIELDS)]))
        offset += len(FIELDS)
        outer["extensions"] = dict(zip(
            EXTENSIONS, values[offset:offset + len(EXTENSIONS)]))
        offset += len(EXTENSIONS)
        outer["missing_reasons"] = values[offset]
        outer["events"] = values[offset + 1]
        validate_row(outer)
        count += 1
        yield outer
    if count == 0:
        raise CodecReject("EMPTY_ROWS")


def decode_rows(text: str) -> list[dict[str, Any]]:
    """Small-fixture convenience wrapper around :func:`iter_decode`."""
    return list(iter_decode(io.StringIO(text, newline="")))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("encode", "decode"))
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with args.input.open("r", encoding="utf-8", newline="") as source:
        with args.output.open("w", encoding="utf-8", newline="") as sink:
            if args.mode == "encode":
                rows = (json.loads(line) for line in source if line.strip())
                write_rows(rows, sink)
            else:
                for row in iter_decode(source):
                    sink.write(json.dumps(row, ensure_ascii=False,
                                          separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
