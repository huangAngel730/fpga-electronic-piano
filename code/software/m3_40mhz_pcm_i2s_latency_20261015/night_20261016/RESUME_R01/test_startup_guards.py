"""Narrow synthetic selection guards, not raw-file or RTL evidence."""
import argparse
import copy
import json
from pathlib import Path

from startup_guards import validate_selection


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    audio_widths = {"rst_n": 1, "left": 24}
    input_widths = {"event_valid": 1, "event_ready": 1, "event_data": 64}
    first_audio = {"rst_n": "0", "left": "0" * 24}
    first_inputs = {"event_valid": "0", "event_ready": "1", "event_data": "0" * 64}
    prefix = [{"absolute_cycle": 1, "time_ps": 12500,
               "audio": {"rst_n": "x", "left": "x" * 24}, "inputs": dict(first_inputs)},
              {"absolute_cycle": 2, "time_ps": 37500,
               "audio": {"rst_n": "0", "left": "x" * 24}, "inputs": dict(first_inputs)}]
    boundary = {"startup_edges": 2, "main_first_absolute_cycle": 3, "main_first_time_ps": 62500,
                "main_first_time_ns": 63, "main_first_relative_cycle": 1}
    results = []
    def check(name, p, a, i, b, time_ns, expected):
        try:
            result = validate_selection(p, a, i, b, audio_widths, input_widths, time_ns)
            actual = None
            assert result["startup_unknown"] is True
        except ValueError as exc:
            actual = str(exc)
        results.append({"name": name, "expected": expected, "actual": actual,
                        "passed": actual == expected, "kind": "SYNTHETIC_NORMALIZED_FIELDS_ONLY"})
    check("prefix_x_kept_main_first_known", prefix, first_audio, first_inputs, boundary, 63, None)
    p = copy.deepcopy(prefix); p[1]["audio"] = dict(first_audio)
    check("skipped_earlier_eligible", p, first_audio, first_inputs, boundary, 63, "MAIN_NOT_FIRST_ELIGIBLE_EDGE")
    p = copy.deepcopy(prefix); p[0]["absolute_cycle"] = 2
    check("missing_or_duplicate_prefix", p, first_audio, first_inputs, boundary, 63, "STARTUP_ABSOLUTE_SEQUENCE")
    p = copy.deepcopy(prefix); p[0]["time_ps"] += 1
    check("wrong_precise_time", p, first_audio, first_inputs, boundary, 63, "STARTUP_25000PS_SPACING")
    p = copy.deepcopy(prefix); p[0]["inputs"]["event_valid"] = "1"
    p[0]["audio"]["rst_n"] = "1"
    check("early_known_accept", p, first_audio, first_inputs, boundary, 63, "PERFORMANCE_ACCEPT_BEFORE_MAIN")
    p = copy.deepcopy(prefix); p[0]["audio"].pop("left")
    check("missing_binary_port", p, first_audio, first_inputs, boundary, 63, "STARTUP_BINARY_FIELDS")
    p = copy.deepcopy(prefix); p[0]["audio"]["left"] = "x"
    check("binary_width_lost", p, first_audio, first_inputs, boundary, 63, "STARTUP_BINARY_WIDTH_OR_VALUE")
    check("main_still_x", prefix, dict(first_audio, left="x" * 24), first_inputs, boundary, 63,
          "MAIN_FIRST_NOT_ALL_KNOWN_RESET_LOW")
    check("main_reset_not_asserted", prefix, dict(first_audio, rst_n="1"), first_inputs, boundary, 63,
          "MAIN_FIRST_NOT_ALL_KNOWN_RESET_LOW")
    check("wrong_main_time", prefix, first_audio, first_inputs, boundary, 62, "STARTUP_MAIN_TIME_MAPPING")
    check("wrong_relative_cycle", prefix, first_audio, first_inputs, dict(boundary, main_first_relative_cycle=0),
          63, "STARTUP_CYCLE_BOUNDARY")
    check("beyond_64_edges", prefix, first_audio, first_inputs, dict(boundary, startup_edges=64),
          63, "STARTUP_CYCLE_BOUNDARY")
    (args.output / "RESULTS.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"tests": len(results), "passed": sum(r["passed"] for r in results),
                      "failed": [r for r in results if not r["passed"]]}))
    return int(not all(r["passed"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
