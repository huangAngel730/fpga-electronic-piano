"""New B0 adapter cases only; no old suite, RTL, EDA, or device execution."""
from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import capture_compare as cc


def document(schema, rows):
    return {'schema': schema, 'origin': 'SYNTHETIC_FIXTURE',
            'producer': 'B0_SYNTHETIC_FIXTURE', 'capture_id': 'B0_FOUR_VOICE_FIXTURE',
            'scene': 'four_different_notes_with_cancel_and_reset',
            'declared_count': len(rows), 'rows': rows}


def make_fixture(directory):
    """Explicit synthetic applications/ticks; use the signed Reference once.

    These generated public rows are acceptance fixtures for this parser, not an
    independent test of the already signed arithmetic and never a DUT capture.
    """
    ref = cc.reference_class()()
    calendar, public = [], []

    def action(cycle, kind, payload):
        calendar.append({'seq': len(calendar), 'cycle': cycle, 'epoch': ref.epoch,
                         'kind': kind, 'payload': payload})

    def event(cycle, kind, source=1, channel=0, note=60, velocity=0, program=0):
        applied = ref.event(cycle, kind, source, channel, note, velocity, program)
        payload = {'event': kind, 'source': source, 'channel': channel, 'note': note,
                   'velocity10': velocity, 'program': program,
                   'decision': applied['decision'], 'lane': applied.get('lane'),
                   'generation': applied.get('generation')}
        action(cycle, 'event', payload)

    def tick(cycle, rid, accepted=True, publish=True):
        sample = ref.sample(cycle, rid, accepted, publish)
        ident = cc.expected_identities(sample)
        action(cycle, 'lane_tick', {'request_id': rid, 'identities': ident,
                                   'lane_cycles': [{'lane': i, 'cycle': cycle} for i in range(4)]})
        if accepted:
            action(cycle + 7, 'effect_accept', {'request_id': rid, 'publish': publish,
                                              'publish_cycle': cycle + 8 if publish else None})
        if not publish:
            action(cycle + (8 if accepted else 6), 'cancel',
                   {'request_id': rid, 'reason': 'synthetic_unpublished_work'})
        else:
            public.append({'seq': len(public), 'cycle': cycle + 8, 'epoch': ref.epoch,
                           'request_id': rid, 'identities': copy.deepcopy(ident),
                           'left': sample['left'], 'right': sample['right'], 'clip': sample['clipped']})

    action(0, 'reset', {})
    ref.config_accept(16, True, 1, 32767, 16384, 8192)
    action(16, 'config_accept', {'enable': True, 'length': 1, 'dry': 32767,
                                'wet': 16384, 'feedback': 8192})
    event(32, 'program', program=0)
    event(48, 'note_on', note=60, velocity=1023)
    event(64, 'program', source=2, channel=1, program=1)
    event(80, 'note_on', source=2, channel=1, note=63, velocity=900)
    event(96, 'note_on', source=3, channel=2, note=67, velocity=800)
    event(112, 'note_on', source=4, channel=3, note=70, velocity=700)
    tick(160, 0)
    tick(993, 1, publish=False)
    tick(1826, 2, accepted=False, publish=False)
    event(1920, 'note_off', note=60)
    tick(2659, 3)
    ref.reset(3000)
    action(3000, 'reset', {})
    event(3016, 'program', source=7, channel=5, program=1)
    event(3032, 'note_on', source=7, channel=5, note=72, velocity=650)
    tick(3100, 0)
    tick(3933, 1)
    cal = document('M1_PRO_INDEPENDENT_CALENDAR_V1', calendar)
    pcm = document('M1_PRO_PUBLIC_PCM_V1', public)
    manifest = {'schema': 'M1_PRO_CAPTURE_BUNDLE_V1', 'mode': 'SYNTHETIC',
                'capture_id': cal['capture_id'], 'scene': cal['scene'], 'profile': cc.PROFILE,
                'reference': cc.signed_reference_bindings(), 'calendar': None,
                'public_pcm': None, 'pro_binding': None, 'counts': {}}
    return save_fixture(directory, manifest, cal, pcm)


def save_fixture(directory, manifest, calendar, public, recalculate_counts=True):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, doc in [('calendar', calendar), ('public_pcm', public)]:
        path = directory / (name + '.json')
        path.write_text(json.dumps(doc, sort_keys=True, indent=2) + '\n', encoding='utf-8', newline='\n')
        manifest[name] = {'path': path.name, 'bytes': path.stat().st_size, 'sha256': cc.digest(path)}
    if recalculate_counts:
        manifest['counts'] = dict.fromkeys(cc.COUNTS, 0)
        manifest['counts']['calendar_rows'] = len(calendar['rows'])
        manifest['counts']['public_pcm_rows'] = len(public['rows'])
        keys = {'reset': 'resets', 'event': 'events', 'lane_tick': 'lane_ticks',
                'effect_accept': 'effect_accepts', 'config_accept': 'config_accepts', 'cancel': 'cancels'}
        for row in calendar['rows']:
            manifest['counts'][keys[row['kind']]] += 1
    path = directory / 'bundle.json'
    path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n', encoding='utf-8', newline='\n')
    return path


class CaptureCompareTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='m1_pro_b0_')
        self.directory = Path(self.temporary.name)
        self.manifest_path = make_fixture(self.directory)
        self.manifest = cc.read_json(self.manifest_path)
        self.calendar = cc.read_json(self.directory / 'calendar.json')
        self.public = cc.read_json(self.directory / 'public_pcm.json')

    def tearDown(self):
        self.temporary.cleanup()

    def save(self, recalculate_counts=True):
        return save_fixture(self.directory, self.manifest, self.calendar, self.public, recalculate_counts)

    def compare(self):
        return cc.compare_bundle(self.save())

    def reject(self, fragment):
        with self.assertRaisesRegex(cc.ContractError, fragment):
            self.compare()

    def test_accepts_four_voice_cancel_unaccepted_work_reset_and_reused_id(self):
        result = self.compare()
        self.assertEqual(result['status'], 'SYNTHETIC_FIXTURE_PASS')
        self.assertEqual(result['identity_check'], 'PASS')
        self.assertEqual(result['zero_lsb_check'], 'PASS')
        self.assertEqual(result['compared_public_samples'], 4)
        self.assertEqual(result['calendar_counts']['lane_ticks'], 6)
        self.assertEqual(result['calendar_counts']['effect_accepts'], 5)
        self.assertFalse(result['rtl_or_board_pass'])
        self.assertFalse(result['board_release_allowed'])

    def test_static_original_fixture_accepts(self):
        path = cc.ROOT / 'code/docs/test/m1_r05_pcm_oracle_20261016/pro_successor_20261016/B0/fixtures/synthetic_idle.bundle.json'
        self.assertEqual(cc.compare_bundle(path)['status'], 'SYNTHETIC_FIXTURE_PASS')

    def test_all_identities_checked_before_first_pcm_difference(self):
        self.public['rows'][0]['left'] += 1
        self.public['rows'][-1]['identities'][0]['generation'] += 1
        self.reject('PUBLIC_SOURCE_CHANNEL_NOTE_GENERATION_IDENTITY_MISMATCH')

    def test_wrong_source_channel_note_generation_lane_each_rejects(self):
        original = copy.deepcopy(self.public)
        for field, value in [('source', 9), ('channel', 9), ('note', 61), ('generation', 2), ('lane', 1)]:
            with self.subTest(field=field):
                self.public = copy.deepcopy(original)
                self.public['rows'][0]['identities'][0][field] = value
                self.reject('IDENTITY_MISMATCH|LANE_ORDER')

    def test_event_slot_and_generation_reject_before_pcm(self):
        row = next(row for row in self.calendar['rows'] if row['kind'] == 'event' and row['payload']['event'] == 'note_on')
        row['payload']['generation'] += 1
        self.reject('EVENT_SLOT_OR_GENERATION_IDENTITY_MISMATCH')

    def test_calendar_identity_does_not_come_from_dut_internal_state(self):
        row = next(row for row in self.calendar['rows'] if row['kind'] == 'lane_tick')
        row['payload']['identities'][0]['note'] += 1
        self.reject('LANE_TICK_SOURCE_NOTE_GENERATION_IDENTITY_MISMATCH')

    def test_one_lsb_and_clip_mismatches_report_expected_layers_without_invented_lane(self):
        original = copy.deepcopy(self.public)
        for field in ('left', 'right', 'clip'):
            with self.subTest(field=field):
                self.public = copy.deepcopy(original)
                if field == 'clip':
                    self.public['rows'][0]['clip'][0] = not self.public['rows'][0]['clip'][0]
                else:
                    self.public['rows'][0][field] += 1
                result = self.compare()
                self.assertEqual(result['status'], 'PCM_MISMATCH')
                report = result['first_difference']
                self.assertEqual(report['source'], [1, 2, 3, 4])
                self.assertIsNone(report['lane'])
                self.assertEqual(len(report['expected_layers']['lanes']), 4)
                self.assertIn('mix', report['expected_layers'])
                self.assertIn('fx', report['expected_layers'])
                self.assertIn('cannot uniquely attribute', report['attribution'])

    def test_optional_internal_observations_are_actual_only(self):
        self.public['rows'][0]['diagnostics'] = {'lanes': [{'lane': 0, 'wave16': -123, 'env_q15': 17}],
                                                  'mixed_left': 123, 'fx_left': -999}
        self.assertEqual(self.compare()['status'], 'SYNTHETIC_FIXTURE_PASS')
        self.public['rows'][0]['left'] += 1
        result = self.compare()
        self.assertEqual(result['status'], 'PCM_MISMATCH')
        self.assertEqual(result['first_difference']['actual_internal_diagnostics']['fx_left'], -999)
        self.assertNotEqual(result['first_difference']['expected_layers']['fx']['left'], -999)
        self.assertEqual(result['first_difference']['observed_layer'], 'wave16')
        self.assertEqual(result['first_difference']['lane'], 0)
        self.assertEqual(result['first_difference']['source'], 1)

    def test_observed_layer_uses_lane_order_then_mix_then_fx_without_changing_golden(self):
        row = self.public['rows'][0]
        row['left'] += 1
        row['diagnostics'] = {'lanes': [{'lane': 2, 'env_q15': 32767}, {'lane': 0, 'timbre': 1}],
                              'mixed_left': -8388608, 'fx_right': -8388608}
        report = self.compare()['first_difference']
        self.assertEqual((report['observed_layer'], report['lane'], report['source']), ('timbre', 0, 1))
        row['diagnostics'].pop('lanes')
        report = self.compare()['first_difference']
        self.assertEqual(report['observed_layer'], 'mixed_left')
        self.assertIsNone(report['lane'])
        row['diagnostics'].pop('mixed_left')
        self.assertEqual(self.compare()['first_difference']['observed_layer'], 'fx_right')

    def test_removing_unpublished_accepted_work_changes_later_pcm(self):
        self.calendar['rows'] = [row for row in self.calendar['rows']
                                 if not (row['epoch'] == 0 and row['kind'] in ('lane_tick', 'effect_accept', 'cancel')
                                         and row['payload']['request_id'] == 1)]
        for seq, row in enumerate(self.calendar['rows']):
            row['seq'] = seq
        self.calendar['declared_count'] = len(self.calendar['rows'])
        self.assertEqual(self.compare()['status'], 'PCM_MISMATCH')

    def test_removing_unaccepted_advance_changes_later_pcm(self):
        self.calendar['rows'] = [row for row in self.calendar['rows']
                                 if not (row['epoch'] == 0 and row['kind'] in ('lane_tick', 'cancel')
                                         and row['payload']['request_id'] == 2)]
        for seq, row in enumerate(self.calendar['rows']):
            row['seq'] = seq
        self.calendar['declared_count'] = len(self.calendar['rows'])
        self.assertEqual(self.compare()['status'], 'PCM_MISMATCH')

    def test_rejects_staggered_or_missing_lane_tick(self):
        row = next(row for row in self.calendar['rows'] if row['kind'] == 'lane_tick')
        row['payload']['lane_cycles'][2]['cycle'] += 1
        self.reject('UNSUPPORTED_STAGGER')
        row['payload']['lane_cycles'].pop()
        self.reject('EVERY_LANE_TICK_REQUIRED')

    def test_rejects_same_edge_and_nonsettled_event(self):
        rows = self.calendar['rows']
        index = next(i for i, row in enumerate(rows) if row['kind'] == 'lane_tick')
        rows[index]['cycle'] = rows[index - 1]['cycle']
        self.reject('SAME_EDGE')

    def test_rejects_config_during_reference_pipeline(self):
        rows = self.calendar['rows']
        config = copy.deepcopy(next(row for row in rows if row['kind'] == 'config_accept'))
        config['cycle'] = 165
        index = next(i for i, row in enumerate(rows) if row['kind'] == 'effect_accept')
        rows.insert(index, config)
        for seq, row in enumerate(rows):
            row['seq'] = seq
        self.calendar['declared_count'] = len(rows)
        self.reject('SIGNED_SETTLED_PROFILE_REJECTED')

    def test_rejects_effect_earlier_than_advance_plus_seven(self):
        row = next(row for row in self.calendar['rows'] if row['kind'] == 'effect_accept')
        row['cycle'] -= 1
        self.reject('EFFECT_ACCEPT_BEFORE_SIGNED_PIPELINE')

    def test_rejects_missing_cancel(self):
        row = next(row for row in self.calendar['rows'] if row['kind'] == 'cancel')
        self.calendar['rows'].remove(row)
        for seq, item in enumerate(self.calendar['rows']):
            item['seq'] = seq
        self.calendar['declared_count'] -= 1
        self.reject('CANCEL_AND_PUBLICATION_INCONSISTENT')

    def test_duplicate_request_action_rejects(self):
        rows = self.calendar['rows']
        second = next(row for row in rows if row['kind'] == 'lane_tick' and row['payload']['request_id'] == 1)
        second['payload']['request_id'] = 0
        self.reject('DUPLICATE_REQUEST_ACTION')

    def test_wrong_epoch_public_id_cycle_and_scene_reject(self):
        original = copy.deepcopy(self.public)
        for field, value in [('epoch', 2), ('request_id', 99), ('cycle', 169)]:
            with self.subTest(field=field):
                self.public = copy.deepcopy(original)
                self.public['rows'][0][field] = value
                self.reject('PUBLIC_ID_EPOCH_OR_CYCLE')
        self.public = original
        self.public['scene'] = 'different_scene'
        self.reject('CAPTURE_OR_SCENE_MISMATCH')

    def test_missing_fields_wrong_types_unknown_fields_reject(self):
        original = copy.deepcopy(self.public)
        for mutation, error in [('missing', 'MISSING_FIELDS'), ('boolean', 'INTEGER_RANGE'),
                                ('float', 'NONINTEGER_JSON_NUMBER'), ('clipint', 'BOOL_REQUIRED'),
                                ('unknown', 'UNKNOWN_FIELDS')]:
            with self.subTest(mutation=mutation):
                self.public = copy.deepcopy(original)
                row = self.public['rows'][0]
                if mutation == 'missing':
                    del row['request_id']
                elif mutation == 'boolean':
                    row['left'] = True
                elif mutation == 'float':
                    row['left'] = 1.0
                elif mutation == 'clipint':
                    row['clip'][0] = 0
                else:
                    row['golden_wave_from_dut'] = 1
                self.reject(error)

    def test_sequence_and_declared_count_reject(self):
        self.public['rows'][0]['seq'] = 1
        self.reject('ROW_SEQUENCE_GAP_OR_DUPLICATE')
        self.public['rows'][0]['seq'] = 0
        self.public['declared_count'] += 1
        self.reject('DECLARED_COUNT_MISMATCH')

    def test_manifest_counts_reject_even_with_valid_file_hashes(self):
        self.manifest['counts']['lane_ticks'] += 1
        path = self.save(recalculate_counts=False)
        with self.assertRaisesRegex(cc.ContractError, 'BUNDLE_COUNTS_MISMATCH'):
            cc.compare_bundle(path)

    def test_original_sha_and_size_mismatch_reject_without_rewriting_original(self):
        before = (self.directory / 'calendar.json').read_bytes()
        self.manifest['calendar']['sha256'] = '0' * 64
        self.manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')
        with self.assertRaisesRegex(cc.ContractError, 'ORIGINAL_FILE_SHA_OR_SIZE_MISMATCH'):
            cc.compare_bundle(self.manifest_path)
        self.assertEqual((self.directory / 'calendar.json').read_bytes(), before)

    def test_reference_binding_and_frozen_pin_drift_reject(self):
        self.manifest['reference']['frozen_files']['frozen/rom/triangle_wavetable.hex'] = '0' * 64
        self.reject('SIGNED_REFERENCE_BINDING_MISMATCH')
        changed = dict(cc.PINNED, **{'oracle.py': '0' * 64})
        with mock.patch.object(cc, 'PINNED', changed):
            with self.assertRaisesRegex(cc.ContractError, 'SIGNED_REFERENCE_DRIFT'):
                cc.signed_reference_bindings()

    def test_duplicate_json_keys_and_nan_reject(self):
        for contents, error in [('{"key":1,"key":2}', 'DUPLICATE_JSON_KEY'),
                                ('{"nested":{"generation":1,"generation":2}}', 'DUPLICATE_JSON_KEY'),
                                ('{"left":NaN}', 'NONINTEGER_JSON_NUMBER')]:
            with self.subTest(contents=contents):
                path = self.directory / 'bad.json'
                path.write_text(contents, encoding='utf-8')
                with self.assertRaisesRegex(cc.ContractError, error):
                    cc.read_json(path)

    def test_bundle_paths_cannot_escape_or_use_absolute_paths(self):
        for value in ('../calendar.json', str(self.directory / 'calendar.json')):
            with self.subTest(value=value):
                self.manifest['calendar']['path'] = value
                self.manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')
                with self.assertRaisesRegex(cc.ContractError, 'ARTIFACT_PATH'):
                    cc.compare_bundle(self.manifest_path)

    def test_only_changing_mode_never_promotes_synthetic_origin_to_real(self):
        self.manifest['mode'] = 'REAL'
        self.reject('SCHEMA_OR_ORIGIN_MISMATCH')

    def test_current_real_inputs_without_signed_pro_mapping_stay_pending(self):
        self.manifest['mode'] = 'REAL'
        self.calendar.update(origin='M3_INDEPENDENT_APPLIED_CALENDAR', producer='M3')
        self.public.update(origin='REAL_DUT_PUBLIC_CAPTURE', producer='DUT_PUBLIC_CAPTURE')
        result = self.compare()
        self.assertEqual(result['status'], 'PENDING_REAL_CAPTURE')
        self.assertEqual(result['zero_lsb_check'], 'PASS')
        self.assertFalse(result['rtl_or_board_pass'])
        self.assertIn('PRO_TOP_SOURCE_SHA_MISSING', result['missing_real_requirements'])
        self.assertIn('PRO_ASYNC_RESET_EDGES_NOT_COVERED_BY_SETTLED_PROFILE', result['missing_real_requirements'])

    def test_missing_real_calendar_and_public_files_are_pending_not_fixture_pass(self):
        self.manifest.update(mode='REAL', calendar=None, public_pcm=None, counts=None)
        self.manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')
        result = cc.compare_bundle(self.manifest_path)
        self.assertEqual(result['status'], 'PENDING_REAL_CAPTURE')
        self.assertEqual(result['zero_lsb_check'], 'NOT_RUN')
        self.assertEqual(result['compared_public_samples'], 0)

    def test_supplied_malformed_public_is_not_hidden_by_missing_real_calendar(self):
        self.manifest['mode'] = 'REAL'
        self.public.update(origin='REAL_DUT_PUBLIC_CAPTURE', producer='DUT_PUBLIC_CAPTURE')
        self.public['rows'][0]['left'] = True
        self.save()
        self.manifest['calendar'] = None
        self.manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')
        with self.assertRaisesRegex(cc.ContractError, 'INTEGER_RANGE'):
            cc.compare_bundle(self.manifest_path)

    def test_report_refuses_overwrite_and_cli_distinguishes_pending_rejection_and_pass(self):
        report = self.directory / 'result.json'
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(cc.main(['--manifest', str(self.manifest_path), '--out', str(report)]), 0)
            before = report.read_bytes()
            self.assertEqual(cc.main(['--manifest', str(self.manifest_path), '--out', str(report)]), 2)
            self.assertEqual(report.read_bytes(), before)
            self.manifest.update(mode='REAL', calendar=None, public_pcm=None, counts=None)
            self.manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')
            self.assertEqual(cc.main(['--manifest', str(self.manifest_path), '--out', str(self.directory / 'pending.json')]), 3)
            self.manifest['profile'] = 'staggered'
            self.manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')
            self.assertEqual(cc.main(['--manifest', str(self.manifest_path), '--out', str(self.directory / 'rejected.json')]), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
