"""Independent accepted-event -> router/control/DSP -> PCM replay for B2b N4.

Only R/I/J/X are stimulus. Q, C, A and G deadlines follow the documented
candidate clock contract; observed routing/math values never feed expectations.
This is not an equivalence claim for the differently timed frozen L top path.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

from inventory import FROZEN, ROOT
from b2_clock import backend_calendar, deadline_missed

sys.path.insert(0, str(ROOT / "code/software/audio_math_acceptance_candidate"))
from dds_model import MASK32, PianoDDS, pitch_mod, signed  # noqa: E402
from envelope_model import Envelope, voice_pcm  # noqa: E402
from b2c_router_model import Router, fields, packed  # noqa: E402


def require(test, reason):
    if not test:
        raise ValueError(reason)


def hx(value, width):
    require(bool(re.fullmatch(r"[0-9a-f]+", value)), "HEX_SCHEMA")
    result = int(value, 16)
    require(result < 1 << width, "HEX_WIDTH")
    return result


def dec(value, low=0, high=0xffffffff):
    require(bool(re.fullmatch(r"-?(0|[1-9][0-9]*)", value)), "DEC_SCHEMA")
    result = int(value)
    require(low <= result <= high, "DEC_RANGE")
    return result


class Oracle:
    def __init__(self, response, n=8, identity_controls=False):
        self.n, self.sw = n, (n-1).bit_length()
        self.identity_controls = identity_controls
        self.tw = 72+self.sw
        names = ("velocity_gain_rom.mem", "piano_band_4x256_8191.mem", "oct_ratio_q16.mem",
                 "sub_ratio_q16.mem", "lfo_sine_q15.mem")
        self.rom = {n: [int(x, 16) for x in (FROZEN / "rom" / n).read_text(encoding="utf-8").split()] for n in names}
        self.env = [Envelope(self.rom[names[0]]) for _ in range(self.n)]
        self.dds = [PianoDDS() for _ in range(self.n)]
        self.counts, self.coverage, self.lifecycle = Counter(), Counter(), Counter()
        self.response = response
        self.frame = None
        self.cycle = -1
        self.route = None
        self.durations = []

    def reset(self, cycle):
        if hasattr(self, "router"):
            self.lifecycle.update(self.router.counts)
        self.router = Router(self.n)
        self.controls = {}
        self.lfo = [0]*self.n
        self.frame = None
        self.committed = None
        self.route = None
        for env, osc in zip(self.env, self.dds):
            env.reset(cycle)
            osc.reset()
        self.cycle = cycle

    def route_values(self):
        r = self.router
        snap = r.snapshot()
        return [r.on, r.off, snap[0], packed([int(s["releasing"]) for s in r.slots], 1),
                packed([s["velocity"] for s in r.slots], 10), snap[4], snap[5], snap[1], snap[2], snap[3]]

    def edge(self, cycle, rows):
        by = {}
        for row in rows:
            require(row[0] not in by, "DUPLICATE_TAG_AT_EDGE")
            by[row[0]] = row
            self.counts[row[0]] += 1
        r = self.router
        on, off = r.on, r.off
        route = self.route_values()
        if route != self.route:
            require("U" in by, "MISSING_ROUTER_TRANSITION")
        if "U" in by:
            require([hx(x, w) for x, w in zip(by["U"][2:], (self.n, self.n, self.n, self.n, 10*self.n, 32*self.n, 8*self.n, 4*self.n, 4*self.n, 32*self.n))] == route,
                    "ROUTER_LIFECYCLE_OR_IDENTITY")
        self.route = route
        old_frame = self.frame
        if "J" in by:
            require(self.frame is None, "OVERLAPPING_FRAME")
            self.frame = {"id": hx(by["J"][2], 32), "j": cycle, "q": None, "lanes": {}, "writes": {},
                          "advance": False, "started": False, "first": None}
        f = self.frame
        identity = r.snapshot()
        identity = [identity[i] for i in (0, 1, 2, 3)]
        identity_abort = bool(f and f["q"] is not None and cycle >= f["q"]+self.n+2 and
                              "identity" in f and identity != f["identity"])
        stop = "X" in by or identity_abort
        if f and stop:
            require("Z" in by and dec(by["Z"][2], 1, 2) == (1 if "X" in by else 2), "ABORT_CAUSE")
            self.coverage["cancel_after_advance" if f["advance"] else "cancel_before_advance"] += 1
            self.coverage["identity_abort"] += identity_abort
            self.frame = f = None
        elif "Z" in by:
            require(False, "SPURIOUS_ABORT")
        if f and f["q"] is None and old_frame is f and not r.busy() and not (on | off):
            f["q"] = cycle+8
        if f and f["q"] == cycle:
            f["slots"] = [dict(s) for s in r.slots]
            f["identity"] = identity
            f["control"] = [self.controls.get((s["source"], s["channel"]), (0, 0, 2))
                            if s["occupied"] or self.identity_controls else (0, 0, 2) for s in r.slots]
            f["pedals"] = set(r.pedals)
        expected_g = f and f["q"] is not None and cycle in [f["q"]+3*self.n+5+3*i for i in range(self.n)]
        require(bool(expected_g) == ("G" in by), "B1_ISSUE_EDGE_OR_MISSING")
        if expected_g:
            i = (cycle-f["q"]-3*self.n-5)//3
            s, ctl = f["slots"][i], f["control"][i]
            tag = (f["id"] << (40+self.sw)) | (s["source"] << (36+self.sw)) | (s["channel"] << (32+self.sw)) | (s["generation"] << self.sw) | i
            context = (s["note"] << 42) | (s["velocity"] << 32) | s["fcw"]
            flags = int(s["occupied"]) | int(s["releasing"]) << 1
            word = ctl[0] | ctl[1] << 12 | ctl[2] << 24
            expected = [tag, context, flags, word, int((s["source"], s["channel"]) in f["pedals"])]
            actual = [hx(x, w) for x, w in zip(by["G"][2:6], (self.tw, 74, 2, 29))] + [dec(by["G"][6], 0, 1)]
            require(actual == expected, "B1_FULL_TAG_CONTEXT_CONTROL_PEDAL")
        expected_c = bool(f and f["q"] is not None and cycle == f["q"]+6*self.n+3)
        require(expected_c == ("C" in by), "BACKEND_LAUNCH_EDGE_OR_MISSING")
        if expected_c:
            slots, controls = f["slots"], f["control"]
            expected = [f["id"], packed([int(s["occupied"]) for s in slots], 1),
                        packed([s["fcw"] for s in slots], 32)]
            expected += [packed([c[i] for c in controls], w) for i, w in ((0, 12), (1, 12), (2, 5))]
            expected += [packed([s[k] for s in slots], w) for k, w in (("source", 4), ("channel", 4), ("generation", 32))]
            require([hx(x, w) for x, w in zip(by["C"][2:], (32, self.n, 32*self.n, 12*self.n, 12*self.n, 5*self.n, 4*self.n, 4*self.n, 32*self.n))] == expected,
                    "BACKEND_FULL_SNAPSHOT")
            self.coverage["full_occupancy_frame"] += all(s["occupied"] for s in slots)
            f["c"] = cycle
            f['clock'] = backend_calendar(cycle, self.n, self.response)
            f["started"] = True
            f["fcw"] = []
            for i, (s, ctl) in enumerate(zip(slots, controls)):
                f["fcw"].append(pitch_mod(s["fcw"], signed(ctl[0], 12), ctl[1], ctl[2], self.lfo[i],
                    self.rom["oct_ratio_q16.mem"], self.rom["sub_ratio_q16.mem"], self.rom["lfo_sine_q15.mem"])
                    if s["occupied"] else s["fcw"])
                if s["occupied"]:
                    self.lfo[i] = (self.lfo[i]+447392) & MASK32
        tick = bool(f and f["started"] and cycle == f['clock'].advance)
        require(tick == ("A" in by), "ADVANCE_EDGE_OR_MISSING")
        if tick:
            require(hx(by["A"][2], 32) == f["id"], "ADVANCE_ID")
            f["advance"] = True
        done = sum(int(s["occupied"] and s["releasing"] and env.snapshot()["public_state"] == 0 and not on & (1 << i)) << i
                   for i, (s, env) in enumerate(zip(r.slots, self.env)))
        for i, (env, osc, s) in enumerate(zip(self.env, self.dds, r.slots)):
            env.edge(tick=tick, on=bool(on & (1 << i)), off=bool(off & (1 << i)), velocity=s["velocity"])
            osc.edge(f["fcw"][i] if tick else s["fcw"], s["velocity"], tick=tick, note_on=bool(on & (1 << i)))
            if on & (1 << i):
                self.lfo[i] = 0
        event = hx(by["I"][2], 64) if "I" in by else None
        r.edge(event=event, release_done=done, owner=old_frame is None and "J" not in by)
        if event is not None:
            e = fields(event)
            key = e["source"], e["channel"]
            bend, mod, ran = self.controls.get(key, (0, 0, 2))
            if e["type"] == 3 and e["control"] == 0:
                bend = e["value"]
                self.coverage["pitch_update"] += 1
            if e["type"] == 4 and e["control"] == 1:
                mod = e["value"]
                self.coverage["mod_update"] += 1
            if e["type"] == 4 and e["control"] == 4:
                if e["value"] <= 24:
                    ran = e["value"]
                else:
                    self.coverage["invalid_range_ignored"] += 1
            self.controls[key] = bend, mod, ran
            self.coverage["identity_" + str(key[0]*16+key[1])] += 1
        expected_lane = bool(f and f['started'] and cycle in f['clock'].lanes)
        require(expected_lane == ('L' in by), 'LANE_CLOCK_OR_MISSING')
        if "L" in by:
            require(bool(f and f["advance"]), "LANE_WITHOUT_LIVE_ADVANCE")
            row = by["L"]
            i = dec(row[3], 0, self.n-1)
            require(i == len(f["lanes"]) and hx(row[2], 32) == f["id"], "LANE_SEQUENCE_OR_ID")
            require(cycle == f['clock'].lanes[i], "LANE_CLOCK")
            osc, env = self.dds[i], self.env[i]
            wave = signed(self.rom["piano_band_4x256_8191.mem"][(osc.active_table << 8) | (osc.phase >> 24)], 16)
            amplitude = env.snapshot()["envelope"]
            pcm = voice_pcm(wave, amplitude) if f["slots"][i]["occupied"] else 0
            expected = [osc.phase, osc.active_table, f["fcw"][i], wave, amplitude, pcm, env.snapshot()["public_state"]]
            actual = [hx(row[4], 32), dec(row[5], 0, 3), hx(row[6], 32), dec(row[7], -32768, 32767),
                      dec(row[8], 0, 32767), dec(row[9], -(1 << 23), (1 << 23)-1), dec(row[10], 0, 4)]
            for name, a, b in zip(("PHASE", "TABLE", "FCW", "WAVE", "ENVELOPE", "GAIN_PCM", "STATE"), actual, expected):
                require(a == b, f"MATH_{name}:{cycle}:slot{i}:{a}!={b}")
            f["lanes"][i] = pcm
            self.coverage["ADSR_state_" + str(expected[-1])] += 1
            self.coverage["nonzero_lane_pcm"] += pcm != 0
            self.coverage["nonzero_slot_" + str(i)] += pcm != 0
        if "W" in by:
            row = by["W"]
            tag, context, accepted, injected = hx(row[2], self.tw), hx(row[3], 74), dec(row[4], 0, 1), dec(row[5], 0, 1)
            if injected:
                require(accepted == 0, "STALE_TAG_ACCEPTED")
                self.coverage["stale_generation_rejected"] += 1
            else:
                require(bool(f and f["started"]), "WRITE_WITHOUT_FRAME")
                i = tag & (self.n-1)
                s = f["slots"][i]
                exp_tag = f["id"] << (40+self.sw) | s["source"] << (36+self.sw) | s["channel"] << (32+self.sw) | s["generation"] << self.sw | i
                require(i in f["lanes"] and i not in f["writes"], "WRITE_MISSING_OR_DUPLICATE")
                exp_context = (f["lanes"][i] & ((1 << 24)-1)) << 50 | s["note"] << 42 | s["velocity"] << 32 | s["fcw"]
                require([tag, context, accepted] == [exp_tag, exp_context, 1], "B1_REAL_RESULT_TAG_OR_CONTEXT")
                f["writes"][i] = context
        # Stop/identity invalidation was applied above and wins on this edge.
        # Compare presence on EVERY edge, including skipped capture gaps.
        expected_first = bool(f and f['started'] and cycle == f['clock'].wrapper_first)
        require(expected_first == ('F' in by), 'FIRST_VALID_CLOCK_OR_MISSING')
        for tag in ("F", "P"):
            if tag not in by:
                continue
            require(bool(f and len(f["writes"]) == self.n), "INCOMPLETE_ATOMIC_PUBLISH")
            pcm = max(-(1 << 23), min((1 << 23)-1, sum(f["lanes"].values())))
            row = by[tag]
            result = [hx(row[2], 32), dec(row[3], -(1 << 23), (1 << 23)-1),
                      dec(row[4], -(1 << 23), (1 << 23)-1), dec(row[5], 0, 1)]
            if tag == "F":
                require(f["first"] is None, "DUPLICATE_FIRST_RESULT")
                elapsed = f['clock'].wrapper_first-f["j"]-1
                require(result == [f["id"], pcm, pcm,
                                   deadline_missed(f['clock'].wrapper_first, f['j'])], "PCM_OR_DEADLINE")
                f["first"] = result
                self.durations.append(elapsed)
            else:
                require(f["first"] == result, "OUTPUT_BACKPRESSURE_STABILITY")
                self.committed = dict(f["writes"])
                self.frame = None
        if "Y" in by:
            require(self.committed is not None and hx(by["Y"][3], 74) == self.committed[dec(by["Y"][2], 0, self.n-1)], "BANK_COMMIT_READBACK")
        self.cycle = cycle

    def advance(self, cycle, rows):
        while self.cycle+1 < cycle:
            # Skip only actual fixed points, with no frame/calendar work,
            # controller transition, Note pulse, or deferred retirement.
            r = self.router
            stable = self.frame is None and not r.busy() and not (r.on | r.off)
            before = [e.registers() for e in self.env]
            done = any(s["occupied"] and s["releasing"] and e.state == 0 for s, e in zip(r.slots, self.env))
            self.edge(self.cycle+1, [])
            if stable and not done and before == [e.registers() for e in self.env]:
                gap = cycle-self.cycle-1
                self.cycle += gap
                for env in self.env:
                    env.cycle += gap
        self.edge(cycle, rows)


def check(raw, *, sizes=(4, 8), responses=(1, 3, 64), identity_controls=False, extra_long_events=0):
    lines = raw.decode("ascii").splitlines()
    if len(lines) > 1 and lines[-2].startswith("END ") and re.fullmatch(r".*[/\\]tb_b2[cd]_event_audio\.sv:[0-9]+: \$finish called at [0-9]+ \(1ps\)", lines[-1]):
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result, code = check(args.input.read_bytes()), 0
    except (ValueError, OSError, UnicodeError) as error:
        result, code = {"status": "REJECT", "reason": str(error)}, 1
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
