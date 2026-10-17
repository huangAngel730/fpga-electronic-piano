"""Small analytic source-clock tests; real captures are checked by the runner."""
import unittest

from b2k_check import Cancellation, FIELDS, check, plan


def row(c, **changes):
    result = dict.fromkeys(FIELDS, 0)
    result.update(cycle=c, rst=1, sid=0, rid=0, fcw=0)
    result.update(changes)
    return result


def front(stop, ready):
    model = Cancellation(4, 1)
    model.edge(row(1, idle=1, sr=1, sv=1))
    for c in range(2, ready):
        model.edge(row(c, cancel=int(c == stop)))
    return model


class CancelTests(unittest.TestCase):
    def test_cancel_suppresses_control_request_same_edge(self):
        model = front(10, 12)
        model.edge(row(12, idle=1, sr=1))
        self.assertEqual(model.events[-1]["ready"], 12)

    def test_control_pending_delays_reuse(self):
        model = front(11, 17)
        model.edge(row(17, idle=1, sr=1))
        self.assertEqual(model.events[-1]["ready"], 17)

    def test_control_pending_early_ready_rejected(self):
        model = front(11, 16)
        with self.assertRaisesRegex(ValueError, "CANCEL_SR"):
            model.edge(row(16, sr=1))

    def test_first_offer_suppressed_has_no_owned_tag(self):
        model = front(27, 29)
        model.edge(row(29, idle=1, sr=1))

    def test_first_offer_accepted_requires_scheduler_drain(self):
        model = front(28, 31)
        model.edge(row(31, idle=1, sr=1))

    def test_pitch_valid_and_counter_retire_before_admission(self):
        model = Cancellation(4, 1)
        model.active = True  # occupied-note precondition, unlike silent unit cases
        model.edge(row(1, idle=1, sr=1, sv=1))
        for c in range(2, 48):
            model.edge(row(c, launch=int(c == 37), cancel=int(c == 38)))
        model.edge(row(48, idle=1, sr=1))
        self.assertEqual(model.events[-1]["ready"], 48)

    def test_reset_discards_pending_work(self):
        model = front(11, 16)
        model.edge(row(16, rst=0, idle=1))
        model.edge(row(17, idle=1, sr=1))
        self.assertEqual(model.phase, 0)

    def test_plan_includes_every_boundary_and_reset(self):
        cases = plan(32, 64)
        self.assertEqual(len(cases), 21)
        self.assertEqual(sum(reset for _, reset, _ in cases), 4)
        self.assertIn((219, 0, 3), cases)

    def test_strict_parameter_types(self):
        for n, response in ((True, 1), (32, True), (3, 1), (32, 65)):
            with self.assertRaisesRegex(ValueError, "CLOCK_PARAMETERS"):
                Cancellation(n, response)

    def test_incomplete_and_unknown_records_rejected(self):
        for raw in (b"", b"B2K 32 1\nEND 0\n", b"B2K 32 1\nWHAT\n",
                    b"B2K 32 1\nEND 0\nEXTRA\n"):
            with self.assertRaises(ValueError):
                check(raw)


if __name__ == "__main__":
    unittest.main()
