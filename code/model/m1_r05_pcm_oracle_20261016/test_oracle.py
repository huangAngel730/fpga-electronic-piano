"""Focused tests of the new adapter and its counterexamples, not old suites."""
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

from oracle import Reference, HERE, PCM_MIN, PCM_MAX, dds, adsr, TRIANGLE, PIANO, mixed, verify_dependencies


def four():
    ref = Reference()
    ref.config_accept(16, True, 1, 32767, 16384, 0)
    ref.event(32, 'note_on', note=60, velocity=1023)
    ref.event(48, 'program', program=1)
    for cycle, note in [(64, 63), (80, 67), (96, 70)]:
        ref.event(cycle, 'note_on', note=note, velocity=800)
    return ref


class IncrementTests(unittest.TestCase):
    def test_four_frequencies_and_phase_rules(self):
        ref = four()
        row = ref.sample(128, 0)
        self.assertEqual([l['fcw'] for l in row['lanes']], [23409859, 27839171, 35075158, 41711627])
        self.assertEqual(len({l['frequency_hz'] for l in row['lanes']}), 4)
        for lane in row['lanes']:
            address = lane['phase_before'] >> 22 if lane['timbre'] else (lane['piano_table'] << 8) | (lane['phase_after'] >> 24)
            self.assertEqual(lane['rom_address'], address)
            self.assertEqual(lane['wave16'], TRIANGLE[address] if lane['timbre'] else PIANO[address])
        self.assertEqual(row['lanes'][1]['wave16'], 0)
        self.assertNotEqual(row['lanes'][1]['wave16'], TRIANGLE[row['lanes'][1]['phase_after'] >> 22])

    def test_program_latched_retrigger_and_generation(self):
        ref = four()
        first = ref.sample(128, 0)
        ref.event(256, 'program', program=0)
        unchanged = ref.sample(400, 1)
        self.assertEqual([l['timbre'] for l in first['lanes']], [l['timbre'] for l in unchanged['lanes']])
        result = ref.event(512, 'note_on', note=63, velocity=400)
        row = ref.sample(600, 2)
        self.assertEqual(result['decision'], 'retrigger')
        self.assertEqual((row['lanes'][1]['timbre'], row['lanes'][1]['generation']), (0, 2))
        self.assertEqual(row['lanes'][1]['phase_before'], unchanged['lanes'][1]['phase_after'])

    def test_fifth_note_lru_identity(self):
        ref = four()
        ref.sample(128, 0)
        result = ref.event(256, 'note_on', note=72, velocity=900)
        row = ref.sample(400, 1)
        self.assertEqual((result['decision'], result['lane']), ('steal', 0))
        self.assertEqual(row['lanes'][0]['identity'][:3], [1, 0, 72])
        self.assertTrue(all(l['identity'] is not None for l in row['lanes']))
        self.assertEqual(row['lanes'][0]['generation'], 2)

    def test_same_note_other_channel_and_zero_velocity_release(self):
        ref = Reference()
        ref.event(32, 'note_on', source=1, channel=0, note=60, velocity=1000)
        ref.event(48, 'note_on', source=1, channel=1, note=60, velocity=500)
        ref.event(64, 'note_on', source=1, channel=0, note=60, velocity=0)
        row = ref.sample(128, 0)
        self.assertEqual(row['lanes'][0]['identity'][3], 'release')
        self.assertEqual(row['lanes'][1]['identity'][3], 'active')

    def test_release_retirement_in_new_profile(self):
        ref = Reference()
        ref.event(32, 'note_on', note=60, velocity=1023)
        ref.sample(128, 0)
        ref.event(256, 'note_off', note=60)
        last = None
        for rid in range(1, 4803):
            last = ref.sample(400 + rid * 833, rid)
        self.assertIsNone(last['lanes'][0]['identity'])
        self.assertEqual(last['mixed_left'], 0)

    def test_cancelled_accepted_work_changes_future_effect(self):
        ref = four()
        first = ref.sample(128, 0)
        cancelled = ref.sample(961, 1, publish=False)
        following = ref.sample(1794, 2)
        expected = (following['mixed_left'] * 32767 >> 15) + (cancelled['mixed_left'] * 16384 >> 15)
        wrong = (following['mixed_left'] * 32767 >> 15) + (first['mixed_left'] * 16384 >> 15)
        self.assertEqual(following['left'], max(PCM_MIN, min(PCM_MAX, expected)))
        self.assertNotEqual(following['left'], max(PCM_MIN, min(PCM_MAX, wrong)))
        self.assertFalse(cancelled['expected_publish'])

    def test_advance_without_effect_accept_keeps_history_but_not_phase(self):
        ref = four()
        first = ref.sample(128, 0)
        cancelled = ref.sample(961, 1, effect_accepted=False, publish=False)
        following = ref.sample(1794, 2)
        self.assertIsNone(cancelled['left'])
        self.assertEqual(following['lanes'][0]['phase_before'], cancelled['lanes'][0]['phase_after'])
        expected = (following['mixed_left'] * 32767 >> 15) + (first['mixed_left'] * 16384 >> 15)
        self.assertEqual(following['left'], max(PCM_MIN, min(PCM_MAX, expected)))

    def test_bypass_gain_config_and_length_flush(self):
        ref = four()
        first = ref.sample(128, 0)
        ref.config_accept(256, False, 1, 32767, 16384, 0)
        bypass = ref.sample(400, 1)
        self.assertEqual(bypass['left'], bypass['mixed_left'])
        self.assertEqual(ref.effects[0].wr_ptr, 0)
        ref.config_accept(512, True, 1, 32767, 16384, 0)
        enabled = ref.sample(600, 2)
        self.assertEqual(enabled['left'], enabled['mixed_left'] * 32767 >> 15)
        ref.config_accept(700, True, 1, 0, 32767, 0)
        retained = ref.sample(800, 3)
        self.assertEqual(retained['left'], enabled['mixed_left'] * 32767 >> 15)
        ref.config_accept(900, True, 2, 0, 32767, 0)
        flushed = ref.sample(1000, 4)
        self.assertEqual(flushed['left'], 0)

    def test_saturation_boundaries_and_negative_floor(self):
        for total, value, clip in [(PCM_MAX, PCM_MAX, False), (PCM_MAX + 1, PCM_MAX, True),
                                   (PCM_MIN, PCM_MIN, False), (PCM_MIN - 1, PCM_MIN, True)]:
            voices = [PCM_MAX, 1, 0, 0] if total == PCM_MAX + 1 else [PCM_MIN, -1, 0, 0] if total == PCM_MIN - 1 else [total, 0, 0, 0]
            self.assertEqual(mixed(voices), (value, clip))
        self.assertEqual(adsr.voice_pcm(-1, 1), -256)
        self.assertNotEqual(adsr.voice_pcm(-1, 1), int(-1 / 32768) << 8)

    def test_reset_clears_phase_program_and_history(self):
        ref = four()
        ref.sample(128, 0)
        ref.reset(256)
        row = ref.sample(400, 0)
        self.assertEqual(row['epoch'], 1)
        self.assertEqual(row['left'], 0)
        self.assertTrue(all(l['phase_after'] == l['generation'] == 0 for l in row['lanes']))
        ref.event(512, 'note_on', note=63, velocity=800)
        row = ref.sample(600, 1)
        self.assertEqual(row['lanes'][0]['timbre'], 0)

    def test_missing_lane_and_wrong_generation_counterexamples(self):
        ref = four()
        ref.sample(128, 0)
        row = ref.sample(961, 1)
        contributions = [l['voice_pcm24'] for l in row['lanes']]
        self.assertNotEqual(mixed(contributions)[0], mixed(contributions[:3] + [0])[0])
        ref.event(1100, 'note_on', note=72, velocity=900)
        changed = ref.sample(1200, 2)
        self.assertNotEqual(row['lanes'][0]['generation'], changed['lanes'][0]['generation'])

    def test_invalid_and_unsupported_inputs_reject(self):
        for kwargs in [dict(kind='sustain'), dict(kind='pitch_bend'), dict(kind='panic'),
                       dict(kind='note_on', note=128), dict(kind='note_on', velocity=True),
                       dict(kind='program', program=-1)]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Reference().event(32, **kwargs)
        with self.assertRaises(ValueError):
            Reference().sample(1, 0)
        ref = Reference()
        ref.sample(32, 0)
        with self.assertRaises(ValueError):
            ref.sample(64, 0)
        with self.assertRaises(ValueError):
            Reference().sample(32, 0, False, True)

    def test_frozen_dependency_drift_is_not_backfilled(self):
        with tempfile.TemporaryDirectory(prefix='m1_r06_dependency_') as temp:
            copy = Path(temp)
            shutil.copyfile(HERE / 'DEPENDENCIES.json', copy / 'DEPENDENCIES.json')
            shutil.copytree(HERE / 'frozen', copy / 'frozen')
            path = copy / 'frozen/rom/triangle_wavetable.hex'
            before = path.read_bytes()
            path.write_bytes(before + b'\n')
            with self.assertRaises(ValueError):
                verify_dependencies(copy)
            self.assertEqual(path.read_bytes(), before + b'\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
