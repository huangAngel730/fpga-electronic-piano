"""New software-only tests. Synthetic rows NEVER count as RTL observations."""
import ast
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from fixtures import cancel_plan, compare, lifecycle_plan, rows, schedule_text, validate_plan  # noqa: E402
from fsm_oracle import Oracle, event_word  # noqa: E402
from prepare import ROOT, check_import_origins, dependencies, frozen, load_roms  # noqa: E402

ARTIFACTS = None


def encoded(records):
    return [json.dumps(row, separators=(',', ':')) + '\n' for row in records]


class PreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roms = load_roms()
        cls.a, cls.b = lifecycle_plan(), cancel_plan(cls.roms)
        cls.a_rows = list(rows(cls.a, cls.roms, 'SYNTHETIC_SOFTWARE_TEST'))
        cls.b_rows = list(rows(cls.b, cls.roms, 'SYNTHETIC_SOFTWARE_TEST'))
        cls.mutants = []
        for name, source, predicate, field, value, diagnostic in (
            ('retirement_reuse_wrong_generation', cls.a_rows,
             lambda r: r.get('generations') == 2, 'generations', 1, 'MINCLOSURE_RETIRE_IDENTITY'),
            ('accepted_panic_missing_off', cls.a_rows,
             lambda r: r.get('cycle', 0) > 4072400 and r.get('off') == 1,
             'off', 0, 'MINCLOSURE_PANIC_RELEASE'),
            ('frame_accepts_old_result', cls.b_rows,
             lambda r: r.get('cycle') == 1033, 'commit', 1, 'MINCLOSURE_CANCEL_OLD_ID'),
            ('advance_rolled_back', cls.b_rows,
             lambda r: r.get('cycle') == 725, 'dds_phase', 78741068,
             'MINCLOSURE_ADVANCE_NONROLLBACK_MATH')):
            damaged = source[:]
            index = next(i for i, r in enumerate(source) if predicate(r))
            damaged[index] = dict(source[index], **{field: value})
            cls.mutants.append((name, damaged, cls.a if source is cls.a_rows else cls.b, diagnostic))
        if ARTIFACTS:
            ARTIFACTS.mkdir(parents=True, exist_ok=False)
            payload = {'normal_A': cls.a_rows, 'normal_B': cls.b_rows}
            payload.update({name: records for name, records, _, _ in cls.mutants})
            manifest = {}
            for name, records in payload.items():
                raw = ''.join(encoded(records)).encode()
                compressed = gzip.compress(raw, mtime=0)
                (ARTIFACTS / (name + '.jsonl.gz')).write_bytes(compressed)
                manifest[name] = dict(origin='SYNTHETIC_SOFTWARE_TEST', records=len(records),
                                      sha256=hashlib.sha256(raw).hexdigest(),
                                      gzip_sha256=hashlib.sha256(compressed).hexdigest())
            (ARTIFACTS / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')

    def test_01_source_identity_and_import_closure(self):
        paths, edges = dependencies()
        self.assertGreaterEqual(len(paths), 8)
        self.assertEqual(len(paths), len(edges))

    def test_02_plan_has_original_release_cadence(self):
        clocks = sorted(int(c) for c, v in self.a['inputs'].items() if v.get('frame'))
        self.assertEqual([clocks[i+1]-clocks[i] for i in range(9)], [833, 833, 834] * 3)
        self.assertNotIn('rst_n', self.a['inputs']['4060400'])

    def test_03_natural_retirement_before_reallocation(self):
        retire = [r for r in self.a_rows if r.get('router_state') == 11]
        self.assertEqual(len(retire), 1)
        self.assertLess(retire[0]['cycle'], 4060400)
        ticks = [r for r in self.a_rows if r.get('tick') and 27306 < r['cycle'] < retire[0]['cycle']]
        self.assertEqual(len(ticks), 4800)
        self.assertTrue(any(r.get('generations') == 2 and r.get('on') == 1 for r in self.a_rows))

    def test_04_deferred_then_accepted_panic(self):
        self.assertTrue(any(r.get('deferred') == 1 and r.get('pedal') == 1 for r in self.a_rows))
        panic = next(r for r in self.a_rows if r.get('cycle') == 4072400)
        self.assertEqual((panic['event_valid'], panic['event_ready']), (1, 1))
        after = next(r for r in self.a_rows if r.get('cycle', 0) > 4072400 and r.get('off'))
        self.assertEqual((after['deferred'], after['pedal'], after['keys']), (0, 0, 0))
        release = [r['env_level'] & 0xffffffff for r in self.a_rows
                   if r.get('tick') and r['cycle'] > after['cycle']]
        self.assertGreater(release[0], release[-1])

    def test_05_four_exact_cancel_targets(self):
        observed = {r['cycle']: r for r in self.b_rows if r['tag'] == 'EDGE'}
        self.assertEqual([c['cycle'] for c in self.b['cases']], [105, 424, 725, 1033])
        for case in self.b['cases']:
            row = observed[case['cycle']]
            self.assertEqual((row['frame'], row['request_id'], row['commit']), (1, case['old_id'], 0))
            self.assertTrue(any(r.get('commit') and r['pcm_id'] == case['old_id'] + 1 for r in self.b_rows))
        self.assertEqual(observed[424]['tick'], 0)

    def test_06_nonrollback_and_held_stability(self):
        by_cycle = {r['cycle']: r for r in self.b_rows if r['tag'] == 'EDGE'}
        self.assertEqual(by_cycle[725]['dds_phase'], (by_cycle[724]['dds_phase'] + 39370534) & 0xffffffff)
        self.assertEqual(by_cycle[726]['dds_phase'], by_cycle[725]['dds_phase'])
        before = by_cycle[1030]
        for cycle in (1031, 1032, 1033):
            for field in ('bank_valid', 'bank_id', 'bank_waves', 'bank_envelopes'):
                self.assertEqual(by_cycle[cycle][field], before[field])
        self.assertEqual(by_cycle[1033]['bank_ready'], 0)
        self.assertEqual(by_cycle[1034]['play_left'], by_cycle[1033]['play_left'])

    def test_07_whole_software_positive_A(self):
        result = compare(encoded(self.a_rows), self.a, self.roms, True)
        self.assertEqual(result['status'], 'SOFTWARE_FIXTURE_ONLY')
        self.assertFalse(result['t060_complete'])

    def test_08_whole_software_positive_B(self):
        self.assertEqual(compare(encoded(self.b_rows), self.b, self.roms, True)['records'], len(self.b_rows))

    def test_09_complete_retirement_bad_capture(self):
        self.assert_mutant(0)

    def test_10_complete_panic_bad_capture(self):
        self.assert_mutant(1)

    def test_11_complete_cancel_bad_capture(self):
        self.assert_mutant(2)

    def test_12_complete_rollback_bad_capture(self):
        self.assert_mutant(3)

    def assert_mutant(self, index):
        name, records, plan, diagnostic = self.mutants[index]
        self.assertEqual(records[-1], (self.a_rows if plan is self.a else self.b_rows)[-1])
        with self.assertRaisesRegex(ValueError, diagnostic):
            compare(encoded(records), plan, self.roms, True)

    def test_13_synthetic_origin_not_RTL(self):
        with self.assertRaisesRegex(ValueError, 'origin'):
            compare(encoded(self.b_rows), self.b, self.roms)

    def test_14_bool_flag_rejected(self):
        records = self.b_rows[:]
        records[2] = dict(records[2], tick=False)
        with self.assertRaisesRegex(ValueError, 'MINCLOSURE_TYPE:tick'):
            compare(encoded(records), self.b, self.roms, True)

    def test_15_unique_END_and_no_tail(self):
        with self.assertRaisesRegex(ValueError, 'RECORD_AFTER_END'):
            compare(encoded(self.b_rows + [self.b_rows[-1]]), self.b, self.roms, True)
        with self.assertRaisesRegex(ValueError, 'TRUNCATED'):
            compare(encoded(self.b_rows[:-1]), self.b, self.roms, True)

    def test_16_END_type_and_duplicate_keys(self):
        records = deepcopy(self.b_rows)
        records[-1]['counts']['RESET'] = True
        with self.assertRaisesRegex(ValueError, 'END_TYPES'):
            compare(encoded(records), self.b, self.roms, True)
        lines = encoded(self.b_rows)
        lines[2] = lines[2].replace('"tick":0', '"tick":0,"tick":0')
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_JSON_KEY'):
            compare(lines, self.b, self.roms, True)

    def test_17_unknown_input_not_supported(self):
        model = Oracle(self.roms)
        model.edge(rst_n=0)
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_EVENT'):
            model.edge(event_valid=1, event=event_word(3, value=1))
        plan = deepcopy(self.b)
        plan['inputs']['999']['force'] = 1
        with self.assertRaisesRegex(ValueError, 'PLAN_INPUT'):
            validate_plan(plan)

    def test_18_static_driver_has_no_phase_trigger_or_force(self):
        tb = (ROOT / 'code/tb/board/m3_midi_pcm_acceptance/t060_minclosure_20261011/tb_minclosure.sv').read_text()
        driver = tb.split('always @(negedge clk)begin', 1)[1].split('`include', 1)[0]
        self.assertNotIn('u_bank.phase', driver)
        self.assertNotIn('force ', driver)
        self.assertNotIn('release ', driver)
        tree = ast.parse((HERE / 'prepare.py').read_text())
        self.assertFalse(any(isinstance(n, ast.Name) and n.id == 'subprocess' for n in ast.walk(tree)))

    def test_19_schedule_flags_match_explicit_inputs(self):
        self.assertTrue(schedule_text(self.b).startswith('6 9 0000000000000000\n'))
        self.assertIn('1033 3 0000000000000000\n', schedule_text(self.b))

    def test_20_observer_static_fields_and_arguments(self):
        observer = (ROOT / 'code/tb/board/m3_midi_pcm_acceptance/t060_minclosure_20261011/observer.svh').read_text(encoding='utf-8')
        body = observer.split('$fdisplay(fd,', 1)[1]
        fmt, arguments = body.split('},', 1)
        self.assertEqual(len(re.findall('%0d', fmt)), len(arguments.split(');', 1)[0].split(',')))
        fields_in_format = set(re.findall(r'\\"([a-z_]+)\\":%0d', fmt)) | {'tag'}
        self.assertEqual(fields_in_format, set(self.b_rows[2]))
        self.assertNotIn('always @', observer)
        self.assertNotIn('<=', observer)
        original = frozen()
        bank = original['sources/polyphonic_envelope_bank.sv'].decode()
        for anchor in ('control_request_valid', 'slot_generations', 'release_done', 'wire lane_tick='):
            self.assertIn(anchor, bank)

    def test_21_runtime_import_origin_rejects_outside_model(self):
        import dds_model
        before = dds_model.__file__
        try:
            dds_model.__file__ = str(HERE / 'not_the_frozen_dds.py')
            with self.assertRaisesRegex(ValueError, 'PRECHECK_OUTSIDE_IMPORT:dds_model'):
                check_import_origins()
        finally:
            dds_model.__file__ = before
        check_import_origins()

    def test_22_quiet_skip_matches_full_clock_execution(self):
        plan = initial = deepcopy(self.b)
        plan['trace_all'], plan['group'], plan['end_cycle'] = False, 1, 980
        plan['inputs'] = {k: v for k, v in initial['inputs'].items() if int(k) <= 980}
        fast = list(rows(plan, self.roms, 'SYNTHETIC_SOFTWARE_TEST'))
        model, slow = Oracle(self.roms), []
        rst_n, consumer = 0, 1
        from fsm_oracle import observable
        for cycle in range(1, 981):
            entry = plan['inputs'].get(str(cycle), {})
            rst_n, consumer = entry.get('rst_n', rst_n), entry.get('consumer', consumer)
            row = model.edge(rst_n=rst_n, consumer=consumer, frame=entry.get('frame', 0),
                             event_valid=int('event' in entry), event=entry.get('event', 0))
            if row is not None and observable(row, False):
                slow.append(row)
        self.assertEqual([r for r in fast if r['tag'] == 'EDGE'], slow)


if __name__ == '__main__':
    if '--evidence-dir' in sys.argv:
        index = sys.argv.index('--evidence-dir')
        ARTIFACTS = Path(sys.argv[index + 1]).resolve()
        del sys.argv[index:index + 2]
    unittest.main()
