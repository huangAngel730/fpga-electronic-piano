"""Synthetic routing contract assertions; no new RTL/hardware execution."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from router_model import Router, ClockOracle, fields


def word(kind=0, source=1, channel=0, note=60, velocity=256, control=0, value=0):
    return (kind << 61) | (source << 57) | (channel << 53) | (note << 46) | (velocity << 36) | (control << 18) | (value << 6)


def dispatch(router, event):
    """Caller drives one accepted event then literal quiet edges until idle."""
    router.edge(event)
    pulses = []
    for cycle in range(1, 40):
        if router.on or router.off:
            pulses.append((cycle, router.on, router.off))
        if not router.busy() and not (router.on | router.off):
            return pulses
        router.edge()
    raise AssertionError("synthetic router did not drain within 40 clocks")


class RouterTests(unittest.TestCase):
    def test_free_lane_order_and_full_lru_steal(self):
        r = Router()
        for i in range(4):
            self.assertEqual(dispatch(r, word(note=60+i)), [(4, 1 << i, 0)])
        self.assertEqual(dispatch(r, word(note=70)), [(4, 1, 0)])
        self.assertEqual([s["note"] for s in r.slots], [70, 61, 62, 63])
        self.assertEqual(sorted(s["age"] for s in r.slots), [0, 1, 2, 3])

    def test_retrigger_same_identity_preserves_lane_increments_generation(self):
        r = Router()
        dispatch(r, word())
        dispatch(r, word(note=61))
        self.assertEqual(dispatch(r, word(velocity=700)), [(4, 1, 0)])
        self.assertEqual((r.slots[0]["generation"], r.slots[0]["velocity"]), (2, 700))
        self.assertEqual(r.slots[0]["age"], 3)

    def test_old_identity_off_after_steal_is_ignored(self):
        r = Router()
        for n in range(60, 65):
            dispatch(r, word(note=n))
        self.assertEqual(dispatch(r, word(kind=1, note=60)), [])
        self.assertTrue(r.slots[0]["key"])
        self.assertFalse(any(s["releasing"] for s in r.slots))

    def test_velocity_zero_releases_with_exact_off_edge(self):
        r = Router()
        dispatch(r, word())
        self.assertEqual(dispatch(r, word(velocity=0)), [(6, 0, 1)])
        self.assertTrue(r.slots[0]["occupied"])
        self.assertTrue(r.slots[0]["releasing"])

    def test_source_and_channel_pedal_isolation_threshold(self):
        r = Router()
        for source, channel in ((1, 2), (9, 2), (1, 3)):
            dispatch(r, word(source=source, channel=channel))
        dispatch(r, word(kind=4, channel=2, control=6, value=2048))
        self.assertEqual(dispatch(r, word(kind=1, channel=2)), [])
        self.assertTrue(r.slots[0]["deferred"])
        self.assertEqual(dispatch(r, word(kind=1, source=9, channel=2)), [(7, 0, 2)])
        self.assertEqual(dispatch(r, word(kind=1, channel=3)), [(8, 0, 4)])
        dispatch(r, word(kind=4, source=9, channel=2, control=6, value=0))
        self.assertFalse(r.slots[0]["releasing"])
        self.assertEqual(dispatch(r, word(kind=4, channel=2, control=6, value=2047)), [(6, 0, 1)])

    def test_retrigger_clears_deferred_release_and_old_done(self):
        r = Router()
        dispatch(r, word())
        dispatch(r, word(kind=4, control=6, value=4095))
        dispatch(r, word(kind=1))
        dispatch(r, word())
        self.assertFalse(r.slots[0]["deferred"])
        self.assertEqual(r.slots[0]["generation"], 2)
        self.assertEqual(dispatch(r, word(kind=4, control=6, value=0)), [])
        r.retire[0] = 1  # stale completion from previous generation
        self.assertFalse(r.busy())
        r.edge(release_done=1)  # unreleasing slot cannot retire
        self.assertTrue(r.slots[0]["occupied"])

    def test_done_retirement_pre_nba_latency_and_retained_public_identity(self):
        r = Router()
        dispatch(r, word())
        dispatch(r, word(kind=1))
        identity = r.snapshot()[1:]
        r.edge(release_done=1)
        self.assertEqual(r.state, "IDLE")
        r.edge()
        self.assertEqual(r.state, "RETIRE")
        self.assertTrue(r.slots[0]["occupied"])
        r.edge()
        self.assertEqual(r.snapshot()[0], 0)
        self.assertEqual(r.snapshot()[1:], identity)
        self.assertEqual(dispatch(r, word(note=65)), [(4, 1, 0)])
        self.assertEqual(r.slots[0]["generation"], 2)

    def test_panic_releases_every_source_in_scan_order(self):
        r = Router()
        for source in (1, 9, 2, 7):
            dispatch(r, word(source=source))
        pulses = dispatch(r, word(kind=5))
        self.assertEqual([p[2] for p in pulses], [1, 2, 4, 8])
        self.assertEqual([p[0] for p in pulses], [6, 9, 12, 15])
        self.assertTrue(all(s["releasing"] for s in r.slots))

    def test_release_retrigger_reuses_lane(self):
        r = Router()
        dispatch(r, word())
        dispatch(r, word(kind=1))
        self.assertEqual(dispatch(r, word()), [(4, 1, 0)])
        self.assertFalse(r.slots[0]["releasing"])

    def test_generation_wrap_and_full_rank_after_many_events(self):
        r = Router()
        r.slots[0]["generation"] = 0xffffffff
        dispatch(r, word())
        self.assertEqual(r.slots[0]["generation"], 0)
        for n in range(1000):
            dispatch(r, word(note=40+n % 70))
            self.assertEqual(sorted(s["age"] for s in r.slots), [0, 1, 2, 3])

    def test_invalid_input_and_owner_backpressure(self):
        r = Router()
        for event in (True, -1, 1 << 64, 1.5):
            with self.assertRaisesRegex(ValueError, "ROUTER_EVENT_WORD"):
                r.edge(event)
        with self.assertRaisesRegex(ValueError, "ROUTER_ACCEPT_WHILE_BUSY"):
            r.edge(word(), owner=False)
        r.edge(word())
        with self.assertRaisesRegex(ValueError, "ROUTER_ACCEPT_WHILE_BUSY"):
            r.edge(word())
        with self.assertRaisesRegex(ValueError, "ROUTER_RELEASE_MASK"):
            Router().edge(release_done=True)

    def test_sparse_matches_every_literal_clock(self):
        fast, slow = ClockOracle([32767]*1024), ClockOracle([32767]*1024)
        stimuli = {1: dict(reset=True), 20: dict(event=word()), 100: dict(frame=True),
                   101: dict(request=1), 200: dict(event=word(kind=1)),
                   300: dict(frame=True), 301: dict(request=2), 400: dict(reset=True)}
        for c, entry in stimuli.items():
            epoch = 2 if c == 400 else 1
            fast.advance(c, epoch, **entry)
            while slow.cycle + 1 < c:
                slow.edge(slow.cycle+1, slow.epoch)
            slow.edge(c, epoch, **entry)
        self.assertEqual(fast.states, slow.states)
        self.assertEqual(fast.qs, slow.qs)
        self.assertEqual(fast.router.snapshot(), slow.router.snapshot())
        self.assertEqual([e.registers() for e in fast.env], [e.registers() for e in slow.env])

    def test_independent_envelope_drives_actual_release_retirement(self):
        m = ClockOracle([32767]*1024)
        m.advance(1, 1, reset=True)
        m.advance(20, 1, event=word())
        m.advance(100, 1, frame=True)
        m.advance(101, 1, request=1)
        m.advance(140, 1)
        self.assertGreater(m.env[0].level, 0)
        m.advance(150, 1, event=word(kind=1))
        for n in range(4800):
            if n == 4799:
                self.assertTrue(m.router.slots[0]["occupied"])
                self.assertEqual(m.env[0].state, 6)
            c = 200 + n*40
            m.advance(c, 1, frame=True)
            m.advance(c+1, 1, request=n+2)
        m.advance(192220, 1)
        self.assertEqual(m.env[0].state, 0)
        self.assertEqual(m.router.snapshot()[0], 0)
        self.assertEqual(m.router.counts["retirements"], 1)
        self.assertEqual(m.router.slots[0]["generation"], 1)

    def test_reset_cancels_pending_note_and_sample(self):
        m = ClockOracle([32767]*1024)
        m.advance(1, 1, reset=True)
        m.advance(20, 1, event=word())
        m.advance(21, 2, reset=True)
        m.advance(40, 2, frame=True)
        m.advance(41, 2, request=1)
        m.advance(55, 3, reset=True)
        m.advance(100, 3)
        self.assertFalse(m.ns)
        self.assertFalse(m.ticks)
        self.assertEqual(m.router.snapshot(), [0]*6)
        self.assertEqual(m.env[0].state, 0)

    def test_non_routing_control_has_no_slot_side_effect(self):
        r = Router()
        dispatch(r, word())
        before = deepcopy(r.slots)
        for kind in (2, 3, 6, 7):
            self.assertEqual(dispatch(r, word(kind=kind)), [])
        self.assertEqual(r.slots, before)
        self.assertEqual(fields(word(channel=15))["channel"], 15)

    def test_runner_exit_zero_after_elapsed_limit_still_fails(self):
        path = Path(__file__).resolve().parents[2] / "scripts/run_m3_audio_math_acceptance.py"
        spec = importlib.util.spec_from_file_location("audio_runner_for_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for total, step, elapsed in ((1800, 900, 901), (10, 900, 11)):
            with tempfile.TemporaryDirectory(prefix="m3_router_runner_test_") as folder:
                process = MagicMock()
                process.wait.return_value = 0
                with patch.object(module.time, "monotonic", side_effect=[0, 0, 0, elapsed]), patch.object(module.subprocess, "Popen", return_value=process):
                    runner = module.Run(Path(folder), total, step)
                    with self.assertRaisesRegex(RuntimeError, "COMMAND_FAIL:late:0"):
                        runner.command("late", ["synthetic-not-launched"])
                self.assertEqual(runner.steps[0]["exit_code"], 0)
                self.assertTrue(runner.steps[0]["elapsed_limit_exceeded"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
