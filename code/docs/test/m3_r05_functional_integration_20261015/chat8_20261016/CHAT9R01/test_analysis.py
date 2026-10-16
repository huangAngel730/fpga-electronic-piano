"""Synthetic software tests only. No RTL/model/legacy test execution."""
import unittest

from analyze_existing import (FIELDS, REQUIRED, decode_event, missing_observations,
                              parse, program_predictions, require_integer_bit)


def synthetic(**values):
    word = 0
    for name, width in FIELDS:
        word = (word << width) | values.get(name, 0)
    return {'epoch': 0, 'event_data_hex': f'{word:016x}'}


class InputDeltaTests(unittest.TestCase):
    def test_actual_event_word_layout(self):
        d = decode_event('0011726000000000')
        self.assertEqual((d['event_type'], d['note_number'], d['velocity']), (0, 69, 806))

    def test_program_only_affects_later_prediction_not_observation(self):
        events = [synthetic(note_number=69, velocity=806),
                  synthetic(event_type=4, control_id=5, control_value=1),
                  synthetic(note_number=64, velocity=645)]
        out = program_predictions(events)
        self.assertEqual(out[0]['program_if_successfully_allocated'], 0)
        self.assertEqual(out[2]['program_if_successfully_allocated'], 1)
        self.assertIsNone(out[0]['program_observed_in_slot'])
        self.assertIsNone(out[2]['slot_identity'])

    def test_program_source_channel_and_reset_epoch_are_separate(self):
        events = [synthetic(event_type=4, control_id=5, control_value=1),
                  synthetic(source_id=1, note_number=64, velocity=1),
                  synthetic(channel=1, note_number=64, velocity=1),
                  synthetic(note_number=64, velocity=1) | {'epoch': 1}]
        self.assertEqual([r['program_if_successfully_allocated']
                          for r in program_predictions(events)[1:]], [0, 0, 0])

    def test_other_program_ignored_and_zero_velocity_not_new_note(self):
        out = program_predictions([
            synthetic(event_type=4, control_id=5, control_value=2),
            synthetic(note_number=64, velocity=0)])
        self.assertEqual(out[0]['meaning'], 'IGNORED_PROGRAM')
        self.assertNotIn('program_if_successfully_allocated', out[1])

    def test_bad_event_hex_and_reserved_rejected(self):
        for text in ['0', '0' * 15 + 'x', '0' * 15 + '1', True]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                decode_event(text)

    def test_duplicate_json_rejected(self):
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_KEY'):
            parse('{"event_valid":0,"event_valid":1}')

    def test_non_binary_flags_rejected(self):
        for value in [2, -1, '1', True, 1.0, None]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'NON_BINARY_FLAG'):
                require_integer_bit(value)
        require_integer_bit(0)
        require_integer_bit(1)

    def test_summary_counts_or_harmonics_never_prove_four_voices(self):
        result = missing_observations(['active_voice_count', 'nonzero', 'spectral_peaks',
                                       'left', 'right', 'clipped', 'commit'])
        self.assertTrue(result['four_independent_voices']['missing_proposed_observations'])
        self.assertTrue(result['effect_history']['missing_proposed_observations'])
        self.assertTrue(all(r['status'].startswith('UNKNOWN') for r in result.values()))

    def test_even_complete_header_is_not_mathematical_pass(self):
        fields = set().union(*map(set, REQUIRED.values()))
        result = missing_observations(fields)
        self.assertTrue(all(not r['missing_proposed_observations'] for r in result.values()))
        self.assertTrue(all(r['status'].startswith('UNKNOWN') for r in result.values()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
