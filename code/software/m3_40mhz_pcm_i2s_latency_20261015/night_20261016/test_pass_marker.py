"""Narrow software regression for the real TB success text, no new RTL run."""
import argparse
import json
from pathlib import Path

from consume_capture import sha256
from consume_real import PASS_MARKER, verify_tool_log


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[4]
    historical = root / "code/docs/test/m3_r05_functional_integration_20261015/REWORK_WATCHDOG_RUN_02/functional_logs/vsim.stdout.log"
    old_raw = historical.read_bytes()
    (args.output / "HISTORICAL_ONLY_vsim.stdout.log").write_bytes(old_raw)
    cases = [
        ("historical_exact_marker_text_only", old_raw.decode("utf-8"), None),
        ("synthetic_exact", PASS_MARKER + "\n", None),
        ("synthetic_hash_prefix", "# " + PASS_MARKER + "\r\n", None),
        ("wrong_tb_name", "PASS tb_m2_m1td_real_chain\n", "PRODUCER_PASS_MISSING_OR_DUPLICATE"),
        ("wrong_prefix", "WRAPPER " + PASS_MARKER + "\n", "PRODUCER_PASS_MISSING_OR_DUPLICATE"),
        ("wrong_suffix", PASS_MARKER + "_FAKE\n", "PRODUCER_PASS_MISSING_OR_DUPLICATE"),
        ("duplicate_pass", (PASS_MARKER + "\n") * 2, "PRODUCER_PASS_MISSING_OR_DUPLICATE"),
        ("pass_with_error", "# Error: bad\n# " + PASS_MARKER + "\n", "PRODUCER_LOG_ERROR"),
        ("pass_with_failure", "# ** Failure: bad\n# " + PASS_MARKER + "\n", "PRODUCER_LOG_ERROR"),
        ("pass_with_suppressible_error", "# ** Error (suppressible): bad\n# " + PASS_MARKER + "\n", "PRODUCER_LOG_ERROR"),
        ("pass_with_errors01", "Errors: 0\nErrors: 01\n" + PASS_MARKER + "\n", "PRODUCER_LOG_ERRORS_NONZERO"),
    ]
    results = []
    for name, raw, expected in cases:
        (args.output / (name + ".log")).write_text(raw, encoding="utf-8", newline="\n")
        try:
            verify_tool_log("vsim", "stdout", raw)
            actual = None
        except ValueError as exc:
            actual = str(exc)
        results.append({"name": name, "passed": actual == expected,
                        "expected": expected, "actual": actual})
    (args.output / "RESULTS.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"tests": len(results), "passed": sum(r["passed"] for r in results),
                      "failed": [r for r in results if not r["passed"]],
                      "historical_log_sha256": sha256(historical),
                      "scope": "PASS_TEXT_SOFTWARE_ONLY_NOT_NEW_RTL_EVIDENCE"}))
    return int(not all(r["passed"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
