"""Focused software-only tests; never run original math/RTL tests."""
import copy
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from publication import calendar, controlled, legacy, read_rows
from vectors import corpus, fixture


class PublicationTests(unittest.TestCase):
    def test_handwritten_positive_and_complete_negatives(self):
        for name, (value, code, diagnostic) in corpus().items():
            with self.subTest(name=name):
                if code:
                    with self.assertRaisesRegex(ValueError, diagnostic):
                        controlled(*value)
                else:
                    self.assertEqual(controlled(*value)['exit_code'], 0)

    def test_phase_advance_not_rolled_back_by_frame_or_cancel(self):
        control, _, _ = fixture('cancel_frame_reset')
        result = calendar(control)
        self.assertEqual([row['cycle'] for row in result['accepted']], [1, 4, 8, 13])
        self.assertEqual([row['phases_before'] for row in result['accepted']],
                         [[0, 0, 0, 0], [1, 2, 3, 4], [2, 4, 6, 8], [0, 0, 0, 0]])
        self.assertEqual(result['phase_ticks'], 4)
        self.assertEqual(result['final_phases'], [1, 2, 3, 4])
        self.assertEqual([row['reason'] for row in result['cancelled']], ['cancel', 'frame', 'reset'])

    def test_booleans_and_nonbinary_flags_not_integers(self):
        for flag in (True, 2, -1, '1'):
            value = list(copy.deepcopy(fixture('normal_repeated_id')))
            value[0][2]['sample_req'] = flag
            with self.assertRaisesRegex(ValueError, 'STRICT_FLAG_01'):
                controlled(*value)

    def test_no_trailing_or_missing_control_cycles(self):
        value = copy.deepcopy(fixture('normal_repeated_id'))
        value[1].pop(3)
        with self.assertRaisesRegex(ValueError, 'OBS_WINDOW_INCOMPLETE'):
            controlled(*value)

    def test_open_request_cannot_hide_in_end(self):
        control = copy.deepcopy(fixture('normal_repeated_id')[0])
        control[-2]['sample_req'] = 1
        with self.assertRaisesRegex(ValueError, 'OPEN_REQUEST_AT_END'):
            calendar(control)

    def test_parser_duplicate_key_nonfinite_and_blank(self):
        with tempfile.TemporaryDirectory() as temporary:
            for index, raw in enumerate(('{}\n\n', '{"a":0,"a":1}\n', '{"a":NaN}\n')):
                path = Path(temporary) / str(index)
                path.write_text(raw, encoding='utf-8')
                with self.assertRaises(ValueError):
                    read_rows(path)

    def test_legacy_equal_count_is_still_unknown(self):
        with tempfile.TemporaryDirectory() as temporary:
            req, cap = Path(temporary) / 'REQ', Path(temporary) / 'CAP'
            req.write_text('ACC 7 00000001 00000002 00000003 00000004 15\nEND requests=1\n', encoding='utf-8')
            cap.write_text('ID=7 v0=0 v1=0 v2=0 v3=0 ACT=4 CLIP=0\nEND results=1\n', encoding='utf-8')
            self.assertEqual(legacy(req, cap)['exit_code'], 3)
            with cap.open('a', encoding='utf-8') as stream:
                stream.write('END results=1\n')
            with self.assertRaisesRegex(ValueError, 'RECORD_AFTER_END'):
                legacy(req, cap)


if __name__ == '__main__':
    unittest.main()
