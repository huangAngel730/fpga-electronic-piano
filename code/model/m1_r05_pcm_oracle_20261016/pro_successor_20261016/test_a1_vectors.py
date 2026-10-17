"""A1 adapter increment only; none of the inherited test suites run here."""
import copy
import unittest

from a1_vectors import (PENDING, SAMPLE_COUNT, SCENES, build_bundle,
                        validate_bundle)


class ProA1IncrementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = build_bundle()

    def changed(self):
        return copy.deepcopy(self.bundle)

    @staticmethod
    def row(bundle, name='all4', index=32):
        return bundle['scenes'][name]['expected'][index]

    def test_positive_five_synthetic_scenes_and_zero_tolerance(self):
        report = validate_bundle(self.bundle)
        self.assertEqual((report['scenes'], report['samples_per_scene'],
                          report['total_samples']), (5, SAMPLE_COUNT, 1280))
        self.assertEqual(set(self.bundle['scenes']), set(SCENES))
        self.assertEqual(report['tolerance_pcm_lsb'], 0)
        self.assertEqual(report['actual_dut_result'], PENDING)
        self.assertFalse(report['real_capture_nonzero_clip_coverage_claimed'])
        self.assertTrue(all(value > 0 for value in
                            report['effect_nonzero_history_rows'].values()))

    def test_each_original_input_identity_field_rejects_before_pcm(self):
        for field, wrong in (('scene_id', 'solo60'), ('source', 1),
                             ('channel', 1), ('note', 71), ('generation', 2)):
            with self.subTest(field=field):
                bundle = self.changed()
                row = self.row(bundle)
                original_pcm = row['left']
                row['lanes'][2]['input_identity'][field] = wrong
                self.assertEqual(row['left'], original_pcm)
                with self.assertRaisesRegex(ValueError, 'PRO_A1_INPUT_IDENTITY:all4:32:2'):
                    validate_bundle(bundle)

    def test_boolean_generation_and_extra_identity_field_reject(self):
        for modification in ('bool', 'extra'):
            with self.subTest(modification=modification):
                bundle = self.changed()
                identity = self.row(bundle)['lanes'][1]['input_identity']
                if modification == 'bool':
                    identity['generation'] = True
                else:
                    identity['capture_authentic'] = True
                with self.assertRaisesRegex(ValueError, 'PRO_A1_INPUT_IDENTITY'):
                    validate_bundle(bundle)

    def test_empty_lane_cannot_claim_note_identity(self):
        bundle = self.changed()
        solo = self.row(bundle, 'solo60')
        self.assertIsNone(solo['lanes'][3]['input_identity'])
        solo['lanes'][3]['input_identity'] = dict(
            scene_id='solo60', source=0, channel=0, note=70, generation=1)
        with self.assertRaisesRegex(ValueError, 'PRO_A1_INPUT_IDENTITY'):
            validate_bundle(bundle)

    def test_wrong_lane_and_swapped_lane_payloads_reject(self):
        for modification in ('lane', 'payload'):
            with self.subTest(modification=modification):
                bundle = self.changed()
                lanes = self.row(bundle)['lanes']
                if modification == 'lane':
                    lanes[2]['lane'] = 3
                    expected = 'PRO_A1_LANE_ORDER'
                else:
                    lanes[1], lanes[2] = lanes[2], lanes[1]
                    expected = 'PRO_A1_INPUT_IDENTITY'
                with self.assertRaisesRegex(ValueError, expected):
                    validate_bundle(bundle)

    def test_wrong_timbre_rejects_with_unchanged_pcm(self):
        bundle = self.changed()
        lane = self.row(bundle)['lanes'][1]
        self.assertEqual(lane['timbre'], 1)
        lane['timbre'] = 0
        with self.assertRaisesRegex(ValueError, 'SOLO_CHORD_PHASE_OR_FCW:all4:timbre'):
            validate_bundle(bundle)

    def test_wrong_public_clip_false_to_true_rejects(self):
        bundle = self.changed()
        row = next(row for row in bundle['scenes']['all4']['expected']
                   if row['clipped'][0] is False)
        row['clipped'][0] = True
        with self.assertRaisesRegex(ValueError, 'SOLO_CHORD_CLIP_METADATA:all4:clipped'):
            validate_bundle(bundle)

    def test_left_and_right_one_lsb_faults_reject(self):
        for channel in ('left', 'right'):
            with self.subTest(channel=channel):
                bundle = self.changed()
                self.row(bundle)[channel] += 1
                with self.assertRaisesRegex(ValueError, 'SOLO_CHORD_INDEPENDENT_DELAY_HISTORY:all4:' + channel):
                    validate_bundle(bundle)

    def test_mix_history_wrong_voice_or_sum_rejects(self):
        for field in ('voice_pcm24', 'sum_before_saturation'):
            with self.subTest(field=field):
                bundle = self.changed()
                history = self.row(bundle)['mix_history']
                if field == 'voice_pcm24':
                    history[field][3] += 256
                else:
                    history[field] += 1
                with self.assertRaisesRegex(ValueError, 'PRO_A1_MIX_HISTORY:all4:32'):
                    validate_bundle(bundle)

    def test_effect_history_wrong_scene_read_write_and_one_lsb_reject(self):
        for field, wrong in (('scene_id', 'solo70'), ('delayed_source_request_id', 32),
                             ('write_pointer_before', 33), ('write_pointer_after', 34),
                             ('read_pointer', 32), ('channel', 'right')):
            with self.subTest(field=field):
                bundle = self.changed()
                self.row(bundle)['effect_history'][0][field] = wrong
                with self.assertRaisesRegex(ValueError, 'PRO_A1_EFFECT_HISTORY:all4:32'):
                    validate_bundle(bundle)
        for field in ('delayed_pcm24', 'output_pcm24', 'feedback_buffer_written_pcm24'):
            with self.subTest(field=field):
                bundle = self.changed()
                self.row(bundle)['effect_history'][0][field] += 1
                with self.assertRaisesRegex(ValueError, 'PRO_A1_EFFECT_HISTORY:all4:32'):
                    validate_bundle(bundle)

    def test_effect_history_wrong_clip_rejects(self):
        bundle = self.changed()
        history = self.row(bundle)['effect_history'][1]
        history['final_clip'] = not history['final_clip']
        with self.assertRaisesRegex(ValueError, 'PRO_A1_EFFECT_HISTORY:all4:32'):
            validate_bundle(bundle)

    def test_scene_history_is_independently_reset_and_tracks_mixed_pcm(self):
        for name in SCENES:
            rows = self.bundle['scenes'][name]['expected']
            first = rows[0]['effect_history']
            self.assertTrue(all(item['write_pointer_before'] == 0 and
                                item['delayed_pcm24'] == 0 and
                                item['delayed_source_request_id'] is None
                                for item in first))
            row = rows[32]
            for index, channel in enumerate(('left', 'right')):
                history = row['effect_history'][index]
                self.assertEqual(history['delayed_pcm24'], rows[31]['mixed_' + channel])
                self.assertEqual(history['output_pcm24'], row[channel])

    def test_four_effected_solos_cannot_replace_chord(self):
        report = validate_bundle(self.bundle)
        witness = report['final_solo_sum_counterexample']
        self.assertIsNotNone(witness)
        self.assertNotEqual(witness['sum_solo_effected_left'], witness['all4_effected_left'])
        bundle = self.changed()
        row = self.row(bundle, index=witness['request_id'])
        row['left'] = witness['sum_solo_effected_left']
        with self.assertRaisesRegex(ValueError, 'SOLO_CHORD_INDEPENDENT_DELAY_HISTORY:all4:left'):
            validate_bundle(bundle)

    def test_pro_identity_and_evidence_cannot_be_promoted(self):
        for field in ('pro_top_sha256', 'pro_reset_contract', 'pro_rom_role_mapping'):
            with self.subTest(field=field):
                bundle = self.changed()
                bundle['pro_identity'][field] = 'UNVERIFIED'
                with self.assertRaisesRegex(ValueError, 'PRO_A1_BUNDLE_IDENTITY:pro_identity'):
                    validate_bundle(bundle)
        bundle = self.changed()
        bundle['actual_dut_result'] = 'PASS'
        with self.assertRaisesRegex(ValueError, 'PRO_A1_BUNDLE_IDENTITY:actual_dut_result'):
            validate_bundle(bundle)


if __name__ == '__main__':
    unittest.main(verbosity=2)
