"""Only NEW B reset suffix / runner tests. No A trajectory or old 22 tests."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from controlled_runner import Budget, check_approval, claim_attempt, dump, identity, load, member, step, verify_inputs  # noqa: E402
from fixtures import cancel_plan, compare, rows  # noqa: E402
from prepare import load_roms  # noqa: E402
from prepare_followup import plan_proof  # noqa: E402
import controlled_runner as runner  # noqa: E402

ARTIFACTS = None


class FinalizationBudgetTests(unittest.TestCase):
    """V0301 increment ONLY; selecting this class never runs the old 13 tests."""
    @classmethod
    def setUpClass(cls):
        ARTIFACTS.mkdir(parents=True)

    def probe(self, name, hash_seconds, receipt_seconds=0):
        work = ARTIFACTS / name
        work.mkdir()
        artifact = work / 'partial.stdout.txt'
        artifact.write_bytes(b'original partial log retained\n')
        now, calls = [899.0], []
        real_identity, real_dump = runner.identity, runner.dump
        budget = Budget(900, lambda: now[0])
        budget.started = 0.0

        def slow_identity(path):
            calls.append(Path(path).name)
            result = real_identity(path)
            now[0] += hash_seconds
            return result

        def slow_dump(path, value):
            real_dump(path, value)
            if Path(path).name == 'receipt.json':
                now[0] += receipt_seconds

        original = dict(status='PRECHECK_ONLY_EXECUTION_LOCKED', exit_code=0,
            failure=None, steps=[], execution_authorized=False,
            total_limit_seconds=900, evidence_origin='SYNTHETIC_CLOCK_NO_TOOLS')
        with mock.patch.object(runner, 'identity', side_effect=slow_identity), \
                mock.patch.object(runner, 'dump', side_effect=slow_dump):
            result = runner.finish(work, budget, original)
        persisted = load(work / 'receipt.json')
        self.assertEqual(result, persisted)
        self.assertEqual(calls, ['partial.stdout.txt'])
        self.assertFalse(result['failure_cleanup_rehash'])
        self.assertEqual(result['artifact_identity_passes'], 1)
        self.assertEqual(artifact.read_bytes(), b'original partial log retained\n')
        dump(ARTIFACTS / (name + '.probe.json'), dict(
            origin='SYNTHETIC_CLOCK_NO_TOOLS', clock_start=899, clock_end=now[0],
            simulated_hash_seconds=hash_seconds, primary_receipt_write_seconds=receipt_seconds,
            identity_calls=calls, actual_runner_exit_code=result['exit_code'], receipt=result))
        print(json.dumps(dict(probe=name, clock_end=now[0],
                              runner_exit_code=result['exit_code'], identity_calls=calls)))
        return result

    def test_artifact_sha_crosses_900_fail_partial(self):
        result = self.probe('sha_cross_900', 2.0)
        self.assertEqual((result['status'], result['exit_code'], result['elapsed_seconds']),
                         ('FAIL_PARTIAL', 1, 901.0))
        self.assertIn('RUNNER_TOTAL_TIMEOUT', result['failure'])
        self.assertEqual(len(result['artifacts']), 1)
        self.assertFalse(result['artifact_collection_complete'])

    def test_artifact_sha_within_budget_remains_locked(self):
        result = self.probe('sha_within_900', 0.25)
        self.assertEqual((result['status'], result['exit_code'], result['elapsed_seconds']),
                         ('PRECHECK_ONLY_EXECUTION_LOCKED', 0, 899.25))
        self.assertTrue(result['artifact_collection_complete'])
        self.assertIsNone(result['failure'])

    def test_receipt_write_overrun_failure_never_rescans(self):
        result = self.probe('receipt_write_cross_900', 0.25, 2.0)
        self.assertEqual((result['status'], result['exit_code'], result['elapsed_seconds']),
                         ('FAIL_PARTIAL', 1, 901.25))
        self.assertIn('RUNNER_TOTAL_TIMEOUT_RECEIPT_WRITE', result['failure'])
        self.assertTrue(result['artifact_collection_complete'])


class NewFollowupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roms = load_roms()
        cls.plan = cancel_plan(cls.roms)
        # 1600 clocks is state bootstrap for new suffix only; no old scenario
        # assertions or A 4800-tick trajectory are run here.
        cls.records = list(rows(cls.plan, cls.roms, 'SYNTHETIC_SOFTWARE_TEST'))
        cls.edges = {r['cycle']: r for r in cls.records if r['tag'] == 'EDGE'}
        ARTIFACTS.mkdir(parents=True)
        (ARTIFACTS / 'B_suffix_software.jsonl').write_text(
            ''.join(json.dumps(r) + '\n' for r in cls.records), encoding='utf-8', newline='\n')
        dump(ARTIFACTS / 'plan_delta.json', plan_proof())

    def test_only_four_suffix_inputs_added(self):
        proof = plan_proof()
        self.assertTrue(proof['original_B_recovered_by_removing_only_four_inputs'])
        self.assertEqual(proof['end_cycle'], 1600)

    def test_inflight_reset_and_second_epoch(self):
        self.assertNotEqual(self.edges[1509]['phase'], 0)
        self.assertEqual([r for r in self.records if r['tag'] == 'RESET'], [
            {'tag': 'RESET', 'epoch': 1, 'cycle': 1},
            {'tag': 'RESET', 'epoch': 2, 'cycle': 1510}])

    def test_first_released_edge_is_clean(self):
        clean = self.edges[1514]
        fields = ('sources', 'channels', 'notes', 'generations', 'occupied', 'releasing',
                  'keys', 'deferred', 'pedal', 'dds_phase', 'lfo_phase', 'env_state',
                  'env_level', 'bank_valid', 'pcm_valid', 'pending_valid', 'play_left',
                  'play_right', 'request_id', 'bank_id', 'pcm_id', 'sample_req')
        self.assertEqual({f: clean[f] for f in fields}, dict.fromkeys(fields, 0))
        self.assertEqual(clean['epoch'], 2)

    def test_recovery_commit_is_new_id_one(self):
        commits = [r for r in self.records if r.get('cycle', 0) >= 1510 and r.get('commit')]
        self.assertEqual([(r['cycle'], r['epoch'], r['pcm_id']) for r in commits], [(1571, 2, 1)])

    def test_complete_new_suffix_damage_refused(self):
        damaged = [dict(r) for r in self.records]
        next(r for r in damaged if r.get('cycle') == 1514)['dds_phase'] = 1
        with self.assertRaisesRegex(ValueError, 'MINCLOSURE_ADVANCE_NONROLLBACK_MATH'):
            compare([json.dumps(r) for r in damaged], self.plan, self.roms, True)
        (ARTIFACTS / 'B_dirty_reset_complete.jsonl').write_text(
            ''.join(json.dumps(r) + '\n' for r in damaged), encoding='utf-8', newline='\n')

    def test_remaining_budget_not_sum_of_caps(self):
        now = [10.0]
        budget = Budget(900, lambda: now[0])
        self.assertEqual(budget.limit(300), 300)
        now[0] = 880
        self.assertEqual(budget.limit(90), 30)
        now[0] = 910
        with self.assertRaisesRegex(ValueError, 'RUNNER_TOTAL_TIMEOUT'):
            budget.limit(90)

    def test_no_approval_and_wrong_exact_identity_rejected(self):
        with self.assertRaisesRegex(ValueError, 'RUNNER_EXECUTION_NOT_AUTHORIZED'):
            check_approval('missing', None)
        with tempfile.TemporaryDirectory(dir=ARTIFACTS) as tmp:
            config, approval = Path(tmp) / 'c.json', Path(tmp) / 'a.json'
            dump(config, {'execution_authorized': False})
            dump(approval, dict(authority='M2', execution_authorized=True, config_sha256='0'*64,
                                 groups=['A', 'B'], attempt=1, notice='fake test only'))
            with self.assertRaisesRegex(ValueError, 'RUNNER_APPROVAL_NOT_EXACT'):
                check_approval(config, approval)

    def test_approved_identity_claimed_once_without_tool_start(self):
        with tempfile.TemporaryDirectory(dir=ARTIFACTS) as tmp:
            config, approval = Path(tmp) / 'c.json', Path(tmp) / 'a.json'
            dump(config, {'execution_authorized': False})
            dump(approval, dict(authority='M2', execution_authorized=True,
                 config_sha256=identity(config)['sha256'], groups=['A', 'B'],
                 attempt=1, notice='SYNTHETIC unit fixture; no execution'))
            approved = check_approval(config, approval)
            claim_attempt(Path(tmp), identity(config), approved, Path(tmp) / 'not_run')
            with self.assertRaises(FileExistsError):
                claim_attempt(Path(tmp), identity(config), approved, Path(tmp) / 'not_run2')

    def test_post_step_budget_overrun_is_not_pass(self):
        work = ARTIFACTS / 'post_budget'
        work.mkdir()
        now = [0.0]
        budget = Budget(1, lambda: now[0])
        # A successful child cannot excuse elapsed post-check/preflight time.
        now[0] = 1.1
        with self.assertRaisesRegex(ValueError, 'RUNNER_TOTAL_TIMEOUT'):
            step(work, 'not_started', [sys.executable, '-c', 'raise SystemExit(99)'], work, budget, 90)
        self.assertFalse((work / 'not_started.stdout.txt').exists())

    def test_type_duplicate_nonfinite_and_path_escape(self):
        with tempfile.TemporaryDirectory(dir=ARTIFACTS) as tmp:
            path = Path(tmp) / 'invalid.json'
            path.write_text('{"x":1,"x":2}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'RUNNER_DUPLICATE_KEY'):
                load(path)
            path.write_text('{"x":NaN}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'RUNNER_NONFINITE'):
                load(path)
            with self.assertRaisesRegex(ValueError, 'RUNNER_MEMBER_ESCAPE'):
                member(tmp, '../outside')
        with self.assertRaisesRegex(ValueError, 'RUNNER_BUDGET'):
            Budget(True)

    def test_inputs_before_after_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=ARTIFACTS) as tmp:
            path = Path(tmp) / 'input'
            path.write_bytes(b'frozen')
            pins = {'input': identity(path)}
            self.assertEqual(verify_inputs(tmp, pins, Budget()), pins)
            path.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'RUNNER_INPUT_SHA'):
                verify_inputs(tmp, pins, Budget())

    def test_step_partial_logs_child_tree_timeout(self):
        work = ARTIFACTS / 'timeout_child'
        work.mkdir()
        # Child would leave a marker after2s if the owned tree wasn't stopped.
        # No real tools; no subprocess names matched or global processes killed.
        marker = work / 'orphan_marker'
        child = "import time,pathlib;time.sleep(2);pathlib.Path('orphan_marker').write_text('bad')"
        parent = "import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c',sys.argv[1]]);print('child='+str(p.pid),flush=True);time.sleep(10)"
        with self.assertRaisesRegex(ValueError, 'RUNNER_STEP_FAILED:timeout'):
            step(work, 'timeout', [sys.executable, '-I', '-S', '-B', '-c', parent, child],
                 work, Budget(5), 0.5)
        receipt = load(work / 'timeout.receipt.json')
        self.assertTrue(receipt['timeout'])
        self.assertIn(b'child=', (work / 'timeout.stdout.txt').read_bytes())
        self.assertIsNotNone(receipt['cleanup'])
        # A bounded fake wait exercises descendant cleanup rather than only
        # checking the parent's return code. Original timeout evidence stays.
        subprocess.run([sys.executable, '-I', '-S', '-B', '-c', 'import time;time.sleep(2.2)'],
                       cwd=work, timeout=4, check=True)
        self.assertFalse(marker.exists())

    def test_step_no_overwrite_and_nonzero_logged(self):
        work = ARTIFACTS / 'fake_nonzero'
        work.mkdir()
        with self.assertRaisesRegex(ValueError, 'RUNNER_STEP_FAILED:fail'):
            step(work, 'fail', [sys.executable, '-I', '-S', '-B', '-c', 'print("fake failure");raise SystemExit(7)'],
                 work, Budget(), 90)
        self.assertEqual(load(work / 'fail.receipt.json')['exit_code'], 7)
        with self.assertRaises(FileExistsError):
            step(work, 'fail', [sys.executable, '-c', 'raise SystemExit(99)'], work, Budget(), 90)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence-dir', type=Path, required=True)
    args, rest = parser.parse_known_args()
    ARTIFACTS = args.evidence_dir.resolve()
    if ARTIFACTS.exists():
        raise ValueError('FOLLOWUP_TEST_REFUSE_OVERWRITE')
    unittest.main(argv=[sys.argv[0], *rest])
