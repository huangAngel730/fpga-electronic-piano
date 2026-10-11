"""Synthetic contract tests only, not additional RTL/capture coverage."""
from copy import deepcopy
import unittest

from closure_audit import scan
from strict_capture import CaptureError


def row(tag, cycle, *values):
    return dict(tag=tag, cycle=cycle, epoch=1, values=list(values))


class ClosureTests(unittest.TestCase):
    def test_edge_63_64(self):
        rows = [row("K", 100, 1), row("P", 162, 1, 0), row("E", 163, 1),
                row("P", 163, 2, 0), row("E", 164, 2)]
        self.assertEqual(scan(rows)["edge_event_cycles"], [163])

    def test_same_edge_uses_previous_frame(self):
        rows = [row("K", 100, 1), row("P", 200, 1, 0),
                row("E", 300, 1), row("K", 300, 2)]
        self.assertEqual(scan(rows)["edge_events"], 0)

    def test_wrong_observer_order_rejected(self):
        with self.assertRaisesRegex(CaptureError, "CLOSURE_E_K_OBSERVER_ORDER"):
            scan([row("P", 1, 7, 0), row("K", 2, 1), row("E", 2, 7)])

    def test_reset_counters_cumulative_queue_dropped(self):
        result = scan([row("P", 1, 5, 0), row("E", 2, 5), row("P", 3, 6, 0),
                       row("R", 4, 2), row("P", 5, 7, 0), row("E", 6, 7)])
        self.assertEqual(result["edge_events"], 2)
        self.assertEqual(result["reset_discarded_entries"], 1)

    def test_full_atomic_pop_push(self):
        rows = [row("P", c + 1, c, 0) for c in range(32)]
        rows += [row("P", 40, 99, 1), row("E", 40, 0)]
        result = scan(rows)
        self.assertEqual(result["full_pop_push"], 1)
        self.assertEqual(result["remaining_fifo_entries"], 32)

    def test_becoming_full_not_full_before_edge(self):
        rows = [row("P", c + 1, c, 0) for c in range(31)]
        rows += [row("P", 40, 99, 0)]
        self.assertEqual(scan(rows)["full_pop_push"], 0)

    def test_empty_push_pop_no_bypass(self):
        with self.assertRaisesRegex(CaptureError, "CLOSURE_FIFO_EMPTY_POP"):
            scan([row("P", 1, 7, 0), row("E", 1, 7)])

    def test_overflow(self):
        with self.assertRaisesRegex(CaptureError, "CLOSURE_FIFO_OVERFLOW"):
            scan([row("P", c + 1, c, 0) for c in range(33)])

    def test_payload_and_multiple(self):
        for rows, diagnostic in (
            ([row("P", 1, 4, 0), row("E", 2, 5)], "CLOSURE_FIFO_PAYLOAD_ORDER"),
            ([row("P", 1, 4, 0), row("P", 1, 5, 1)], "CLOSURE_FIFO_MULTIPLE_HANDSHAKES"),
        ):
            with self.subTest(diagnostic=diagnostic):
                with self.assertRaisesRegex(CaptureError, diagnostic):
                    scan(rows)

    def test_reset_is_not_retirement_evidence(self):
        result = scan([row("R", 1, 1)])
        self.assertNotIn("retirements", result)
        self.assertEqual(result["accepted_panic_events"], [])

    def test_overlap_screen_boundary(self):
        for delta, count in ((20, 1), (21, 0)):
            result = scan([row("Q", 10, 1), row("K", 10 + delta, 2)])
            self.assertEqual(len(result["observed_q_math_frame_overlaps"]), count)

    def test_fixture_observed_never_expected_and_no_input_mutation(self):
        rows = [row("T", 1, "sample_edge"), row("M", 2, 1, 0, 0, 1),
                row("T", 3, "accepted_only"), row("M", 4, 2, 0, 0, 0)]
        before = deepcopy(rows)
        result = scan(rows)
        self.assertEqual(rows, before)
        self.assertEqual(len(result["fixture_transition_commits"]), 1)
        self.assertIsNone(result["fixture_transition_commits"][0]["independently_expected_flag"])


if __name__ == "__main__":
    unittest.main()
