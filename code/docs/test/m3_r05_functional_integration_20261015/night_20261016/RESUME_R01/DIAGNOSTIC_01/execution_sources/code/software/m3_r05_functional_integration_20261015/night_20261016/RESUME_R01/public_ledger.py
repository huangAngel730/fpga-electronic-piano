"""Independent acceptance/frame/commit ledger; no inference from max_cycles."""
from common import Refusal, json_load
from bisect import bisect_right


FIELDS = {
    "kind", "cycle", "epoch", "rst_n", "frame_tick", "request_accept", "request_id",
    "commit", "committed_id", "left", "right", "clipped", "pending",
    "play_left", "play_right", "clip_count", "underflow", "bclk", "ws", "din", "first_valid",
}
BITS = ("rst_n", "frame_tick", "request_accept", "commit", "clipped", "pending", "bclk", "ws", "din")


def analyze(data):
    lines = data.splitlines()
    if not lines:
        raise Refusal("CAPTURE_EMPTY", "missing header")
    records = [json_load(line) for line in lines]
    header = records[0]
    if header != {
        "kind": "HEADER", "schema": "M3_R05_PUBLIC_PRE_NBA_V1",
        "clock_hz": 40000000, "first_valid_observable": False,
    } or type(header.get("clock_hz")) is not int or header.get("first_valid_observable") is not False:
        raise Refusal("CAPTURE_HEADER", "wrong public trace contract")
    if len(records) < 3 or records[-1].get("kind") != "END":
        raise Refusal("CAPTURE_END", "missing unique terminal END")
    if any(r.get("kind") == "END" for r in records[1:-1]):
        raise Refusal("CAPTURE_END", "early or duplicate END")
    cycle, epoch = 0, 0
    boundaries = {}
    for item in records[1:-1]:
        if item.get("kind") == "TICK" and item.get("frame_tick") == 1:
            if type(item.get("epoch")) is int and type(item.get("cycle")) is int:
                boundaries.setdefault(item["epoch"], []).append(item["cycle"])
    outstanding = {}
    accepted = committed = cancelled = 0
    last_frame = None
    intervals = []
    latencies = []
    all_ids = set()
    last_clip = 0
    clip_pending = 0
    initialized = False
    previous_reset = None
    proven_deadlines = 0
    deadline_unknown = 0
    for item in records[1:-1]:
        kind = item.get("kind")
        if kind == "RESET":
            if set(item) != {"kind", "epoch", "cycle", "time_ns"}:
                raise Refusal("CAPTURE_RESET", "wrong reset fields")
            if any(type(item[k]) is not int for k in ("epoch", "cycle", "time_ns")) or item["time_ns"] < 0:
                raise Refusal("CAPTURE_RESET", "reset fields must be nonnegative integers")
            if item["epoch"] != epoch + 1 or item["cycle"] != cycle:
                raise Refusal("CAPTURE_RESET", "wrong reset lifetime/cycle")
            previous_reset = 0
            epoch = item["epoch"]
            cancelled += len(outstanding)
            outstanding.clear()
            all_ids.clear()
            last_frame = None
            last_clip = clip_pending = 0
            initialized = False
            continue
        if kind != "TICK" or set(item) != FIELDS:
            raise Refusal("CAPTURE_FIELDS", "unknown row or fields")
        for name in FIELDS - {"kind", "first_valid"}:
            if type(item[name]) is not int:
                raise Refusal("CAPTURE_X_OR_TYPE", name)
        if item["cycle"] != cycle + 1 or item["epoch"] != epoch:
            raise Refusal("CAPTURE_ORDER", "missing/repeated/out-of-order tick")
        cycle += 1
        if any(item[name] not in (0, 1) for name in BITS) or item["first_valid"] is not None:
            raise Refusal("CAPTURE_BIT", "invalid bit or invented first valid")
        for name in ("left", "right", "play_left", "play_right"):
            if not -(1 << 23) <= item[name] < (1 << 23):
                raise Refusal("PCM24_RANGE", name)
        for name in ("request_id", "committed_id", "clip_count", "underflow"):
            if not 0 <= item[name] <= 0xFFFFFFFF:
                raise Refusal("CAPTURE_UNSIGNED_RANGE", name)
        if not item["rst_n"]:
            # Assertion may share this first posedge: pre-NBA observer has
            # no license to invent post-NBA reset values on that same edge.
            if previous_reset == 1:
                raise Refusal("CAPTURE_RESET", "reset assertion missing independent RESET record")
            previous_reset = 0
            continue
        if previous_reset == 0:
            outstanding.clear()
            last_frame = None
            initialized = False
        previous_reset = 1
        if item["underflow"]:
            raise Refusal("UNDERFLOW", str(cycle))
        if initialized and item["clip_count"] != min(last_clip + clip_pending, 0xFFFFFFFF):
            raise Refusal("CLIP_COUNT_ALIGNMENT", str(cycle))
        initialized = True
        last_clip = item["clip_count"]
        clip_pending = 0
        if item["frame_tick"]:
            if last_frame is not None:
                interval = cycle - last_frame
                if interval not in (833, 834):
                    raise Refusal("FRAME_INTERVAL", str(interval))
                intervals.append(interval)
            last_frame = cycle
            cancelled += len(outstanding)
            outstanding.clear()
            if item["request_accept"] or item["commit"]:
                raise Refusal("SAME_FRAME_ACCEPT_OR_COMMIT", str(cycle))
        if item["request_accept"]:
            key = (epoch, item["request_id"])
            if key in all_ids:
                raise Refusal("DUPLICATE_REQUEST_ID", str(key))
            all_ids.add(key)
            outstanding[key] = (cycle, last_frame)
            accepted += 1
        if item["commit"]:
            key = (epoch, item["committed_id"])
            if key not in outstanding:
                raise Refusal("STALE_OR_DUPLICATE_COMMIT", str(key))
            start, frame = outstanding.pop(key)
            latency = cycle - start
            if latency < 1 or latency > 400000:
                raise Refusal("DIGITAL_LATENCY_OVER_10MS", str(latency))
            next_frames = boundaries.get(epoch, [])
            position = bisect_right(next_frames, start)
            if position >= len(next_frames):
                deadline_unknown += 1
            elif cycle >= next_frames[position]:
                raise Refusal("REQUEST_FRAME_DEADLINE", str(cycle))
            else:
                proven_deadlines += 1
            latencies.append(latency)
            committed += 1
            clip_pending = item["clipped"]
    if records[-1] != {"kind": "END", "cycle": cycle, "epoch": epoch} or any(
        type(records[-1].get(k)) is not int for k in ("cycle", "epoch")
    ):
        raise Refusal("CAPTURE_END", "terminal counters differ")
    if accepted == 0 or committed == 0 or len(intervals) < 3:
        raise Refusal("COVERAGE_INSUFFICIENT", "need accepted/commit and three frame intervals")
    # Frequency can only be assessed on a complete 3-frame 2500-cycle period;
    # not all valid windows start at accumulator phase zero.
    for index in range(len(intervals) - 2):
        if sum(intervals[index:index + 3]) != 2500:
            raise Refusal("FRAME_48K_DISTRIBUTION", str(intervals[index:index + 3]))
    return {
        "status": "PUBLIC_LEDGER_CONSISTENT", "ticks": cycle, "epochs": epoch + 1,
        "accepted": accepted, "committed": committed, "cancelled": cancelled,
        "pending_at_end": len(outstanding), "frame_intervals": intervals,
        "max_accept_to_commit_cycles": max(latencies),
        "commits_with_observed_next_frame_deadline": proven_deadlines,
        "commits_without_observed_next_frame_boundary": deadline_unknown,
        "per_request_deadline": "UNKNOWN_TAIL_BOUNDARY" if deadline_unknown else "CONSISTENT_FOR_OBSERVED_FRAME_WINDOWS",
        "first_valid": "UNKNOWN_NOT_EXPORTED", "serial_decode": "DELEGATED_TO_C_RAW_PIN_CHECKER",
        "clip_math": "UNKNOWN_ONLY_PUBLIC_ALIGNMENT_CHECKED",
        "analog_latency": "UNKNOWN_NOT_MEASURED", "board_release_allowed": False,
    }
