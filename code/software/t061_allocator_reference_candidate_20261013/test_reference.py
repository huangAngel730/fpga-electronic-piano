"""New software contract tests; no HDL compiler or simulator is called."""

from copy import deepcopy
from dataclasses import asdict
import unittest

from reference import Allocator, ContractError, Edge, Slot, compare_records, strict_json
from vectors import build_vectors, jsonl_bytes


class ReferenceTests(unittest.TestCase):
    def test_reset_all_parameters(self):
        for n in (4, 8, 16, 32):
            model = Allocator(n)
            model.step(Edge(note_on=1, source=1, channel=2, note=60))
            result = model.step(Edge(rst_n=0, note_on=1, note_off=1,
                                     release_done=(1 << n) - 1))
            self.assertEqual(result["slots"], list(range(n)))
            self.assertEqual(list(result["outputs"].values()), [0, 0, 0, 0])

    def test_fill_steal_and_age_rank_no_wrap(self):
        for n in (4, 8, 16, 32):
            model = Allocator(n)
            for i in range(n * 10):
                output = model.step(Edge(note_on=1, note=i % 256))
                self.assertEqual(output["outputs"]["allocated_slot"], i % n)
                self.assertEqual(sorted(s.age for s in model.slots), list(range(n)))

    def test_match_over_idle_and_release_retrigger(self):
        model = Allocator(4)
        model.load_slots([Slot(age=i).packed(2) for i in range(3)]
                         + [Slot(release=1, source=1, channel=2,
                                 note=60, age=3).packed(2)])
        result = model.step(Edge(note_on=1, source=1, channel=2, note=60,
                                 release_done=8))
        self.assertEqual(result["outputs"]["allocated_slot"], 3)
        self.assertEqual((model.slots[3].active, model.slots[3].release), (1, 0))

    def test_done_does_not_change_preedge_idle_or_lru(self):
        model = Allocator(4)
        model.load_slots([Slot(active=1, note=i, age=i).packed(2) for i in range(3)]
                         + [Slot(release=1, note=3, age=3).packed(2)])
        result = model.step(Edge(note_on=1, note=100, release_done=8))
        self.assertEqual(result["outputs"]["allocated_slot"], 0)
        self.assertEqual((model.slots[3].active, model.slots[3].release), (0, 0))

    def test_all_duplicate_off_targets_public_max(self):
        model = Allocator(8)
        model.load_slots([Slot(active=1, source=1, channel=2,
                               note=60, age=i).packed(3) for i in range(8)])
        result = model.step(Edge(note_on=1, note_off=1, source=1,
                                 channel=2, note=60, release_done=255))
        self.assertEqual(result["outputs"]["allocated_slot"], 0)
        self.assertEqual(result["outputs"]["release_slot"], 7)
        self.assertTrue(all((s.active, s.release) == (0, 1) for s in model.slots))

    def test_new_on_is_not_visible_to_same_edge_off(self):
        model = Allocator(4)
        model.step(Edge(note_on=1, note_off=1, note=60))
        self.assertEqual((model.slots[0].active, model.slots[0].release), (1, 0))
        self.assertEqual(model.outputs["release_target_valid"], 0)

    def test_release_only_does_not_match_off(self):
        model = Allocator(4)
        model.step(Edge(note_on=1, note=60))
        model.step(Edge(note_off=1, note=60))
        model.step(Edge(note_off=1, note=60))
        self.assertEqual(model.outputs["release_target_valid"], 0)

    def test_lru_tie_and_idle_low_index(self):
        model = Allocator(4)
        model.load_slots([Slot(active=1, note=i,
                               age=0 if i in (1, 3) else 3).packed(2)
                          for i in range(4)])
        self.assertEqual(model.step(Edge(note_on=1, note=255))
                         ["outputs"]["allocated_slot"], 1)
        model.reset()
        self.assertEqual(model.step(Edge(note_on=1))["outputs"]["allocated_slot"], 0)

    def test_identity_source_channel_and_full_note_width(self):
        model = Allocator(4)
        for source, channel, note in ((1, 2, 255), (2, 2, 255), (1, 3, 255), (1, 2, 127)):
            model.step(Edge(note_on=1, source=source, channel=channel, note=note))
        model.step(Edge(note_off=1, source=1, channel=2, note=255))
        self.assertEqual([s.release for s in model.slots], [1, 0, 0, 0])

    def test_outputs_hold_without_event(self):
        model = Allocator(4)
        for note in (60, 61):
            model.step(Edge(note_on=1, note=note))
        model.step(Edge(note_off=1, note=61))
        model.step(Edge())
        self.assertEqual(model.outputs, {"allocated_slot": 1, "slot_valid": 0,
                                         "release_slot": 1, "release_target_valid": 0})

    def test_all_enable_combinations_and_reset_in_vectors(self):
        for n in (4, 8, 16, 32):
            rows = build_vectors(n, random_edges=0)
            labels = {r["label"] for r in rows}
            self.assertTrue(all(f"COMBO_{c}_edge" in labels for c in range(8)))
            capture = [dict(index=r["index"], **r["expected"]) for r in rows]
            self.assertEqual(compare_records(rows, capture, n)["edges"], len(rows))

    def test_determinism_and_normal_age_invariant(self):
        for n in (4, 8, 16, 32):
            rows = build_vectors(n)
            self.assertEqual(jsonl_bytes(rows), jsonl_bytes(build_vectors(n)))
            for row in rows:
                if row["label"].startswith("RANDOM_"):
                    self.assertEqual(sorted(v & (n - 1) for v in row["expected"]["slots"]),
                                     list(range(n)))

    def test_strict_capture_and_golden_recompute(self):
        rows = build_vectors(4, random_edges=0)
        capture = [dict(index=r["index"], **deepcopy(r["expected"])) for r in rows]
        mutations = []
        for kind in ("missing", "duplicate", "extra_field", "bool", "state", "public"):
            bad = deepcopy(capture)
            if kind == "missing":
                bad.pop()
            elif kind == "duplicate":
                bad[1] = bad[0]
            elif kind == "extra_field":
                bad[0]["fake"] = 0
            elif kind == "bool":
                bad[0]["outputs"]["slot_valid"] = False
            elif kind == "state":
                bad[0]["slots"][0] = 1
            else:
                bad[0]["outputs"]["allocated_slot"] = 1
            mutations.append(bad)
        for bad in mutations:
            with self.assertRaises(ContractError):
                compare_records(rows, bad, 4)
        bad_rows = deepcopy(rows)
        bad_rows[0]["expected"]["outputs"]["allocated_slot"] = 1
        with self.assertRaisesRegex(ContractError, "GOLDEN_RECOMPUTE"):
            compare_records(bad_rows, capture, 4)

    def test_parser_types_and_ranges(self):
        for text in ('{"x":1,"x":2}', '{"x":NaN}', '{'):
            with self.assertRaises(ContractError):
                strict_json(text)
        for key, value in (("rst_n", True), ("note_on", 2), ("source", 16),
                           ("note", -1), ("release_done", 16)):
            raw = asdict(Edge())
            raw[key] = value
            with self.assertRaises(ContractError):
                Edge.from_dict(raw, 4)
        with self.assertRaises(ContractError):
            Allocator(True)

    def test_priority_and_tie_mutant_outputs_rejected(self):
        rows = build_vectors(4, random_edges=0)
        for label, wrong_target in (("INJECT_match_over_idle", 0),
                                    ("INJECT_lru_tie_min_slot", 3)):
            bad = [dict(index=r["index"], **deepcopy(r["expected"])) for r in rows]
            index = next(i for i, r in enumerate(rows) if r["label"] == label)
            bad[index]["outputs"]["allocated_slot"] = wrong_target
            with self.assertRaisesRegex(ContractError, "ALLOCATOR_PUBLIC"):
                compare_records(rows, bad, 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
