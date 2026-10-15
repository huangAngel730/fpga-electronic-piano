"""Independent literal log expectations, including the retained false-green."""
import json
from pathlib import Path
import tempfile
import unittest
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
