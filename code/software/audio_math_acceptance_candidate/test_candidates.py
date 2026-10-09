"""Component self-tests: all generated captures are SYNTHETIC, never capture2.

These tests do not establish A1 real replay, A2 PCM arithmetic or RTL equivalence.
Semantic mutations retain complete END records and require specific diagnostics.
"""
from collections import Counter
import copy
import json
from pathlib import Path
import re
import sys
import unittest

from dds_model import MASK32, PianoDDS, note_fcw, pitch_mod, replay_states
from strict_capture import (
    CaptureError, F_FORMAT, META, PUBLIC_STATES, STATE_HEX, STATE_RANGES,
    compare_pair, parse_f, parse_jsonl,
)
from timeline import replay

ROOT = Path(__file__).resolve().parents[3]
FROZEN = ROOT / "code/rtl/138K_try/clock_trials_20261005/H_pll_core40_route2"
DIAGNOSTICS = Counter()


def end_json(rows):
    """Recompute structural counts, including for intentionally wrong semantics."""
    rows = [row for row in rows if row["tag"] != "END"]
    counts = {tag: sum(row["tag"] == tag for row in rows)
              for tag in ("RESET", "REQUEST", "STATE", "COMMIT")}
    return rows + [{"tag": "END", "counts": counts}]


def json_text(rows):
    return "\n".join(json.dumps(row, separators=(",", ":")) for row in end_json(rows)) + "\n"


def fixture(fcw=0):
    """Two synthetic transactions, four lanes; independent constant-FCW input."""
    rows = [dict(META), {"tag": "RESET", "epoch": 1, "cycle": 1}]
    for request_id, cycle in ((1, 2), (2, 5)):
        rows.append({"tag": "REQUEST", "epoch": 1, "cycle": cycle, "request_id": request_id})
        for lane in range(4):
            state = {key: 0 for key in STATE_RANGES}
            state.update({key: "0" * ((bits + 3) // 4) for key, bits in STATE_HEX.items()})
            state.update(tag="STATE", epoch=1, cycle=cycle + 1, lane=lane,
                         pending_request_id=request_id, tick=1, table=3,
                         dds_fcw=f"{fcw:08x}", phase_acc=f"{(request_id - 1) * fcw:08x}")
            rows.append(state)
        rows.append({"tag": "COMMIT", "epoch": 1, "cycle": cycle + 2,
                     "request_id": request_id, "pcm_left": 0, "pcm_right": 0})
    return end_json(rows)


def f_text(rows, all_tags=False):
    """Unit-only paired F stream. F END's five opaque counters are not inferred."""
    lines = []
    if all_tags:
        # Cover every additional legal tag and exact printed width at cycle1.
        lines.append("R 1 1")
        for tag, schema in F_FORMAT.items():
            if tag in ("R", "J", "D", "M"):
                continue
            values = ["0" * ((int(kind[1:]) + 3) // 4) if isinstance(kind, str) else "1"
                      for kind in schema]
            lines.append(f"{tag} 1 " + " ".join(values))
        lines.append("T 1 four_voices")
    for row in rows:
        tag = row["tag"]
        if tag == "RESET" and not all_tags:
            lines.append(f"R {row['cycle']} {row['epoch']}")
        elif tag == "REQUEST":
            lines.append(f"J {row['cycle']} {row['request_id']}")
        elif tag == "STATE" and row["tick"] and row["lane"] == 0:
            group = [r for r in rows if r["tag"] == "STATE" and r["tick"]
                     and (r["epoch"], r["cycle"]) == (row["epoch"], row["cycle"])]
            packed = sum(int(r["dds_fcw"], 16) << (32 * r["lane"]) for r in group)
            lines.append(f"D {row['cycle']} {row['pending_request_id']} {packed:032x}")
        elif tag == "COMMIT":
            lines.append(f"M {row['cycle']} {row['request_id']} "
                         f"{row['pcm_left'] & 0xffffff:06x} {row['pcm_right'] & 0xffffff:06x} 0")
    commits = [row for row in rows if row["tag"] == "COMMIT"]
    lines.append(f"END {len(commits)} {sum(row['pcm_left'] != 0 for row in commits)} "
                 f"0 0 0 0 0 {int(all_tags)} 0")
    return "\n".join(lines) + "\n"


class Checks(unittest.TestCase):
    def rejected(self, callable_, diagnostic):
        with self.assertRaisesRegex(ValueError, re.escape(diagnostic)):
            callable_()
        DIAGNOSTICS[diagnostic] += 1


class StrictCaptureTests(Checks):
    def test_explicit_observer_counter_profile_keeps_strict_default(self):
        j, f = parse_jsonl(json_text(fixture())), parse_f(f_text(fixture()))
        for row in f["rows"]:
            if row["tag"] == "D":
                row["cycle"] += 1
        self.rejected(lambda: compare_pair(j, f), "D_TICK_GROUPS")
        self.assertEqual(compare_pair(j, f, observer_counter=True)["d_cycle_minus_state_counter"], {"1": 2})
        for delta in (-2, 1):
            bad = copy.deepcopy(f)
            next(r for r in bad["rows"] if r["tag"] == "D")["cycle"] += delta
            self.rejected(lambda: compare_pair(j, bad, observer_counter=True), "OBSERVER_COUNTER_NOT_SAME_EDGE")

    def test_all_sixteen_legal_tags(self):
        rows = fixture()
        parsed_f = parse_f(f_text(rows, all_tags=True))
        self.assertEqual(set(r["tag"] for r in parsed_f["rows"]), {*F_FORMAT, "T", "END"})
        result = compare_pair(parse_jsonl(json_text(rows)), parsed_f)
        self.assertEqual(result["commits_compared"], 2)
        self.assertFalse(result["arithmetic_golden_passed"])
        self.assertEqual(len(parsed_f["unobservable_end_counters"]), 5)

    def test_silent_lanes_are_legal(self):
        rows = fixture()
        self.assertEqual(replay_states(parse_jsonl(json_text(rows))["rows"], lambda row: 0)
                         ["state_rows_compared"], 8)
        compare_pair(parse_jsonl(json_text(rows)), parse_f(f_text(rows)))

    def test_signed_pcm_extremes_transport_only(self):
        rows = fixture()
        commits = [r for r in rows if r["tag"] == "COMMIT"]
        commits[0].update(pcm_left=-8388608, pcm_right=8388607)
        commits[1].update(pcm_left=-1, pcm_right=0)
        compare_pair(parse_jsonl(json_text(rows)), parse_f(f_text(rows)))

    def test_duplicate_json_key(self):
        text = json_text(fixture()).replace('"schema":1', '"schema":1,"schema":1', 1)
        self.rejected(lambda: parse_jsonl(text), "DUPLICATE_JSON_KEY:schema")

    def test_meta_types_and_unknown_fields(self):
        for field, value, code in (("schema", True, "META_PROFILE"),
                                   ("sys_hz", 50000000, "META_PROFILE"),
                                   ("extra", 0, "META_KEYS")):
            rows = fixture()
            rows[0][field] = value
            self.rejected(lambda: parse_jsonl(json_text(rows)), code)

    def test_integer_bool_rejected(self):
        rows = fixture()
        rows[3]["lane"] = False
        self.rejected(lambda: parse_jsonl(json_text(rows)), "INTEGER_RANGE:lane")

    def test_duplicate_and_missing_lane_with_correct_end(self):
        rows = fixture()
        rows.insert(4, copy.deepcopy(rows[3]))
        self.rejected(lambda: parse_jsonl(json_text(rows)), "DUPLICATE_STATE_LANE")
        rows = fixture()
        del rows[3]
        self.rejected(lambda: parse_jsonl(json_text(rows)), "TICK_STATE_MISSING_LANE")

    def test_enum_and_hex_width(self):
        rows = fixture()
        rows[3]["raw_state"] = 10
        self.rejected(lambda: parse_jsonl(json_text(rows)), "STATE_ENUM_MAPPING")
        rows = fixture()
        rows[3]["step_q16_twos33"] = "200000000"
        self.rejected(lambda: parse_jsonl(json_text(rows)), "HEX_WIDTH:step_q16_twos33")

    def test_every_private_enum_mapping(self):
        for private, public in PUBLIC_STATES.items():
            rows = fixture()
            rows[3].update(raw_state=private, public_state=public)
            parse_jsonl(json_text(rows))

    def test_future_tick_request_rejected(self):
        rows = fixture()
        for row in rows[3:7]:
            row["pending_request_id"] = 2
        self.rejected(lambda: parse_jsonl(json_text(rows)), "TICK_WITHOUT_PENDING_REQUEST")

    def test_reset_cancels_pending_and_reuses_id(self):
        rows = fixture()
        rows.insert(-1, {"tag": "REQUEST", "epoch": 1, "cycle": 8, "request_id": 3})
        rows.insert(-1, {"tag": "RESET", "epoch": 2, "cycle": 9})
        rows.insert(-1, {"tag": "REQUEST", "epoch": 2, "cycle": 10, "request_id": 1})
        rows.insert(-1, {"tag": "COMMIT", "epoch": 2, "cycle": 11,
                         "request_id": 1, "pcm_left": 0, "pcm_right": 0})
        parsed = parse_jsonl(json_text(rows))
        self.assertEqual(parsed["cancelled_requests"], [(1, 3)])
        compare_pair(parsed, parse_f(f_text(rows)))

    def test_orphan_and_duplicate_commit(self):
        rows = fixture()
        rows[7]["request_id"] = 9
        self.rejected(lambda: parse_jsonl(json_text(rows)), "ORPHAN_OR_DUPLICATE_COMMIT")
        rows = fixture()
        rows.insert(8, copy.deepcopy(rows[7]))
        self.rejected(lambda: parse_jsonl(json_text(rows)), "ORPHAN_OR_DUPLICATE_COMMIT")

    def test_end_counts_and_trailing_record(self):
        rows = fixture()
        rows[-1]["counts"]["STATE"] += 1
        raw = "\n".join(json.dumps(row) for row in rows)
        self.rejected(lambda: parse_jsonl(raw), "END_COUNTS")
        self.rejected(lambda: parse_jsonl(json_text(fixture()) + json.dumps(rows[1])), "JSON_RECORD_AFTER_END")

    def test_f_every_tag_rejects_extra_token(self):
        text = f_text(fixture(), all_tags=True)
        for tag in F_FORMAT:
            lines = text.splitlines()
            index = next(i for i, line in enumerate(lines) if line.startswith(tag + " "))
            lines[index] += " junk"
            self.rejected(lambda: parse_f("\n".join(lines)), "F_ARITY:" + tag)

    def test_f_bad_tag_scenario_hex_and_fixture(self):
        text = f_text(fixture(), all_tags=True)
        for old, new, code in (("T 1 four_voices", "T 1 invented", "F_SCENARIO"),
                               ("U 1 1 00", "U 1 1 000", "HEX_WIDTH:U"),
                               ("P 1 0000000000000000 1", "P 1 0000000000000000 2", "INTEGER_RANGE:P"),
                               ("N 1 0", "X 1 0", "UNKNOWN_F_TAG:X")):
            self.assertIn(old, text)
            self.rejected(lambda: parse_f(text.replace(old, new, 1)), code)

    def test_f_end_recomputed_counters(self):
        text = f_text(fixture(), all_tags=True)
        for replacement, code in (("END 3 0 0 0 0 0 0 1 0", "F_END_TOTAL"),
                                  ("END 2 1 0 0 0 0 0 1 0", "F_END_NONZERO_LEFT"),
                                  ("END 2 0 0 0 0 0 1 1 0", "F_END_NORMAL_PUSHES"),
                                  ("END 2 0 0 0 0 0 0 0 0", "F_END_SYNTHETIC_PUSHES")):
            self.rejected(lambda: parse_f(text.replace("END 2 0 0 0 0 0 0 1 0", replacement)), code)

    def test_reset_binding_and_ordered_m_not_dictionary(self):
        rows = fixture()
        # Change reset cycle only; grammar remains complete and valid.
        text = f_text(rows).replace("R 1 1", "R 2 1")
        self.rejected(lambda: compare_pair(parse_jsonl(json_text(rows)), parse_f(text)),
                      "RESET_PAIR_ORDER_OR_CYCLE")
        text = f_text(rows).replace("M 4 1", "M 4 2").replace("M 7 2", "M 7 1")
        self.rejected(lambda: compare_pair(parse_jsonl(json_text(rows)), parse_f(text)),
                      "COMMIT_PAIR_ORDER_OR_PCM")

    def test_self_consistent_late_fcw_wrong_chain(self):
        rows = fixture(10)
        # Both files agree on wrong final observed FCW. Independent input is10.
        rows[-3]["dds_fcw"] = "0000000b"
        parsed = parse_jsonl(json_text(rows))
        compare_pair(parsed, parse_f(f_text(rows)))
        self.rejected(lambda: replay_states(parsed["rows"], lambda row: 10), "DDS_FCW:1:6:3")

    def test_legal_wrong_table_and_phase_are_semantic_errors(self):
        for field, value, diagnostic in (("table", 2, "DDS_table:1:6:3"),
                                          ("phase_acc", "0000000b", "DDS_phase_acc:1:6:3")):
            rows = fixture(10)
            rows[-3][field] = value
            parsed = parse_jsonl(json_text(rows))
            compare_pair(parsed, parse_f(f_text(rows)))
            self.rejected(lambda: replay_states(parsed["rows"], lambda row: 10), diagnostic)


class DDSTests(Checks):
    def test_all_128_note_codes_against_frozen_constants(self):
        source = (FROZEN / "sources/note_pitch.sv").read_text(encoding="utf-8")
        table = source.split("SEMITONE_TABLE = {", 1)[1].split("};", 1)[0]
        constants = list(reversed([int(v) for v in re.findall(r"32'd(\d+)", table)]))
        self.assertEqual(len(constants), 12)
        for note in range(128):
            offset = (note - 60 - note % 12) // 12
            expected = constants[note % 12] * (1 << offset) if offset >= 0 else constants[note % 12] // (1 << -offset)
            self.assertEqual(note_fcw(note), expected & MASK32)
        self.assertEqual(note_fcw(69), 39370534)
        for bad in (True, -1, 128, 60.0):
            self.rejected(lambda: note_fcw(bad), "NOTE_RANGE")

    def test_pre_nba_retrigger_keeps_phase_and_full_attack(self):
        lane = PianoDDS(phase=123)
        before = lane.edge(10, velocity=256, tick=True, note_on=True)
        self.assertEqual(before, {"phase_acc": 123, "table": 3, "rom_addr": 768})
        self.assertEqual((lane.phase, lane.active_table, lane.attack_left), (133, 0, 480))

    def test_attack_windows_and_pending_until_wrap(self):
        for velocity, duration in ((255, 0), (256, 480), (511, 480), (512, 960),
                                    (767, 960), (768, 1440), (1023, 1440)):
            lane = PianoDDS()
            lane.edge(1, velocity=velocity, note_on=True)
            self.assertEqual(lane.attack_left, duration)
            if not duration:
                self.assertEqual(lane.active_table, 1)
                continue
            for _ in range(duration - 1):
                lane.edge(1, tick=True)
            self.assertEqual((lane.attack_left, lane.change_pending, lane.active_table), (1, False, 0))
            lane.edge(1, tick=True)
            self.assertEqual((lane.attack_left, lane.change_pending, lane.active_table), (0, True, 0))
            lane.phase = MASK32
            before = lane.edge(1, tick=True)
            self.assertEqual(before["table"], 0)
            self.assertEqual((lane.phase, lane.active_table, lane.change_pending), (0, 1, False))

    def test_expiration_on_wrap_and_retrigger_cancels_pending(self):
        lane = PianoDDS(phase=MASK32, attack_left=1, active_table=0)
        lane.edge(1, tick=True)
        self.assertEqual((lane.active_table, lane.change_pending), (1, False))
        lane = PianoDDS(phase=MASK32, active_table=0, pending_table=1, change_pending=True)
        lane.edge(300000000, velocity=512, tick=True, note_on=True)
        self.assertEqual((lane.active_table, lane.attack_left, lane.change_pending), (2, 960, False))

    def test_band_boundaries_and_reset(self):
        for fcw, body, attack in ((134217728, 1, 0), (134217729, 2, 1),
                                  (268435456, 2, 1), (268435457, 3, 2),
                                  (536870912, 3, 2), (536870913, 3, 3)):
            lane = PianoDDS()
            lane.edge(fcw, velocity=0, note_on=True)
            self.assertEqual(lane.active_table, body)
            lane.edge(fcw, velocity=1023, note_on=True)
            self.assertEqual(lane.active_table, attack)
            lane.reset()
            self.assertEqual(lane, PianoDDS())

    def test_idle_edges_do_not_advance(self):
        lane = PianoDDS(phase=99, attack_left=42, active_table=0)
        for _ in range(500):
            lane.edge(123)
        self.assertEqual((lane.phase, lane.attack_left), (99, 42))

    def test_pitch_center_floor_rounding_and_saturation(self):
        roms = [[int(word, 16) for word in (FROZEN / "rom" / name).read_text(encoding="utf-8").split()]
                for name in ("oct_ratio_q16.mem", "sub_ratio_q16.mem", "lfo_sine_q15.mem")]
        self.assertEqual((len(roms[0]), len(roms[1]), len(roms[2])), (50, 1024, 1024))
        for note in range(128):
            base = note_fcw(note)
            self.assertEqual(pitch_mod(base, 0, 0, 24, 0, *roms), min(base, 0x80000000))
        # Independent synthetic ROMs isolate exact final +32768 rounding.
        octaves, fractions, sine = [65536] * 50, [32768] * 1024, [0] * 1024
        self.assertEqual(pitch_mod(3, 0, 0, 0, 0, octaves, fractions, sine), 2)
        fractions = [131072] * 1024
        self.assertEqual(pitch_mod(0x70000000, 0, 0, 0, 0, octaves, fractions, sine), 0x80000000)
        # Negative fractional displacement uses floor and low10 ROM bits.
        octaves, fractions = [65536] * 50, [65536] * 1024
        octaves[24], fractions[1023] = 32768, 32768
        self.assertEqual(pitch_mod(100, -1, 0, 1, 0, octaves, fractions, sine), 25)
        self.rejected(lambda: pitch_mod(True, 0, 0, 0, 0, *roms), "PITCH_INPUT_RANGE")


def timeline_fixture(note=False):
    """SYNTHETIC full stage chain, independent accepted note/control input."""
    base = note_fcw(60) if note else 0
    event = (1 << 57) | (60 << 46) | (256 << 36)
    rows = [dict(META), {"tag": "RESET", "epoch": 1, "cycle": 1}]

    def state(cycle, lane, on=False):
        result = {key: 0 for key in STATE_RANGES}
        result.update({key: "0" * ((bits + 3) // 4) for key, bits in STATE_HEX.items()})
        result.update(tag="STATE", epoch=1, cycle=cycle, lane=lane,
                      pending_request_id=0 if on else 1, tick=int(not on), note_on=int(on),
                      table=3 if on or not note or lane else 0)
        if note and lane == 0:
            result.update(source=1, note=60, generation=1, velocity=256, occupied=1, dds_fcw=f"{base:08x}")
        return result

    if note:
        rows.append(state(5, 0, True))
    rows.append({"tag": "REQUEST", "epoch": 1, "cycle": 8, "request_id": 1})
    rows.extend(state(24, lane) for lane in range(4))
    rows.append({"tag": "COMMIT", "epoch": 1, "cycle": 31, "request_id": 1, "pcm_left": 0, "pcm_right": 0})
    occupied, source, generation, notes = (1, 1, 1, 60) if note else (0, 0, 0, 0)
    f = ["R 1 1"]
    if note:
        f.extend((f"E 2 {event:016x}", "N 5 1"))
    f.extend(("J 8 1", f"Q 10 1 {occupied:x} {source:04x} 0000 {generation:032x} {base:032x} {notes:08x}",
              "S 15 1 000000000000 000000000000 10842", "C 15 1",
              f"F 23 1 {occupied:x} {source:04x} 0000 {generation:032x} {base:032x}",
              f"D 24 1 {base:032x}",
              f"H 30 1 {occupied:x} 0000000000000000 0000000000000000 {'fc' if note else 'ff'}",
              "M 31 1 000000 000000 0", "END 1 0 0 0 0 0 0 0 0"))
    return parse_jsonl(json_text(rows)), parse_f("\n".join(f))


class TimelineTests(Checks):
    @staticmethod
    def roms():
        return [[int(word, 16) for word in (FROZEN / "rom" / name).read_text(encoding="utf-8").split()]
                for name in ("oct_ratio_q16.mem", "sub_ratio_q16.mem", "lfo_sine_q15.mem")]

    def test_full_silent_stage_chain(self):
        j, f = timeline_fixture()
        result = replay(j, f, self.roms())
        self.assertEqual(result["comparisons"]["state_rows"], 4)
        self.assertFalse(result["a1_complete"])

    def test_accepted_note_pre_nba_then_tick(self):
        j, f = timeline_fixture(True)
        self.assertEqual(replay(j, f, self.roms())["comparisons"]["state_rows"], 5)

    def test_coherent_fcw_chain_cannot_be_its_own_expected(self):
        j, f = timeline_fixture(True)
        for row in j["rows"]:
            if row["tag"] == "STATE" and row["tick"] and row["lane"] == 0:
                row["dds_fcw"] = f"{note_fcw(60) + 1:08x}"
        for row in f["rows"]:
            if row["tag"] == "F":
                row["values"][5] += 1
            if row["tag"] == "D":
                row["values"][1] += 1
        compare_pair(j, f, observer_counter=True)
        self.rejected(lambda: replay(j, f, self.roms()), "PITCH_MOD_FCW")

    def test_control_and_stage_and_terminal_table(self):
        for tag, index, value, diagnostic in (("S", 1, 1, "CONTROL_SNAPSHOT"),
                                               ("H", 4, 255, "H_DDS_TABLE")):
            j, f = timeline_fixture(True)
            next(row for row in f["rows"] if row["tag"] == tag)["values"][index] = value
            self.rejected(lambda: replay(j, f, self.roms()), diagnostic)
        j, f = timeline_fixture(True)
        next(row for row in f["rows"] if row["tag"] == "F")["cycle"] += 1
        self.rejected(lambda: replay(j, f, self.roms()), "STAGE_DELAY:F")
        j, f = timeline_fixture(True)
        next(row for row in j["rows"] if row["tag"] == "STATE" and row["tick"] and row["lane"] == 3)["table"] = 2
        self.rejected(lambda: replay(j, f, self.roms()), "DDS_table")

    def test_fixture_identity_is_not_only_a_boolean_range(self):
        j, f = timeline_fixture()
        next(row for row in f["rows"] if row["tag"] == "M")["values"][3] = 1
        self.rejected(lambda: replay(j, f, self.roms()), "M_FIXTURE_KNOWN_ZERO")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    # Import only when run as entry point to avoid test module circular loading.
    sys.modules.setdefault("test_candidates", sys.modules[__name__])
    import test_audio_math
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(test_audio_math))
    import test_router
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(test_router))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"scope": "SYNTHETIC_COMPONENT_ONLY", "tests_run": result.testsRun,
                      "negative_cases_rejected": sum(DIAGNOSTICS.values()),
                      "diagnostics": dict(DIAGNOSTICS), "successful": result.wasSuccessful(),
                      "real_capture_replayed": False, "a1_complete": False, "t060_complete": False},
                     sort_keys=True))
    sys.exit(0 if result.wasSuccessful() else 1)
