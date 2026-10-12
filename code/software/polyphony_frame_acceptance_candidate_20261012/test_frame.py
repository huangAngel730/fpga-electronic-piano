"""Directed, hand-written semantic expectations plus strict-parser checks."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from frame_reference import FrameReference, U32, default_input
from trace_check import check
from vectors import BAD, encoded, generate, plans, records


class FrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = {n: records(n, p) for n, p in plans().items()}

    def edges(self, name):
        return {r['cycle']: r for r in self.corpus[name] if r['tag'] == 'EDGE'}

    def times(self, name, field):
        return [c for c, r in self.edges(name).items() if r['pre'][field]]

    def checked(self, rows):
        return check(encoded(rows).decode('utf-8').splitlines())

    def test_normal_manual_calendar(self):
        name = 'normal_833_834'
        self.assertEqual(self.times(name, 'dispatch_accept'), [5, 838, 1672])
        self.assertEqual(self.times(name, 'result_accept'), [20, 850, 1680])
        self.assertEqual(self.times(name, 'commit'), [21, 851, 1681])
        self.assertEqual(self.edges(name)[837]['post']['held']['left'], 111)
        self.assertEqual(self.edges(name)[1671]['post']['held']['left'], -8388608)

    def test_delayed_dispatch_actual_handshake_and_expiry(self):
        self.assertEqual(self.times('delayed_dispatch_success', 'dispatch_accept'), [8, 21])
        rows = self.edges('delayed_dispatch_expiry')
        self.assertEqual(rows[8]['pre']['dispatch_accept'], 0)
        self.assertEqual(rows[8]['pre']['cancelled_request'], 1)
        self.assertEqual(rows[9]['pre']['current_id'], 2)
        self.assertEqual(self.times('delayed_dispatch_expiry', 'dispatch_accept'), [9, 23])
        self.assertEqual(rows[15]['pre']['dispatch_accept'], 0)  # ready alone

    def test_frame_priority_and_registered_commit(self):
        rows = self.edges('frame_coincident_result')
        self.assertEqual(rows[10]['pre']['result_accept'], 0)
        self.assertEqual(rows[10]['pre']['discard_result'], 1)
        self.assertEqual(rows[17]['pre']['commit'], 0)
        self.assertEqual(rows[18]['pre']['commit_payload']['left'], 300)
        rows = self.edges('frame_cancels_uncommitted_PCM')
        self.assertEqual(rows[9]['pre']['cancelled_pcm'], 1)
        self.assertEqual(rows[9]['pre']['commit'], 0)
        self.assertEqual(rows[9]['post']['clip_count'], 0)
        self.assertEqual(self.times('frame_cancels_uncommitted_PCM', 'commit'), [14])

    def test_hold_and_pcm_backpressure(self):
        name = 'result_HOLD_and_PCM_backpressure'
        rows = self.edges(name)
        self.assertEqual(self.times(name, 'result_accept'), [12])
        self.assertEqual(self.times(name, 'commit'), [16])
        self.assertEqual([rows[c]['post']['pcm_record']['left'] for c in (12, 13, 14, 15)], [111] * 4)
        self.assertEqual([rows[c]['post']['clip_count'] for c in (10, 12, 15, 16, 31)], [0, 0, 0, 1, 1])
        self.assertEqual(rows[22]['post']['held'], rows[30]['post']['held'])

    def test_illegal_input_hold_not_only_observed_mutation(self):
        plan = deepcopy(plans()['result_HOLD_and_PCM_backpressure'])
        plan['inputs'][8]['left'] += 1
        with self.assertRaisesRegex(ValueError, '^RESULT_HOLD_STABILITY$'):
            records('illegal_environment', plan)

    def test_always_ready_at_most_once(self):
        name = 'always_ready_and_duplicate'
        self.assertEqual(self.times(name, 'result_accept'), [8])
        self.assertEqual(self.times(name, 'commit'), [9])
        self.assertEqual(self.times(name, 'discard_result'), [9, 10, 11, 12])

    def test_reset_cancels_pending_and_rejects_old_epoch(self):
        rows = self.edges('reset_pending_old_epoch')
        self.assertEqual(rows[7]['post']['epoch'], 2)
        self.assertEqual(rows[8]['post']['epoch'], 2)
        self.assertEqual(rows[7]['post']['pending_request'], 0)
        self.assertEqual(rows[13]['pre']['result_accept'], 0)
        self.assertEqual(rows[13]['pre']['discard_result'], 1)
        self.assertEqual(rows[15]['pre']['result_accept'], 1)
        self.assertEqual(rows[16]['pre']['commit_payload']['left'], 17)

    def test_reset_held_clears_playback(self):
        rows = self.edges('reset_held')
        self.assertEqual(rows[14]['pre']['play_left'], 111)
        self.assertIsNone(rows[15]['post']['held'])
        self.assertEqual(rows[17]['pre']['play_left'], 0)
        self.assertEqual(rows[30]['post']['held']['left'], 123)

    def test_wrap_and_entry_seed_reset(self):
        rows = self.edges('ID32_wrap_entry_fixture')
        self.assertEqual([rows[c]['post']['current_id'] for c in (2, 10, 18)], [U32-1, U32, 0])
        self.assertEqual(self.times('ID32_wrap_entry_fixture', 'commit'), [7, 15, 23])
        model = FrameReference(dict(current_id=U32-2, clip_count=U32-1))
        _, post = model.edge(default_input(rst_n=0))
        self.assertEqual((post['current_id'], post['clip_count']), (0, 0))
        model.epoch = U32
        model.was_reset = False
        with self.assertRaisesRegex(ValueError, 'EPOCH_EXHAUSTED_NO_REUSE'):
            model.edge(default_input(rst_n=0))

    def test_clip_commit_saturation_not_inferred_from_pcm(self):
        name = 'clip_once_saturating_entry_fixture'
        rows = self.edges(name)
        self.assertEqual(self.times(name, 'commit'), [11, 20, 33])
        self.assertEqual([rows[c]['post']['clip_count'] for c in (10, 11, 20, 33)], [U32-1, U32, U32, U32])
        self.assertEqual(rows[33]['pre']['commit_payload']['clipped'], 0)
        model = FrameReference(dict(current_id=0, clip_count=0))
        model.edge(default_input(frame_tick=1))
        model.edge(default_input())
        model.edge(default_input(result_valid=1, result_id=1, left=8388607, right=-8388608))
        _, post = model.edge(default_input())
        self.assertEqual(post['clip_count'], 0)

    def test_all_positive_evidence_and_boundaries(self):
        for name, rows in self.corpus.items():
            with self.subTest(name=name):
                result = self.checked(rows)
                self.assertTrue(any(result['ledger'][k] for k in ('dispatch', 'commit', 'discard')))
                for key in ('RTL_verified', 'physical_verified', 'math_verified', 'admission_verified', 't060_complete', 't061_complete'):
                    self.assertIs(result[key], False)

    def test_six_complete_single_target_bad_observations(self):
        for name, base, cycle, region, field, value, diagnostic in BAD:
            rows = deepcopy(self.corpus[base])
            edge = next(r for r in rows if r.get('tag') == 'EDGE' and r['cycle'] == cycle)
            edge[region][field] = value
            self.assertEqual(rows[-1], self.corpus[base][-1])
            self.assertEqual([r['inputs'] for r in rows if r['tag'] == 'EDGE'],
                             [r['inputs'] for r in self.corpus[base] if r['tag'] == 'EDGE'])
            self.assertEqual(sum(a != b for a, b in zip(rows, self.corpus[base])), 1)
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, '^' + diagnostic + '$'):
                self.checked(rows)

    def test_strict_schema_types_identity_and_end(self):
        original = self.corpus['frame_coincident_result']
        mutations = [
            (1, ('extra',), 0), (2, ('epoch',), 9), (2, ('cycle',), 2),
            (2, ('inputs', 'rst_n'), False), (2, ('inputs', 'frame_tick'), 2),
            (2, ('inputs', 'result_id'), U32+1), (2, ('inputs', 'left'), 8388608),
            (2, ('post', 'received'), False), (-1, ('counts', 'EDGE'), 999),
            (0, ('origin',), 'RTL_CAPTURE'), (0, ('initial', 'clip_count'), -1)]
        for index, path, value in mutations:
            rows = deepcopy(original)
            item = rows[index]
            for key in path[:-1]:
                item = item[key]
            item[path[-1]] = value
            with self.subTest(path=path), self.assertRaises((ValueError, TypeError)):
                self.checked(rows)
        for rows in (original[:-1], original + [original[-1]], original[:1] + original[2:],
                     original + [dict(tag='EDGE')], [dict(original[0], schema=True)] + original[1:]):
            with self.assertRaises(ValueError):
                self.checked(rows)

    def test_duplicate_key_nan_unknown_and_empty(self):
        for raw in ('{"tag":"META","tag":"META"}', '{"tag":NaN}',
                    '[]', '', '{"tag":"OTHER"}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                check([raw])
        rows = deepcopy(self.corpus['frame_coincident_result'])
        rows[2]['tag'] = 'UNKNOWN'
        with self.assertRaisesRegex(ValueError, 'TRACE_UNKNOWN_TAG'):
            self.checked(rows)

    def test_generator_refuses_overwrite_and_hashes_complete_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'new'
            manifest = generate(out)
            self.assertEqual((len(manifest['positives']), len(manifest['negatives'])), (11, 6))
            for kind in ('positives', 'negatives'):
                for item in manifest[kind].values():
                    self.assertEqual((out / item['file']).stat().st_size, item['bytes'])
                    self.assertEqual(json.loads((out / item['file']).read_text(encoding='utf-8').splitlines()[-1])['tag'], 'END')
            with self.assertRaisesRegex(ValueError, 'VECTORS_REFUSE_OVERWRITE'):
                generate(out)


if __name__ == '__main__':
    unittest.main(verbosity=2)
