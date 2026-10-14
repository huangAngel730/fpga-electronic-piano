"""Incremental P0-1 source schedule tests; no HDL tools or old test suite."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schedule_check as audit


class ScheduleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tb = audit.TB.read_text(encoding='utf-8')
        cls.observer = audit.OBSERVER.read_text(encoding='utf-8')
        cls.rows = [json.loads(line) for line in
                    audit.PLAN.read_text(encoding='utf-8').splitlines()][1:-1]
        cls.words = audit.MEM.read_text(encoding='ascii').splitlines()

    def run_audit(self, tb=None, observer=None, words=None):
        return audit.audit(tb or self.tb, observer or self.observer, self.rows,
                           words or self.words)

    def test_all_128_rows_and_four_resets(self):
        result = self.run_audit()
        self.assertEqual([r['memory_index'] for r in result['schedule']], list(range(128)))
        self.assertEqual([r['time'] for r in result['schedule']], list(range(10, 2551, 20)))
        self.assertEqual([(r['time'], r['cycle_visible_next'], r['rst_n'])
                          for r in result['reset_events']],
                         [(0, 0, 0), (40, 2, 1), (1280, 64, 0), (1320, 66, 1)])

    def test_offset_recreates_plan1_skip(self):
        tb = self.tb.replace('apply_control(controls[driver_index]);\n        end',
                             'apply_control(controls[driver_index + 1]);\n        end')
        self.assertNotEqual(tb, self.tb)
        with self.assertRaisesRegex(ValueError, 'SOURCE_SCHEDULE_MISMATCH:1'):
            self.run_audit(tb=tb)

    def test_no_progress_and_last_row_duplicate_rejected(self):
        tb = self.tb.replace('driver_index = driver_index + 1;',
                             'driver_index = driver_index + 0;')
        with self.assertRaisesRegex(ValueError, 'SOURCE_SCHEDULE_MISMATCH:1'):
            self.run_audit(tb=tb)
        tb = self.tb.replace('driver_index < 127', 'driver_index < 126')
        with self.assertRaisesRegex(ValueError, 'SOURCE_SCHEDULE_MISMATCH:127'):
            self.run_audit(tb=tb)

    def test_boundary_rows_cannot_be_changed(self):
        for index in (0, 1, 127):
            words = list(self.words)
            words[index] = f'{int(words[index], 16) ^ 1:043x}'
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, 'MEM_PLAN_MISMATCH'):
                self.run_audit(words=words)

    def test_nonblocking_driver_update_is_not_guessed(self):
        tb = self.tb.replace('driver_index = driver_index + 1;',
                             'driver_index <= driver_index + 1;')
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_SCHEDULE_SOURCE'):
            self.run_audit(tb=tb)

    def test_time_unit_or_postnba_observer_rejected(self):
        with self.assertRaisesRegex(ValueError, 'CLOCK_50MHZ'):
            self.run_audit(tb=self.tb.replace('forever #10', 'forever #5'))
        with self.assertRaisesRegex(ValueError, 'OBSERVER_TIME_AMBIGUOUS'):
            self.run_audit(observer=self.observer.replace('time\\\":%0d', 'time\\\":%0t'))
        with self.assertRaisesRegex(ValueError, 'POST_NBA_OBSERVER'):
            self.run_audit(observer=self.observer.replace('always @(posedge clk) begin',
                                                        'always @(posedge clk) begin #1;'))

    def test_async_reset_and_public_port_only(self):
        with self.assertRaisesRegex(ValueError, 'EXTRA_CONTROL_DRIVER'):
            self.run_audit(tb=self.tb.replace('endmodule',
                                             'always @(posedge clk) rst_n <= 0;\nendmodule'))
        with self.assertRaisesRegex(ValueError, 'ASYNC_RESET_OBSERVER_REQUIRED'):
            self.run_audit(observer=self.observer.replace('always @(rst_n)', 'always @(negedge rst_n)'))
        with self.assertRaisesRegex(ValueError, 'OBSERVER_PUBLIC_ONLY'):
            self.run_audit(observer=self.observer.replace('if (pending)', 'if (dut.pending)'))

    def test_observer_cancel_reason_is_exact_and_unpadded(self):
        padded = self.observer.replace('reason\\\":\\\"frame',
                                       'reason\\\":\\\" frame', 1)
        self.assertNotEqual(padded, self.observer)
        with self.assertRaisesRegex(ValueError, 'OBSERVER_REASON_CONTRACT'):
            self.run_audit(observer=padded)
        ternary = self.observer.replace('if (frame_tick) begin',
                                        'if (frame_tick ? "frame" : "cancel") begin', 1)
        self.assertNotEqual(ternary, self.observer)
        with self.assertRaisesRegex(ValueError, 'OBSERVER_REASON_WIDTH'):
            self.run_audit(observer=ternary)

    def test_original_source_is_not_accepted_as_successor(self):
        old = (audit.HERE.parent / 'tb_t052_publication_control_128.sv').read_text(encoding='utf-8')
        regression = audit.reproduce_legacy(old)
        self.assertEqual(regression['memory_indices'], [0, *range(2, 128), 127])
        self.assertEqual(regression['first_mismatch_cycle'], 1)
        with self.assertRaisesRegex(ValueError, 'SCHEDULE_MARKERS'):
            self.run_audit(tb=old)


if __name__ == '__main__':
    unittest.main()
