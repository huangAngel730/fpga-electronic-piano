"""Strict capture2 transport grammar, independent of M1's checker.

No field projection, sorted reconstruction, bool-as-int or duplicate JSON keys.
This module checks transport/structure, not envelope or PCM arithmetic.
"""
from collections import Counter, defaultdict
import json
import re


class CaptureError(ValueError):
    """A specific input contract violation."""


def require(condition, code):
    if not condition:
        raise CaptureError(code)


def integer(value, low, high, name):
    require(type(value) is int and low <= value <= high, "INTEGER_RANGE:" + name)
    return value


def hexword(value, bits, name):
    require(type(value) is str and re.fullmatch(r"[0-9a-fA-F]{%d}" % ((bits + 3) // 4), value)
            and int(value, 16) < 1 << bits, "HEX_WIDTH:" + name)
    return int(value, 16)


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_KEY:" + key)
        result[key] = value
    return result


STATE_RANGES = {
    "epoch": (1, 2**31-1), "cycle": (1, 2**31-1), "lane": (0, 3),
    "pending_request_id": (0, 2**32-1), "tick": (0, 1), "note_on": (0, 1),
    "note_off": (0, 1), "occupied": (0, 1), "source": (0, 15), "channel": (0, 15),
    "note": (0, 127), "generation": (0, 2**32-1), "velocity": (0, 1023),
    "raw_state": (0, 10), "public_state": (0, 4), "elapsed": (0, 8191),
    "table": (0, 3), "envelope": (0, 32767),
}
STATE_HEX = {"level_q16": 32, "start_q16": 32, "peak_q16": 32,
             "sustain_q16": 32, "step_q16_twos33": 33, "phase_acc": 32, "dds_fcw": 32}
PUBLIC_STATES = {0: 0, 1: 1, 2: 1, 3: 1, 4: 2, 5: 3, 6: 4, 7: 1, 8: 1, 9: 4, 10: 4}
META = {"tag": "META", "schema": 1, "sys_hz": 40000000, "sample_hz": 48000,
        "physical_PLL_test": False, "analog_test": False}


def parse_jsonl(text):
    require(bool(text.strip()), "EMPTY_JSONL")
    rows = []
    for line_number, line in enumerate(text.splitlines(), 1):
        require(bool(line.strip()), "BLANK_JSONL_LINE")
        try:
            row = json.loads(line, object_pairs_hook=object_pairs,
                             parse_constant=lambda value: (_ for _ in ()).throw(CaptureError("NONFINITE_JSON")))
        except (json.JSONDecodeError, CaptureError) as error:
            raise CaptureError(f"JSON_LINE:{line_number}:{error}") from error
        require(type(row) is dict and type(row.get("tag")) is str, "JSON_RECORD_OBJECT")
        rows.append(row)
    require(set(rows[0]) == set(META), "META_KEYS")
    require(all(type(rows[0][k]) is type(v) and rows[0][k] == v for k, v in META.items()), "META_PROFILE")
    counts = Counter({name: 0 for name in ("RESET", "REQUEST", "STATE", "COMMIT")})
    pending, seen, groups = set(), set(), defaultdict(list)
    epoch, cycle, finished = 0, 0, False
    cancelled = []
    last_request = 0
    for row in rows[1:]:
        require(not finished, "JSON_RECORD_AFTER_END")
        tag = row["tag"]
        require(tag in (*counts, "END"), "UNKNOWN_JSON_TAG:" + tag)
        if tag == "END":
            require(set(row) == {"tag", "counts"} and type(row["counts"]) is dict, "END_KEYS")
            require(set(row["counts"]) == set(counts), "END_COUNT_KEYS")
            for name, amount in row["counts"].items():
                integer(amount, 0, 2**31-1, "END." + name)
            require(dict(counts) == row["counts"], "END_COUNTS")
            require(not pending, "END_PENDING_REQUEST")
            require(counts["RESET"] and counts["REQUEST"] and counts["COMMIT"] and counts["STATE"], "EMPTY_JSON_TRANSACTION_SET")
            finished = True
            continue
        integer(row.get("cycle"), 1, 2**31-1, "cycle")
        require(row["cycle"] >= cycle, "JSON_CYCLE_ORDER")
        cycle = row["cycle"]
        integer(row.get("epoch"), 1, 2**31-1, "epoch")
        if tag == "RESET":
            require(set(row) == {"tag", "epoch", "cycle"}, "RESET_KEYS")
            require(row["epoch"] == epoch + 1, "RESET_EPOCH_ORDER")
            cancelled.extend(sorted(pending))
            pending.clear()
            epoch, last_request = row["epoch"], 0
        else:
            require(row["epoch"] == epoch and epoch > 0, "JSON_EPOCH_BINDING")
            if tag in ("REQUEST", "COMMIT"):
                keys = {"tag", "epoch", "cycle", "request_id"}
                if tag == "COMMIT":
                    keys |= {"pcm_left", "pcm_right"}
                require(set(row) == keys, tag + "_KEYS")
                integer(row["request_id"], 1, 2**32-1, "request_id")
                key = epoch, row["request_id"]
                if tag == "REQUEST":
                    require(key not in seen, "DUPLICATE_REQUEST")
                    require(row["request_id"] > last_request, "REQUEST_ORDER")
                    last_request = row["request_id"]
                    pending.add(key)
                    seen.add(key)
                else:
                    require(key in pending, "ORPHAN_OR_DUPLICATE_COMMIT")
                    for name in ("pcm_left", "pcm_right"):
                        integer(row[name], -(1 << 23), (1 << 23)-1, name)
                    pending.remove(key)
            else:
                require(set(row) == {"tag", *STATE_RANGES, *STATE_HEX}, "STATE_KEYS")
                for name, (low, high) in STATE_RANGES.items():
                    integer(row[name], low, high, name)
                for name, bits in STATE_HEX.items():
                    hexword(row[name], bits, name)
                require(row["tick"] or row["note_on"] or row["note_off"], "STATE_WITHOUT_TRIGGER")
                require(row["public_state"] == PUBLIC_STATES[row["raw_state"]], "STATE_ENUM_MAPPING")
                if row["tick"]:
                    require((epoch, row["pending_request_id"]) in pending, "TICK_WITHOUT_PENDING_REQUEST")
                key = epoch, cycle
                require(row["lane"] not in [x["lane"] for x in groups[key]], "DUPLICATE_STATE_LANE")
                groups[key].append(row)
        counts[tag] += 1
    require(finished, "MISSING_JSON_END")
    for key, group in groups.items():
        ticks = [row for row in group if row["tick"]]
        if ticks:
            require(len(ticks) == 4 and {row["lane"] for row in ticks} == set(range(4)), "TICK_STATE_MISSING_LANE")
            require(len({row["pending_request_id"] for row in ticks}) == 1, "TICK_REQUEST_DISAGREEMENT")
            require((key[0], ticks[0]["pending_request_id"]) in seen, "TICK_WITHOUT_REQUEST")
    return {"rows": rows, "counts": dict(counts), "cancelled_requests": cancelled}


# token kinds: decimal maximum or exact-width hex. cycle is common, except END.
F_FORMAT = {
    "R": (2**31-1,), "U": (15, "h8"), "P": ("h64", 1), "E": ("h64",),
    "K": (2**32-1,), "J": (2**32-1,), "N": ("h4",),
    "Q": (2**32-1, "h4", "h16", "h16", "h128", "h128", "h32"),
    "S": (2**32-1, "h48", "h48", "h20"), "C": (2**32-1,),
    "F": (2**32-1, "h4", "h16", "h16", "h128", "h128"),
    "D": (2**32-1, "h128"), "H": (2**32-1, "h4", "h64", "h64", "h8"),
    "M": (2**32-1, "h24", "h24", 1),
}
SCENARIOS = frozenset(("four_voices", "center512", "held_controls", "steal_old_off", "velocity_zero",
                      "release_retrigger", "pedal_tail_controls", "release_controls", "pedal_steal",
                      "program_transport", "sample_edge", "fifo_pressure", "accepted_only",
                      "reset_partial", "reset_compute", "reset_pending", "recovered"))


def decimal(token, maximum, name):
    require(re.fullmatch(r"[0-9]+", token) is not None, "DECIMAL_TOKEN:" + name)
    return integer(int(token), 0, maximum, name)


def signed24(value):
    return value - (1 << 24) if value & (1 << 23) else value


def parse_f(text):
    require(bool(text.strip()), "EMPTY_F")
    rows, counts, end = [], Counter(), None
    epoch, last_cycle = 0, 0
    seen_scenarios = set()
    for line_number, line in enumerate(text.splitlines(), 1):
        tokens = line.split()
        require(bool(tokens), "BLANK_F_LINE")
        require(end is None, "F_RECORD_AFTER_END")
        tag = tokens[0]
        if tag == "END":
            require(len(tokens) == 10, "F_END_ARITY")
            end = [decimal(value, 2**31-1, "END") for value in tokens[1:]]
            rows.append({"tag": tag, "values": end, "line": line_number})
            continue
        require(tag in F_FORMAT or tag == "T", "UNKNOWN_F_TAG:" + tag)
        require(len(tokens) == (3 if tag == "T" else 2 + len(F_FORMAT[tag])), "F_ARITY:" + tag)
        cycle = decimal(tokens[1], 2**31-1, "cycle")
        require(cycle >= last_cycle and cycle >= 1, "F_CYCLE_ORDER")
        last_cycle = cycle
        if tag == "T":
            require(tokens[2] in SCENARIOS and tokens[2] not in seen_scenarios, "F_SCENARIO")
            seen_scenarios.add(tokens[2])
            values = [tokens[2]]
        else:
            values = []
            for token, kind in zip(tokens[2:], F_FORMAT[tag]):
                values.append(hexword(token, int(kind[1:]), tag) if isinstance(kind, str)
                              else decimal(token, kind, tag))
        if tag == "R":
            require(values[0] == epoch + 1, "F_RESET_EPOCH")
            epoch = values[0]
        require(epoch > 0, "F_BEFORE_RESET")
        rows.append({"tag": tag, "cycle": cycle, "epoch": epoch, "values": values, "line": line_number})
        counts[tag] += 1
    require(end is not None, "MISSING_F_END")
    commits = [row for row in rows if row["tag"] == "M"]
    require(bool(commits), "EMPTY_F_COMMIT_SET")
    require(end[0] == len(commits), "F_END_TOTAL")
    require(end[1] == sum(row["values"][1] != 0 for row in commits), "F_END_NONZERO_LEFT")
    pushes = [row for row in rows if row["tag"] == "P"]
    require(end[6] == sum(row["values"][1] == 0 for row in pushes), "F_END_NORMAL_PUSHES")
    require(end[7] == sum(row["values"][1] == 1 for row in pushes), "F_END_SYNTHETIC_PUSHES")
    return {"rows": rows, "counts": dict(counts), "end": end,
            "unobservable_end_counters": ["full_pop_push", "control_stalls", "edge_events", "center_samples", "checks"]}


def compare_pair(json_capture, f_capture):
    jrows, frows = json_capture["rows"], f_capture["rows"]
    jreset = [(r["epoch"], r["cycle"]) for r in jrows if r["tag"] == "RESET"]
    freset = [(r["values"][0], r["cycle"]) for r in frows if r["tag"] == "R"]
    require(jreset == freset, "RESET_PAIR_ORDER_OR_CYCLE")
    jrequest = [(r["epoch"], r["cycle"], r["request_id"]) for r in jrows if r["tag"] == "REQUEST"]
    frequest = [(r["epoch"], r["cycle"], r["values"][0]) for r in frows if r["tag"] == "J"]
    require(jrequest == frequest, "REQUEST_PAIR_ORDER_OR_CYCLE")
    jcommit = [(r["epoch"], r["cycle"], r["request_id"], r["pcm_left"], r["pcm_right"])
               for r in jrows if r["tag"] == "COMMIT"]
    fcommit = [(r["epoch"], r["cycle"], r["values"][0], signed24(r["values"][1]), signed24(r["values"][2]))
               for r in frows if r["tag"] == "M"]
    require(jcommit == fcommit, "COMMIT_PAIR_ORDER_OR_PCM")
    ticks = defaultdict(list)
    for row in jrows:
        if row["tag"] == "STATE" and row["tick"]:
            ticks[(row["epoch"], row["cycle"], row["pending_request_id"])].append(row)
    drows = [r for r in frows if r["tag"] == "D"]
    require(set(ticks) == {(r["epoch"], r["cycle"], r["values"][0]) for r in drows}, "D_TICK_GROUPS")
    require(len(drows) == len(ticks), "D_DUPLICATE")
    for row in drows:
        group = ticks[(row["epoch"], row["cycle"], row["values"][0])]
        for state in group:
            require(int(state["dds_fcw"], 16) == ((row["values"][1] >> (32 * state["lane"])) & 0xffffffff),
                    "D_STATE_FCW_TRANSPORT")
    return {"status": "PARTIAL_TRANSPORT_ONLY", "commits_compared": len(jcommit),
            "resets_compared": len(jreset), "requests_compared": len(jrequest),
            "tick_groups_compared": len(ticks), "arithmetic_golden_passed": False}


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Transport checks only; not full audio golden")
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("f_capture", type=Path)
    args = parser.parse_args()
    try:
        result = compare_pair(parse_jsonl(args.jsonl.read_text(encoding="utf-8")),
                              parse_f(args.f_capture.read_text(encoding="utf-8")))
        print(json.dumps(result, sort_keys=True))
    except (CaptureError, OSError, UnicodeError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}))
        raise SystemExit(1) from error
