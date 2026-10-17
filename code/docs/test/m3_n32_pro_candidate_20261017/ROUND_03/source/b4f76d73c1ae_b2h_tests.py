"""Complete N32 long-capture negatives fail at early semantic/time boundaries."""
import argparse
import hashlib
import json
from pathlib import Path
import unittest

from b2_clock import backend_calendar
from b2h_check import check
from b2c_router_model import Router, packed
from b2e_tests import damage


class LongN32Tests(unittest.TestCase):
    def test_long_schema_only(self):
        for raw in (b"", b"B2C 32 1 0\n", b"B2C 16 1 1\n", b"B2C 32 8 1\n"):
            with self.assertRaisesRegex(ValueError, "N32_LONG_HEADER"):
                check(raw)

    def test_slot31_independent_generation(self):
        r = Router(32)
        r.slots[31].update(occupied=True, releasing=True, source=15, channel=15,
                           generation=0xffffffff, note=95)
        self.assertEqual(r.snapshot()[0], 1 << 31)
        self.assertEqual(r.snapshot()[3] >> (31*32), 0xffffffff)
        self.assertEqual(packed([0]*31+[15], 4), 15 << 124)

    def test_tag77_high_slot(self):
        prefix = 0xffffffff << 45 | 15 << 41 | 15 << 37 | 0xffffffff << 5
        self.assertEqual((prefix | 31).bit_length(), 77)
        self.assertNotEqual(prefix | 31, prefix | 15)

    def test_exact_backend_clock(self):
        clock = backend_calendar(100, 32, 1)
        self.assertEqual(clock.advance, 108)
        self.assertEqual(len(clock.lanes), 32)
        self.assertEqual(clock.lanes[-1], 240)
        self.assertEqual(clock.wrapper_first, 244)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit-only", action="store_true")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LongN32Tests)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise ValueError("N32_LONG_UNIT_FAILURE")
    if args.unit_only:
        return
    args.output.mkdir(exist_ok=False)
    raw = args.input.read_bytes()
    # Positive long replay is a preceding qualified command; don't replay the
    # whole expensive normal case again merely to generate early counterexamples.
    specs = (
        ("advance_early", "A", 1, -1, None, "ADVANCE_EDGE_OR_MISSING"),
        ("advance_late", "A", 1, 1, None, "ADVANCE_EDGE_OR_MISSING"),
        ("first_early", "F", 1, -1, None, "FIRST_VALID_CLOCK_OR_MISSING"),
        ("first_late", "F", 1, 1, None, "FIRST_VALID_CLOCK_OR_MISSING"),
        ("slot31_early", "L", 1, -1, 31, "LANE_CLOCK_OR_MISSING"),
        ("slot31_late", "L", 1, 1, 31, "LANE_CLOCK_OR_MISSING"),
        ("slot31_generation", "G", 2, 32, 31, "B1_FULL_TAG_CONTEXT_CONTROL_PEDAL"),
        ("slot31_to15_alias", "G", 2, 16, 31, "B1_FULL_TAG_CONTEXT_CONTROL_PEDAL"),
        ("occupied_bit31", "C", 3, 1 << 31, None, "BACKEND_FULL_SNAPSHOT"),
        ("publish_pcm", "P", 3, 1, None, "OUTPUT_BACKPRESSURE_STABILITY"),
    )
    reports = []
    for name, tag, field, delta, slot, reason in specs:
        changed = damage(raw, tag, field, delta, slot=slot)
        (args.output/(name+".txt")).write_bytes(changed)
        try:
            check(changed)
        except ValueError as error:
            if str(error) != reason:
                raise ValueError(f"WRONG_REJECTION:{name}:{error}") from error
            reports.append(dict(name=name, expected=reason, actual=str(error),
                                sha256=hashlib.sha256(changed).hexdigest()))
        else:
            raise ValueError("COUNTEREXAMPLE_ACCEPTED:"+name)
    result = dict(exit_code=0, unit_tests=suite.countTestCases(), complete_long_negatives=reports,
                  normal_sha256=hashlib.sha256(raw).hexdigest())
    (args.output/"report.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
