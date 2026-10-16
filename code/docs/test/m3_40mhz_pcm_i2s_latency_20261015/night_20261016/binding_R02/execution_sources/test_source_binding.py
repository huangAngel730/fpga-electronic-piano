"""Software-only source-binding rejection and companion timebase tests.

No positive real-run provenance is manufactured. Valid file identities and
synthetic timeline parsing are tested separately from the genuine-run gate.
"""
import argparse
import copy
import json
from pathlib import Path

from consume_capture import sha256
from consume_real import verify_identity, verify_inputs, verify_receipt
from test_consumer import synthetic_records, write_records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    results = []

    def expect(name, expected, function):
        try:
            function()
            actual = None
        except (ValueError, OSError, KeyError, TypeError) as exc:
            actual = str(exc)
        results.append({"name": name, "expected": expected, "actual": actual,
                        "passed": actual == expected, "kind": "SYNTHETIC_SOFTWARE_ONLY"})

    identity_file = args.output / "IDENTITY_TEST_ONLY.txt"
    identity_file.write_bytes(b"SYNTHETIC IDENTITY POSITIVE; NOT A TOOL LOG\n")
    identity = {"path": str(identity_file.resolve()), "bytes": identity_file.stat().st_size,
                "sha256": sha256(identity_file)}
    expect("exact_identity", None, lambda: verify_identity(identity))
    expect("wrong_identity_sha", "IDENTITY_BYTES_OR_SHA", lambda: verify_identity(dict(identity, sha256="0" * 64)))
    expect("wrong_identity_bytes", "IDENTITY_BYTES_OR_SHA", lambda: verify_identity(dict(identity, bytes=1)))
    expect("missing_identity_field", "IDENTITY_FIELDS", lambda: verify_identity({"path": str(identity_file)}))
    for name, receipt in (
        ("failed_producer", {"schema": "M3_R05_NIGHT_OBSERVATION_RUN_V1", "status": "FAILED_STOP", "exit_code": 1}),
        ("old_fixture_receipt", {"schema": "C_HISTORICAL_AUDIT_V1", "passed": True}),
        ("old_a_success_without_new_capture", {"schema": "M3_R05_ISOLATED_RUN_V1", "status": "CONSISTENT_PENDING_M2", "exit_code": 0}),
        ("schema_missing", {"passed": True})):
        path = args.output / (name + ".SYNTHETIC.json")
        path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
        expect(name, "PRODUCER_RUN_NOT_SUCCESSFUL", lambda p=path: verify_receipt(p, sha256(p)))
        expect(name + "_wrong_sha", "PRODUCER_RECEIPT_SHA", lambda p=path: verify_receipt(p, "0" * 64))
    base = synthetic_records()
    audio = args.output / "AUDIO.SYNTHETIC.jsonl"
    write_records(audio, base)
    companion = [{"kind": "HEADER", "schema": "M3_R05_INPUT_PRE_NBA_V1", "clock_hz": 40000000}]
    companion.append({"kind": "INITIAL_INPUTS", "time_ns": 0, "midi_rx": 1, "sys_rst_n": 0})
    for r in base:
        if r["kind"] == "TICK":
            companion.append({"kind": "TICK", "cycle": r["cycle"], "time_ns": r["cycle"] * 25,
                "rst_n": r["rst_n"], "midi_rx": 1, "event_valid": int(r["cycle"] in (1000, 5000)),
                "event_ready": 1, "event_data_hex": "0000000000000000", "config_valid": 0,
                "config_ready": 1, "active_voice_count": 0})
    companion.append({"kind": "END", "cycle": 12000})
    input_path = args.output / "INPUTS.SYNTHETIC.jsonl"
    write_records(input_path, companion)
    input_result = verify_inputs(input_path, audio, sha256(input_path))
    results.append({"name": "synthetic_input_timeline_positive", "passed": len(input_result["accepted_events"]) == 2,
                    "kind": "SYNTHETIC_SOFTWARE_ONLY"})
    mutation = (
        ("missing_input_tick", "INPUT_ORDER_OR_BITS", lambda r: r.pop(100)),
        ("repeated_input_tick", "INPUT_ORDER_OR_BITS", lambda r: r.insert(100, r[100])),
        ("wrong_timebase", "INPUT_40MHZ_TIMEBASE", lambda r: r[100].__setitem__("time_ns", 2498)),
        ("wrong_input_reset", "INPUT_AUDIO_TICK_ALIGNMENT", lambda r: r[100].__setitem__("rst_n", 0)),
        ("event_hex_x", "INPUT_EVENT_OR_VOICE_RANGE", lambda r: r[100].__setitem__("event_data_hex", "x" * 16)),
        ("input_bool", "INPUT_X_OR_TYPE", lambda r: r[100].__setitem__("midi_rx", True)),
        ("voice_range", "INPUT_EVENT_OR_VOICE_RANGE", lambda r: r[100].__setitem__("active_voice_count", 5)),
        ("input_end_missing", "INPUT_AUDIO_LENGTH_OR_END", lambda r: r.pop()),
        ("input_end_duplicate", "INPUT_AFTER_END", lambda r: r.append(r[-1])),
        ("raw_midi_x", "RAW_INPUT_EDGE", lambda r: r.insert(100, {"kind": "MIDI_EDGE", "time_ns": 2400, "value": "x"})),
        ("initial_inputs_missing", "INITIAL_INPUTS_MISSING", lambda r: r.pop(1)),
        ("initial_inputs_x", "INITIAL_INPUTS_CONTRACT", lambda r: r[1].__setitem__("midi_rx", "x")),
    )
    for name, diagnostic, transform in mutation:
        rows = copy.deepcopy(companion)
        transform(rows)
        path = args.output / (name + ".SYNTHETIC.jsonl")
        write_records(path, rows)
        expect(name, diagnostic, lambda p=path: verify_inputs(p, audio, sha256(p)))
    (args.output / "RESULTS.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"tests": len(results), "passed": sum(r["passed"] for r in results),
                      "failed": [r for r in results if not r["passed"]],
                      "real_producer_positive": "UNKNOWN_NOT_AVAILABLE"}))
    return int(not all(r["passed"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
