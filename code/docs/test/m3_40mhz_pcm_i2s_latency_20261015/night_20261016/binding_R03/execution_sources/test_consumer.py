"""Synthetic software tests ONLY; never evidence of a real RTL execution."""
import argparse
import copy
import json
from pathlib import Path

from consume_capture import HEADER, analyze, digital_cycles, quantize, sha256


def synthetic_records(*, swap_serial=False, load_slot=16, reset_cycle=4210):
    records = [dict(HEADER)]
    phase = bclk = ws = din = slot = shift = 0
    latched = (0, 0)
    held = (0, 0)
    pending = None
    clip_count = frame_id = epoch = 0
    accepted_cycle = None
    for cycle in range(1, 12001):
        reset = cycle <= 5 or reset_cycle <= cycle <= reset_cycle + 4
        if cycle == reset_cycle:
            epoch += 1
            records.append({"kind": "RESET", "epoch": epoch,
                            "cycle": cycle - 1, "time_ns": cycle * 25 - 1})
        if reset:
            phase = bclk = ws = din = slot = shift = 0
            latched = held = (0, 0)
            pending = None
            clip_count = frame_id = 0
            accepted_cycle = None
        carry = int(phase + 659706977 >= 1 << 32) if not reset else 0
        frame = int(bool(carry and bclk and slot == 63))
        accept = int(not reset and accepted_cycle == cycle)
        commit = int(not reset and accepted_cycle is not None
                     and cycle == accepted_cycle + 100)
        values = [0, 8388607, -8388608, 127, 128, -129, 234567, -765432]
        left = values[(frame_id + epoch) % len(values)]
        right = values[(frame_id + epoch + 3) % len(values)]
        play = pending if pending is not None else held
        row = {"kind": "TICK", "cycle": cycle, "epoch": epoch,
               "rst_n": int(not reset), "frame_tick": frame,
               "request_accept": accept, "request_id": frame_id,
               "commit": commit, "committed_id": frame_id,
               "left": left, "right": right, "clipped": int(frame_id % 2 == 0),
               "pending": int(pending is not None), "play_left": play[0],
               "play_right": play[1], "clip_count": clip_count,
               "underflow": 0, "bclk": bclk, "ws": ws, "din": din,
               "first_valid": None}
        records.append(row)
        if reset:
            continue
        phase = (phase + 659706977) % (1 << 32)
        if carry:
            if bclk:
                ws = slot // 32
                if slot % 32 == load_slot:
                    value = latched[0 if slot >= 32 else 1]
                    # Deliberately explicit integer reference, not the
                    # consumer's quantize function.
                    rounded = (value + 128) // 256
                    rounded = min(32767, max(-32768, rounded))
                    shift = (rounded & 65535) << 16
                else:
                    shift = (shift << 1) & 0xFFFFFFFF
                din = shift >> 31
                slot = (slot + 1) % 64
            bclk ^= 1
        if frame:
            latched = tuple(reversed(play)) if swap_serial else play
            if pending is not None:
                held = pending
                pending = None
            frame_id += 1
            accepted_cycle = cycle + 1
        elif commit:
            pending = (left, right)
            clip_count += row["clipped"]
    records.append({"kind": "END", "cycle": 12000, "epoch": epoch})
    return records


def write_records(path, records):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in records:
            stream.write(json.dumps(row, separators=(",", ":")) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    original = synthetic_records()
    positive = args.output / "SYNTHETIC_POSITIVE.jsonl"
    write_records(positive, original)
    baseline = analyze(positive, sha256(positive))
    results = [{"name": "synthetic_positive", "passed": baseline["passed"],
                "kind": "SYNTHETIC_SOFTWARE_ONLY", "capture_sha256": sha256(positive)}]
    (args.output / "SYNTHETIC_POSITIVE_RESULT.json").write_text(
        json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    ticks = [i for i, r in enumerate(original) if r["kind"] == "TICK"]
    commit = next(i for i in ticks if original[i]["commit"])
    request = next(i for i in ticks if original[i]["request_accept"])
    live = next(i for i in ticks if original[i]["rst_n"])
    frame = next(i for i in ticks if original[i]["frame_tick"])
    reset = next(i for i, r in enumerate(original) if r["kind"] == "RESET")

    def mutation(name, expected, transform):
        rows = copy.deepcopy(original)
        transform(rows)
        path = args.output / (name + ".SYNTHETIC.jsonl")
        write_records(path, rows)
        try:
            analyze(path, sha256(path))
            actual = "ACCEPTED"
        except (ValueError, OSError) as exc:
            actual = str(exc)
        results.append({"name": name, "expected": expected, "actual": actual,
                        "passed": actual in expected, "sha256": sha256(path),
                        "kind": "SYNTHETIC_MUTATION"})

    def field(index, name, value):
        return lambda rows: rows[index].__setitem__(name, value)

    mutation("missing_tick", ["TICK_ORDER_MISSING_DUPLICATE_OR_EPOCH"], lambda r: r.pop(live + 30))
    mutation("duplicate_tick", ["TICK_ORDER_MISSING_DUPLICATE_OR_EPOCH"], lambda r: r.insert(live + 30, r[live + 30]))
    mutation("out_of_order", ["TICK_ORDER_MISSING_DUPLICATE_OR_EPOCH"],
             lambda r: r.__setitem__(slice(live + 30, live + 32), list(reversed(r[live + 30:live + 32]))))
    mutation("missing_end", ["END_MISSING"], lambda r: r.pop())
    mutation("duplicate_end", ["RECORD_AFTER_END"], lambda r: r.append(r[-1]))
    mutation("wrong_end", ["END_COUNTERS"], field(len(original) - 1, "cycle", 11999))
    mutation("missing_field", ["TICK_FIELDS"], lambda r: r[commit].pop("clipped"))
    mutation("invented_first_valid", ["BIT_OR_FIRST_VALID"], field(commit, "first_valid", 0))
    mutation("x_pin", ["X_OR_NONINTEGER"], field(live + 10, "din", "x"))
    mutation("bool_pin", ["X_OR_NONINTEGER"], field(live + 10, "din", True))
    mutation("out_of_range_bit", ["BIT_OR_FIRST_VALID"], field(live + 10, "din", 2))
    mutation("pcm_range", ["PCM24_RANGE"], field(commit, "left", 8388608))
    mutation("pcm_negative_range", ["PCM24_RANGE"], field(commit, "right", -8388609))
    mutation("wrong_pcm", ["PLAY_PCM_COMMIT_OR_HOLD_ALIGNMENT"], field(commit, "left", 7))
    mutation("wrong_commit_id", ["STALE_DUPLICATE_OR_UNREQUESTED_COMMIT"], field(commit, "committed_id", 999))
    mutation("missing_accept", ["STALE_DUPLICATE_OR_UNREQUESTED_COMMIT"], field(request, "request_accept", 0))
    mutation("duplicate_accept", ["DUPLICATE_REQUEST_ID"], field(request + 1, "request_accept", 1))
    mutation("wrong_clip", ["CLIP_COUNT_ALIGNMENT"], field(commit + 1, "clip_count", 123))
    mutation("wrong_pending", ["PENDING_ALIGNMENT"], field(commit + 1, "pending", 0))
    mutation("underflow", ["UNEXPECTED_UNDERFLOW"], field(commit + 1, "underflow", 1))
    mutation("same_frame_commit", ["FRAME_FENCE_HANDSHAKE"], field(frame, "commit", 1))
    def missed_first_deadline(rows):
        next_frame = next(i for i in ticks if i > frame and rows[i]["frame_tick"])
        for row in rows[commit:next_frame + 1]:
            row.update(commit=0, pending=0, play_left=0, play_right=0, clip_count=0)
    mutation("first_request_misses_frame", ["REQUEST_NEXT_FRAME_DEADLINE_MISSED"], missed_first_deadline)
    def reset_then_end(rows):
        rows[-1:] = [{"kind": "RESET", "cycle": 12000, "epoch": 2, "time_ns": 300001},
                     {"kind": "END", "cycle": 12000, "epoch": 2}]
    mutation("reset_then_end_without_tick", ["END_WITH_UNOBSERVED_RESET"], reset_then_end)
    def stalled_tail(rows):
        start = next(i for i in ticks if rows[i]["cycle"] == 11900)
        prior = rows[start - 1]
        for row in rows[start:-1]:
            row.update(bclk=prior["bclk"], ws=prior["ws"], din=prior["din"], frame_tick=0)
    mutation("bclk_stalled_tail", ["BCLK_STALLED_OR_MISSING_EDGE"], stalled_tail)
    mutation("missing_reset", ["TICK_ORDER_MISSING_DUPLICATE_OR_EPOCH"], lambda r: r.pop(reset))
    mutation("wrong_reset_epoch", ["RESET_SEQUENCE"], field(reset, "epoch", 9))
    mutation("reset_nonzero", ["RESET_OUTPUT_NOT_ZERO"], field(reset + 2, "din", 1))
    mutation("wrong_frame_phase", ["FRAME_TICK_BCLK_PHASE", "FRAME_WS_BOUNDARY_PHASE"],
             field(live + 100, "frame_tick", 1))

    def bad_serial(rows, swap=False):
        for row in rows:
            if row["kind"] == "TICK" and row["rst_n"] and row["cycle"] > 2000:
                if swap:
                    row["ws"] ^= 1
                else:
                    row["din"] ^= 1
    mutation("wrong_serial_bits", ["WS_DIN_CHANGED_OUTSIDE_FALLING_BCLK", "LSBJ_PADDING_OR_PHASE"], bad_serial)
    mutation("swap_channels", ["WS_DIN_CHANGED_OUTSIDE_FALLING_BCLK", "FRAME_WS_BOUNDARY_PHASE",
                                 "SERIAL_PCM_OR_CHANNEL_MISMATCH"], lambda r: bad_serial(r, True))
    for name, records, expected in (
        ("serial_channels_swapped_with_valid_pin_phase", synthetic_records(swap_serial=True),
         "SERIAL_PCM_OR_CHANNEL_MISMATCH"),
        ("serial_load_one_slot_early", synthetic_records(load_slot=15), "SERIAL_PCM_OR_CHANNEL_MISMATCH")):
        path = args.output / (name + ".SYNTHETIC.jsonl")
        write_records(path, records)
        try:
            analyze(path, sha256(path))
            actual = "ACCEPTED"
        except ValueError as exc:
            actual = str(exc)
        results.append({"name": name, "expected": expected, "actual": actual,
                        "passed": actual == expected, "kind": "SYNTHETIC_SERIAL_GENERATOR",
                        "sha256": sha256(path)})
    reset_pending = args.output / "reset_after_commit.SYNTHETIC.jsonl"
    write_records(reset_pending, synthetic_records(reset_cycle=4350))
    reset_result = analyze(reset_pending)
    results.append({"name": "commit_reset_before_sample_known_cancel", "passed":
                    reset_result["commits_cancelled_by_reset_before_next_frame"] == 1,
                    "kind": "SYNTHETIC_SOFTWARE_ONLY"})
    (args.output / "reset_after_commit.RESULT.json").write_text(
        json.dumps(reset_result, indent=2) + "\n", encoding="utf-8")
    for start, end, expected in ((10, 400010, None), (10, 400011, "DIGITAL_LATENCY_OVER_10MS"),
                                 (10, 9, "DIGITAL_TIME_ORDER")):
        try:
            digital_cycles(start, end)
            actual = None
        except ValueError as exc:
            actual = str(exc)
        results.append({"name": f"digital_{start}_{end}", "passed": actual == expected,
                        "expected": expected, "actual": actual, "kind": "SYNTHETIC_TIMESTAMPS_ONLY"})
    for value, expected in ((8388607, 32767), (-8388608, -32768), (8388480, 32767),
                             (127, 0), (128, 1), (-128, 0), (-129, -1)):
        actual = quantize(value)
        results.append({"name": f"quantize_{value}", "passed": actual == expected,
                        "expected": expected, "actual": actual, "kind": "INTEGER_BOUNDARY"})
    for name, passed in (("tail_deadline_unknown", baseline["commits_with_unknown_next_frame_deadline"] > 0),
                          ("reset_cancellation", baseline["cancelled_requests"] > 0),
                          ("serial_signed_stereo", any(r["left"] != r["right"] and r["right"] < 0
                                                       for r in baseline["serial_frames"]))):
        results.append({"name": name, "passed": passed, "kind": "SYNTHETIC_COVERAGE"})
    # Duplicate-key rejection must be tested with raw JSON, not a dict.
    duplicate = args.output / "duplicate_key.SYNTHETIC.jsonl"
    duplicate.write_text(positive.read_text(encoding="utf-8").replace(
        '"clock_hz":40000000', '"clock_hz":40000000,"clock_hz":40000000', 1), encoding="utf-8")
    try:
        analyze(duplicate)
        actual = "ACCEPTED"
    except ValueError as exc:
        actual = str(exc)
    results.append({"name": "duplicate_json_key", "passed": actual == "JSON_DUPLICATE_KEY",
                    "actual": actual, "kind": "SYNTHETIC_MUTATION"})
    try:
        analyze(positive, "0" * 64)
        actual = "ACCEPTED"
    except ValueError as exc:
        actual = str(exc)
    results.append({"name": "sha_mismatch", "passed": actual == "CAPTURE_SHA_MISMATCH", "actual": actual})
    (args.output / "RESULTS.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"tests": len(results), "passed": sum(r["passed"] for r in results),
                      "failed": [r for r in results if not r["passed"]],
                      "evidence_kind": "SYNTHETIC_SOFTWARE_ONLY"}))
    return int(not all(r["passed"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
