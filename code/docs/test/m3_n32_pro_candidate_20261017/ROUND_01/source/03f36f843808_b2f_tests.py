"""N8 successor strict-clock/control negatives, complete logs and END retained."""
import argparse
import hashlib
import json
from pathlib import Path
import unittest

from b2_clock import backend_calendar
from b2c_check import Oracle
from b2d_tests import damaged_capture
from b2f_check import check


class N8IdentityTests(unittest.TestCase):
    def test_controls_are_identity_not_slot(self):
        oracle = Oracle(1, 8, identity_controls=True)
        oracle.reset(0)
        oracle.controls[15, 15] = (2047, 4080, 5)
        for i in (3, 7):
            oracle.router.slots[i].update(source=15, channel=15, occupied=i == 3)
        # Same expression as the pinned oracle, exercising the contract choice.
        words = [oracle.controls.get((s["source"], s["channel"]), (0, 0, 2))
                 for s in oracle.router.slots]
        self.assertEqual(words[3], words[7])
        self.assertEqual(words[7], (2047, 4080, 5))
        self.assertEqual(words[0], (0, 0, 2))

    def test_distinct_source_channel_pairs(self):
        controls = {(10, 2): (500, 1111, 7), (10, 3): (3000, 2222, 12),
                    (4, 2): (900, 0, 2)}
        self.assertEqual(len(set(controls.values())), 3)
        self.assertEqual(controls.get((15, 14), (0, 0, 2)), (0, 0, 2))

    def test_source_calendar_not_observed_range(self):
        for r in (1, 3, 64):
            clock = backend_calendar(100, 8, r)
            self.assertEqual(clock.lanes[-1], 115+r+(3+r)*7)
            self.assertEqual(clock.wrapper_first, 116+8*(r+3))

    def test_only_N8_successor_schema(self):
        for raw in (b"", b"B2C 16 1 0\n", b"B2C 8 32 0\n"):
            with self.assertRaisesRegex(ValueError, "HEADER"):
                check(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("normal", "slow", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(N8IdentityTests)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise ValueError("N8_IDENTITY_UNIT_FAILURE")
    normal, slow = args.normal.read_bytes(), args.slow.read_bytes()
    if not check(normal)["sample_deadline_qualified"] or not check(slow)["sample_deadline_qualified"]:
        raise ValueError("N8_EXPECTED_DEADLINE_CLASSIFICATION")
    specs = (
        ("advance_early", "A", 1, -1, None, "ADVANCE_EDGE_OR_MISSING"),
        ("advance_late", "A", 1, 1, None, "ADVANCE_EDGE_OR_MISSING"),
        ("first_early", "F", 1, -1, None, "FIRST_VALID_CLOCK_OR_MISSING"),
        ("first_late", "F", 1, 1, None, "FIRST_VALID_CLOCK_OR_MISSING"),
        ("slot7_early", "L", 1, -1, 7, "LANE_CLOCK_OR_MISSING"),
        ("slot7_late", "L", 1, 1, 7, "LANE_CLOCK_OR_MISSING"),
        ("slot7_generation", "G", 2, 8, 7, "B1_FULL_TAG_CONTEXT_CONTROL_PEDAL"),
        ("slot7_to3_alias", "G", 2, 4, 7, "B1_FULL_TAG_CONTEXT_CONTROL_PEDAL"),
        ("occupied_bit7", "C", 3, 1 << 7, None, "BACKEND_FULL_SNAPSHOT"),
        ("publish_pcm", "P", 3, 1, None, "OUTPUT_BACKPRESSURE_STABILITY"),
        ("bank_context", "Y", 3, 1, None, "BANK_COMMIT_READBACK"),
    )
    reports = []
    for name, tag, field, delta, slot, reason in specs:
        raw = damaged_capture(normal, tag, field, delta, slot=slot)
        (args.output/(name+".txt")).write_bytes(raw)
        try:
            check(raw)
        except ValueError as error:
            if str(error) != reason:
                raise ValueError(f"WRONG_REJECTION:{name}:{error}") from error
            reports.append(dict(name=name, expected=reason, actual=str(error),
                                sha256=hashlib.sha256(raw).hexdigest()))
        else:
            raise ValueError("MUTANT_ACCEPTED:"+name)
    result = dict(exit_code=0, unit_tests=suite.countTestCases(), complete_N8_negatives=reports,
                  normal_sha256=hashlib.sha256(normal).hexdigest(),
                  slow_sha256=hashlib.sha256(slow).hexdigest())
    (args.output/"report.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
