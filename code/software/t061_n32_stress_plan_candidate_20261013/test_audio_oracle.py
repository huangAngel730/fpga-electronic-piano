"""Focused tests for the independent N32-C frozen-math oracle."""

from __future__ import annotations

import hashlib
import json
import unittest

from audio_oracle import FrozenAudioOracle, replay_operations
from generate_plan import build_operations
from n32c_common import ContractError


def note_on(note: int = 60) -> dict:
    return {
        "op": "note_on", "source": 1, "channel": 2, "note": note,
        "velocity": 900, "expression": 800,
    }


def note_off(note: int = 60) -> dict:
    return {"op": "note_off", "source": 1, "channel": 2, "note": note}


class FrozenAudioOracleTests(unittest.TestCase):
    def test_pcm_is_deterministic_and_not_capture_derived(self):
        def run_once():
            oracle = FrozenAudioOracle()
            oracle.event(note_on())
            return [oracle.sample(0x40 + index) for index in range(8)]

        first = run_once()
        second = run_once()
        self.assertEqual(first, second)
        payload = json.dumps([
            [row.result_id, row.left_pcm, row.right_pcm, row.clipped,
             list(row.lane_pcm)] for row in first
        ], separators=(",", ":")).encode("ascii")
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(),
            "cc924f071298082613f66aea009c62a06dbbd37ec1690cd375434fad32c35fab",
        )
        self.assertTrue(any(row.left_pcm for row in first))
        self.assertTrue(all(row.left_pcm == row.right_pcm for row in first))

    def test_release_requires_real_sample_advances(self):
        oracle = FrozenAudioOracle()
        oracle.event(note_on())
        oracle.sample(1)
        oracle.event(note_off())
        with self.assertRaisesRegex(
                ContractError, "RELEASE_AWAIT_WITHOUT_ENOUGH_SAMPLE_TICKS"):
            oracle.await_release_done(0)
        for index in range(4800):
            oracle.sample(0x1000 + index)
        oracle.await_release_done(0)
        self.assertEqual(oracle.sample_advances, 4801)
        self.assertFalse(oracle.router.slots[0]["occupied"])

    def test_current_plan_exposes_release_tick_gap(self):
        operations = build_operations()
        await_index = next(index for index, operation in enumerate(operations)
                           if operation["op"] == "await_release_done")
        with self.assertRaisesRegex(
                ContractError, "RELEASE_AWAIT_WITHOUT_ENOUGH_SAMPLE_TICKS"):
            replay_operations(operations[:await_index + 1])
        pedal_up = max(
            index for index, operation in enumerate(operations[:await_index])
            if operation["op"] == "cc64" and not operation["down"])
        post_release_samples = sum(
            operation["op"] == "sample"
            for operation in operations[pedal_up + 1:await_index]
        )
        self.assertEqual(post_release_samples, 1)

    def test_read_context_comes_from_last_published_frame(self):
        oracle = FrozenAudioOracle()
        oracle.event(note_on(64))
        result = oracle.sample(0x55)
        self.assertEqual(oracle.read_context(0), result.contexts[0])
        oracle.sample(0x56, publish=False)
        self.assertEqual(oracle.read_context(0), result.contexts[0])


if __name__ == "__main__":
    unittest.main()
