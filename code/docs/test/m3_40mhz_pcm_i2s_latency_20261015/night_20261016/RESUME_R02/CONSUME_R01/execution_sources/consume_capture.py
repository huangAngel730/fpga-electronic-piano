"""Independent R05 public-port ledger and PT8211 physical-pin decoder.

Streaming input; no imports from producer/checker or fixture golden calendar.
Only complete observed frame windows prove deadlines. No analog timing claim.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


HEADER = {"kind": "HEADER", "schema": "M3_R05_PUBLIC_PRE_NBA_V1",
          "clock_hz": 40000000, "first_valid_observable": False}
FIELDS = set("kind cycle epoch rst_n frame_tick request_accept request_id commit "
             "committed_id left right clipped pending play_left play_right "
             "clip_count underflow bclk ws din first_valid".split())
BITS = "rst_n frame_tick request_accept commit clipped pending bclk ws din".split()
PCM = "left right play_left play_right".split()
UNSIGNED = "request_id committed_id clip_count underflow".split()


def require(ok, diagnostic):
    if not ok:
        raise ValueError(diagnostic)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "JSON_DUPLICATE_KEY")
        result[key] = value
    return result


def parse_json(line):
    try:
        value = json.loads(line, object_pairs_hook=unique_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(
                               ValueError("JSON_NONFINITE")))
    except json.JSONDecodeError as exc:
        raise ValueError("JSON_INVALID") from exc
    require(type(value) is dict, "JSON_OBJECT_REQUIRED")
    return value


def quantize(value):
    require(type(value) is int and -(1 << 23) <= value < (1 << 23), "PCM24_RANGE")
    return min(32767, max(-32768, (value + 128) // 256))


def digital_cycles(start, end):
    require(type(start) is int and type(end) is int and 0 <= start <= end,
            "DIGITAL_TIME_ORDER")
    require(end - start <= 400000, "DIGITAL_LATENCY_OVER_10MS")
    return end - start


class PinDecoder:
    """Decode external WS-bounded words, then compare against sampled PCM.

    Output changes become visible one TICK after the pre-NBA frame_tick.
    WS transitions happen on falling BCLK. The full-frame pulse is on the
    preceding falling edge to WS high->low (frozen transmitter contract).
    """
    def __init__(self, ledger):
        self.ledger = ledger
        self.frames = []
        self.halves = []
        self.partial_resets = 0
        self.clear()

    def clear(self):
        self.previous = None
        self.active_start = None
        self.last_toggle = self.last_rise = None
        self.last_fall_frame = False
        self.synchronized = False
        self.bits = []
        self.word_ws = 0
        self.word_sample = None
        self.right_half = None
        self.current_sample = {"cycle": 0, "epoch": None, "left": 0,
                               "right": 0, "id": None, "frame": 0}

    def reset(self):
        self.partial_resets += int(bool(self.bits or self.right_half))
        self.clear()

    def complete_half(self, row):
        require(len(self.bits) == 32, "WS_HALF_NOT_32_BCLK")
        require(not any(bit for _, bit in self.bits[:16]), "LSBJ_PADDING_OR_PHASE")
        raw = 0
        for _, bit in self.bits[16:]:
            raw = (raw << 1) | bit
        decoded = raw - 65536 if raw & 32768 else raw
        sample = self.word_sample
        channel = "left" if self.word_ws else "right"
        require(decoded == quantize(sample[channel]), "SERIAL_PCM_OR_CHANNEL_MISMATCH")
        half = {"epoch": row["epoch"], "channel": channel,
                "first_rise_cycle": self.bits[0][0],
                "last_rise_cycle": self.bits[-1][0],
                "completed_at_boundary_cycle": row["cycle"],
                "sample_frame": sample["frame"], "sample_cycle": sample["cycle"],
                "request_id": sample["id"], "pcm24": sample[channel], "pcm16": decoded}
        self.halves.append(half)
        if channel == "right":
            self.right_half = half
        elif self.right_half:
            right = self.right_half
            require(right["sample_frame"] == half["sample_frame"]
                    and right["sample_cycle"] == half["sample_cycle"], "STEREO_FRAME_MIX")
            frame = {"epoch": row["epoch"], "frame": sample["frame"],
                     "sample_cycle": sample["cycle"], "request_id": sample["id"],
                     "left": decoded, "right": right["pcm16"],
                     "start_cycle": right["first_rise_cycle"],
                     "last_data_cycle": half["last_rise_cycle"],
                     "boundary_cycle": row["cycle"]}
            if sample["id"] is not None:
                key = (row["epoch"], sample["id"])
                entry = self.ledger[key]
                # Held replays remain serial frames, never fresh commits.
                if "serial_last_data_cycle" not in entry:
                    entry["serial_last_data_cycle"] = half["last_rise_cycle"]
                    entry["digital_request_to_serial_cycles"] = digital_cycles(
                        entry["request_cycle"], half["last_rise_cycle"])
            self.frames.append(frame)
            self.right_half = None

    def observe(self, row):
        if not row["rst_n"]:
            self.reset()
            return
        previous = self.previous
        if previous is not None:
            toggle = previous["bclk"] != row["bclk"]
            falling = toggle and row["bclk"] == 0
            rising = toggle and row["bclk"] == 1
            require(not previous["frame_tick"] or falling, "FRAME_TICK_BCLK_PHASE")
            if toggle:
                if self.last_toggle is not None:
                    require(row["cycle"] - self.last_toggle in (6, 7), "BCLK_HALF_PERIOD")
                self.last_toggle = row["cycle"]
            require(row["cycle"] - (self.last_toggle if self.last_toggle is not None
                                     else self.active_start) <= 7, "BCLK_STALLED_OR_MISSING_EDGE")
            changed = previous["ws"] != row["ws"] or previous["din"] != row["din"]
            require(not changed or falling, "WS_DIN_CHANGED_OUTSIDE_FALLING_BCLK")
            if falling:
                high_to_low = previous["ws"] == 1 and row["ws"] == 0
                require(high_to_low == self.last_fall_frame, "FRAME_WS_BOUNDARY_PHASE")
                self.last_fall_frame = bool(previous["frame_tick"])
            if rising:
                if self.last_rise is not None:
                    require(row["cycle"] - self.last_rise in (13, 14), "BCLK_PERIOD")
                self.last_rise = row["cycle"]
                if row["ws"] != self.word_ws:
                    if self.synchronized:
                        self.complete_half(row)
                    self.synchronized = True
                    self.bits = []
                    self.word_ws = row["ws"]
                    self.word_sample = dict(self.current_sample)
                if self.synchronized:
                    self.bits.append((row["cycle"], row["din"]))
                    require(len(self.bits) <= 32, "WS_HALF_NOT_32_BCLK")
        if self.active_start is None:
            self.active_start = row["cycle"]
        self.previous = row


def analyze(path, expected_sha256=None):
    path = Path(path)
    before = sha256(path)
    if expected_sha256 is not None:
        require(before == expected_sha256, "CAPTURE_SHA_MISMATCH")
    ledger = {}
    pins = PinDecoder(ledger)
    outstanding = None
    pending = None
    held = (0, 0, None)
    cycle = epoch = 0
    frame_number = 0
    clip_count = 0
    last_frame = None
    per_epoch = {}
    resets = []
    samples = []
    end_seen = False
    prior_rst = None
    reset_since_tick = False
    released_once = False
    first_active_cycle = None

    def cancel(reason, at_cycle):
        nonlocal outstanding
        if outstanding is not None:
            ledger[outstanding].update(status=reason, cancel_cycle=at_cycle)
            outstanding = None

    with path.open("r", encoding="utf-8") as stream:
        first = stream.readline()
        require(bool(first), "HEADER_MISSING")
        header = parse_json(first)
        require(header == HEADER and type(header["clock_hz"]) is int
                and header["first_valid_observable"] is False, "HEADER_CONTRACT")
        for line_number, line in enumerate(stream, 2):
            require(not end_seen, "RECORD_AFTER_END")
            row = parse_json(line)
            kind = row.get("kind")
            if kind == "END":
                require(not reset_since_tick, "END_WITH_UNOBSERVED_RESET")
                require(row == {"kind": "END", "cycle": cycle, "epoch": epoch}
                        and type(row["cycle"]) is int and type(row["epoch"]) is int,
                        "END_COUNTERS")
                end_seen = True
                continue
            if kind == "RESET":
                require(set(row) == {"kind", "epoch", "cycle", "time_ns"}, "RESET_FIELDS")
                require(all(type(row[k]) is int and row[k] >= 0
                            for k in ("epoch", "cycle", "time_ns")), "RESET_TYPE")
                require(row["epoch"] == epoch + 1 and row["cycle"] == cycle,
                        "RESET_SEQUENCE")
                require(not resets or row["time_ns"] > resets[-1]["time_ns"], "RESET_TIME_ORDER")
                cancel("CANCELLED_RESET", cycle)
                for key, entry in ledger.items():
                    if key[0] == epoch and "commit_cycle" in entry and "serial_last_data_cycle" not in entry:
                        entry["serial_disposition"] = "CANCELLED_RESET_BEFORE_SERIAL_COMPLETE"
                        entry["reset_cycle"] = cycle
                if pending is not None:
                    ledger[(epoch, pending[2])].update(
                        sample_disposition="CANCELLED_RESET_BEFORE_SAMPLE",
                        deadline="CANCELLED_RESET_BEFORE_NEXT_FRAME", reset_cycle=cycle)
                epoch = row["epoch"]
                resets.append(row)
                reset_since_tick = True
                pending = None
                held = (0, 0, None)
                clip_count = frame_number = 0
                last_frame = None
                first_active_cycle = None
                pins.reset()
                continue
            require(kind == "TICK" and set(row) == FIELDS, "TICK_FIELDS")
            require(all(type(row[k]) is int for k in FIELDS - {"kind", "first_valid"}),
                    "X_OR_NONINTEGER")
            require(row["cycle"] == cycle + 1 and row["epoch"] == epoch,
                    "TICK_ORDER_MISSING_DUPLICATE_OR_EPOCH")
            require(all(row[k] in (0, 1) for k in BITS) and row["first_valid"] is None,
                    "BIT_OR_FIRST_VALID")
            require(all(-(1 << 23) <= row[k] < (1 << 23) for k in PCM), "PCM24_RANGE")
            require(all(0 <= row[k] <= 0xFFFFFFFF for k in UNSIGNED), "UNSIGNED_RANGE")
            cycle += 1
            if not row["rst_n"]:
                require(prior_rst != 1 or reset_since_tick, "RESET_ASSERTION_RECORD_MISSING")
                if prior_rst == 0:
                    require(not any(row[k] for k in ("frame_tick", "request_accept", "commit",
                            "pending", "play_left", "play_right", "clip_count", "underflow",
                            "bclk", "ws", "din")), "RESET_OUTPUT_NOT_ZERO")
                cancel("CANCELLED_RESET", cycle)
                pending = None
                held = (0, 0, None)
                clip_count = frame_number = 0
                last_frame = None
                first_active_cycle = None
                pins.observe(row)
                prior_rst = 0
                reset_since_tick = False
                continue
            require(not reset_since_tick, "RESET_RECORD_WITHOUT_LOW_TICK")
            require(prior_rst is not None, "INITIAL_RESET_NOT_OBSERVED")
            released_once = True
            if first_active_cycle is None:
                first_active_cycle = cycle
            prior_rst = 1
            require(cycle - (last_frame if last_frame is not None else first_active_cycle) <= 834,
                    "FRAME_STALLED_OR_MISSING_TICK")
            require(row["underflow"] == 0, "UNEXPECTED_UNDERFLOW")
            require(row["clip_count"] == clip_count, "CLIP_COUNT_ALIGNMENT")
            require(row["pending"] == int(pending is not None), "PENDING_ALIGNMENT")
            expected_play = pending if pending is not None else held
            require((row["play_left"], row["play_right"]) == expected_play[:2],
                    "PLAY_PCM_COMMIT_OR_HOLD_ALIGNMENT")
            pins.observe(row)
            if row["frame_tick"]:
                gaps = per_epoch.setdefault(str(epoch), [])
                if last_frame is not None:
                    gap = cycle - last_frame
                    require(gap in (833, 834), "FRAME_INTERVAL")
                    gaps.append(gap)
                    if len(gaps) >= 3:
                        require(sum(gaps[-3:]) == 2500, "FRAME_48K_DISTRIBUTION")
                last_frame = cycle
                frame_number += 1
                require(not row["commit"] and not row["request_accept"], "FRAME_FENCE_HANDSHAKE")
                require(outstanding is None, "REQUEST_NEXT_FRAME_DEADLINE_MISSED")
                require(pending is not None or held[2] is None,
                        "FRAME_WITHOUT_PENDING_AFTER_STARTUP")
                cancel("CANCELLED_FRAME", cycle)
                sample = {"epoch": epoch, "cycle": cycle, "frame": frame_number,
                          "left": row["play_left"], "right": row["play_right"],
                          "id": expected_play[2]}
                samples.append(sample)
                # TX captures these pre-NBA inputs on this edge. Pins still
                # refer to the previous sample until the next channel word.
                pins.current_sample = sample
                if pending is not None:
                    key = (epoch, pending[2])
                    ledger[key].update(sample_cycle=cycle, deadline="PROVEN_BEFORE_NEXT_FRAME",
                                       next_frame_cycle=cycle)
                    held = pending
                    pending = None
            if row["request_accept"]:
                key = (epoch, row["request_id"])
                require(last_frame is not None, "ACCEPT_BEFORE_FIRST_FRAME")
                require(key not in ledger, "DUPLICATE_REQUEST_ID")
                require(outstanding is None and pending is None, "MULTIPLE_FRAME_REQUESTS")
                require(row["request_id"] == frame_number & 0xFFFFFFFF, "REQUEST_FRAME_ID")
                ledger[key] = {"epoch": epoch, "id": row["request_id"], "request_cycle": cycle,
                               "request_frame_cycle": last_frame, "status": "IN_FLIGHT",
                               "deadline": "UNKNOWN_TAIL_BOUNDARY"}
                outstanding = key
            if row["commit"]:
                key = (epoch, row["committed_id"])
                require(outstanding == key, "STALE_DUPLICATE_OR_UNREQUESTED_COMMIT")
                require(pending is None, "COMMIT_WHILE_PENDING")
                entry = ledger[key]
                elapsed = digital_cycles(entry["request_cycle"], cycle)
                require(elapsed >= 1, "COMMIT_NOT_AFTER_ACCEPT")
                entry.update(commit_cycle=cycle, left=row["left"], right=row["right"],
                             clipped=row["clipped"], status="COMMITTED",
                             accept_to_commit_cycles=elapsed)
                pending = (row["left"], row["right"], row["committed_id"])
                outstanding = None
                clip_count = min(0xFFFFFFFF, clip_count + row["clipped"])
    require(end_seen, "END_MISSING")
    require(released_once, "NO_ACTIVE_LIFETIME")
    require(any(len(gaps) >= 3 for gaps in per_epoch.values()), "FRAME_COVERAGE_INSUFFICIENT")
    require(ledger and any("commit_cycle" in r for r in ledger.values()), "REQUEST_COMMIT_COVERAGE")
    require(pins.frames, "SERIAL_FRAME_COVERAGE")
    require(sha256(path) == before, "CAPTURE_CHANGED_DURING_READ")
    committed = [r for r in ledger.values() if "commit_cycle" in r]
    serial = [r for r in committed if "serial_last_data_cycle" in r]
    unknown_deadlines = sum(r["deadline"] == "UNKNOWN_TAIL_BOUNDARY" for r in committed)
    return {"passed": True, "level": "L1_INDEPENDENT_CONSUMER_OF_SUPPLIED_CAPTURE",
            "capture_sha256": before, "ticks": cycle, "last_epoch": epoch,
            "clock_hz": 40000000, "sample_rate_hz": 48000,
            "accepted_requests": len(ledger), "committed_requests": len(committed),
            "cancelled_requests": sum(r["status"].startswith("CANCELLED") for r in ledger.values()),
            "pending_requests_at_end": int(outstanding is not None),
            "commits_with_proven_next_frame_deadline": sum(
                r["deadline"] == "PROVEN_BEFORE_NEXT_FRAME" for r in committed),
            "commits_with_unknown_next_frame_deadline": unknown_deadlines,
            "commits_cancelled_by_reset_before_next_frame": sum(
                r["deadline"] == "CANCELLED_RESET_BEFORE_NEXT_FRAME" for r in committed),
            "serial_observed_committed_requests": len(serial),
            "serial_unobserved_committed_requests": len(committed) - len(serial),
            "frame_distribution": {e: dict(Counter(g)) for e, g in per_epoch.items()},
            "max_accept_to_commit_cycles": max(r["accept_to_commit_cycles"] for r in committed),
            "max_request_to_serial_cycles": max((r["digital_request_to_serial_cycles"] for r in serial), default=None),
            "reset_records": resets, "sampled_frames": samples,
            "request_ledger": list(ledger.values()), "serial_frames": pins.frames,
            "serial_half_frames": pins.halves, "partial_serial_aborted_by_reset": pins.partial_resets,
            "first_valid": "UNKNOWN_NOT_EXPORTED", "clip_math": "UNKNOWN_PUBLIC_METADATA_ONLY",
            "analog_end_to_end_10ms": "UNKNOWN_NOT_MEASURED", "board_release_allowed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), "REFUSE_OVERWRITE")
    try:
        result = analyze(args.capture, args.sha256)
        code = 0
    except (ValueError, OSError, UnicodeError) as exc:
        result = {"passed": False, "diagnostic": str(exc), "board_release_allowed": False}
        code = 1
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k not in (
        "request_ledger", "serial_frames", "serial_half_frames", "sampled_frames")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
