"""Independent literal log expectations, including the retained false-green."""
import json
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

import rom_gate

ROOT = Path(__file__).resolve().parents[3]
TOKEN = 'PASS tb_contract_fixture'
CLEAN = TOKEN + '\nfixture.sv:7: $finish called at 100 (1ns)\n'


class LogContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            prefix='repo_gate_rom_audit_test_', dir=ROOT / 'code/output')
        self.directory = Path(self.temp.name)
        self.stdout, self.stderr = self.directory / 'stdout.log', self.directory / 'stderr.log'

    def tearDown(self):
        self.temp.cleanup()

    def outcome(self, out=CLEAN, err='', code=0, token=TOKEN):
        self.stdout.write_text(out, encoding='utf-8')
        self.stderr.write_text(err, encoding='utf-8')
        try:
            result = rom_gate.audit_logs(self.stdout, self.stderr, code, token)
        except (ValueError, OSError):
            return False
        return bool(result.get('passed', result.get('status') == 'PASS'))

    def test_clean_literal(self):
        self.assertTrue(self.outcome())

    def test_readmem_error_plus_pass(self):
        self.assertFalse(self.outcome('ERROR: unit.sv:149: $readmemh: Unable to open '
                                      'model/generated/sine_wavetable.hex for reading.\n' + CLEAN))

    def test_readmem_stderr_plus_pass(self):
        self.assertFalse(self.outcome(err='ERROR: $readmemh: Unable to open x for reading.\n'))

    def test_short_rom_warning_plus_pass(self):
        self.assertFalse(self.outcome('WARNING: $readmemh(x): Not enough words in the file '
                                      'for the requested range [0:1023].\n' + CLEAN))

    def test_long_rom_warning_plus_pass(self):
        self.assertFalse(self.outcome('WARNING: $readmemh(x): Too many words in the file '
                                      'for the requested range [0:1023].\n' + CLEAN))

    def test_nonzero_with_pass_and_finish(self):
        self.assertFalse(self.outcome(code=5))

    def test_access_violation(self):
        self.assertFalse(self.outcome(out='', code=3221225477))

    def test_missing_pass(self):
        self.assertFalse(self.outcome(out='fixture.sv:7: $finish called at 100 (1ns)\n'))

    def test_missing_finish(self):
        self.assertFalse(self.outcome(out=TOKEN + '\n'))

    def test_wrong_top(self):
        self.assertFalse(self.outcome(token='PASS tb_different_fixture'))

    def test_fatal_after_pass(self):
        self.assertFalse(self.outcome(CLEAN + 'FATAL: later failure\n'))

    def test_named_failure(self):
        self.assertFalse(self.outcome('[FAIL] frame count\n' + CLEAN))

    def test_error_without_readmem(self):
        self.assertFalse(self.outcome('ERROR: simulation dependency error\n' + CLEAN))

    def test_empty(self):
        self.assertFalse(self.outcome(out=''))

    def test_truncated_last_line(self):
        self.assertFalse(self.outcome(out=CLEAN.rstrip('\n')))

    def test_data_after_finish(self):
        self.assertFalse(self.outcome(out=CLEAN + 'unexpected extra output\n'))

    def test_missing_log(self):
        self.stdout.write_text(CLEAN, encoding='utf-8')
        with self.assertRaises((OSError, ValueError)):
            rom_gate.audit_logs(self.stdout, self.stderr, 0, TOKEN)

    def test_real_historical_false_green_is_rejected(self):
        original = ROOT / ('code/software/score_midi_import_candidate_20261014/'
                           'PUBLICATION_20261015_R01/REPOSITORY_GATE_R02_LOGS.zip')
        found, rejected = 0, 0
        with zipfile.ZipFile(original) as archive:
            self.assertIsNone(archive.testzip())
            for name in archive.namelist():
                if not name.endswith('/receipt.json'):
                    continue
                receipt = json.loads(archive.read(name))
                prefix = name.rsplit('/', 1)[0] + '/'
                out = archive.read(prefix + 'stdout.log').decode('utf-8')
                err = archive.read(prefix + 'stderr.log').decode('utf-8')
                self.assertEqual(receipt['exit'], 0)
                self.assertTrue(receipt['passed'])
                if receipt['top'] == 'tb_electronic_piano_top':
                    # Fixed-tone generate branch never instantiates the timbre ROM.
                    self.assertNotIn('Unable to open', out)
                    self.assertTrue(self.outcome(out, err, 0, '>>> 顶层自检 PASS'))
                else:
                    self.assertIn('$readmemh', out)
                    self.assertIn('Unable to open', out)
                    self.assertFalse(self.outcome(out, err, 0, 'PASS ' + receipt['top']))
                    rejected += 1
                found += 1
        self.assertEqual(found, 3)
        self.assertEqual(rejected, 2)


class ConfigContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = Path(os.environ['ROM_GATE_EXPECTED'])
        cls.tools = Path(json.loads(cls.expected.read_text(encoding='utf-8'))['tool_root'])
        cls.temp = tempfile.TemporaryDirectory(prefix='repo_gate_rom_audit_configtest_',
                                             dir=ROOT / 'code/output')
        cls.directory = Path(cls.temp.name)
        cls.config = rom_gate.prepare(ROOT, cls.directory / 'repo_gate_rom_audit_stage',
                                      cls.expected, cls.tools)
        cls.original_config = cls.config.read_bytes()
        cls.original_sha = (cls.config.parent / 'config.sha256').read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def tearDown(self):
        self.config.write_bytes(self.original_config)
        (self.config.parent / 'config.sha256').write_bytes(self.original_sha)

    def changed_config(self, change):
        doc = json.loads(self.original_config)
        change(doc)
        raw = (json.dumps(doc, ensure_ascii=False) + '\n').encode('utf-8')
        self.config.write_bytes(raw)
        (self.config.parent / 'config.sha256').write_text(
            hashlib.sha256(raw).hexdigest() + '\n', encoding='ascii')

    def test_fresh_config(self):
        result = rom_gate.verify(self.config)
        self.assertTrue(result['passed'])
        self.assertEqual(result['tool_calls'], 0)
        self.assertEqual(len(result['mapped_roms']), 4)

    def test_output_overwrite_rejected(self):
        with self.assertRaises(ValueError):
            rom_gate.prepare(ROOT, self.config.parent, self.expected, self.tools)

    def test_command_injection_rejected_even_with_new_config_digest(self):
        self.changed_config(lambda d: d['commands'][0]['argv'].append('arbitrary-command'))
        with self.assertRaises(ValueError):
            rom_gate.verify(self.config)

    def test_wrong_cwd_rejected(self):
        self.changed_config(lambda d: d.update(output=str(self.directory)))
        with self.assertRaises(ValueError):
            rom_gate.verify(self.config)

    def test_timeout_increase_rejected(self):
        self.changed_config(lambda d: d.update(total_seconds=301))
        with self.assertRaises(ValueError):
            rom_gate.verify(self.config)

    def test_environment_path_drift_rejected(self):
        self.changed_config(lambda d: d['environment'].update(PATH='unbound-path'))
        with self.assertRaises(ValueError):
            rom_gate.verify(self.config)

    def test_forged_scope_rejected(self):
        self.changed_config(lambda d: d.update(scope='HARDWARE_ACCEPTED'))
        with self.assertRaises(ValueError):
            rom_gate.verify(self.config)

    def test_consumed_attempt_cannot_run(self):
        marker = self.config.parent / 'consumed.json'
        marker.write_text('{"consumed":true}', encoding='utf-8')
        try:
            with self.assertRaises(ValueError):
                rom_gate.run(self.config)
        finally:
            marker.unlink()

    def test_missing_expected_after_launch_still_writes_failure_receipt(self):
        stage = self.directory / 'repo_gate_rom_audit_fault_expected'
        config = rom_gate.prepare(ROOT, stage, self.expected, self.tools)

        def fake_execute(argv, cwd, env, seconds, stdout, stderr, job):
            stdout.write_bytes(b'synthetic failure fixture; no tool launched\n')
            stderr.write_bytes(b'')
            (cwd / 'expected.json').unlink()
            return {'started': False, 'timeout': False, 'exit_code': 1, 'elapsed_seconds': 0}

        with mock.patch.object(rom_gate, '_job_module', return_value=None), \
                mock.patch.object(rom_gate, '_execute', side_effect=fake_execute):
            receipt = rom_gate.run(config)
        self.assertFalse(receipt['passed'])
        self.assertEqual(receipt['tool_calls'], 0)
        self.assertTrue((stage / 'receipt.json').is_file())

    def test_unreadable_tool_after_launch_still_writes_failure_receipt(self):
        stage = self.directory / 'repo_gate_rom_audit_fault_tool'
        config = rom_gate.prepare(ROOT, stage, self.expected, self.tools)
        original_sha = rom_gate.sha
        state = {'after': False}
        target = self.tools / 'bin/iverilog.exe'

        def fake_sha(path):
            if state['after'] and Path(path).resolve() == target.resolve():
                raise PermissionError('synthetic permission failure; tool bytes untouched')
            return original_sha(path)

        def fake_execute(argv, cwd, env, seconds, stdout, stderr, job):
            stdout.write_bytes(b'synthetic failure fixture; no tool launched\n')
            stderr.write_bytes(b'')
            state['after'] = True
            return {'started': False, 'timeout': False, 'exit_code': 1, 'elapsed_seconds': 0}

        with mock.patch.object(rom_gate, '_job_module', return_value=None), \
                mock.patch.object(rom_gate, '_execute', side_effect=fake_execute), \
                mock.patch.object(rom_gate, 'sha', side_effect=fake_sha):
            receipt = rom_gate.run(config)
        self.assertFalse(receipt['passed'])
        self.assertIsNone(receipt['tools_after']['bin/iverilog.exe'])
        self.assertTrue((stage / 'receipt.json').is_file())

    def test_generated_rom_omission_rejected(self):
        self.changed_config(lambda d: (d['generated'].pop('model/generated/sine_wavetable.hex'),
                                        d['mapped_roms'].pop('model/generated/sine_wavetable.hex')))
        with self.assertRaises(ValueError):
            rom_gate.verify(self.config)

    def test_corrupt_staged_rom_rejected(self):
        path = self.config.parent / 'model/generated/triangle_wavetable.hex'
        original = path.read_bytes()
        try:
            path.write_bytes(original + b'0000\n')
            with self.assertRaises(ValueError):
                rom_gate.verify(self.config)
        finally:
            path.write_bytes(original)

    def test_missing_staged_rom_rejected(self):
        path = self.config.parent / 'model/generated/sine_wavetable.hex'
        backup = path.with_suffix('.owned_test_backup')
        path.rename(backup)
        try:
            with self.assertRaises(ValueError):
                rom_gate.verify(self.config)
        finally:
            backup.rename(path)

    def test_corrupt_allocator_copy_rejected(self):
        path = self.config.parent / 'allocator_source.sv'
        original = path.read_bytes()
        try:
            path.write_bytes(original + b'// altered isolated copy\n')
            with self.assertRaises(ValueError):
                rom_gate.verify(self.config)
        finally:
            path.write_bytes(original)

    def test_frozen_bad_sha_rejected(self):
        document = json.loads(self.expected.read_text(encoding='utf-8'))
        document['files']['code/model/generated/sine_wavetable.hex'] = '0' * 64
        expected = self.directory / 'bad_expected.json'
        expected.write_text(json.dumps(document), encoding='utf-8')
        with self.assertRaises(ValueError):
            rom_gate.prepare(ROOT, self.directory / 'repo_gate_rom_audit_badsha', expected, self.tools)

    def test_tool_dependency_omitted_rejected(self):
        document = json.loads(self.expected.read_text(encoding='utf-8'))
        key = next(k for k in document['tools'] if k.startswith('lib/ivl/'))
        del document['tools'][key]
        expected = self.directory / 'incomplete_tools.json'
        expected.write_text(json.dumps(document), encoding='utf-8')
        with self.assertRaises(ValueError):
            rom_gate.prepare(ROOT, self.directory / 'repo_gate_rom_audit_incomplete', expected, self.tools)

    def test_unsafe_identity_path_rejected(self):
        with self.assertRaises(ValueError):
            rom_gate.identity(ROOT, {'../outside': '0' * 64})

    def test_duplicate_json_key_rejected(self):
        path = self.directory / 'duplicate.json'
        path.write_text('{"schema": 1, "schema": 2}', encoding='utf-8')
        with self.assertRaises(ValueError):
            rom_gate.read_json(path)


class IncludeClosureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='repo_gate_rom_audit_include_', dir=ROOT / 'code/output')
        self.repo = Path(self.temp.name)
        self.board, self.common = self.repo / 'code/rtl/board', self.repo / 'code/rtl/common'
        self.stage = self.repo / 'code/output/stage'
        for folder in (self.board, self.common, self.stage):
            folder.mkdir(parents=True)
        self.source = self.board / 'fixture.sv'

    def tearDown(self):
        self.temp.cleanup()

    def test_literal_recursive(self):
        self.source.write_text('`include "a.svh"\n', encoding='utf-8')
        (self.common / 'a.svh').write_text('`include "b.svh"\n', encoding='utf-8')
        (self.common / 'b.svh').write_text('// fixture only\n', encoding='utf-8')
        result = rom_gate.include_closure(self.repo, [self.source], self.stage)
        self.assertEqual(len(result['files']), 2)
        self.assertEqual(len(result['edges']), 2)

    def test_dynamic_rejected(self):
        self.source.write_text('`include GENERATED_MACRO\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            rom_gate.include_closure(self.repo, [self.source], self.stage)

    def test_missing_rejected(self):
        self.source.write_text('`include "missing.svh"\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            rom_gate.include_closure(self.repo, [self.source], self.stage)

    def test_cwd_shadow_rejected(self):
        self.source.write_text('`include "same.svh"\n', encoding='utf-8')
        for directory in (self.common, self.stage):
            (directory / 'same.svh').write_text('// same bytes, ambiguous identity\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            rom_gate.include_closure(self.repo, [self.source], self.stage)

    def test_escape_rejected(self):
        self.source.write_text('`include "../../../../../outside.svh"\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            rom_gate.include_closure(self.repo, [self.source], self.stage)

    def test_cycle_rejected(self):
        self.source.write_text('`include "a.svh"\n', encoding='utf-8')
        (self.common / 'a.svh').write_text('`include "a.svh"\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            rom_gate.include_closure(self.repo, [self.source], self.stage)


if __name__ == '__main__':
    unittest.main(verbosity=2)
