"""Synthetic oracle checks, explicitly not downloaded-input acceptance."""
import sys
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'score_midi_import_candidate_20261014'))
import midi_fixtures as f
from independent_oracle import expected_notes, smf_inventory, REAL_SHA
import hashlib


class OracleTests(unittest.TestCase):
    def test_real_identity_and_literal_counts(self):
        raw = (HERE / 'inputs/MIDI_sample_2018-03-21.mid').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), REAL_SHA)
        notes, origins, tempos = expected_notes(smf_inventory(raw))
        self.assertEqual((len(notes), notes[-1]['tick'], tempos), (44, 384000, []))
        self.assertTrue(all(n['channel'] == 4 and n['velocity'] == 96 for n in notes))
        self.assertEqual(origins[0]['file_byte_offset'], 98)

    def test_type1_tempo(self):
        raw = f.smf(f.tempo(0, 500000) + f.tempo(480, 1000000) + f.end(480),
                    f.note_on() + f.note_off(960) + f.end(),
                    f.note_on(480, note=67, velocity=90) + f.note_off(480, note=67, velocity=64) + f.end())
        notes, _, tempos = expected_notes(smf_inventory(raw))
        self.assertEqual([n['tick'] for n in notes], [0, 24000, 72000, 72000])
        self.assertEqual([n['note'] for n in notes], [60, 67, 60, 67])
        self.assertEqual([t['us_per_quarter'] for t in tempos], [500000, 1000000])

    def test_half_sample_up(self):
        # PPQN must fit 15 bits. 100000 us / 9600 ticks gives 1/2 sample.
        raw = f.smf(f.tempo(0, 100000) + f.note_on() + f.note_off(1) + f.end(),
                    division=9600)
        notes, origins, _ = expected_notes(smf_inventory(raw))
        self.assertEqual(notes[-1]['tick'], 1)
        self.assertEqual((origins[-1]['sample_numerator'], origins[-1]['sample_denominator']), (1, 2))

    def test_zero_velocity(self):
        raw = f.smf(f.note_on() + f.note_on(480, velocity=0) + f.end())
        notes, _, _ = expected_notes(smf_inventory(raw))
        self.assertEqual(notes[-1]['type'], 'note_off')

    def test_actual_unsupported_inventory(self):
        inventory = smf_inventory((HERE / 'inputs/charge.mid').read_bytes())
        self.assertEqual((inventory['format'], inventory['tracks'], inventory['ppqn']), (1, 8, 480))
        self.assertTrue(any(e.get('meta_type') == 84 for e in inventory['events']))
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_META'):
            expected_notes(inventory)

    def test_truncated(self):
        with self.assertRaisesRegex(ValueError, 'TRUNCATED'):
            smf_inventory(f.basic()[:-1])


if __name__ == '__main__':
    unittest.main(verbosity=2)
