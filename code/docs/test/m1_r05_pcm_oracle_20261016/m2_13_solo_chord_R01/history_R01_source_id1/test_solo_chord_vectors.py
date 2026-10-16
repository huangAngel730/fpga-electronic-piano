"""Only the new five-scene mapping increment; no old test mains are run."""
import copy
import unittest

from solo_chord_vectors import PARTS, SCENES, build_bundle, validate_bundle


class SoloChordIncrementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = build_bundle()

    def altered(self):
        return copy.deepcopy(self.bundle)

    def test_five_matched_scenes_and_mapped_contributions(self):
        report = validate_bundle(self.bundle)
        self.assertEqual((report['scene_count'], report['total_samples']), (5, 1280))
        self.assertEqual(set(report['coverage']), set(SCENES))
        self.assertTrue(all(all(row['selected_lane_nonzero_rows'])
                            for row in report['coverage'].values()))
        for lane, part in enumerate(PARTS):
            solo = self.bundle['solo' + str(part[0])]['expected'][32]
            chord = self.bundle['all4']['expected'][32]
            self.assertEqual(solo['lanes'][0]['identity'], chord['lanes'][lane]['identity'])
            self.assertEqual(solo['lanes'][0]['voice_pcm24'], chord['lanes'][lane]['voice_pcm24'])

    def test_missing_solo_scene_rejects(self):
        bundle = self.altered()
        del bundle['solo70']
        with self.assertRaisesRegex(ValueError, 'EXACT_FIVE_SCENES'):
            validate_bundle(bundle)

    def test_raw_midi_velocities_match_frozen_expansion(self):
        mappings = self.bundle['all4']['mapping']
        self.assertEqual([row['raw7'] for row in mappings], [127, 112, 96, 80])
        self.assertEqual([row['expanded10'] for row in mappings], [1023, 903, 774, 645])
        self.assertTrue(all(row['expanded10'] == ((row['raw7'] << 3) | (row['raw7'] >> 4))
                            for row in mappings))
        bundle = self.altered()
        bundle['solo63']['mapping'][0]['expanded10'] = 896
        with self.assertRaisesRegex(ValueError, 'NOTE_MAPPING'):
            validate_bundle(bundle)

    def test_swapped_scene_records_reject(self):
        bundle = self.altered()
        bundle['solo63'], bundle['solo70'] = bundle['solo70'], bundle['solo63']
        with self.assertRaisesRegex(ValueError, 'SCENE_IDENTITY'):
            validate_bundle(bundle)

    def test_wrong_identity_with_unchanged_nonzero_audio_rejects(self):
        bundle = self.altered()
        lane = bundle['solo67']['expected'][32]['lanes'][0]
        lane['identity'][2] = 70
        with self.assertRaisesRegex(ValueError, 'LANE_IDENTITY'):
            validate_bundle(bundle)

    def test_zero_fourth_contribution_with_four_identities_rejects(self):
        bundle = self.altered()
        row = next(row for row in bundle['all4']['expected'] if row['lanes'][3]['voice_pcm24'])
        self.assertEqual(sum(lane['identity'] is not None for lane in row['lanes']), 4)
        row['lanes'][3]['voice_pcm24'] = 0
        with self.assertRaisesRegex(ValueError, 'GAIN_FLOOR'):
            validate_bundle(bundle)

    def test_wrong_fcw_and_wrong_phase_reject_separately(self):
        for field in ('fcw', 'phase_after'):
            with self.subTest(field=field):
                bundle = self.altered()
                bundle['solo63']['expected'][32]['lanes'][0][field] += 1
                with self.assertRaisesRegex(ValueError, 'PHASE_OR_FCW'):
                    validate_bundle(bundle)

    def test_shifted_sample_calendar_rejects(self):
        bundle = self.altered()
        bundle['solo70']['expected'][1]['advance_cycle'] += 1
        with self.assertRaisesRegex(ValueError, 'SAMPLE_CALENDAR'):
            validate_bundle(bundle)

    def test_triangle_posttick_rom_sample_rejects(self):
        bundle = self.altered()
        lane = bundle['solo63']['expected'][0]['lanes'][0]
        from oracle import TRIANGLE
        wrong = TRIANGLE[lane['phase_after'] >> 22]
        self.assertNotEqual(lane['wave16'], wrong)
        lane['wave16'] = wrong
        with self.assertRaisesRegex(ValueError, 'ROM_SAMPLE'):
            validate_bundle(bundle)

    def test_four_final_solo_effects_are_not_chord_golden(self):
        report = validate_bundle(self.bundle)
        witness = report['final_solo_sum_counterexample']
        self.assertIsNotNone(witness, 'Fixed profile needs a non-vacuous rounding/history witness')
        self.assertNotEqual(witness['sum_solo_effected_left'], witness['all4_effected_left'])
        # Raw sum is the tempting incorrect replacement. The checker also
        # enforces PCM24 saturation independently, without assuming linearity.
        bundle = self.altered()
        rid = witness['request_id']
        row = bundle['all4']['expected'][rid]
        row['left'] = witness['sum_solo_effected_left']
        with self.assertRaisesRegex(ValueError, 'INDEPENDENT_DELAY_HISTORY'):
            validate_bundle(bundle)

    def test_current_input_used_as_delayed_history_rejects(self):
        bundle = self.altered()
        row = next(row for row in bundle['all4']['expected']
                   if row['left'] != max(-8388608, min(8388607,
                       (row['mixed_left'] * 32767 >> 15) + (row['mixed_left'] * 16384 >> 15))))
        wrong = max(-8388608, min(8388607,
                    (row['mixed_left'] * 32767 >> 15) + (row['mixed_left'] * 16384 >> 15)))
        self.assertNotEqual(row['left'], wrong)
        row['left'] = wrong
        with self.assertRaisesRegex(ValueError, 'INDEPENDENT_DELAY_HISTORY'):
            validate_bundle(bundle)


if __name__ == '__main__':
    unittest.main(verbosity=2)
