"""Independent integer replay of B2a public lane/audio capture, not MIDI E->N.

Reuse the independently written T060 arithmetic as a READ-ONLY reference.
No observed wave/envelope/FCW/PCM is used to generate another expected value.
Every accepted C snapshot, E pulse, A edge, cancelled token and reset is replayed.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

from inventory import FROZEN, ROOT

sys.path.insert(0, str(ROOT / "code/software/audio_math_acceptance_candidate"))
from dds_model import MASK32, PianoDDS, pitch_mod, signed  # noqa: E402
from envelope_model import Envelope, voice_pcm  # noqa: E402


def mix_signed24(voices):
    if len(voices) not in (4, 8, 16, 32) or any(type(x) is not int or not -(1 << 23) <= x < (1 << 23) for x in voices):
        raise ValueError("MIX_INPUT_RANGE")
    total = sum(voices)
    pcm = max(-(1 << 23), min((1 << 23)-1, total))
    return pcm, pcm != total


def check(raw):
    lines = raw.decode("ascii").splitlines()
    # Icarus14 appends exactly this tool diagnostic after $finish. It is NOT
    # capture data. Accept only one final known diagnostic after a real END;
    # arbitrary extra rows/noise/missing END remain hard errors.
    if (len(lines) >= 2 and lines[-2].startswith("END ") and
            re.fullmatch(r".*[/\\]tb_b2_audio\.sv:[0-9]+: \$finish called at [0-9]+ \(1ps\)", lines[-1])):
        lines = lines[:-1]
    if not lines or not re.fullmatch(r"B2 (4|8|16|32) ([1-9][0-9]?) [01]", lines[0]):
        raise ValueError("HEADER")
    _, n, response, long_case = map_header(lines[0])
    if response > 64:
        raise ValueError("RESPONSE_RANGE")
    roms = {name: [int(word, 16) for word in (FROZEN / "rom" / name).read_text(encoding="utf-8").split()]
            for name in ("velocity_gain_rom.mem", "piano_band_4x256_8191.mem",
                         "oct_ratio_q16.mem", "sub_ratio_q16.mem", "lfo_sine_q15.mem")}
    envelopes = [Envelope(roms["velocity_gain_rom.mem"]) for _ in range(n)]
    dds = [PianoDDS() for _ in range(n)]
    lfo = [0] * n
    counts, states, coverage = Counter(), Counter(), Counter()
    frame = None
    reset_seen = ended = False
    last_cycle = -1
    elapsed = []
    previous_commit_request = None
    cadence_interrupted = True

    def field_hex(text, width):
        if not re.fullmatch(r"[0-9a-fA-F]+", text):
            raise ValueError("HEX_SCHEMA")
        value = int(text, 16)
        if value >= 1 << width:
            raise ValueError("HEX_RANGE")
        return value

    def decimal(text, minimum=0, maximum=None):
        if not re.fullmatch(r"-?(0|[1-9][0-9]*)", text):
            raise ValueError("DECIMAL_SCHEMA")
        value = int(text)
        if value < minimum or maximum is not None and value > maximum:
            raise ValueError("DECIMAL_RANGE")
        return value

    def split(value, width):
        return [(value >> (i * width)) & ((1 << width) - 1) for i in range(n)]

    def quiet(cycle, include):
        target = cycle + int(include)
        for env in envelopes:
            if target > env.cycle:
                env.quiet_until(target)

    for line in lines[1:]:
        parts = line.split()
        if ended or not parts:
            raise ValueError("TRAILING_OR_EMPTY_ROW")
        tag = parts[0]
        lengths = {"R": 2, "E": 6, "C": 11, "A": 3, "L": 11,
                   "O": 11, "X": 2, "END": 8}
        if tag not in lengths or len(parts) != lengths[tag]:
            raise ValueError("ROW_SCHEMA:" + tag)
        cycle = decimal(parts[1])
        if cycle < last_cycle:
            raise ValueError("CYCLE_ORDER")
        last_cycle = cycle
        if tag == "R":
            for env, osc in zip(envelopes, dds):
                env.reset(cycle)
                osc.reset()
            lfo = [0] * n
            frame = None
            reset_seen = True
            cadence_interrupted = True
            counts["R"] += 1
            continue
        if not reset_seen:
            raise ValueError("MISSING_INITIAL_RESET")
        if tag == "END":
            expected = [counts[t] for t in ("C", "E", "A", "L", "O", "X")]
            if list(map(decimal, parts[2:])) != expected or frame is not None:
                raise ValueError("END_COUNTS_OR_INCOMPLETE_FRAME")
            ended = True
            continue
        counts[tag] += 1
        if tag == "E":
            cadence_interrupted = True
            if frame is not None:
                raise ValueError("EVENT_WHILE_OWNED")
            ons, offs = field_hex(parts[2], n), field_hex(parts[3], n)
            velocity = split(field_hex(parts[4], n * 10), 10)
            bases = split(field_hex(parts[5], n * 32), 32)
            quiet(cycle, False)
            for i, (env, osc) in enumerate(zip(envelopes, dds)):
                on, off = bool(ons & (1 << i)), bool(offs & (1 << i))
                env.edge(on=on, off=off, velocity=velocity[i])
                osc.edge(bases[i], velocity[i], note_on=on)
                if on:
                    lfo[i] = 0
                    coverage["attack_load_" + str(osc.attack_left)] += 1
        elif tag == "C":
            if frame is not None:
                raise ValueError("OVERLAPPING_REQUEST")
            quiet(cycle, True)
            if response < 32 and previous_commit_request is not None and not cadence_interrupted:
                if cycle - previous_commit_request != 833:
                    raise ValueError("ORDINARY_SAMPLE_CADENCE_NOT_833")
                coverage["exact_833_intervals"] += 1
            cadence_interrupted = False
            ident = field_hex(parts[2], 32)
            occupied = field_hex(parts[3], n)
            bases, bends, mods, ranges = [split(field_hex(parts[j], n * width), width)
                                         for j, width in ((4, 32), (5, 12), (6, 12), (7, 5))]
            fcws = []
            for i in range(n):
                active = bool(occupied & (1 << i))
                value = pitch_mod(bases[i], signed(bends[i], 12), mods[i], ranges[i], lfo[i],
                                  roms["oct_ratio_q16.mem"], roms["sub_ratio_q16.mem"],
                                  roms["lfo_sine_q15.mem"]) if active else bases[i]
                fcws.append(value)
                if active:
                    new_lfo = (lfo[i] + 447392) & MASK32
                    coverage["lfo_wraps"] += new_lfo < lfo[i]
                    lfo[i] = new_lfo
            frame = {"id": ident, "occupied": occupied, "fcw": fcws, "cycle": cycle,
                     "identity": [field_hex(parts[j], n * width) for j, width in ((8, 4), (9, 4), (10, 32))],
                     "lanes": {}, "advance": False}
        elif tag == "A":
            if frame is None or frame["advance"] or field_hex(parts[2], 32) != frame["id"]:
                raise ValueError("ADVANCE_ID_OR_DUPLICATE")
            quiet(cycle, False)
            for i, (env, osc) in enumerate(zip(envelopes, dds)):
                expiring = osc.attack_left == 1
                pending = osc.change_pending
                env.edge(tick=True)
                osc.edge(frame["fcw"][i], tick=True)
                coverage["brightness_expiries"] += expiring
                coverage["pending_table_wraps"] += pending and not osc.change_pending
            frame["advance"] = True
        elif tag == "L":
            if frame is None or not frame["advance"] or field_hex(parts[2], 32) != frame["id"]:
                raise ValueError("LANE_WITHOUT_LIVE_ADVANCE")
            slot = decimal(parts[3], 0, n - 1)
            if slot in frame["lanes"] or slot != len(frame["lanes"]):
                raise ValueError("LANE_DUPLICATE_OR_SEQUENCE")
            quiet(cycle, True)
            osc, env = dds[slot], envelopes[slot]
            expected_phase, expected_table, expected_fcw = osc.phase, osc.active_table, frame["fcw"][slot]
            expected_wave = signed(roms["piano_band_4x256_8191.mem"][(expected_table << 8) | (expected_phase >> 24)], 16)
            expected_envelope = env.snapshot()["envelope"]
            expected_pcm = voice_pcm(expected_wave, expected_envelope) if frame["occupied"] & (1 << slot) else 0
            expected_state = env.snapshot()["public_state"]
            actual = [field_hex(parts[4], 32), decimal(parts[5], 0, 3), field_hex(parts[6], 32),
                      decimal(parts[7], -32768, 32767), decimal(parts[8], 0, 32767),
                      decimal(parts[9], -(1 << 23), (1 << 23)-1), decimal(parts[10], 0, 4)]
            expected = [expected_phase, expected_table, expected_fcw, expected_wave,
                        expected_envelope, expected_pcm, expected_state]
            for name, observed, wanted in zip(("PHASE", "TABLE", "FCW", "WAVE", "ENVELOPE", "GAIN_PCM", "STATE"), actual, expected):
                if observed != wanted:
                    raise ValueError(f"MATH_{name}:{cycle}:slot{slot}:{observed}!={wanted}")
            frame["lanes"][slot] = expected_pcm
            states[expected_state] += 1
            coverage["negative_nonintegral_gain"] += expected_wave < 0 and expected_wave * expected_envelope % 32768 != 0
            coverage["nonzero_voice_samples"] += expected_pcm != 0
        elif tag == "O":
            if frame is None or not frame["advance"] or len(frame["lanes"]) != n:
                raise ValueError("ALL_N_REQUIRED_BEFORE_RESULT")
            quiet(cycle, True)
            if field_hex(parts[2], 32) != frame["id"]:
                raise ValueError("RESULT_ID")
            total = sum(frame["lanes"].values())
            pcm, clipped = mix_signed24(list(frame["lanes"].values()))
            actual = [decimal(parts[j], -(1 << 23), (1 << 23)-1) for j in (3, 4)]
            if actual != [pcm, pcm] or decimal(parts[5], 0, 1) != int(clipped):
                raise ValueError("MATH_STEREO_SATURATION")
            if field_hex(parts[7], n) != (1 << n)-1:
                raise ValueError("COMPLETED_MASK")
            if [field_hex(parts[j], n * width) for j, width in ((8, 4), (9, 4), (10, 32))] != frame["identity"]:
                raise ValueError("FULL_SNAPSHOT_IDENTITY")
            duration = cycle - frame["cycle"] - 1
            if decimal(parts[6], 0, 1) != int(duration >= 833):
                raise ValueError("DEADLINE_FLAG")
            elapsed.append(duration)
            coverage["positive_clips"] += total > pcm
            coverage["negative_clips"] += total < pcm
            previous_commit_request = frame["cycle"]
            frame = None
        elif tag == "X":
            cadence_interrupted = True
            quiet(cycle, True)
            if frame is not None:
                coverage["cancel_after_advance"] += frame["advance"]
                coverage["cancel_before_advance"] += not frame["advance"]
                coverage["cancel_with_partial_render"] += 0 < len(frame["lanes"]) < n
            frame = None
    if not ended or counts["O"] < 8 or not elapsed:
        raise ValueError("MISSING_END_OR_REQUIRED_RESULTS")
    target_results = 10230 if long_case else 18 if response >= 32 else 106
    if counts["O"] != target_results or counts["R"] != (2 if response >= 32 else 3):
        raise ValueError("MISSING_REQUIRED_FIXTURE_RESULTS_OR_RESETS")
    if long_case and (not all(states[x] for x in range(5)) or
                      not all(coverage["attack_load_" + str(x)] for x in (0, 480, 960, 1440)) or
                      not coverage["brightness_expiries"] or not coverage["pending_table_wraps"] or
                      not coverage["lfo_wraps"]):
        raise ValueError("LONG_REQUIRED_MATH_COVERAGE")
    if response < 32 and (counts["X"] != 4 or not coverage["cancel_before_advance"] or
                          not coverage["cancel_after_advance"]):
        raise ValueError("REQUIRED_CANCEL_COVERAGE")
    if response >= 32 and not any(x >= 833 for x in elapsed):
        raise ValueError("SLOW_PROFILE_MUST_EXCEED_DEADLINE")
    return {"status": "B2A_REAL_MATH_BACKEND_PASS_T061_PARTIAL", "N": n,
            "wave_response_cycles": response, "long_case": bool(long_case),
            "counts": dict(counts), "public_ADSR_state_samples": dict(states),
            "coverage": dict(coverage), "max_compute_cycles": max(elapsed),
            "min_compute_cycles": min(elapsed), "over_833_results": sum(x >= 833 for x in elapsed),
            "reference": "read-only T060 integer models plus frozen five ROMs, no observed math expected values",
            "capture_sha256": hashlib.sha256(raw).hexdigest(), "task_complete": False,
            "MIDI_CC64_router_B1_context_integration": "NOT_IMPLEMENTED",
            "physical_STA": "NOT_RUN"}


def map_header(line):
    tag, *numbers = line.split()
    return tag, *(int(x) for x in numbers)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = check(args.input.read_bytes())
        code = 0
    except (ValueError, OSError, UnicodeError) as error:
        result = {"status": "REJECT", "reason": str(error)}
        code = 1
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
