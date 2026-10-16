"""Necessary new raw-schema/selection mutations only; synthetic software data."""
import argparse
import copy
import json
from pathlib import Path

from consume_capture import HEADER, sha256
from startup_adapter import AUDIO_WIDTHS, INPUT_WIDTHS, check_schema, validate_raw


def write_json(path, value):
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def write_jsonl(path, values):
    path.write_text("".join(json.dumps(v) + "\n" for v in values), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[5]
    schema = root / "code/docs/test/m3_r05_functional_integration_20261015/night_20261016/RESUME_R01/STARTUP_SCHEMA.json"
    check_schema(schema, sha256(schema))
    (args.output / "FROZEN_STARTUP_SCHEMA.json").write_bytes(schema.read_bytes())
    audio = [{"kind": "HEADER", "schema": "M3_R05_STARTUP_PUBLIC_BINARY_V1", "clock_hz": 40000000}]
    inputs = [{"kind": "HEADER", "schema": "M3_R05_STARTUP_INPUT_BINARY_V1", "clock_hz": 40000000}]
    for index in (1, 2):
        values = {k: "0" * width for k, width in AUDIO_WIDTHS.items()}
        values["left"] = "x" * 24
        if index == 1:
            values["rst_n"] = "x"
        audio.append(dict(values, kind="STARTUP_TICK", absolute_cycle=index, time_ps=12500 + (index - 1) * 25000))
        iv = {k: "0" * width for k, width in INPUT_WIDTHS.items()}
        iv["rst_n"] = values["rst_n"]
        inputs.append(dict(iv, kind="STARTUP_TICK", absolute_cycle=index, time_ps=12500 + (index - 1) * 25000))
    audio.insert(2, {"kind": "STARTUP_RESET", "absolute_cycle": 1, "time_ps": 12500, "rst_n_binary": "0"})
    audio.append({"kind": "END", "absolute_edges": 2, "main_first_absolute_cycle": 3})
    inputs.append({"kind": "END", "absolute_edges": 2})
    main_audio = [dict(HEADER), {"kind": "TICK", "cycle": 1, "epoch": 0,
                  **{k: 0 for k in AUDIO_WIDTHS}, "first_valid": None}, {"kind": "END", "cycle": 1, "epoch": 0}]
    main_inputs = [{"kind": "HEADER", "schema": "M3_R05_INPUT_PRE_NBA_V1", "clock_hz": 40000000},
                   {"kind": "INITIAL_INPUTS", "time_ns": 0, "midi_rx": 1, "sys_rst_n": 0},
                   {"kind": "TICK", "cycle": 1, "time_ns": 63,
                    **{k: 0 for k in INPUT_WIDTHS if k != "event_data_binary"}, "event_data_hex": "0" * 16},
                   {"kind": "END", "cycle": 1}]
    boundary = {"startup_edges": 2, "main_first_absolute_cycle": 3, "main_first_relative_cycle": 1,
                "main_first_time_ps": 62500, "main_first_time_ns": 63}
    results = []
    def case(name, expected, transform=None):
        payload = copy.deepcopy([audio, inputs, boundary, main_audio, main_inputs])
        if transform:
            transform(payload)
        folder = args.output / name
        folder.mkdir()
        files = [folder / n for n in ("startup.SYNTHETIC.jsonl", "inputs.SYNTHETIC.jsonl", "boundary.SYNTHETIC.json",
                                     "main.SYNTHETIC.jsonl", "main_inputs.SYNTHETIC.jsonl")]
        for i, path in enumerate(files):
            (write_json if i == 2 else write_jsonl)(path, payload[i])
        try:
            result = validate_raw(*files)
            actual = None
            assert result["startup_unknown"] is True
        except (ValueError, OSError, TypeError, KeyError) as exc:
            actual = str(exc)
        results.append({"name": name, "expected": expected, "actual": actual,
                        "passed": expected == actual, "evidence_kind": "SYNTHETIC_RAW_SCHEMA_ONLY"})
    case("raw_positive_keeps_x", None)
    case("missing_audio_tick", "STARTUP_RESET_FIELDS_OR_POSITION", lambda p: p[0].pop(1))
    case("duplicate_audio_tick", "STARTUP_ABSOLUTE_SEQUENCE", lambda p: p[0].insert(2, p[0][1]))
    case("missing_input_tick", "STARTUP_ABSOLUTE_SEQUENCE", lambda p: p[1].pop(1))
    case("binary_width_wrong", "STARTUP_BINARY_WIDTH_OR_VALUE", lambda p: p[0][1].__setitem__("left", "x"))
    case("binary_port_missing", "STARTUP_TICK_FIELDS", lambda p: p[0][1].pop("left"))
    case("main_earlier_eligible_was_skipped", "MAIN_NOT_FIRST_ELIGIBLE_EDGE", lambda p: p[0][3].__setitem__("left", "0" * 24))
    case("prefix_wrong_time", "STARTUP_AUDIO_INPUT_ALIGNMENT", lambda p: p[1][1].__setitem__("time_ps", 12501))
    case("main_not_reset", "MAIN_FIRST_NOT_ALL_KNOWN_RESET_LOW", lambda p: (p[3][1].__setitem__("rst_n", 1), p[4][2].__setitem__("rst_n", 1)))
    case("main_x", "MAIN_BINARY_SOURCE_TYPE", lambda p: p[3][1].__setitem__("left", "x"))
    case("boundary_mapping_wrong", "STARTUP_CYCLE_BOUNDARY", lambda p: p[2].__setitem__("main_first_absolute_cycle", 4))
    case("boundary_time_wrong", "STARTUP_MAIN_TIME_MAPPING", lambda p: p[2].__setitem__("main_first_time_ns", 62))
    case("startup_end_missing", "STARTUP_END_MISSING", lambda p: p[0].pop())
    case("startup_reset_time_wrong", "STARTUP_RECORD_TIME_ORDER", lambda p: p[0][2].__setitem__("time_ps", 1))
    def early(p):
        p[0][1]["rst_n"] = p[1][1]["rst_n"] = "1"
        p[1][1]["event_valid"] = p[1][1]["event_ready"] = "1"
    case("business_before_boundary", "PERFORMANCE_ACCEPT_BEFORE_MAIN", early)
    (args.output / "RESULTS.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"tests": len(results), "passed": sum(r["passed"] for r in results),
                      "failed": [r for r in results if not r["passed"]], "schema_sha256": sha256(schema)}))
    return int(not all(r["passed"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
