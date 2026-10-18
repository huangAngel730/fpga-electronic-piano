"""Lossless, streaming CSV for the whole C9 envelope and all 74 fields."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[6]
COMMON_PATH = ROOT / ("code/software/m3_pro_fourvoice_trace_20261016/"
    "pro_basis_r08_20261017/coordinator/task_day4_completion_20261017/common.py")
COMMON_SHA = "55cb7481fe9c0870247a7d8b2453dea859f0f2e81879795cc0e34ffe8c996dca"
STREAM_PATH = ROOT / ("code/software/m3_pro_fourvoice_trace_20261016/"
    "pro_basis_r07_20261017/public_capture_tb/c9_completion_r01/c9_stream.py")
STREAM_SHA = "5584ab7201544a8d30bfdd7603a51483d1c5340ccc219e853df0d146d042ebef"
OUTER = ("schema", "capture_id", "origin", "source", "raw_ports",
         "missing_reasons", "events", "semantics")
_COMMON = None


def support():
    global _COMMON
    if _COMMON is None:
        raw = COMMON_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != COMMON_SHA:
            raise ValueError("COMMON_SOURCE_CHANGED")
        module = ModuleType("_m3_c9_d4_common_codec")
        module.__file__ = str(COMMON_PATH)
        exec(compile(raw, str(COMMON_PATH), "exec"), module.__dict__)
        _COMMON = module
    return _COMMON


def modules():
    c = support()
    stream = c.load_source(STREAM_PATH, STREAM_SHA)
    return c, stream, stream.dependencies()


def header(d):
    return tuple("fields." + name for name in d["bridge"].REQUIRED_FIELDS) + OUTER


def encode_file(public_rows_path, csv_path):
    c, stream, d = modules()
    source = c.artifact(public_rows_path)
    target = c.no_alias(csv_path)
    c.require(target.is_relative_to(ROOT), "OUTPUT_SCOPE")
    target.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with target.open("x", encoding="utf-8", newline="") as sink:
        writer = csv.writer(sink, lineterminator="\n")
        writer.writerow(header(d))
        for count, row in enumerate(stream.iter_public_rows(public_rows_path, d), 1):
            cells = [row["fields"][name] for name in d["bridge"].REQUIRED_FIELDS]
            cells.extend(row[name] for name in OUTER)
            writer.writerow([json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                                        allow_nan=False) for value in cells])
            c.require(sink.tell() <= stream.MAX_OUTPUT_BYTES, "CSV_OUTPUT_BOUND")
    c.checked_descriptor(source, allow_external=True)
    return {"schema": "M3_D4_C9_CSV_RECEIPT_V1", "mode": "encode",
            "rows": count, "input": source, "artifact": c.artifact(target),
            "all_74_fields": True, "full_envelope_preserved": True,
            "real_verified": False, "board_release_allowed": False}


def _csv_rows(csv_path, stream, d):
    c = support()
    expected = header(d)
    # A record contains JSON cells only. Multi-line cells are not accepted:
    # physical JSON source newlines were escaped by json.dumps.
    prior_limit = csv.field_size_limit(stream.MAX_LINE_BYTES * 2)
    try:
        source = c.no_alias(csv_path).open("r", encoding="utf-8", newline="")
        def records_one_line():
            with source:
                while True:
                    line = source.readline(stream.MAX_LINE_BYTES * 2 + 1)
                    if not line:
                        return
                    c.require(len(line.encode("utf-8")) <= stream.MAX_LINE_BYTES * 2,
                              "CSV_PHYSICAL_LINE_BOUND")
                    try:
                        parsed = list(csv.reader([line], strict=True))
                    except csv.Error as error:
                        raise c.ContractReject("C9_CSV_RECORD_SYNTAX") from error
                    c.require(len(parsed) == 1, "CSV_SINGLE_PHYSICAL_RECORD")
                    yield parsed[0]
        records = records_one_line()
        c.require(tuple(next(records, ())) == expected, "C9_CSV_HEADER")
        count = 0
        field_names = d["bridge"].REQUIRED_FIELDS
        for count, cells in enumerate(records, 1):
            c.require(len(cells) == len(expected), "C9_CSV_CELL_COUNT")
            values = [c.loads(value) for value in cells]
            row = {name: values[len(field_names) + index]
                   for index, name in enumerate(OUTER)}
            row["fields"] = dict(zip(field_names, values[:len(field_names)]))
            stream.validate_public_row(row, count, d)
            yield row
        c.require(count > 0, "EMPTY_C9_CSV")
    finally:
        csv.field_size_limit(prior_limit)


def decode_file(csv_path, public_rows_path):
    c, stream, d = modules()
    source = c.artifact(csv_path)
    target = c.no_alias(public_rows_path)
    c.require(target.is_relative_to(ROOT), "OUTPUT_SCOPE")
    target.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    capture = None
    prior_time = -1
    with target.open("xb") as sink:
        for count, row in enumerate(_csv_rows(csv_path, stream, d), 1):
            current = (row["capture_id"], row["origin"],
                       row["source"]["raw_sha256"], row["source"]["reset_edges_sha256"])
            if capture is None:
                capture = current
            c.require(current == capture, "MIXED_C9_CAPTURE")
            c.require(row["source"]["time_ps"] > prior_time, "C9_TIME_SEQUENCE")
            prior_time = row["source"]["time_ps"]
            stream.json_line(sink, row)
    c.checked_descriptor(source, allow_external=True)
    return {"schema": "M3_D4_C9_CSV_RECEIPT_V1", "mode": "decode",
            "rows": count, "input": source, "artifact": c.artifact(target),
            "all_74_fields": True, "full_envelope_preserved": True,
            "real_verified": False, "board_release_allowed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("encode", "decode"))
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = (encode_file(args.input, args.output) if args.mode == "encode"
              else decode_file(args.input, args.output))
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
