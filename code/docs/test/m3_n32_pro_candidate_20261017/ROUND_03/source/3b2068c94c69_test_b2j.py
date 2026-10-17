"""Small source-calendar tests, not synthetic replacement for real captures."""
import unittest

from b2j_check import Completion, check


def row(c, **kwargs):
    result = dict(cycle=c, rst=1, cancel=0, sv=0, sr=0, rv=0, rr=0,
                  idle=0, inject=0, read=0, publish=0, launch=0,
                  sid=7, rid=7, left=17, right=17, er=0)
    result.update(kwargs)
    return result


def to_hold():
    m = Completion(4, 1)
    m.edge(row(1, idle=1, sr=1, sv=1))
    # J1 -> C37 -> F69, from independent source calendar.
    for c in range(2, 69):
        m.edge(row(c, launch=int(c == 37)))
    m.edge(row(69, rv=1))
    return m


class CompletionTests(unittest.TestCase):
    def test_publish_three_observer_edges(self):
        m = to_hold()
        m.edge(row(70, rv=1, rr=1, publish=1))
        m.edge(row(71))
        m.edge(row(72))
        m.edge(row(73, idle=1, sr=1))
        self.assertEqual(m.events[-1]["delay"], 3)

    def test_hold_cancel_four_observer_edges(self):
        m = to_hold()
        m.edge(row(70, rv=1, cancel=1))
        for c in (71, 72, 73):
            m.edge(row(c))
        m.edge(row(74, idle=1, sr=1))
        self.assertEqual(m.events[-1]["delay"], 4)

    def test_repeat_cancel_does_not_rollback(self):
        m = to_hold()
        m.edge(row(70, rv=1, cancel=1))
        m.edge(row(71, cancel=1))
        m.edge(row(72, cancel=1))
        for c in (73, 74, 75):
            m.edge(row(c))
        m.edge(row(76, idle=1, sr=1))
        self.assertEqual(m.events[-1]["termination"], 72)
        self.assertEqual(m.events[-1]["delay"], 4)

    def test_rejected_injection_delays_fence(self):
        m = to_hold()
        m.edge(row(70, rv=1, rr=1, publish=1, inject=1))
        for c in (71, 72, 73):
            m.edge(row(c, inject=1))
        m.edge(row(74))
        m.edge(row(75))
        m.edge(row(76, idle=1, sr=1))
        self.assertEqual(m.events[-1]["delay"], 6)

    def test_early_ready_rejected(self):
        m = to_hold()
        m.edge(row(70, rv=1, rr=1, publish=1))
        m.edge(row(71))
        with self.assertRaisesRegex(ValueError, "COMPLETION_SR"):
            m.edge(row(72, sr=1))

    def test_read_blocks_sample_not_idle(self):
        m = Completion(32, 8)
        m.edge(row(1, idle=1, read=1))
        self.assertEqual(m.counts["read_block_edges"], 1)
        with self.assertRaisesRegex(ValueError, "COMPLETION_SR"):
            m.edge(row(2, idle=1, read=1, sr=1))

    def test_reset_hold_and_drain(self):
        for drain in (False, True):
            m = to_hold()
            if drain:
                m.edge(row(70, rv=1, rr=1, publish=1))
            m.edge(row(71, rst=0, idle=1))
            m.edge(row(72, idle=1, sr=1))
            self.assertEqual(m.counts["reset_active"], 1)

    def test_held_data_not_math_expectation(self):
        m = to_hold()
        with self.assertRaisesRegex(ValueError, "HELD_RESULT_CHANGED"):
            m.edge(row(70, rv=1, left=18))

    def test_boolean_parameter_rejected(self):
        with self.assertRaisesRegex(ValueError, "CLOCK_PARAMETERS"):
            Completion(True, 1)

    def test_strict_incomplete_and_unknown_records(self):
        for raw, diagnostic in ((b"", "EMPTY_CAPTURE"), (b"B2J 32 1\nWHAT\n", "TRACE_SCHEMA"),
                                (b"B2J 32 1\nEND 0\nEXTRA\n", "AFTER_END"),
                                (b"B2J 32 1\nEND 1\n", "END_COUNT")):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(ValueError, diagnostic):
                    check(raw)


if __name__ == "__main__":
    unittest.main()
