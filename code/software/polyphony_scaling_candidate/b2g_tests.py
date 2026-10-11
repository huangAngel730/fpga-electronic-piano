"""Full normal captures damaged at exact math/time boundaries, unchanged END."""
import argparse
import hashlib
import json
from pathlib import Path
import unittest

from b2_check import mix_signed24
from b2_clock import backend_calendar
from b2g_check import check
from b2g_run import substitute_once


class SaturationTests(unittest.TestCase):
    def test_inclusive_limits(self):
        for total in (8388606, 8388607, -8388607, -8388608):
            self.assertEqual(mix_signed24([total]+[0]*31), (total, False))
        self.assertEqual(mix_signed24([8388607, 1]+[0]*30), (8388607, True))
        self.assertEqual(mix_signed24([-8388608, -1]+[0]*30), (-8388608, True))

    def test_full_signed_sum_no_intermediate_saturation(self):
        self.assertEqual(mix_signed24([8388607]*16+[-8388608]*16), (-16, False))
        self.assertEqual(mix_signed24([8388607]*32), (8388607, True))
        self.assertEqual(mix_signed24([-8388608]*32), (-8388608, True))

    def test_strict_profile_and_substitution(self):
        for raw in (b"", b"B2 16 1 0\n", b"B2 32 1 1\n", b"B2 32 32 0\n"):
            with self.assertRaisesRegex(ValueError, "N32_SATURATION_HEADER"):
                check(raw)
        for data in (b"", b"aa"):
            with self.assertRaisesRegex(ValueError, "PRECISE_SUBSTITUTION_COUNT"):
                substitute_once(data, b"a", b"b")

    def test_source_calendar(self):
        for response in (1, 8):
            clock = backend_calendar(7, 32, response)
            self.assertEqual(clock.advance, 15)
            self.assertEqual(len(clock.lanes), 32)
            self.assertEqual(clock.lanes[31], 22+response+31*(response+3))
            self.assertEqual(clock.backend_first, 21+32*(response+3))


def mutate(raw, tag, field, delta, *, sign=None, slot=None):
    lines = raw.decode("ascii").splitlines()
    for index, line in enumerate(lines):
        row = line.split()
        if row[0] != tag:
            continue
        if slot is not None and int(row[3]) != slot:
            continue
        if sign is not None and int(row[3]) != (8388607 if sign == 1 else -8388608):
            continue
        base = 16 if (tag, field) in (("O", 7), ("O", 10)) else 10
        value = int(row[field], base)+delta
        row[field] = format(value, "x") if base == 16 else str(value)
        lines[index] = " ".join(row)
        break
    else:
        raise ValueError("COUNTEREXAMPLE_TARGET_MISSING")
    if field == 1:
        body = [x for x in lines[1:] if "$finish called" not in x]
        body.sort(key=lambda x: int(x.split()[1]))
        lines = lines[:1]+body+[x for x in lines[1:] if "$finish called" in x]
    return ("\n".join(lines)+"\n").encode("ascii")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SaturationTests)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise ValueError("SATURATION_UNIT_FAILURE")
    raw = args.input.read_bytes()
    check(raw)
    specs = (
        ("positive_limit_minus_one", "O", 3, -1, 1, None, "MATH_STEREO_SATURATION"),
        ("negative_limit_plus_one", "O", 4, 1, -1, None, "MATH_STEREO_SATURATION"),
        ("positive_clip_flag_clear", "O", 5, -1, 1, None, "MATH_STEREO_SATURATION"),
        ("negative_clip_flag_clear", "O", 5, -1, -1, None, "MATH_STEREO_SATURATION"),
        ("advance_early", "A", 1, -1, None, None, "ADVANCE_CLOCK"),
        ("advance_late", "A", 1, 1, None, None, "ADVANCE_CLOCK"),
        ("slot31_early", "L", 1, -1, None, 31, "LANE_CLOCK"),
        ("slot31_late", "L", 1, 1, None, 31, "LANE_CLOCK"),
        ("output_early", "O", 1, -1, None, None, "OUTPUT_HANDSHAKE_CLOCK_FIXTURE"),
        ("output_late", "O", 1, 1, None, None, "OUTPUT_HANDSHAKE_CLOCK_FIXTURE"),
        ("drop_completed_bit31", "O", 7, -(1 << 31), None, None, "COMPLETED_MASK"),
        ("high_generation_corrupt", "O", 10, -(1 << (31*32)), None, None, "FULL_SNAPSHOT_IDENTITY"),
    )
    reports = []
    for name, tag, field, delta, sign, slot, reason in specs:
        changed = mutate(raw, tag, field, delta, sign=sign, slot=slot)
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
    result = dict(exit_code=0, unit_tests=suite.countTestCases(), complete_negatives=reports,
                  normal_sha256=hashlib.sha256(raw).hexdigest())
    (args.output/"report.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
