"""New paired Program semantics only; no old 13/12/50-test entry is invoked."""
import copy
import unittest

from timbre_switch_pairs_R01 import SCENES, build_pairs, validate_pairs


class TimbrePairIncrementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pairs = build_pairs()

    def altered(self):
        return copy.deepcopy(self.pairs)

    def test_fixed_pair_has_actual_software_differences_and_restore(self):
        report = validate_pairs(self.pairs)
        self.assertEqual((report['scenes'], report['total_samples']), (2, 512))
        self.assertEqual(set(self.pairs), set(SCENES))
        self.assertEqual(len(report['witnesses']), 4)
        self.assertNotEqual(report['effect_output_difference']['control_left'],
                            report['effect_output_difference']['switched_left'])
        self.assertEqual(report['mixed_equal_from_sample'], 176)
        self.assertEqual(report['effected_equal_from_sample'], 177)
        for witness in report['witnesses'].values():
            self.assertNotEqual(witness['control_lane2']['wave16'], witness['switched_lane2']['wave16'])
            self.assertNotEqual(witness['control_lane2']['voice_pcm24'], witness['switched_lane2']['voice_pcm24'])

    def test_missing_or_swapped_scene_rejects(self):
        pairs = self.altered()
        del pairs['control_pc0']
        with self.assertRaisesRegex(ValueError, 'EXACT_TWO_SCENES'):
            validate_pairs(pairs)
        pairs = self.altered()
        pairs['control_pc0'], pairs['switch_ch0_pc1'] = pairs['switch_ch0_pc1'], pairs['control_pc0']
        with self.assertRaisesRegex(ValueError, 'SCENE_IDENTITY'):
            validate_pairs(pairs)

    def test_program_change_does_not_rewrite_existing_nonzero_note(self):
        pairs = self.altered()
        row = next(row for row in pairs['switch_ch0_pc1']['expected'][64:80]
                   if row['lanes'][0]['voice_pcm24'])
        self.assertEqual(row['lanes'][0]['timbre'], 0)
        row['lanes'][0]['timbre'] = 1
        with self.assertRaisesRegex(ValueError, 'HELD_TIMBRE_OR_CHANNEL_ISOLATION'):
            validate_pairs(pairs)

    def test_channel1_new_note_does_not_take_channel0_program(self):
        pairs = self.altered()
        row = next(row for row in pairs['switch_ch0_pc1']['expected'][96:]
                   if row['lanes'][3]['voice_pcm24'])
        self.assertEqual(row['lanes'][3]['identity'], [0, 1, 70, 'active'])
        row['lanes'][3]['timbre'] = 1
        with self.assertRaisesRegex(ValueError, 'HELD_TIMBRE_OR_CHANNEL_ISOLATION'):
            validate_pairs(pairs)

    def test_pc127_cannot_select_triangle_in_control_retrigger(self):
        pairs = self.altered()
        row = pairs['control_pc0']['expected'][128]
        self.assertEqual(row['lanes'][2]['generation'], 2)
        self.assertEqual(row['lanes'][2]['timbre'], 0)
        row['lanes'][2]['timbre'] = 1
        with self.assertRaisesRegex(ValueError, 'HELD_TIMBRE_OR_CHANNEL_ISOLATION'):
            validate_pairs(pairs)

    def test_pc127_decision_must_be_explicitly_ignored(self):
        pairs = self.altered()
        decision = next(row for row in pairs['switch_ch0_pc1']['event_decisions']
                        if row['kind'] == 'program' and row['program'] == 127)
        decision['decision'] = 'program'
        with self.assertRaisesRegex(ValueError, 'PC127_IGNORED'):
            validate_pairs(pairs)

    def test_pc0_preserves_held_triangle_before_retrigger(self):
        pairs = self.altered()
        row = pairs['switch_ch0_pc1']['expected'][160]
        self.assertEqual(row['lanes'][2]['timbre'], 1)
        self.assertEqual(row['lanes'][2]['generation'], 2)
        row['lanes'][2]['timbre'] = 0
        with self.assertRaisesRegex(ValueError, 'HELD_TIMBRE_OR_CHANNEL_ISOLATION'):
            validate_pairs(pairs)

    def test_retrigger_cannot_zero_phase_or_skip_generation(self):
        for field, wrong in (('phase_before', 0), ('generation', 2)):
            with self.subTest(field=field):
                pairs = self.altered()
                lane = pairs['switch_ch0_pc1']['expected'][176]['lanes'][2]
                self.assertNotEqual(lane[field], wrong)
                lane[field] = wrong
                with self.assertRaisesRegex(ValueError, 'GENERATION_FCW_OR_PHASE'):
                    validate_pairs(pairs)

    def test_triangle_window_cannot_reuse_control_piano_contribution(self):
        pairs = self.altered()
        witness = validate_pairs(self.pairs)['witnesses']['held_through_pc0']
        index = witness['sample']
        before = pairs['control_pc0']['expected'][index]['lanes'][2]['voice_pcm24']
        after = pairs['switch_ch0_pc1']['expected'][index]['lanes'][2]
        self.assertNotEqual(before, after['voice_pcm24'])
        after['voice_pcm24'] = before
        with self.assertRaisesRegex(ValueError, 'FROZEN_GAIN_MATH'):
            validate_pairs(pairs)

    def test_changed_result_cannot_be_hidden_by_program_metadata(self):
        pairs = self.altered()
        witness = validate_pairs(self.pairs)['effect_output_difference']
        index = witness['sample']
        row = pairs['switch_ch0_pc1']['expected'][index]
        self.assertNotEqual(row['left'], pairs['control_pc0']['expected'][index]['left'])
        row['left'] = pairs['control_pc0']['expected'][index]['left']
        with self.assertRaisesRegex(ValueError, 'FROZEN_EFFECT_RESULT'):
            validate_pairs(pairs)

    def test_restore_window_wrong_right_output_rejects(self):
        pairs = self.altered()
        row = pairs['switch_ch0_pc1']['expected'][177]
        self.assertEqual(row['right'], pairs['control_pc0']['expected'][177]['right'])
        row['right'] += 1
        with self.assertRaisesRegex(ValueError, 'FROZEN_EFFECT_RESULT'):
            validate_pairs(pairs)

    def test_shifted_application_cycle_or_missing_sample_rejects(self):
        pairs = self.altered()
        program = next(row for row in pairs['switch_ch0_pc1']['stimulus']['rows']
                       if row['kind'] == 'program' and row['program'] == 1)
        program['cycle'] += 1
        with self.assertRaisesRegex(ValueError, 'FIXED_INPUT_CALENDAR'):
            validate_pairs(pairs)
        pairs = self.altered()
        pairs['control_pc0']['expected'].pop()
        with self.assertRaisesRegex(ValueError, 'FIXED_ROW_COUNT'):
            validate_pairs(pairs)


if __name__ == '__main__':
    unittest.main(verbosity=2)
