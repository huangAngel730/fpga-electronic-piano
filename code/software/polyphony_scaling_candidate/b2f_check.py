"""N8 identity-control successor; original N8 checker contract stays unchanged."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from b2c_check import Oracle, dec, require

def reference_check(raw, *, sizes=(4, 8), responses=(1, 3, 64), identity_controls=False,
          extra_long_events=0, finish_names=("tb_b2c_event_audio", "tb_b2d_event_audio")):
    lines = raw.decode("ascii").splitlines()
    finish = "|".join(re.escape(name) for name in finish_names)
    if len(lines) > 1 and lines[-2].startswith("END ") and re.fullmatch(rf".*[/\\](?:{finish})\.sv:[0-9]+: \$finish called at [0-9]+ \(1ps\)", lines[-1]):
        lines.pop()
    # Default N8 entry retains its old accepted schema. Later checkpoints opt
    # into explicit sizes/responses; observed outputs never choose the calendar.
    ns = "|".join(str(n) for n in sizes)
    rs = "|".join(str(r) for r in responses)
    require(bool(lines and re.fullmatch(rf"B2C ({ns}) ({rs}) [01]", lines[0])), "HEADER")
    _, n, response, long_case = lines[0].split()
    n = int(n)
    oracle = Oracle(int(response), n, identity_controls=identity_controls)
    lengths = {"R": 2, "I": 3, "J": 3, "U": 12, "G": 7, "W": 6, "C": 11,
               "A": 3, "L": 11, "F": 6, "P": 6, "X": 2, "Z": 3, "Y": 4, "END": 14}
    groups = {}
    last = -1
    ended = False
    for line in lines[1:]:
        row = line.split()
        require(not ended and bool(row) and row[0] in lengths and len(row) == lengths[row[0]], "ROW_SCHEMA_OR_TRAILING")
        cycle = dec(row[1])
        require(cycle >= last, "CYCLE_ORDER")
        last = cycle
        groups.setdefault(cycle, []).append(row)
        ended = row[0] == "END"
    require(ended, "MISSING_END")
    for cycle, rows in groups.items():
        if rows[0][0] == "R":
            require(len(rows) == 1, "RESET_ROW_CONFLICT")
            oracle.counts["R"] += 1
            oracle.reset(cycle)
        elif rows[0][0] == "END":
            require(len(rows) == 1 and oracle.frame is None, "END_LIVE_FRAME")
            keys = ("I", "J", "C", "A", "L", "P", "X", "Z", "W", "G", "Y", "F")
            require([dec(x) for x in rows[0][2:]] == [oracle.counts[k] for k in keys], "END_COUNTS")
        else:
            require(hasattr(oracle, "router"), "MISSING_RESET")
            oracle.advance(cycle, rows)
    oracle.lifecycle.update(oracle.router.counts)
    require(oracle.counts["I"] == 1553+n-4+(extra_long_events if int(long_case) else 0) and oracle.counts["R"] == 4 and oracle.counts["X"] == 7 and
            oracle.counts["P"] + oracle.coverage["identity_abort"] == (10368 if int(long_case) else 100), "FIXTURE_COUNTS")
    for key in ("steal", "retrigger", "pedal_deferred", "unmatched_note_off", "off_pulses"):
        require(oracle.lifecycle[key] > 0, "MISSING_LIFECYCLE:" + key)
    require(all(oracle.coverage["identity_" + str(i)] for i in range(256)), "ALL_256_IDENTITIES")
    for key in ("stale_generation_rejected", "cancel_after_advance", "cancel_before_advance", "nonzero_lane_pcm"):
        require(oracle.coverage[key] > 0, "MISSING_COVERAGE:" + key)
    if int(long_case):
        require(oracle.lifecycle["retirements"] >= n, "RELEASE_RETIREMENT_REQUIRED")
        require(all(oracle.coverage["ADSR_state_" + str(i)] for i in range(5)), "FULL_ADSR_STATES_REQUIRED")
    require(oracle.coverage["full_occupancy_frame"] > 0, "FULL_N_OCCUPANCY")
    require(all(oracle.coverage["nonzero_slot_" + str(i)] for i in range(n)), "ALL_N_SOUND_CONTRIBUTIONS")
    return {"status": "B2C_EVENT_AUDIO_PASS_T061_PARTIAL", "N": n, "response": int(response),
            "long_case": bool(int(long_case)), "counts": dict(oracle.counts), "lifecycle": dict(oracle.lifecycle),
            "coverage": dict(oracle.coverage), "max_request_to_result_cycles": max(oracle.durations),
            "min_request_to_result_cycles": min(oracle.durations), "capture_sha256": hashlib.sha256(raw).hexdigest(),
            "deadline_misses": sum(age >= 833 for age in oracle.durations),
            "reference_inputs": ["R", "I", "J", "X", "frozen ROMs"], "task_complete": False,
            "whole_frozen_L_clock_path_equivalence": False, "physical_STA": "NOT_RUN"}

STATUS = "B2F_N8_IDENTITY_SUCCESSOR_PASS_T061_PARTIAL"


def check(raw):
    result = reference_check(raw, sizes=(8,), responses=(1, 3, 64),
                             identity_controls=True,
                             finish_names=("tb_b2f_event_audio",))
    result.update(status=STATUS, sample_deadline_qualified=result["deadline_misses"] == 0,
                  control_contract="SOURCE_CHANNEL_SHARED_INCLUDING_IDLE_SLOTS")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result, code = check(args.input.read_bytes()), 0
    except (ValueError, OSError, UnicodeError) as error:
        result, code = dict(status="REJECT", reason=str(error)), 1
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
