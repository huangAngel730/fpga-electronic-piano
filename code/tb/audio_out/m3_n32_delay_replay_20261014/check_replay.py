#!/usr/bin/env python3
"""Independent fixed-point/reference and transport-ledger checker."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path


PCM_MIN = -(1 << 23)
PCM_MAX = (1 << 23) - 1


class CheckFailure(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def sat24(value: int) -> tuple[int, bool]:
    if value > PCM_MAX:
        return PCM_MAX, True
    if value < PCM_MIN:
        return PCM_MIN, True
    return value, False


def signed24(value: int) -> int:
    value &= 0xFFFFFF
    return value - (1 << 24) if value & (1 << 23) else value


def q15_term(sample: int, gain: int) -> int:
    if not 0 <= gain <= 0x7FFF:
        raise CheckFailure("GAIN_RANGE", str(gain))
    return signed24((sample * gain) >> 15)


@dataclass
class DelayReference:
    enabled: bool = False
    delay: int = 1
    dry: int = 0x7FFF
    wet: int = 0
    feedback: int = 0
    pointer: int = 0
    left_history: list[int] = field(default_factory=lambda: [0] * 1024)
    right_history: list[int] = field(default_factory=lambda: [0] * 1024)
    flush_count: int = 0
    enabled_since_flush: int = 0
    maximum_enabled_run: int = 0

    def configure(self, enabled: bool, delay: int, dry: int, wet: int, feedback: int) -> None:
        if not 0 <= delay < 1024:
            raise CheckFailure("DELAY_RANGE", str(delay))
        flush = self.enabled != enabled or self.delay != delay
        self.enabled = enabled
        self.delay = delay
        self.dry = dry
        self.wet = wet
        self.feedback = feedback
        if flush:
            self.left_history = [0] * 1024
            self.right_history = [0] * 1024
            self.pointer = 0
            self.flush_count += 1
            self.enabled_since_flush = 0

    def _channel(self, sample: int, history: list[int]) -> tuple[int, bool, bool]:
        delayed = history[(self.pointer - self.delay) & 1023]
        mixed, effect_clip = sat24(q15_term(sample, self.dry) + q15_term(delayed, self.wet))
        feedback_value, feedback_clip = sat24(sample + q15_term(delayed, self.feedback))
        history[self.pointer] = feedback_value
        return mixed, effect_clip, feedback_clip

    def accept(self, left: int, right: int, upstream_clip: int) -> dict:
        if not self.enabled:
            return {
                "left": left,
                "right": right,
                "clip": bool(upstream_clip),
                "effect_clip_left": False,
                "effect_clip_right": False,
                "feedback_clip_left": False,
                "feedback_clip_right": False,
            }
        left_out, left_effect_clip, left_feedback_clip = self._channel(left, self.left_history)
        right_out, right_effect_clip, right_feedback_clip = self._channel(right, self.right_history)
        self.pointer = (self.pointer + 1) & 1023
        self.enabled_since_flush += 1
        self.maximum_enabled_run = max(self.maximum_enabled_run, self.enabled_since_flush)
        return {
            "left": left_out,
            "right": right_out,
            "clip": bool(upstream_clip or left_effect_clip or right_effect_clip),
            "effect_clip_left": left_effect_clip,
            "effect_clip_right": right_effect_clip,
            "feedback_clip_left": left_feedback_clip,
            "feedback_clip_right": right_feedback_clip,
        }


def parse_int(value: str) -> int:
    return int(value, 0)


def load_trace(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    with path.open("r", encoding="ascii") as stream:
        for line_number, line in enumerate(stream, 1):
            fields = line.split()
            if not fields:
                continue
            fields.append(str(line_number))
            rows.append(fields)
    return rows


def check(trace_path: Path, expected_vectors: int = 1300) -> dict:
    model = DelayReference()
    expected: dict[int, dict] = {}
    source_by_request: dict[int, dict] = {}
    canceled: set[int] = set()
    resolved: set[int] = set()
    commits: set[int] = set()
    hold_values: dict[int, tuple[int, int, int]] = {}
    hold_counts: dict[int, int] = {}
    requested: set[int] = set()
    first_valid: set[int] = set()
    pending: tuple[int, int, int, int] | None = None
    held = (0, 0, 0, 0)
    observed_frames: dict[int, tuple[int, int]] = {}
    frame_count = 0
    underruns = 0
    ever_committed = False
    clip_commits = 0
    configs = 0
    result_handshakes = 0
    pixel_samples = 0
    end = None
    i2s_summary = None
    last_source_line = -1
    source_lifetimes: set[int] = set()
    source_ids: set[int] = set()

    for fields in load_trace(trace_path):
        tag = fields[0]
        line_no = fields[-1]
        try:
            if tag == "CFG":
                _, _sim, enabled, delay, dry, wet, feedback, _ = fields
                model.configure(bool(int(enabled)), int(delay), int(dry), int(wet), int(feedback))
                configs += 1
            elif tag == "REQUEST":
                _, _sim, request_id, _ = fields
                request_id_i = int(request_id, 16)
                if request_id_i in requested:
                    raise CheckFailure("DUPLICATE_REQUEST", request_id)
                requested.add(request_id_i)
            elif tag == "REQ":
                (
                    _, _sim, request_id, index, lifetime, k_line, p_line, source_cycle,
                    source_id, left, right, clipped, _,
                ) = fields
                request_id_i = int(request_id, 16)
                source_id_i = int(source_id, 16)
                source = {
                    "index": int(index),
                    "lifetime": int(lifetime),
                    "k_line": int(k_line),
                    "p_line": int(p_line),
                    "cycle": int(source_cycle),
                    "source_id": source_id_i,
                    "left": int(left),
                    "right": int(right),
                    "clip": int(clipped),
                }
                if request_id_i in expected:
                    raise CheckFailure("DUPLICATE_REQUEST_ID", f"id={request_id}")
                if request_id_i not in requested:
                    raise CheckFailure("ACCEPT_WITHOUT_REQUEST", request_id)
                if source["p_line"] <= last_source_line:
                    raise CheckFailure("SOURCE_LINE_ORDER", f"line={source['p_line']}")
                if source["source_id"] in source_ids:
                    raise CheckFailure("DUPLICATE_SOURCE_ID", f"id={source_id}")
                if source["left"] != source["right"] or source["clip"] != 0:
                    raise CheckFailure("FROZEN_CAPTURE_SCOPE_CHANGED", f"trace_line={line_no}")
                last_source_line = source["p_line"]
                source_lifetimes.add(source["lifetime"])
                source_ids.add(source["source_id"])
                source_by_request[request_id_i] = source
                expected[request_id_i] = model.accept(
                    source["left"], source["right"], source["clip"]
                )
            elif tag == "FIRST":
                _, _sim, request_id, left, right, clipped, _ = fields
                request_id_i = int(request_id, 16)
                wanted = expected.get(request_id_i)
                if wanted is None:
                    raise CheckFailure("FIRST_UNKNOWN_ID", request_id)
                if request_id_i in first_valid:
                    raise CheckFailure("DUPLICATE_FIRST_VALID", request_id)
                actual = (int(left), int(right), bool(int(clipped)))
                target = (wanted["left"], wanted["right"], wanted["clip"])
                if actual != target:
                    raise CheckFailure("FIRST_VALID_MISMATCH", f"id={request_id}")
                first_valid.add(request_id_i)
            elif tag == "HOLD":
                _, _sim, request_id, left, right, clipped, _ = fields
                request_id_i = int(request_id, 16)
                value = (int(left), int(right), int(clipped))
                old = hold_values.setdefault(request_id_i, value)
                if old != value:
                    raise CheckFailure("HOLD_NOT_STABLE", f"id={request_id}")
                hold_counts[request_id_i] = hold_counts.get(request_id_i, 0) + 1
            elif tag == "CANCEL":
                _, _sim, request_id, _ = fields
                request_id_i = int(request_id, 16)
                if request_id_i not in expected:
                    raise CheckFailure("CANCEL_UNKNOWN_ID", request_id)
                canceled.add(request_id_i)
            elif tag == "RES":
                _, _sim, request_id, left, right, clipped, _ = fields
                request_id_i = int(request_id, 16)
                if request_id_i in canceled:
                    raise CheckFailure("CANCELED_RESULT_ACCEPTED", request_id)
                wanted = expected.get(request_id_i)
                if wanted is None:
                    raise CheckFailure("RESULT_UNKNOWN_ID", request_id)
                actual = (int(left), int(right), bool(int(clipped)))
                target = (wanted["left"], wanted["right"], wanted["clip"])
                if actual != target:
                    raise CheckFailure("RESULT_MATH_MISMATCH", f"id={request_id} {actual}!={target}")
                result_handshakes += 1
                resolved.add(request_id_i)
            elif tag == "COM":
                _, _sim, request_id, left, right, clipped, _ = fields
                request_id_i = int(request_id, 16)
                if request_id_i not in resolved:
                    raise CheckFailure("COMMIT_WITHOUT_RESULT", request_id)
                if request_id_i in commits:
                    raise CheckFailure("DUPLICATE_COMMIT", request_id)
                wanted = expected[request_id_i]
                actual = (int(left), int(right), bool(int(clipped)))
                target = (wanted["left"], wanted["right"], wanted["clip"])
                if actual != target:
                    raise CheckFailure("COMMIT_PCM_MISMATCH", f"id={request_id} {actual}!={target}")
                commits.add(request_id_i)
                pending = (request_id_i, actual[0], actual[1], int(actual[2]))
                clip_commits += int(actual[2])
            elif tag == "FRAME":
                _, _sim, seq, left, right, _ = fields
                seq_i = int(seq)
                if seq_i != frame_count:
                    raise CheckFailure("FRAME_SEQUENCE", f"actual={seq_i} expected={frame_count}")
                expected_play = pending if pending is not None else held
                actual_play = (int(left), int(right))
                if actual_play != (expected_play[1], expected_play[2]):
                    raise CheckFailure(
                        "PLAYBACK_MAPPING_MISMATCH",
                        f"seq={seq_i} actual={actual_play} expected={expected_play[1:3]}",
                    )
                observed_frames[seq_i] = actual_play
                if pending is not None:
                    held = pending
                    pending = None
                    ever_committed = True
                elif ever_committed:
                    underruns += 1
                frame_count += 1
            elif tag == "OBS":
                _, _sim, seq, left, right, _ = fields
                seq_i = int(seq)
                target = observed_frames.get(seq_i)
                actual = (int(left), int(right))
                if target is None or target != actual:
                    raise CheckFailure("OBSERVER_MISMATCH", f"seq={seq_i} actual={actual} target={target}")
            elif tag == "PX":
                _, _sim, seq, left, right, _ = fields
                target = observed_frames.get(int(seq))
                if target != (int(left), int(right)):
                    raise CheckFailure("PIXEL_CDC_MISMATCH", f"seq={seq}")
                pixel_samples += 1
            elif tag == "I2S":
                _, _sim, bclk_rises, lrck_edges, observation_drops, dut_clip_count, _ = fields
                i2s_summary = {
                    "bclk_rises": int(bclk_rises),
                    "lrck_edges": int(lrck_edges),
                    "observation_drops": int(observation_drops),
                    "clip_count": int(dut_clip_count),
                }
            elif tag == "END":
                end = fields
            else:
                raise CheckFailure("UNKNOWN_TRACE_TAG", f"tag={tag} line={line_no}")
        except (ValueError, IndexError) as exc:
            raise CheckFailure("TRACE_FORMAT", f"line={line_no} fields={fields[:-1]}") from exc

    if end is None:
        raise CheckFailure("END_MISSING", str(trace_path))
    if len(expected) != expected_vectors:
        raise CheckFailure("REQUEST_COUNT", f"actual={len(expected)} expected={expected_vectors}")
    if not set(expected).issubset(requested):
        missing = sorted(set(expected) - requested)[:8]
        raise CheckFailure("ACCEPT_WITHOUT_REQUEST_SET", f"missing={missing}")
    unaccepted_requests = requested - set(expected)
    if first_valid != set(expected):
        missing = sorted(set(expected) - first_valid)[:8]
        raise CheckFailure("FIRST_VALID_SET", f"missing={missing}")
    if source_lifetimes != {1}:
        raise CheckFailure("RESET_LIFETIME_SCOPE", str(source_lifetimes))
    if len(canceled) != 1:
        raise CheckFailure("CANCEL_COUNT", str(len(canceled)))
    if commits != set(expected) - canceled:
        missing = sorted((set(expected) - canceled) - commits)[:8]
        extra = sorted(commits - (set(expected) - canceled))[:8]
        raise CheckFailure("COMMIT_SET", f"missing={missing} extra={extra}")
    if not hold_values or max(hold_counts.values()) < 5:
        raise CheckFailure("HOLD_NOT_COVERED", "no held result")
    if configs != 5:
        raise CheckFailure("CONFIG_COUNT", f"actual={configs} expected=5")
    if model.flush_count != 4:
        raise CheckFailure("FLUSH_COUNT", f"actual={model.flush_count} expected=4")
    if model.maximum_enabled_run < 1025:
        raise CheckFailure("WRAP_NOT_COVERED", str(model.maximum_enabled_run))
    if frame_count < expected_vectors:
        raise CheckFailure("FRAME_COUNT_LOW", str(frame_count))
    if pixel_samples == 0:
        raise CheckFailure("PIXEL_OBSERVATION_MISSING", "0")
    if i2s_summary is None:
        raise CheckFailure("I2S_SUMMARY_MISSING", "0")
    if i2s_summary["bclk_rises"] < frame_count * 64:
        raise CheckFailure("I2S_BCLK_COUNT_LOW", str(i2s_summary))
    if i2s_summary["lrck_edges"] < frame_count * 2 - 2:
        raise CheckFailure("I2S_LRCK_COUNT_LOW", str(i2s_summary))
    if i2s_summary["observation_drops"] != 0:
        raise CheckFailure("OBSERVER_DROP", str(i2s_summary["observation_drops"]))
    if i2s_summary["clip_count"] != clip_commits:
        raise CheckFailure("CLIP_COUNTER_MISMATCH", str(i2s_summary))
    (
        _end_tag, _end_sim, end_accepted, end_commits, end_frames,
        end_underruns, end_clips, end_drops, _line,
    ) = end
    if int(end_accepted) != len(expected):
        raise CheckFailure("END_ACCEPT_COUNT", end_accepted)
    if int(end_commits) != len(commits):
        raise CheckFailure("END_COMMIT_COUNT", end_commits)
    if int(end_frames) != frame_count:
        raise CheckFailure("END_FRAME_COUNT", end_frames)
    if int(end_underruns) != underruns:
        raise CheckFailure("END_UNDERRUN_COUNT", f"dut={end_underruns} ref={underruns}")
    if len(unaccepted_requests) != underruns:
        raise CheckFailure(
            "UNACCEPTED_REQUEST_UNDERRUN_COUNT",
            f"unaccepted={len(unaccepted_requests)} underruns={underruns}",
        )
    if int(end_clips) != clip_commits or int(end_drops) != 0:
        raise CheckFailure("END_CLIP_OR_DROP", f"clip={end_clips} drops={end_drops}")

    return {
        "status": "PASS",
        "requests": len(expected),
        "request_indications": len(requested),
        "unaccepted_requests_after_source_exhaustion": len(unaccepted_requests),
        "first_valids": len(first_valid),
        "results": result_handshakes,
        "commits": len(commits),
        "cancels": len(canceled),
        "hold_request_ids": [f"{value:08x}" for value in sorted(hold_values)],
        "hold_edges": sum(hold_counts.values()),
        "configs": configs,
        "history_flushes": model.flush_count,
        "maximum_enabled_samples_after_flush": model.maximum_enabled_run,
        "wrap_depth": 1024,
        "frames": frame_count,
        "underrun_or_repeat_frames": underruns,
        "pixel_samples": pixel_samples,
        "clip_commits": clip_commits,
        "i2s": i2s_summary,
        "source_scope": {
            "reset_lifetimes": sorted(source_lifetimes),
            "source_ids": len(source_ids),
            "unequal_stereo": 0,
            "nonzero_clip": 0,
        },
        "limitations": [
            "C_FULL real publications have equal left/right PCM and clipped=0.",
            "Observer pins carry sequence and PCM, not request ID or clipped; those use the commit ledger.",
            "This is isolated functional replay, not production realtime N32, STA, or hardware audio proof.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--vectors", type=int, default=1300)
    args = parser.parse_args()
    try:
        receipt = check(args.trace, args.vectors)
    except CheckFailure as exc:
        failure = {"status": "FAIL", "diagnostic": exc.code, "detail": exc.detail}
        args.receipt.write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(failure, indent=2))
        return 2
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
