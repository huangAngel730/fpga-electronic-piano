"""Bounded orchestration around unchanged R10 integer math and ROM code.

This module defines a candidate factory, not an import-time execution path.
The caller must freeze/verify the complete dependency closure before calling it.
"""
from identity_guard import require
from results_stream import AppendSink


def make_engine(legacy, plan, store, audit):
    class BoundedMath(legacy.ClockedMath):
        def check(self, field, expected, actual, row, layer, event=None):
            if expected != actual:
                key = (legacy.known(row, 'result_id', 32) if legacy.known(row, 'result_valid') else
                       legacy.known(row, 'effect_input_id', 32) if legacy.known(row, 'effect_input_valid') else
                       legacy.known(row, 'commit_id', 32) if legacy.known(row, 'commit') else
                       legacy.known(row, 'advance_frame_req_id', 32))
                token = self.tokens.get(key, {})
                self.first_difference = dict(source_line=row['cycle'] + 1,
                    cycle=row['cycle'], epoch=row['epoch'], request_id=key,
                    independent_event_seq=event if event is not None else token.get('plan_event_seq'),
                    router_sequence=token.get('router_sequence'), layer=layer, field=field,
                    expected=expected, actual=actual)
                raise legacy.MathIssue('MATH_OR_IDENTITY_MISMATCH', field, 'FAIL', expected, actual)

        def reset(self, cycle, epoch):
            if hasattr(self, 'tokens') and hasattr(self.tokens, 'checkpoint_all'):
                for key in tuple(self.tokens.live):
                    token = self.tokens.live[key]
                    token['cancelled'], token['reset_abort'] = True, True
                    audit.append('cancellation', dict(epoch=self.epoch, request_id=key,
                                                     reason='RESET', token=token))
                    self.tokens.retire(key)
                self.accepted.checkpoint_all()
            super().reset(cycle, epoch)
            self.tokens = store.mapping('request', epoch, 128)
            self.accepted = store.mapping('event', epoch, 128)
            self.last_independent_event = None
            self.last_router_sequence = None

        def accept_event(self, row):
            previous = self.router_next
            super().accept_event(row)
            if previous != self.router_next:
                self.last_independent_event = self.accepted[previous]['plan_seq']
                self.last_router_sequence = previous
                audit.append('accepted', dict(epoch=self.epoch, router_seq=previous,
                    event={k: v for k, v in self.accepted[previous].items() if k != 'stages'}, stages=[]))

        def application(self, row):
            result = super().application(row)
            if legacy.known(row, 'apply_valid') and legacy.known(row, 'router_apply_seq_valid'):
                key = legacy.known(row, 'router_apply_seq', 32)
                self.accepted.checkpoint(key)
            return result

        def configuration(self, row):
            super().configuration(row)
            if legacy.known(row, 'config_take'):
                audit.append('configuration', dict(cycle=row['cycle'], epoch=row['epoch'],
                                                  config=self.config))

        def input_effect(self, row):
            before = self.counts['effect_accepts']
            super().input_effect(row)
            if before != self.counts['effect_accepts']:
                key = legacy.known(row, 'effect_input_id', 32)
                audit.append('fx', dict(epoch=self.epoch, request_id=key,
                                       golden=self.tokens[key]['effect'], rollback=False))

        def outputs(self, row):
            if legacy.known(row, 'result_valid'):
                key = legacy.known(row, 'result_id', 32)
                token = self.tokens.get(key)
                require(token is not None and not token.get('committed')
                        and not token.get('cancelled'), 'RESULT_WITHOUT_ACCEPTED_EFFECT', key)
            super().outputs(row)
            if legacy.known(row, 'result_valid'):
                key = legacy.known(row, 'result_id', 32)
                audit.append('comparison', dict(cycle=row['cycle'], epoch=row['epoch'],
                    request_id=key, actual={k: row[k] for k in (
                        'result_left', 'result_right', 'result_clip_mask', 'upstream_clip_mask',
                        'effect_clip_mask', 'feedback_clip_mask', 'result_ready')},
                    expected=self.tokens[key]['effect']))

        def row(self, row):
            super().row(row)
            if legacy.known(row, 'rst_n') and legacy.known(row, 'req_valid') and legacy.known(row, 'req_ready'):
                token = self.tokens.live[legacy.known(row, 'req_id', 32)]
                token['plan_event_seq'] = self.last_independent_event
                token['router_sequence'] = self.last_router_sequence
            for key in tuple(self.tokens.live):
                token = self.tokens.live[key]
                if token.get('committed') or token.get('cancelled'):
                    audit.append('request', dict(epoch=self.epoch, request_id=key, token=token))
                    if token.get('cancelled'):
                        audit.append('cancellation', dict(epoch=self.epoch, cycle=row['cycle'],
                            request_id=key, after_fx='effect' in token, rollback_fx=False))
                    self.tokens.retire(key)
            for key in tuple(self.accepted.live):
                event = self.accepted.live[key]
                stages = event['stages']
                if {1, 2} <= stages or bool(stages & {5, 6, 7}):
                    self.accepted.retire(key)
            if row['cycle'] % 128 == 0:
                self.tokens.checkpoint_all()
                self.accepted.checkpoint_all()
            audit.append('clock', dict(cycle=row['cycle'], epoch=row['epoch'],
                rst_n=row['rst_n'], frame=row['frame_tick'], req_valid=row['req_valid'],
                req_id=row['req_id'], advance_id=row['advance_frame_req_id'],
                result_valid=row['result_valid'], result_id=row['result_id'],
                commit=row['commit'], commit_id=row['commit_id']))

        def finish(self):
            self.close_epoch()
            require(not self.pending_off and all(l.note_consumed for l in self.lanes),
                    'UNFINISHED_EVENT_APPLICATION')
            require(not self.tokens.live, 'UNFINISHED_REQUESTS')
            self.tokens.checkpoint_all()
            self.accepted.checkpoint_all()
            return dict(profile=legacy.PROFILE, counts=dict(self.counts),
                first_difference=self.first_difference,
                tolerances=dict(pcm_lsb=0, id_exact=True, clip_exact=True),
                expected_values_from_observed_pcm=False)

    engine = BoundedMath(plan, diagnostic_limit=1 << 63)
    engine.actions = AppendSink(audit, 'action')
    engine.compared = AppendSink(audit, 'result_accept')
    engine.epoch_receipts = AppendSink(audit, 'epoch')
    return engine
