"""Software-only checks for the precise FULL thirty-third-note mutation."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT/"code/software/t061_n32_stress_plan_candidate_20261013"))
from full_steal_successor import FIELDS, mutate_full_steal, steal_index, swap_descriptors
from generate_v6 import build_v6_operations


class StealSuccessorTests(unittest.TestCase):
    def test_actual_thirty_third_not_first_allocation(self):
        operations = build_v6_operations("FULL")
        target = steal_index(operations)
        self.assertEqual(target, 67)
        self.assertEqual(operations[target]["note"], 100)
        self.assertEqual(operations[target]["source"], 3)

    def test_swap_all_fields_preserves_other_slots(self):
        row = ["U", "10", "0", "0"] + ["0"]*8
        for field, width in FIELDS:
            mask = (1 << width)-1
            a, b, c = 1 & mask, 2 & mask, 3 & mask
            row[field] = "%x" % (a | (b << width) | (c << (2*width)))
        output = swap_descriptors(" ".join(row)+"\n").split()
        for field, width in FIELDS:
            before, after, mask = int(row[field], 16), int(output[field], 16), (1 << width)-1
            self.assertEqual(after & mask, (before >> width) & mask)
            self.assertEqual((after >> width) & mask, before & mask)
            self.assertEqual(after >> (2*width), before >> (2*width))

    def test_only_route_inside_target_operation_is_mutated(self):
        operations = build_v6_operations("FULL")
        target = steal_index(operations)
        route = "U 10 0 0 3 0 801 100000002 2400 1 2 100000002\n"
        lines = [route, "OP 10 %d BEGIN note_on\n" % target,
                 route, "OP 11 %d END\n" % target]
        changed, metadata = mutate_full_steal(lines, operations)
        self.assertEqual(metadata["route_line_index"], 2)
        self.assertEqual(changed[0], route)
        self.assertNotEqual(changed[2], route)

    def test_missing_target_route_cannot_use_earlier_route(self):
        operations = build_v6_operations("FULL")
        target = steal_index(operations)
        lines = ["U 9 0 0 3 0 801 100000002 2400 1 2 100000002\n",
                 "OP 10 %d BEGIN note_on\n" % target, "OP 11 %d END\n" % target]
        with self.assertRaisesRegex(ValueError, "C_FULL_STEAL_OBSERVATION_REQUIRED"):
            mutate_full_steal(lines, operations)


if __name__ == "__main__":
    unittest.main()
