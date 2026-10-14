"""New pure-software preparation guards; no HDL processes are started."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import a_harness as harness


class PreparationGuards(unittest.TestCase):
    def test_tb_preedge_drive_postnba_observation(self):
        rows = harness.case_vectors(4, "none")
        text = harness.tb_text(4, rows)
        self.assertEqual(text.count("@(negedge sys_clk);"), len(rows))
        self.assertEqual(text.count("@(posedge sys_clk); #1; observe("), len(rows))
        self.assertEqual(text.count("// Verification-only arbitrary old state;"), 5)
        self.assertIn("original.slots[j]", text)
        self.assertIn("candidate.slots[j]", text)

    def test_mutations_are_unique_and_targeted(self):
        raw = harness.CANDIDATE.read_bytes()
        for mutation in ("priority", "tie"):
            changed = harness.mutated(raw, mutation)
            self.assertNotEqual(raw, changed)
            rows = harness.case_vectors(32, mutation)
            self.assertEqual(len(rows), 2)
            self.assertIsNotNone(rows[1]["inject_slots"])
            with self.assertRaisesRegex(ValueError, "MUTATION_SITE_NOT_UNIQUE"):
                harness.mutated(changed, mutation)

    def test_named_negative_checker_and_original_oracle(self):
        with tempfile.TemporaryDirectory(dir=harness.ROOT / "code/output", prefix="n32_a_guard_") as temporary:
            folder = Path(temporary)
            rows = harness.case_vectors(32, "priority")
            normal = [{"index": row["index"], **row["expected"]} for row in rows]
            bad = copy.deepcopy(normal)
            bad[1]["outputs"]["allocated_slot"] = 0
            for name, records in (("vectors", rows), ("original", normal), ("candidate", bad)):
                (folder / name).write_bytes(harness.jsonl_bytes(records))
            result = harness.check(32, folder / "vectors", folder / "original",
                                   folder / "candidate", "priority")
            self.assertEqual(result["diagnostic"], "ALLOC_PRIORITY")
            self.assertEqual(result["edge"], 1)
            bad[1]["outputs"]["allocated_slot"] = 31
            (folder / "candidate").write_bytes(harness.jsonl_bytes(bad))
            with self.assertRaisesRegex(ValueError, "MUTATION_FALSE_ACCEPT"):
                harness.check(32, folder / "vectors", folder / "original",
                              folder / "candidate", "priority")

    def test_truncated_negative_not_counted_as_rejection(self):
        with tempfile.TemporaryDirectory(dir=harness.ROOT / "code/output", prefix="n32_a_guard_") as temporary:
            folder = Path(temporary)
            rows = harness.case_vectors(32, "tie")
            normal = [{"index": row["index"], **row["expected"]} for row in rows]
            for name, records in (("vectors", rows), ("original", normal), ("candidate", normal[:1])):
                (folder / name).write_bytes(harness.jsonl_bytes(records))
            with self.assertRaisesRegex(ValueError, "MUTATION_CAPTURE_TRUNCATED"):
                harness.check(32, folder / "vectors", folder / "original",
                              folder / "candidate", "tie")

    def test_output_escape_and_root_rejected(self):
        for path in (harness.ROOT, harness.ROOT / "code/output", harness.ROOT.parent / "escaped"):
            with self.assertRaisesRegex(ValueError, "OUTPUT_OUTSIDE_CODE_OUTPUT"):
                harness.under_output(path)

    def test_sv_string_escaping_emits_plain_json(self):
        text = harness.tb_text(4, harness.case_vectors(4, "priority"))
        line = next(line for line in text.splitlines() if line.startswith('$fwrite(fo,"{'))
        self.assertIn(r'{\"index\":%0d', line)
        self.assertNotIn(r'{\\\"index', line)
        # SV interprets \" as a single quote in the written JSON string.
        literal = line.split('$fwrite(fo,"', 1)[1].split('",idx', 1)[0]
        self.assertTrue(literal.replace(r'\"', '"').startswith('{"index":%0d'))

    def test_negative_malformed_record_never_counts(self):
        with tempfile.TemporaryDirectory(dir=harness.ROOT / "code/output", prefix="n32_a_guard_") as temporary:
            folder = Path(temporary)
            rows = harness.case_vectors(32, "priority")
            normal = [{"index": row["index"], **row["expected"]} for row in rows]
            bad = copy.deepcopy(normal)
            bad[1]["outputs"]["allocated_slot"] = 0
            bad[1]["unexpected"] = 1
            for name, records in (("vectors", rows), ("original", normal), ("candidate", bad)):
                (folder / name).write_bytes(harness.jsonl_bytes(records))
            with self.assertRaisesRegex(ValueError, "FIELDS:capture"):
                harness.check(32, folder / "vectors", folder / "original",
                              folder / "candidate", "priority")


if __name__ == "__main__":
    unittest.main()
