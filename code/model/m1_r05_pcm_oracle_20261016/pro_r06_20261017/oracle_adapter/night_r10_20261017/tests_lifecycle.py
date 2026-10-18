"""New R10 lifecycle unit cases; collected only by the authorized group runner.

Rows and expected values below are explicit contract fixtures, never projections
of ClockedMath state. The terminal-release and FX tests seed a bounded unit
precondition so they do not need thousands of frames or another test harness.
No test, child process, HDL tool, or old script runs when this file is imported.
"""
import unittest

from c9_math import ClockedMath, MathIssue


ON60 = (1 << 57) | (2 << 53) | (60 << 46) | (512 << 36)
OFF60 = (1 << 61) | (1 << 57) | (2 << 53) | (60 << 46)
ZERO_ON60 = (1 << 57) | (2 << 53) | (60 << 46)
PROGRAM1 = (4 << 61) | (1 << 57) | (2 << 53) | (5 << 18) | (1 << 6)
CONFIG = (1 << 61) | (2 << 45) | (32767 << 30) | (16384 << 15) | 8192


def planned(word, cycle, seq=0, epoch=0):
    return dict(event_seq=seq, epoch=epoch, expected_event_hex=f'{word:016x}',
                arrival_window=dict(min_cycle=cycle, max_cycle=cycle))


def row(cycle, *, occupied=0, releasing=0, retained=False, epoch=0, **changes):
    """A four-lane public row with literal lane-0 identity (1, 2, 60, 1)."""
    identity = bool(occupied or retained)
    value = dict(
        cycle=cycle, epoch=epoch, rst_n=1, frame_tick=0, cancel=0,
        occupied_mask=occupied, releasing_mask=releasing,
        slot_sources=1 if identity else 0,
        slot_channels=2 if identity else 0,
        slot_notes=60 if identity else 0,
        slot_generations=1 if identity else 0,
        event_valid=0, event_ready=0, event_data=0,
        apply_valid=0, apply_kind=0, apply_mask=0, apply_data=0,
        router_apply_seq_valid=0, router_apply_seq=0,
        note_on_mask=0, note_off_mask=0, retire_mask=0,
        config_take=0, config_valid=0, config_ready=0, config_payload=0,
        req_valid=0, req_ready=0, req_id=0,
        advance_mask=0, advance_frame_req_id=0,
        effect_input_valid=0, effect_input_ready=0, effect_input_id=0,
        effect_input_left=0, effect_input_right=0, effect_input_clip_mask=0,
        result_valid=0, result_ready=0, result_id=0,
        result_left=0, result_right=0, result_clip_mask=0,
        upstream_clip_mask=0, effect_clip_mask=0, feedback_clip_mask=0,
        commit=0, commit_id=0, commit_left=0, commit_right=0, commit_clip=0,
    )
    value.update(changes)
    return value


def apply(kind, mask=0, *, word=0, seq=0):
    """Unassociated release/off/retire actions use the specified zero sentinel."""
    return dict(apply_valid=1, apply_kind=kind, apply_mask=mask,
                apply_data=word, router_apply_seq=seq,
                router_apply_seq_valid=int(kind not in (3, 4, 8)))


class LifecycleTests(unittest.TestCase):
    def assert_issue(self, code, action):
        with self.assertRaises(MathIssue) as caught:
            action()
        self.assertEqual(code, caught.exception.code)
        return caught.exception

    def released_engine(self, off_word=OFF60):
        """Complete on, matched off-control, release commit, and off consumption."""
        engine = ClockedMath(dict(events=[planned(ON60, 1),
                                         planned(off_word, 5, seq=1)]))
        engine.row(row(0, rst_n=0))
        engine.row(row(1, event_valid=1, event_ready=1, event_data=ON60))
        engine.row(row(2))
        # ALLOC_COMMIT is observed with the old, empty pre-NBA identity.
        engine.row(row(3, **apply(1, 1, word=ON60)))
        engine.row(row(4, occupied=1))
        # This consume must retain seq 0 despite simultaneous acceptance of seq 1.
        engine.row(row(5, occupied=1, note_on_mask=1,
                       event_valid=1, event_ready=1, event_data=off_word,
                       **apply(2, 1, word=ON60)))
        for cycle in (6, 7, 8):
            engine.row(row(cycle, occupied=1))
        engine.row(row(9, occupied=1, **apply(6, 1, word=off_word, seq=1)))
        # CONTROL_ACCEPT and RELEASE_COMMIT do not consume an ADSR off pulse.
        self.assertEqual(3, engine.lanes[0].envelope.state)
        engine.row(row(10, occupied=1, **apply(3, 1)))
        self.assertEqual(3, engine.lanes[0].envelope.state)
        self.assertEqual((1, 2, 60, 'release'), engine.slots.slots[0])
        engine.row(row(11, occupied=1, releasing=1, note_off_mask=1,
                       **apply(4, 1)))
        self.assertEqual(9, engine.lanes[0].envelope.state)
        engine.row(row(12, occupied=1, releasing=1))
        engine.row(row(13, occupied=1, releasing=1))
        self.assertEqual(6, engine.lanes[0].envelope.state)
        return engine

    def test_control_release_and_off_consume_are_distinct_stages(self):
        engine = self.released_engine()
        result = engine.finish()
        self.assertEqual({1, 2}, engine.accepted[0]['stages'])
        self.assertEqual({6}, engine.accepted[1]['stages'])
        self.assertEqual([1, 2, 6, 3, 4], [x['kind'] for x in result['actions']])
        self.assertEqual(2, result['counts']['accepted_events'])
        self.assertEqual(1, engine.lanes[0].generation)
        self.assertEqual({}, engine.pending_off)

    def test_note_on_velocity_zero_follows_the_off_lifecycle(self):
        engine = self.released_engine(ZERO_ON60)
        result = engine.finish()
        self.assertEqual([1, 2, 6, 3, 4], [x['kind'] for x in result['actions']])
        self.assertEqual(1, result['counts']['apply_kind_1'])
        self.assertEqual(1, engine.lanes[0].generation)

    def test_retire_rejects_a_still_running_release(self):
        engine = self.released_engine()
        self.assert_issue('RETIRE_BEFORE_ENVELOPE_DONE', lambda: engine.row(
            row(14, occupied=1, releasing=1, retire_mask=1, **apply(8, 1))))

    def terminal_release(self):
        engine = self.released_engine()
        # Independent unit precondition: the final release sample is next.
        # Q16 level/step do not derive from a prior ClockedMath result.
        env = engine.lanes[0].envelope
        env.state, env.elapsed, env.level, env.step = 6, 4799, 65536, -65536
        engine.row(row(14, occupied=1, releasing=1,
                       req_valid=1, req_ready=1, req_id=7))
        engine.row(row(15, occupied=1, releasing=1,
                       advance_mask=15, advance_frame_req_id=7))
        self.assertEqual(0, env.state)
        self.assertEqual(0, env.level)
        engine.row(row(16, occupied=1, releasing=1))
        self.assertEqual(16, engine.done_seen[0])
        return engine

    def test_retire_waits_for_registered_pending_and_router_selection(self):
        engine = self.terminal_release()
        self.assert_issue('RETIRE_BEFORE_ROUTER_PENDING', lambda: engine.row(
            row(17, occupied=1, releasing=1, retire_mask=1, **apply(8, 1))))

    def test_legal_retire_clears_occupancy_but_retains_identity_and_phase(self):
        engine = self.terminal_release()
        engine.row(row(17, occupied=1, releasing=1))
        engine.row(row(18, occupied=1, releasing=1, retire_mask=1, **apply(8, 1)))
        # RETIRE updates occupancy after the sampled row; stored identity remains.
        self.assertIsNone(engine.slots.slots[0])
        engine.row(row(19, retained=True, frame_tick=1, cancel=1))
        self.assertEqual((1, 2, 60, 1, 512, 23409859), (
            engine.lanes[0].source, engine.lanes[0].channel,
            engine.lanes[0].note, engine.lanes[0].generation,
            engine.lanes[0].velocity, engine.lanes[0].fcw))
        self.assertEqual(23409859, engine.lanes[0].piano.phase)
        self.assertEqual(1, engine.finish()['counts']['apply_kind_8'])

    def test_allocation_row_cannot_show_post_nba_identity(self):
        engine = ClockedMath(dict(events=[planned(ON60, 1)]))
        engine.row(row(0, rst_n=0))
        engine.row(row(1, event_valid=1, event_ready=1, event_data=ON60))
        engine.row(row(2))
        error = self.assert_issue('MATH_OR_IDENTITY_MISMATCH', lambda: engine.row(
            row(3, occupied=1, **apply(1, 1, word=ON60))))
        self.assertEqual('occupied_mask', error.where)
        self.assertEqual((0, 1), (error.expected, error.actual))

    def test_note_on_consume_does_not_borrow_same_edge_new_event(self):
        engine = self.released_engine()
        self.assertEqual(ON60, engine.accepted[0]['word'])
        self.assertEqual(OFF60, engine.accepted[1]['word'])
        self.assertEqual(5, engine.accepted[1]['accepted_cycle'])
        on_consume = [x for x in engine.actions if x['kind'] == 2]
        self.assertEqual([(5, 0, 0)], [
            (x['cycle'], x['plan_seq'], x['router_seq']) for x in on_consume])

    def test_finish_rejects_accepted_events_without_their_required_application(self):
        for word in (ON60, OFF60, ZERO_ON60, PROGRAM1):
            with self.subTest(word=f'{word:016x}'):
                engine = ClockedMath(dict(events=[planned(word, 1)]))
                engine.row(row(0, rst_n=0))
                engine.row(row(1, event_valid=1, event_ready=1, event_data=word))
                engine.row(row(2))
                self.assert_issue('ACCEPTED_EVENT_WITHOUT_REQUIRED_APPLY', engine.finish)

    def test_unmatched_off_has_an_explicit_ignore_terminal_stage(self):
        engine = ClockedMath(dict(events=[planned(OFF60, 1)]))
        engine.row(row(0, rst_n=0))
        engine.row(row(1, event_valid=1, event_ready=1, event_data=OFF60))
        engine.row(row(2, **apply(7, word=OFF60)))
        self.assertEqual(1, engine.finish()['counts']['apply_kind_7'])
        self.assertEqual([None] * 4, engine.slots.slots)

    def test_new_epoch_cannot_erase_an_unconsumed_old_epoch_plan(self):
        engine = ClockedMath(dict(events=[planned(ON60, 1)]))
        engine.row(row(0, rst_n=0))
        engine.row(row(1))
        self.assert_issue('UNCONSUMED_INDEPENDENT_INPUT_PLAN', lambda: engine.row(
            row(2, rst_n=0, epoch=1)))

    def test_reset_records_accepted_but_not_applied_event_as_aborted(self):
        engine = ClockedMath(dict(events=[planned(ON60, 1, seq=17)]))
        engine.row(row(0, rst_n=0))
        engine.row(row(1, event_valid=1, event_ready=1, event_data=ON60))
        engine.row(row(2, rst_n=0, epoch=1))
        engine.row(row(3, epoch=1))
        result = engine.finish()
        self.assertEqual([
            dict(epoch=0, reset_aborted_events=[17]),
            dict(epoch=1, reset_aborted_events=[]),
        ], result['epoch_receipts'])
        self.assertEqual([None] * 4, engine.slots.slots)
        self.assertEqual([0] * 4, [x.piano.phase for x in engine.lanes])
        self.assertEqual([0] * 4, [x.generation for x in engine.lanes])
        self.assertEqual(0, engine.router_next)

    def fx_fixture(self):
        """Two independently specified mixed PCM snapshots, bypass enabled."""
        engine = ClockedMath(dict(events=[], config_events=[dict(
            epoch=0, payload=CONFIG,
            arrival_window=dict(min_cycle=11, max_cycle=11))]))
        engine.row(row(0, rst_n=0))
        for req in (1, 2):
            engine.tokens[req] = dict(
                snapshot_cycle=0,
                snapshot=dict(left=12345, right=-12345, clip_mask=0, lanes=[]))
        engine.input_effect(row(7, effect_input_valid=1, effect_input_ready=1,
                                effect_input_id=1, effect_input_left=12345,
                                effect_input_right=-12345))
        return engine

    def test_fx_held_result_blocks_another_effect_accept(self):
        engine = self.fx_fixture()
        self.assert_issue('EFFECT_ACCEPT_PIPELINE_ORDER', lambda: engine.input_effect(
            row(11, effect_input_valid=1, effect_input_ready=1,
                effect_input_id=2, effect_input_left=12345,
                effect_input_right=-12345)))
        self.assertEqual(1, engine.counts['effect_accepts'])

    def test_fx_held_result_blocks_config_even_after_arithmetic_finishes(self):
        engine = self.fx_fixture()
        self.assert_issue('CONFIG_DURING_EFFECT_TRANSACTION', lambda: engine.configuration(
            row(11, config_take=1, config_valid=1, config_ready=1,
                config_payload=CONFIG)))
        self.assertEqual((False, 1, 32767, 0, 0), engine.config)

    def test_fx_result_handshake_frees_the_next_edge_not_the_same_edge(self):
        engine = self.fx_fixture()
        engine.outputs(row(11, result_valid=1, result_ready=1, result_id=1,
                           result_left=12345, result_right=-12345))
        self.assertTrue(engine.effect_locked(11))
        self.assertFalse(engine.effect_locked(12))
        self.assert_issue('EFFECT_ACCEPT_PIPELINE_ORDER', lambda: engine.input_effect(
            row(11, effect_input_valid=1, effect_input_ready=1,
                effect_input_id=2, effect_input_left=12345,
                effect_input_right=-12345)))
        engine.input_effect(row(12, effect_input_valid=1, effect_input_ready=1,
                                effect_input_id=2, effect_input_left=12345,
                                effect_input_right=-12345))
        self.assertEqual(2, engine.counts['effect_accepts'])
        self.assertEqual((12345, -12345), (
            engine.tokens[2]['effect']['left'], engine.tokens[2]['effect']['right']))

    def test_frame_cannot_publish_accept_or_commit_a_result(self):
        for forbidden in (dict(result_valid=1), dict(commit=1),
                          dict(req_valid=1, req_ready=1)):
            with self.subTest(forbidden=forbidden):
                engine = ClockedMath(dict(events=[]))
                engine.row(row(0, rst_n=0))
                self.assert_issue('TRANSACTION_ON_FRAME_CANCEL_EDGE', lambda: engine.row(
                    row(1, frame_tick=1, cancel=1, **forbidden)))
