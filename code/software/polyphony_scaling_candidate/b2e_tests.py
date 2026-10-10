"""Complete N32 high-slot/time counterexamples with unchanged END counts."""
import argparse
import hashlib
import json
from pathlib import Path
import unittest

from b2_clock import backend_calendar, deadline_missed
from b2e_check import check
from b2c_router_model import Router, packed


class N32Tests(unittest.TestCase):
    def test_slot31_and_mask_width(self):
        model = Router(32)
        model.slots[31].update(occupied=True, source=15, channel=15,
                               generation=0xffffffff, note=95)
        self.assertEqual(model.snapshot()[0], 1 << 31)
        self.assertEqual(model.snapshot()[3] >> (31*32), 0xffffffff)
        self.assertEqual(packed([0]*31+[15], 4), 15 << 124)

    def test_tag77_distinguishes_slot15_from31(self):
        prefix = (0xffffffff << 45) | (15 << 41) | (15 << 37) | (0xffffffff << 5)
        self.assertEqual((prefix | 31).bit_length(), 77)
        self.assertNotEqual(prefix | 15, prefix | 31)
        self.assertEqual((prefix | 31) & 31, 31)

    def test_calendar_all32_lanes(self):
        for response in (1, 8, 16, 32):
            clock = backend_calendar(100, 32, response)
            self.assertEqual(len(clock.lanes), 32)
            self.assertEqual(clock.advance, 108)
            self.assertEqual(clock.lanes[0], 115+response)
            self.assertEqual(clock.lanes[31], 115+response+(3+response)*31)
            self.assertEqual(clock.wrapper_first, 116+32*(response+3))

    def test_833_first_not_handshake(self):
        self.assertEqual(deadline_missed(833, 0), 0)
        self.assertEqual(deadline_missed(834, 0), 1)
        self.assertEqual(deadline_missed(835, 0), 1)

    def test_strict_N_and_short_schema(self):
        for n in (True, 32.0, 0, 31, 33):
            with self.assertRaises(ValueError):
                Router(n)
        for raw in (b"", b"B2C 16 1 0\n", b"B2C 32 1 1\n", b"B2C 32 3 0\n"):
            with self.assertRaisesRegex(ValueError, "N32_SHORT_HEADER"):
                check(raw)


def damage(raw, tag, field, change, *, slot=None):
    lines = raw.decode("ascii").splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith(tag+" ")
                 and (slot is None or (int(line.split()[3]) == slot if tag == "L"
                                      else int(line.split()[2], 16) & 31 == slot)))
    row = lines[index].split()
    hexadecimal = (tag, field) in (("G", 2), ("U", 9), ("C", 3), ("Y", 3))
    value = int(row[field], 16 if hexadecimal else 10)
    row[field] = format(value ^ change, "x") if hexadecimal else str(value+change)
    lines[index] = " ".join(row)
    if field == 1:
        body = [x for x in lines[1:] if "$finish called" not in x]
        body.sort(key=lambda x: int(x.split()[1]))
        lines = lines[:1]+body+[x for x in lines[1:] if "$finish called" in x]
    return ("\n".join(lines)+"\n").encode("ascii")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("normal", "slow", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(N32Tests)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise ValueError("N32_UNIT_FAILURE")
    normal, slow = args.normal.read_bytes(), args.slow.read_bytes()
    if not check(normal)["sample_deadline_qualified"] or check(slow)["sample_deadline_qualified"]:
        raise ValueError("DEADLINE_BOUNDARY_NOT_EXERCISED")
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
        ("bank_context", "Y", 3, 1, None, "BANK_COMMIT_READBACK"),
        ("late_flag_false", "F", 5, -1, None, "PCM_OR_DEADLINE"),
    )
    reports = []
    for name, tag, field, delta, slot, reason in specs:
        raw = damage(slow if name == "late_flag_false" else normal,
                     tag, field, delta, slot=slot)
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
    result = dict(exit_code=0, unit_tests=suite.countTestCases(),
                  complete_N32_negatives=reports,
                  normal_sha256=hashlib.sha256(normal).hexdigest(),
                  slow_sha256=hashlib.sha256(slow).hexdigest())
    (args.output/"report.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
