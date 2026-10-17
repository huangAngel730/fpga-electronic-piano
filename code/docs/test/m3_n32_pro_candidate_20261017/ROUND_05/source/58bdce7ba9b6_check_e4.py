"""Independent frozen-piano math and new E4 request/transport checker.

Only accepted stimulus R/I/J/X and frozen references select expectations.
Quiet retirement tails are explicitly L2-only and never enter the math oracle.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "code/software/polyphony_scaling_candidate"))
from b2c_check import Oracle, dec, hx  # noqa: E402

BASE_LENGTHS = {"R": 2, "I": 3, "J": 3, "U": 12, "G": 7, "W": 6,
                "C": 11, "A": 3, "L": 11, "F": 6, "P": 6,
                "X": 2, "Z": 3, "Y": 4, "END": 14}
END_KEYS = ("I", "J", "C", "A", "L", "P", "X", "Z", "W", "G", "Y", "F")


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def sat24(value):
    return max(-(1 << 23), min((1 << 23) - 1, value))


def dac16(value):
    return max(-32768, min(32767, (value + 128) >> 8)) & 65535


class Checker:
    def __init__(self, n):
        self.n = n
        self.oracle = Oracle(response=1, n=n, identity_controls=True)
        self.epoch = -1
        self.live = None
        self.used_ids = set()
        self.counts = Counter()
        self.first = {}
        self.published = {}
        self.hold = None
        self.tail = False
        self.tail_result = None
        self.tail_done_mask = 0
        self.tail_done_rows = 0
        self.tail_wait_reset = None
        self.nonzero = set()
        self.full_unique = 0
        self.maximum_latency = 0
        self.tlive = None
        self.returned = None
        self.last_frame = None
        self.frame_intervals = Counter()
        self.tcounts = Counter()
        self.transport_ids = set()
        self.transport_end = False
        self.play_held = (0, 0)
        self.play_pending = None
        self.play_commit_cycle = None
        self.serial = None
        self.half_bits = []
        self.half_expected = None
        self.half_synced = False
        self.loaded = (0, 0)
        self.serial_halves = Counter()
        self.serial_rises = 0
        self.ended = False
        self.current_line = None

    def reset(self, cycle):
        if self.live is not None:
            self.counts["reset_cancelled"] += 1
        need(self.tlive is None and self.returned is None,
             "TRANSPORT_RESET_WITH_UNCLOSED_REQUEST")
        self.live = None
        self.hold = None
        self.epoch += 1
        self.oracle.counts["R"] += 1
        self.oracle.reset(cycle)
        self.serial = None
        self.half_bits = []
        self.half_synced = False
        self.loaded = (0, 0)
        self.last_frame = None
        self.play_held = (0, 0)
        self.play_pending = None
        self.play_commit_cycle = None

    def math_group(self, cycle, rows):
        by = {row[0]: row for row in rows}
        need(len(by) == len(rows), "DUPLICATE_BASE_TAG")
        if "R" in by:
            if [row[0] for row in rows] == ["R", "END"]:
                # The TB's final negedge reset marker and immediate END share
                # the same cycle. Preserve their explicit text order; this
                # terminal reset must not conceal an unfinished transaction.
                need(self.live is None and self.oracle.frame is None,
                     "TERMINAL_RESET_WITH_UNCLOSED_MATH")
                self.reset(cycle)
                return self.math_group(cycle, [by["END"]])
            need(len(rows) == 1, "RESET_BASE_ROW_CONFLICT")
            self.reset(cycle)
            return None
        need(hasattr(self.oracle, "router"), "MISSING_RESET")
        if "END" in by:
            need(len(rows) == 1 and self.live is None and self.oracle.frame is None,
                 "END_UNCLOSED_REQUEST")
            need([dec(x) for x in by["END"][2:]] ==
                 [self.oracle.counts[key] for key in END_KEYS], "END_COUNTS")
            self.ended = True
            return None
        if "J" in by:
            need(self.live is None, "OVERLAPPING_ACCEPT")
            request_id = hx(by["J"][2], 32)
            key = self.epoch, request_id
            need(key not in self.used_ids, "DUPLICATE_ACCEPT_ID_IN_EPOCH")
            self.used_ids.add(key)
            self.live = {"key": key, "cycle": cycle, "first": None}
            self.counts["accepted"] += 1
        before = self.oracle.frame
        self.oracle.advance(cycle, rows)
        frame = before if before is not None else self.oracle.frame
        expected = None
        if frame and len(frame["lanes"]) == self.n:
            total = sum(frame["lanes"].values())
            pcm = sat24(total)
            expected = (frame["id"], pcm, pcm, int(total != pcm))
        if "L" in by:
            lane = dec(by["L"][3], 0, self.n - 1)
            # This PCM was independently checked by Oracle.advance above.
            if frame["lanes"][lane] != 0:
                self.nonzero.add(lane)
        if "F" in by:
            need(self.live is not None and expected is not None,
                 "FIRST_WITHOUT_COMPLETE_VERIFIED_LANES")
            need(self.live["first"] is None, "DUPLICATE_FIRST")
            self.live["first"] = expected
            self.first[self.live["key"]] = expected
            need(cycle - self.live["cycle"] < 833, "REQUEST_FIRST_DEADLINE")
            if all(slot["occupied"] for slot in frame["slots"]):
                need(len(set(frame["fcw"])) == self.n,
                     "FULL_FRAME_NOT_N_UNIQUE_FCW")
                self.full_unique += 1
        if "P" in by:
            need(self.live is not None and self.live["first"] == expected,
                 "PUBLISH_WITHOUT_FIRST_OR_CHANGED_PCM")
            need(cycle - self.live["cycle"] < 833,
                 "MANUAL_PUBLISH_DEADLINE")
            key = self.live["key"]
            need(key not in self.published, "DUPLICATE_PUBLISH")
            self.published[key] = expected
            self.counts["published"] += 1
        if "X" in by or "Z" in by:
            need("P" not in by, "PUBLISH_ON_CANCEL")
            if self.live is not None:
                self.counts["cancelled"] += 1
                self.live = None
        return expected

    def k_group(self, cycle, rows, expected, tags):
        need(len(rows) <= 1, "DUPLICATE_K")
        stopped = "R" in tags or "X" in tags or "Z" in tags
        if self.hold is not None and not stopped:
            need(bool(rows) and cycle == self.hold[0] + 1,
                 "HOLD_EDGE_MISSING_OR_GAP")
        if not rows:
            if stopped:
                self.hold = None
            return
        row = rows[0]
        if len(row) == 8:
            ready, rid = dec(row[2], 0, 1), hx(row[3], 32)
            left, right = dec(row[4], -(1 << 23), (1 << 23)-1), dec(row[5], -(1 << 23), (1 << 23)-1)
            clip, late = dec(row[6], 0, 1), dec(row[7], 0, 1)
            valid, publish = 1, int("P" in tags)
        elif len(row) == 10:
            valid, ready, publish = [dec(x, 0, 1) for x in row[2:5]]
            rid = hx(row[5], 32)
            left, right = dec(row[6], -(1 << 23), (1 << 23)-1), dec(row[7], -(1 << 23), (1 << 23)-1)
            late, clip = dec(row[8], 0, 1), dec(row[9], 0, 1)
        else:
            raise ValueError("K_SCHEMA")
        if stopped:
            need(not publish, "K_CANCEL_PUBLISH")
            self.hold = None
            return
        need(valid == 1 and self.live is not None and expected is not None,
             "K_STALE_OR_UNOWNED")
        payload = rid, left, right, clip
        need(payload == expected, "K_ID_PCM_CLIPPED_INDEPENDENT_MATH")
        need(late == 0, "K_LATE")
        need(publish == (valid and ready) and bool(publish) == ("P" in tags),
             "K_PUBLISH_HANDSHAKE")
        if self.hold is not None:
            need(payload == self.hold[1], "K_HOLD_PAYLOAD_CHANGED")
        self.counts["k_edges"] += 1
        self.counts["hold_edges"] += not ready
        self.hold = (cycle, payload) if not ready else None
        if publish:
            need(cycle - self.live["cycle"] < 833,
                 "K_PUBLISH_DEADLINE")
            self.live = None

    def transport(self, row):
        need(len(row) == 17, "T_SCHEMA")
        cycle, epoch = dec(row[1]), dec(row[2])
        frame, accept, transfer, commit, cancel = [dec(x, 0, 1) for x in row[3:8]]
        sid, rid = hx(row[8], 32), hx(row[9], 32)
        pcm = (rid, dec(row[10], -(1 << 23), (1 << 23)-1),
               dec(row[11], -(1 << 23), (1 << 23)-1), dec(row[12], 0, 1))
        committed = (hx(row[13], 32), dec(row[14], -(1 << 23), (1 << 23)-1),
                     dec(row[15], -(1 << 23), (1 << 23)-1), dec(row[16], 0, 1))
        # Current TB contract is 17 tokens (tag plus 16 values).
        need(epoch == self.epoch, "T_RESET_EPOCH")
        if frame:
            if self.last_frame is not None:
                distance = cycle - self.last_frame
                need(distance in (833, 834), "FRAME_NOT_833_834")
                self.frame_intervals[distance] += 1
            need(self.tlive is None and self.returned is None,
                 "FRAME_BOUNDARY_UNCLOSED_REQUEST")
            self.last_frame = cycle
            self.tcounts["frames"] += 1
            if self.play_pending is not None:
                need(self.play_commit_cycle < cycle, "PLAY_PENDING_FRAME_SAME_EDGE")
                self.play_held = self.play_pending
                self.play_pending = None
        if accept:
            need(not cancel and self.tlive is None, "T_ACCEPT_OVERLAP_CANCEL")
            key = epoch, sid
            need(key not in self.transport_ids, "T_DUPLICATE_ACCEPT_ID_IN_EPOCH")
            self.transport_ids.add(key)
            self.tlive = {"id": sid, "cycle": cycle, "epoch": epoch}
            self.tcounts["accepted"] += 1
        if transfer:
            need(self.tlive is not None and not cancel and rid == self.tlive["id"]
                 and epoch == self.tlive["epoch"],
                 "T_TRANSFER_ID_OR_CANCEL")
            key = self.epoch, rid
            need(self.published.get(key) == pcm, "T_TRANSFER_NOT_MATH_PUBLICATION")
            self.returned = self.tlive | {"pcm": pcm}
            self.tlive = None
            self.tcounts["transferred"] += 1
        if commit:
            need(self.returned is not None and not cancel,
                 "T_COMMIT_WITHOUT_RETURN")
            need(epoch == self.returned["epoch"], "T_COMMIT_ACCEPTED_EPOCH")
            need(committed == self.returned["pcm"], "T_COMMIT_ID_PCM_CLIP")
            need(self.play_pending is None and not frame,
                 "PLAY_PENDING_OVERWRITE_OR_FRAME_COMMIT")
            latency = cycle - self.returned["cycle"]
            need(0 <= latency < 833, "T_REQUEST_COMMIT_DEADLINE")
            self.maximum_latency = max(self.maximum_latency, latency)
            # This is a pre-NBA commit. New pending PCM is visible on the
            # following cycle, not to same-edge S pin observers.
            self.play_pending = self.returned["pcm"][1:3]
            self.play_commit_cycle = cycle
            self.returned = None
            self.tcounts["committed"] += 1
        need(not cancel or not (transfer or commit), "T_CANCEL_TRANSFER")

    def finish_transport(self, number, row):
        self.current_line = {"line": number, "raw": " ".join(row)}
        need(len(row) == 5 and not self.transport_end, "TRANSPORT_END_SCHEMA")
        need(self.tlive is None and self.returned is None,
             "TRANSPORT_END_UNCLOSED_REQUEST")
        need([dec(x) for x in row[1:]] == [self.tcounts["accepted"], self.tcounts["transferred"],
             self.tcounts["committed"], self.maximum_latency], "TRANSPORT_END_COUNTS")
        self.transport_end = True

    def pins(self, row):
        need(len(row) == 8, "S_SCHEMA")
        cycle = dec(row[1])
        bclk, ws, din, frame = [dec(x, 0, 1) for x in row[2:6]]
        left, right = [dec(x, -(1 << 23), (1 << 23)-1) for x in row[6:8]]
        expected_play = self.play_held
        if self.play_pending is not None and self.play_commit_cycle < cycle:
            expected_play = self.play_pending
        need((left, right) == expected_play, "S_PLAY_NOT_INDEPENDENT_COMMIT_BUFFER")
        previous = self.serial
        if previous is not None and ws != previous[1]:
            if self.half_synced:
                need(len(self.half_bits) == 32, "PT8211_HALF_NOT_32_RISES")
                value = 0
                for bit in self.half_bits[-16:]:
                    value = (value << 1) | bit
                need(value == self.half_expected, "PT8211_DECODED_PCM_MISMATCH")
                self.serial_halves["left" if previous[1] else "right"] += 1
            self.half_synced = True
            self.half_bits = []
            self.half_expected = self.loaded[0 if ws else 1]
        if previous is not None and not previous[0] and bclk:
            self.serial_rises += 1
            self.half_bits.append(din)
        if frame:
            self.loaded = tuple(dac16(value) for value in expected_play)
        self.serial = bclk, ws, din, cycle

    def tail_done(self, row):
        need(len(row) == 5, "TAIL_D_SCHEMA")
        mask = hx(row[2], self.n)
        need(mask != 0, "TAIL_D_EMPTY_MASK")
        slot = dec(row[3], 0, self.n - 1)
        generation = hx(row[4], 32)
        need(slot == (mask & -mask).bit_length() - 1,
             "TAIL_D_SLOT_NOT_LOWEST_ASSERTED")
        need(generation == 1, "TAIL_D_RESET_FILL_GENERATION")
        self.tail_done_mask |= mask
        self.tail_done_rows += 1

    def check(self, raw):
        groups = {}
        header = False
        last = -1
        end_rows = []
        for number, original in enumerate(raw.decode("utf-8", errors="strict").splitlines(), 1):
            self.current_line = {"line": number, "raw": original}
            line = original[2:] if original.startswith("# ") else original
            need("** Fatal:" not in line and "FATAL:" not in line,
                 "SIMULATOR_FATAL_DIAGNOSTIC")
            row = line.split()
            if not row:
                continue
            tag = row[0]
            if tag == "B2C":
                need(not header and row == ["B2C", str(self.n), "1", "0"], "HEADER")
                header = True
                continue
            if tag not in {*BASE_LENGTHS, "K", "T", "S", "V", "D",
                           "TAIL_BEGIN", "TAIL_END", "TRANSPORT_END"}:
                continue
            need(header, "DATA_BEFORE_HEADER")
            if tag == "TRANSPORT_END":
                end_rows.append((number, row, last))
                continue
            if tag in BASE_LENGTHS:
                need(len(row) == BASE_LENGTHS[tag], "BASE_ROW_SCHEMA")
            cycle = dec(row[1])
            need(cycle >= last, "CYCLE_ORDER")
            last = cycle
            groups.setdefault(cycle, []).append((number, original, row))
        need(header, "MISSING_HEADER")
        for cycle, records in groups.items():
            need(not self.ended, "ROWS_AFTER_END")
            self.current_line = {"line": records[0][0], "raw": records[0][1], "cycle": cycle}
            tags = {record[2][0] for record in records}
            if self.tail_wait_reset is not None:
                need(cycle - self.tail_wait_reset <= 8,
                     "TAIL_RESET_BOUNDARY_EXCEEDED_8_CYCLES")
                if "R" in tags:
                    need(tags <= {"R", "END"}, "TAIL_RESET_ROW_CONFLICT")
                    self.tail_wait_reset = None
                else:
                    need(tags <= {"D", "U"}, "TAIL_POST_END_NEW_BUSINESS")
                    for number, original, row in records:
                        self.current_line = {"line": number, "raw": original, "cycle": cycle}
                        if row[0] == "D":
                            self.tail_done(row)
                        elif row[0] == "U":
                            need(all(hx(value, self.n) == 0 for value in row[2:6]),
                                 "TAIL_POST_END_NONEMPTY_ROUTER")
                    continue
            if "TAIL_BEGIN" in tags:
                need(not self.tail and self.live is None and self.oracle.frame is None,
                     "TAIL_BEGIN_UNCLOSED_MATH")
                self.tail = True
                self.tail_done_mask = 0
                self.tail_done_rows = 0
            if self.tail:
                for number, original, row in records:
                    if row[0] == "D":
                        self.current_line = {"line": number, "raw": original, "cycle": cycle}
                        self.tail_done(row)
            if "TAIL_END" in tags:
                row = next(record[2] for record in records if record[2][0] == "TAIL_END")
                need(self.tail and len(row) == 7, "TAIL_END_SCHEMA")
                req, advances, done = [dec(x) for x in row[2:5]]
                done_mask = hx(row[6], self.n)
                need(req == advances and advances >= 4800 and done > 0 and hx(row[5], self.n) == 0,
                     "TAIL_RETIREMENT_L2_NOT_EARNED")
                need(done_mask == (1 << self.n) - 1, "TAIL_ALL_N_RETIREMENT_MASK")
                need(done_mask == self.tail_done_mask and done == self.tail_done_rows,
                     "TAIL_SUMMARY_NOT_REAL_D_MASK_AND_COUNT")
                self.tail_result = {"requests": req, "advances": advances, "done_observations": done,
                                    "done_mask": done_mask,
                                    "independent_D_or_mask": self.tail_done_mask,
                                    "independent_D_rows": self.tail_done_rows,
                                    "scope": "RTL_LIFECYCLE_L2_NO_TAIL_MATH"}
                self.tail = False
                self.tail_wait_reset = cycle
                continue
            if self.tail:
                continue
            base = [record[2] for record in records if record[2][0] in BASE_LENGTHS]
            krows = [record[2] for record in records if record[2][0] == "K"]
            expected = self.math_group(cycle, base) if base or krows else None
            if base or krows:
                self.k_group(cycle, krows, expected, tags)
            # S and T observe pre-NBA state. Decode/check pins first, then
            # apply the independent buffer's frame/commit state transitions.
            serial_records = [record for record in records if record[2][0] == "S"]
            transport_records = [record for record in records if record[2][0] == "T"]
            need(len(serial_records) <= 1 and len(transport_records) <= 1,
                 "DUPLICATE_S_OR_T_EDGE")
            for number, original, row in serial_records + transport_records:
                self.current_line = {"line": number, "raw": original, "cycle": cycle}
                if row[0] == "T":
                    self.transport(row)
                elif row[0] == "S":
                    self.pins(row)
            for number, row, marker_cycle in end_rows:
                if marker_cycle == cycle:
                    self.finish_transport(number, row)
        need(self.ended and not self.tail and self.tail_wait_reset is None and
             self.live is None and self.tlive is None and self.returned is None,
             "END_MISSING_OR_UNCLOSED")
        need(self.counts["accepted"] == self.counts["published"] + self.counts["cancelled"] +
             self.counts["reset_cancelled"], "ACCEPT_DISPOSITION_COUNTS")
        need(self.nonzero == set(range(self.n)) and self.full_unique > 0,
             "N_DISTINCT_ACTIVE_CONTRIBUTIONS_MISSING")
        need(self.counts["hold_edges"] > 0 and self.counts["cancelled"] > 0 and
             self.counts["reset_cancelled"] > 0, "LIFECYCLE_COVERAGE_MISSING")
        need(self.transport_end and self.tcounts["committed"] >= 32 and self.frame_intervals,
             "TRANSPORT_COVERAGE_MISSING")
        need(min(self.serial_halves["left"], self.serial_halves["right"]) >= 16,
             "INDEPENDENT_SERIAL_COVERAGE_MISSING")
        return {"status": "PASS_ISOLATED_FROZEN_PIANO_E4_PARTIAL", "n": self.n,
                "input_sha256": hashlib.sha256(raw).hexdigest(), "counts": dict(self.counts),
                "math_counts": dict(self.oracle.counts), "math_coverage": dict(self.oracle.coverage),
                "all_nonzero_lanes": sorted(self.nonzero), "unique_fcw_full_frames": self.full_unique,
                "transport": dict(self.tcounts), "frame_intervals": dict(self.frame_intervals),
                "max_request_commit_cycles": self.maximum_latency,
                "serial_halves": dict(self.serial_halves), "serial_bclk_rises": self.serial_rises,
                "retirement_tail": self.tail_result, "board_release_allowed": False,
                "physical_STA": "NOT_RUN", "pure_sine_or_audible_claim": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--n", type=int, choices=(4, 8, 16, 32), required=True)
    args = parser.parse_args()
    checker = Checker(args.n)
    try:
        result = checker.check(args.input.read_bytes())
        code = 0
    except (ValueError, OSError, UnicodeError, KeyError, IndexError) as error:
        result = {"status": "REJECT", "n": args.n, "reason": str(error),
                  "first_failure_location": checker.current_line, "board_release_allowed": False}
        code = 1
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
