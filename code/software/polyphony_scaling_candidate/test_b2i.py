"""Software-only source ledger tests; no tool/device operation."""
import copy
import unittest

from b2_clock import backend_calendar
from b2i_audit import (FIELDS, calendar, integer, operators, render, roms,
                       source_path, storage)


class ActualHybridBudget(unittest.TestCase):
    def test_all_declarations_all_four_sizes(self):
        for n in (4, 8, 16, 32):
            for module in FIELDS:
                rows = storage(module, source_path(module).read_text(encoding="utf-8"), n)
                self.assertEqual({row["field"] for row in rows}, set(FIELDS[module].split()))
                self.assertTrue(all(row["declared_bits"] > 0 and row["line"] > 0 for row in rows))

    def test_new_unlisted_storage_rejected(self):
        text = source_path("b1_statebank").read_text(encoding="utf-8")
        text += "\nlogic [7:0] surprise; always_ff @(posedge clk) surprise<=0;\n"
        with self.assertRaisesRegex(ValueError, "STORAGE_COVERAGE.*surprise"):
            storage("b1_statebank", text, 8)

    def test_missing_or_width_mutation_visible(self):
        text = source_path("b1_statebank").read_text(encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "STORAGE_COVERAGE"):
            storage("b1_statebank", text.replace("reg [39:0] identities", "wire [39:0] identities"), 8)
        rows = storage("b1_statebank", text.replace("reg [39:0] identities", "reg [7:0] identities"), 8)
        self.assertEqual(next(row for row in rows if row["field"] == "identities")["declared_bits"], 64)

    def test_real_CW_and_complete_tags(self):
        for n in (4, 8, 16, 32):
            rows = {r["field"]: r for r in storage("b1_statebank", source_path("b1_statebank").read_text(encoding="utf-8"), n)}
            self.assertEqual(rows["context_a"]["declared_bits"] + rows["context_b"]["declared_bits"], 148*n)
            self.assertEqual(rows["controls"]["declared_bits"], 256*29)
            self.assertEqual(rows["pedals"]["declared_bits"], 256)
            sched = {r["field"]: r for r in storage("b1_scheduler", source_path("b1_scheduler").read_text(encoding="utf-8"), n)}
            self.assertEqual(sched["issued_tags"]["declared_bits"], (72+(n-1).bit_length())*n)

    def test_continuous_leaf_copies_not_one_working_set(self):
        for module in ("adsr_piano_envelope", "pitch_mod_fcw_pipeline"):
            text = source_path(module).read_text(encoding="utf-8")
            bits4 = sum(r["declared_bits"] for r in storage(module, text, 4))
            bits32 = sum(r["declared_bits"] for r in storage(module, text, 32))
            self.assertEqual(bits32, 8*bits4)

    def test_runtime_ROM_copies_not_initialization_scratch(self):
        for n in (4, 8, 16, 32):
            rows = roms(n)
            self.assertEqual(sum(r["logical_runtime_bits"] for r in rows), 16384+54248*n)
            self.assertEqual(len(rows), 5)
            self.assertTrue(all(r["mapped_blocks"] is None for r in rows))
            self.assertFalse(any(r["field"] == "sub_source" for r in rows))

    def test_all_256_source_calendars_and_II(self):
        for n in (4, 8, 16, 32):
            for r in range(1, 65):
                c = calendar(n, r)
                self.assertEqual(c["backend_accept_offset"], 12+6*n)
                self.assertEqual(c["wrapper_first_valid_offset"], 28+n*(r+9))
                be = backend_calendar(c["backend_accept_offset"], n, r)
                self.assertEqual(c["first_lane_offset"], be.lanes[0])
                self.assertTrue(all(b-a == r+3 for a, b in zip(be.lanes, be.lanes[1:])))
                self.assertEqual(c["age_excludes_admission_edge"], be.wrapper_first-1)

    def test_admission_age_boundary_and_output_backpressure_unknown(self):
        before, at = calendar(32, 1, 485), calendar(32, 1, 486)
        self.assertEqual(before["age_excludes_admission_edge"], 832)
        self.assertEqual(at["age_excludes_admission_edge"], 833)
        self.assertTrue(before["fixture_833_deadline_met"])
        self.assertFalse(at["fixture_833_deadline_met"])
        for key in ("output_handshake_offset", "return_to_idle_offset", "whole_engine_worst_case_bound"):
            self.assertIsNone(at[key])

    def test_invalid_types_ranges_rejected(self):
        for values in ((True, 1), (32, True), (32, 1.0), (32, 0), (32, 65), (3, 1), (32, 1, -1), (32, 1, True)):
            with self.assertRaises(ValueError):
                calendar(*values)

    def test_expression_evaluator_rejects_code_and_bad_types(self):
        self.assertEqual(integer("N*32-1", dict(N=32)), 1023)
        for expression in ("__import__('os')", "N/2", "True", "N**2", "M+1"):
            with self.assertRaises(ValueError):
                integer(expression, dict(N=32))

    def test_operators_are_source_sites_not_DSPs(self):
        rows = operators()
        self.assertEqual(len(rows), 9)
        self.assertEqual(sum(r["module"] == "pitch_mod_fcw_pipeline" for r in rows), 5)
        self.assertTrue(all(r["mapped_DSP_blocks"] is None for r in rows))

    def test_markdown_is_generated_from_same_object(self):
        item = dict(N=32, declared_sequential_payload_bits=1, runtime_ROM_bits=2,
                    multiply_expression_instances=257, R1_calendar=calendar(32, 1))
        obj = dict(configurations=[item], historical_reports=[])
        before = copy.deepcopy(obj)
        self.assertIn("| 32 | 1 | 2 | 257 | 348 | 347 |", render(obj))
        self.assertEqual(obj, before)


if __name__ == "__main__":
    unittest.main()
