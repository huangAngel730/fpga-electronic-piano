"""B0 assertions only; HDL compiled mutants are explicitly still pending B1."""
import copy
from dataclasses import replace
import unittest

from budget import VOICE_STEPS, calendar, markdown, report, resources
from inventory import inventory, rom_inventory, slot_width, verify_manifest
from protocol_oracle import ProtocolOracle


def oracle(n=4):
    return ProtocolOracle([(i % 16, (i * 3) % 16, 1000 + i) for i in range(n)], drain_limit=8)


def acknowledge_empty(model):
    return model.drain_step(rom_empty=True, engine_empty=True, result_empty=True)


class BudgetTests(unittest.TestCase):
    def test_frozen_56(self):
        rows = verify_manifest()
        self.assertEqual(len(rows), 56)
        self.assertEqual(sum(r["original_recovery"] != "identity_LF" for r in rows), 3)

    def test_ROMs_and_bits(self):
        rows = rom_inventory()
        self.assertEqual(len(rows), 7)
        self.assertEqual(sum(r["active_piano"] for r in rows), 5)
        self.assertEqual(sum(r["bits_per_copy"] for r in rows if r["active_piano"]), 70632)

    def test_private_state4_and_identity256(self):
        for n in (4, 8, 16, 32):
            rows = inventory(n)
            state = next(r for r in rows if r["module"] == "adsr_piano_envelope"
                         and "state" in r["fields"])
            self.assertEqual(state["fields"]["state"], 4)
            identities = [r for r in rows if r["class"] == "identity"]
            self.assertEqual(sum(r["bits"] for r in identities), 256 * 31)
            self.assertTrue(all(r["copies"] == 256 for r in identities))

    def test_all_N_each_once_and_no_overlap(self):
        for n in (4, 8, 16, 32):
            schedule = calendar(n)
            segments = schedule["segments"]
            self.assertEqual([s["slot"] for s in segments if s["stage"] == "context_write"], list(range(n)))
            for a, b in zip(segments, segments[1:]):
                self.assertEqual(a["end"], b["begin"])
            self.assertEqual(schedule["conditional_cycles"], 29 + 22 * n)

    def test_unknown_propagates(self):
        schedule = calendar(32)
        self.assertEqual(schedule["end_to_end_status"], "UNKNOWN")
        self.assertIsNone(schedule["actual_shared_engine_II"])
        self.assertFalse(schedule["verified_voice_audio_equivalence"])

    def test_bounded_idle_contract_not_actual_pass(self):
        schedule = calendar(32, dispatch_bound=0)
        self.assertEqual(schedule["end_to_end_status"], "CONDITIONAL_FITS")
        self.assertEqual(schedule["conditional_slack"], 100)

    def test_dispatch_exceeds_deadline(self):
        self.assertEqual(calendar(32, dispatch_bound=100)["conditional_status"], "CONDITIONAL_EXCEEDS")

    def test_slow_operator_exceeds(self):
        steps = tuple((name, 1000 if name == "gain" else cost) for name, cost in VOICE_STEPS)
        self.assertEqual(calendar(4, step_contract=steps)["conditional_status"], "CONDITIONAL_EXCEEDS")

    def test_unknown_cost_rejected(self):
        for cost in (None, 0, -1, True, 1.5):
            steps = list(VOICE_STEPS)
            steps[0] = ("context_read", cost)
            with self.assertRaisesRegex(ValueError, "UNKNOWN_OR_INVALID"):
                calendar(4, step_contract=steps)

    def test_missing_work_rejected(self):
        with self.assertRaisesRegex(ValueError, "MISSING_OR_REORDERED"):
            calendar(4, step_contract=VOICE_STEPS[:-1])

    def test_port_and_ROM_latency_need_rebudget(self):
        for ports, latency in ((0, 1), (2, 1), (1, 2), (1, None)):
            with self.assertRaisesRegex(ValueError, "REBUDGET"):
                calendar(4, rom_ports=ports, rom_latency=latency)

    def test_slot_width_and_N_rejection(self):
        self.assertEqual([slot_width(n) for n in (4, 8, 16, 32)], [2, 3, 4, 5])
        for n in (0, 1, 3, 33, True, False, 4.0, 8.0, None, "4"):
            with self.assertRaises(ValueError):
                slot_width(n)

    def test_working_copies_and_mixer_nodes(self):
        for n in (4, 8, 16, 32):
            row = resources(n, inventory(n), rom_inventory())
            tree = row["alternative_balanced_stereo_tree"]
            self.assertEqual(tree["registered_payload_bits"], 2 * (n - 1) * 32)
            # 440 pitch + 179 ADSR pipeline + 16 synchronous wave output.
            self.assertEqual(row["candidate_extra_logical_allocations"]["context_engine_work_bits"], 635)
            self.assertIsNone(row["actual_DSP"])
            self.assertIsNone(row["actual_BSRAM_blocks"])

    def test_independent_state_subtotals(self):
        rows = inventory(4)
        for module, expected in (("piano_dds_oscillator", 64),
                                 ("adsr_piano_envelope", 400),
                                 ("pitch_mod_fcw_pipeline", 472)):
            per_voice = sum(sum(row["fields"].values()) for row in rows if row["module"] == module)
            self.assertEqual(per_voice, expected, module)

    def test_same_object_json_markdown(self):
        data = report()
        rendered = markdown(data)
        for budget, schedule in zip(data["budgets"], data["calendars"]):
            self.assertIn(f"| {budget['N']} | {schedule['conditional_cycles']} | {schedule['conditional_slack']} | "
                          f"{budget['candidate_logical_allocation_bits']} | UNKNOWN |", rendered)
        changed = copy.deepcopy(data)
        changed["calendars"][0]["conditional_cycles"] = 999
        self.assertIn("| 4 | 999 |", markdown(changed))


class ProtocolTests(unittest.TestCase):
    def test_all_N_reordered_full_commit(self):
        for n in (4, 8, 16, 32):
            model = oracle(n)
            model.begin(77)
            tags = [model.issue(i) for i in range(n)]
            for tag in reversed(tags):
                self.assertTrue(model.accept(tag, (tag.slot, "opaque Release or silent state")))
            self.assertEqual(model.commit(), tuple((i, "opaque Release or silent state") for i in range(n)))

    def test_incomplete_no_write(self):
        model = oracle()
        model.begin(1)
        model.accept(model.issue(0), 123)
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_FRAME"):
            model.commit()
        self.assertEqual(model.committed, [None] * 4)

    def test_duplicate_issue(self):
        model = oracle()
        model.begin(1)
        model.issue(0)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_ISSUE"):
            model.issue(0)

    def test_unissued_result(self):
        model = oracle()
        model.begin(1)
        tag = model.issue(0)
        model.issued.clear()
        self.assertFalse(model.accept(tag, 1))

    def test_duplicate_and_write_conflict(self):
        model = oracle()
        model.begin(1)
        tag = model.issue(0)
        self.assertTrue(model.accept(tag, 10))
        self.assertFalse(model.accept(tag, 99))
        self.assertEqual(model.scratch[0], 10)

    def test_wrong_identity_each_field(self):
        model = oracle()
        model.begin(3)
        tag = model.issue(0)
        for field in ("slot", "source", "channel", "generation", "request"):
            wrong = replace(tag, **{field: getattr(tag, field) + 1})
            self.assertFalse(model.accept(wrong, 99), field)

    def test_cancel_old_request(self):
        model = oracle()
        model.begin(3)
        tag = model.issue(0)
        model.cancel()
        self.assertFalse(model.accept(tag, 999))
        acknowledge_empty(model)
        model.begin(4)
        model.issue(0)
        self.assertFalse(model.accept(tag, 999))

    def test_generation_reuse_after_cancel(self):
        model = oracle()
        model.begin(3)
        tag = model.issue(0)
        model.cancel()
        acknowledge_empty(model)
        model.replace(0, tag.source, tag.channel, tag.generation + 1)
        model.begin(3)  # Same request alone must not bypass generation guard.
        model.issue(0)
        self.assertFalse(model.accept(tag, 999))

    def test_reset_at_each_protocol_point(self):
        for count in range(5):
            model = oracle()
            model.begin(1)
            tags = [model.issue(i) for i in range(4)]
            for tag in tags[:count]:
                model.accept(tag, 1)
            model.reset()
            self.assertTrue(all(not model.accept(tag, 999) for tag in tags))
            acknowledge_empty(model)
            model.begin(2)
            for i in range(4):
                model.accept(model.issue(i), i)
            self.assertEqual(model.commit(), (0, 1, 2, 3))

    def test_pedal_full_identity(self):
        model = oracle()
        model.pedal(15, 15, True)
        self.assertEqual(sum(model.pedals), 1)
        self.assertTrue(model.pedals[255])
        self.assertFalse(model.pedals[15])
        self.assertFalse(model.pedals[240])

    def test_atomic_event_lock(self):
        model = oracle()
        model.begin(1)
        with self.assertRaisesRegex(ValueError, "EVENT_DURING"):
            model.replace(0, 1, 2, 4)
        with self.assertRaisesRegex(ValueError, "CONTROL_DURING"):
            model.pedal(1, 2, True)

    def test_width_and_busy_guards(self):
        model = oracle()
        for request in (-1, 2**32):
            with self.assertRaisesRegex(ValueError, "REQUEST_WIDTH"):
                model.begin(request)
        with self.assertRaisesRegex(ValueError, "IDENTITY_WIDTH"):
            model.replace(0, 16, 0, 0)
        model.begin(1)
        with self.assertRaisesRegex(ValueError, "BUSY"):
            model.begin(2)


class ReviewRepairTests(unittest.TestCase):
    def test_constructor_strict_identity(self):
        for n in (4, 8, 16, 32):
            for field, upper in ((0, 16), (1, 16), (2, 2**32)):
                for bad in (True, False, 0.5, 1.0, -1, upper, None, "1"):
                    with self.subTest(n=n, field=field, bad=repr(bad)):
                        rows = [(1, 1, 1)] * n
                        row = list(rows[0])
                        row[field] = bad
                        rows[0] = tuple(row)
                        with self.assertRaisesRegex(ValueError, "IDENTITY_WIDTH"):
                            ProtocolOracle(rows, drain_limit=8)

    def test_replace_strict_all_fields_no_mutation(self):
        for field, upper in ((0, 4), (1, 16), (2, 16), (3, 2**32)):
            for bad in (True, False, 0.5, 1.0, -1, upper, None, "1"):
                model = oracle()
                before = model.identities.copy()
                args = [1, 1, 1, 1]
                args[field] = bad
                with self.assertRaisesRegex(ValueError, "IDENTITY_WIDTH"):
                    model.replace(*args)
                self.assertEqual(model.identities, before)

    def test_pedal_strict_identity_and_boolean_no_mutation(self):
        for field in range(3):
            invalid = (True, False, 0.5, 1.0, -1, 16, None, "1") if field < 2 else (0, 1, 1.0, None, "yes")
            for bad in invalid:
                model = oracle()
                args = [1, 1, True]
                args[field] = bad
                with self.assertRaisesRegex(ValueError, "PEDAL_INPUT"):
                    model.pedal(*args)
                self.assertEqual(model.pedals, [False] * 256)

    def test_tag_strict_fields_reject_false_not_exception(self):
        for n in (4, 8, 16, 32):
            model = ProtocolOracle([(1, 1, 1)] * n, drain_limit=8)
            model.begin(1)
            tag = model.issue(1)
            for field, upper in (("slot", n), ("source", 16), ("channel", 16),
                                 ("generation", 2**32), ("request", 2**32)):
                for bad in (True, False, 0.5, 1.0, -1, upper, None, "1", []):
                    with self.subTest(n=n, field=field, bad=repr(bad)):
                        self.assertIs(model.accept(replace(tag, **{field: bad}), 99), False)
                        self.assertEqual(model.scratch, {})
            self.assertIs(model.accept(None, 99), False)
            self.assertTrue(model.accept(tag, 10))

    def test_valid_width_extremes(self):
        model = ProtocolOracle([(0, 0, 0), (15, 15, 2**32 - 1)] * 2, drain_limit=8)
        model.begin(2**32 - 1)
        for i in range(4):
            self.assertTrue(model.accept(model.issue(i), i))
        self.assertEqual(model.commit(), (0, 1, 2, 3))

    def test_cancel_same_tag_fenced_at_all_completion_points(self):
        for n in (4, 8, 16, 32):
            for count in range(n + 1):
                model = oracle(n)
                model.begin(7)
                tags = [model.issue(i) for i in range(n)]
                for tag in tags[:count]:
                    model.accept(tag, 5)
                model.cancel()
                with self.assertRaisesRegex(ValueError, "DRAIN_REQUIRED"):
                    model.begin(7)
                for tag in tags:
                    self.assertFalse(model.accept(tag, 99))
                self.assertEqual(model.scratch, {})
                self.assertEqual(model.committed, [None] * n)
                self.assertFalse(model.drain_step(rom_empty=False, engine_empty=True, result_empty=True))
                with self.assertRaisesRegex(ValueError, "DRAIN_REQUIRED"):
                    model.begin(7)
                acknowledge_empty(model)
                model.begin(7)
                for i in range(n):
                    self.assertTrue(model.accept(model.issue(i), i))
                self.assertEqual(model.commit(), tuple(range(n)))

    def test_wrap_and_replacement_fenced(self):
        model = ProtocolOracle([(1, 1, 2**32 - 1)] * 4, drain_limit=8)
        model.begin(2**32 - 1)
        old = model.issue(0)
        model.cancel()
        for action in (lambda: model.begin(0), lambda: model.replace(0, 1, 1, 0),
                       lambda: model.pedal(1, 1, True)):
            with self.assertRaisesRegex(ValueError, "DRAIN_REQUIRED"):
                action()
        self.assertFalse(model.accept(old, 99))
        acknowledge_empty(model)
        model.replace(0, 1, 1, 0)
        model.begin(0)
        new = model.issue(0)
        self.assertFalse(model.accept(old, 99))
        self.assertTrue(model.accept(new, 12))

    def test_all_three_empty_inputs_and_strict_types(self):
        for busy in range(3):
            model = oracle()
            model.begin(1)
            model.issue(0)
            model.cancel()
            flags = [True] * 3
            flags[busy] = False
            self.assertFalse(model.drain_step(**dict(zip(("rom_empty", "engine_empty", "result_empty"), flags))))
            for bad in (0, 1, 1.0, None, "true"):
                with self.assertRaisesRegex(ValueError, "DRAIN_INPUT"):
                    model.drain_step(rom_empty=bad, engine_empty=True, result_empty=True)
            self.assertEqual(model.drain_cycles, 1)
            self.assertTrue(acknowledge_empty(model))

    def test_timeout_closed_and_reset_does_not_extend_bound(self):
        model = ProtocolOracle([(1, 1, 1)] * 4, drain_limit=2)
        model.begin(1)
        model.issue(0)
        model.cancel()
        self.assertFalse(model.drain_step(rom_empty=True, engine_empty=False, result_empty=True))
        model.cancel()
        model.reset()
        self.assertEqual(model.drain_cycles, 1)
        with self.assertRaisesRegex(ValueError, "DRAIN_TIMEOUT"):
            model.drain_step(rom_empty=True, engine_empty=False, result_empty=True)
        model.reset()
        with self.assertRaisesRegex(ValueError, "DRAIN_TIMEOUT"):
            acknowledge_empty(model)
        with self.assertRaisesRegex(ValueError, "DRAIN_REQUIRED"):
            model.begin(2)

    def test_drain_bound_must_be_explicit_positive_int(self):
        for bad in (None, True, 0, -1, 2.0):
            with self.assertRaisesRegex(ValueError, "DRAIN_LIMIT"):
                ProtocolOracle([(1, 1, 1)] * 4, drain_limit=bad)

    def test_successful_commit_fences_duplicate_across_reuse(self):
        model = oracle()
        model.begin(7)
        tags = [model.issue(i) for i in range(4)]
        for tag in tags:
            model.accept(tag, tag.slot)
        self.assertEqual(model.commit(), (0, 1, 2, 3))
        with self.assertRaisesRegex(ValueError, "DRAIN_REQUIRED"):
            model.begin(7)
        self.assertFalse(model.accept(tags[0], 99))
        self.assertEqual(model.committed, [0, 1, 2, 3])
        acknowledge_empty(model)
        model.begin(7)

    def test_cancel_before_issue_has_no_external_work(self):
        model = oracle()
        model.begin(7)
        model.cancel()
        model.begin(7)
        with self.assertRaisesRegex(ValueError, "NOT_DRAINING"):
            acknowledge_empty(model)

    def test_false_empty_ack_is_not_epoch_disambiguation(self):
        # Document the unavoidable external assumption: equal complete tags are
        # indistinguishable. RTL may not assert empty then emit an old duplicate.
        model = oracle()
        model.begin(7)
        old = model.issue(0)
        model.cancel()
        acknowledge_empty(model)
        model.begin(7)
        new = model.issue(0)
        self.assertEqual(old, new)
        self.assertTrue(model.accept(old, 99))  # Lying producer violates the contract.


if __name__ == "__main__":
    unittest.main(verbosity=2)
