"""B0 assertions only; HDL compiled mutants are explicitly still pending B1."""
import copy
from dataclasses import replace
import unittest

from budget import VOICE_STEPS, calendar, markdown, report, resources
from inventory import inventory, rom_inventory, slot_width, verify_manifest
from protocol_oracle import ProtocolOracle


def oracle(n=4):
    return ProtocolOracle([(i % 16, (i * 3) % 16, 1000 + i) for i in range(n)])


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
        for n in (0, 1, 3, 33):
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
        model.begin(4)
        model.issue(0)
        self.assertFalse(model.accept(tag, 999))

    def test_generation_reuse_after_cancel(self):
        model = oracle()
        model.begin(3)
        tag = model.issue(0)
        model.cancel()
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
