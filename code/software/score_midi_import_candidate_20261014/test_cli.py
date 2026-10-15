"""Exercise actual CLI subprocesses with independent literal SMF and records."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('midi_import.py')
# PPQN=480, 480 ticks at 500000us/quarter = 24000 samples.
SMF = bytes.fromhex('4d546864000000060000000101e04d54726b0000000d00903c648360803c0000ff2f00')
EXPECTED = bytes.fromhex('0000000000003c64c05d000001003c00')


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='midi_import_cli_')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root / 'notes.mid'
        self.input.write_bytes(SMF)

    def invoke(self, *args):
        return subprocess.run([sys.executable, '-B', '-X', 'utf8', str(SCRIPT), *map(str, args)], capture_output=True, timeout=15)

    def import_score(self, out='good', *args):
        return self.invoke('import', '--input', self.input, '--output', self.root / out, *args)

    def test_full_import_literal_bytes_and_verify(self):
        result = self.import_score()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        out = self.root / 'good'
        self.assertEqual((out / 'records.bin').read_bytes(), EXPECTED)
        receipt = json.loads((out / 'receipt.json').read_bytes())
        self.assertEqual(receipt['serial_calls'], 0)
        self.assertFalse(receipt['hardware_pass_claim'])
        checked = self.invoke('verify', '--score', out / 'score.json', '--records', out / 'records.bin', '--upload', out / 'upload.bin', '--output', self.root / 'verified')
        self.assertEqual(checked.returncode, 0, checked.stderr + checked.stdout)

    def test_existing_output_refused_without_modification(self):
        self.assertEqual(self.import_score().returncode, 0)
        before = {p.name: p.read_bytes() for p in (self.root / 'good').iterdir()}
        self.assertEqual(self.import_score().returncode, 2)
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.root / 'good').iterdir()})

    def test_malformed_input_nonzero_with_receipt(self):
        self.input.write_bytes(SMF[:-1])
        self.assertEqual(self.import_score().returncode, 1)
        receipt = json.loads((self.root / 'good/receipt.json').read_bytes())
        self.assertEqual(receipt['status'], 'FAIL')
        self.assertNotIn('readback', receipt)

    def test_invalid_session_nonzero(self):
        self.assertEqual(self.import_score('bad_session', '--session', '0').returncode, 1)

    def test_records_tamper_rejected(self):
        self.assertEqual(self.import_score().returncode, 0)
        out = self.root / 'good'
        raw = bytearray((out / 'records.bin').read_bytes())
        raw[6] ^= 1
        corrupt = self.root / 'corrupt.bin'
        corrupt.write_bytes(raw)
        result = self.invoke('verify', '--score', out / 'score.json', '--records', corrupt, '--upload', out / 'upload.bin', '--output', self.root / 'bad_readback')
        self.assertEqual(result.returncode, 1)
        receipt = json.loads((self.root / 'bad_readback/receipt.json').read_bytes())
        self.assertEqual(receipt['status'], 'FAIL')
        self.assertIn('READBACK_RECORD_MISMATCH', receipt['error'])
        self.assertNotIn('readback', receipt)

    def test_verify_resource_limits(self):
        self.assertEqual(self.import_score().returncode, 0)
        out = self.root / 'good'
        files = {'score': out / 'score.json', 'records': out / 'records.bin', 'upload': out / 'upload.bin'}
        for key, size in (('score', 2 * 1024 * 1024 + 1), ('records', 4097), ('upload', 65537)):
            oversized = self.root / (key + '_oversized')
            oversized.write_bytes(b'0' * size)
            selected = dict(files)
            selected[key] = oversized
            result = self.invoke('verify', '--score', selected['score'], '--records', selected['records'], '--upload', selected['upload'], '--output', self.root / ('bad_size_' + key))
            self.assertEqual(result.returncode, 1)
            receipt = json.loads((self.root / ('bad_size_' + key) / 'receipt.json').read_bytes())
            self.assertIn('VERIFY_RESOURCE_LIMIT', receipt['error'])

    def test_duplicate_json_key_rejected(self):
        self.assertEqual(self.import_score().returncode, 0)
        out = self.root / 'good'
        score = self.root / 'duplicate.json'
        score.write_text('{"schema":1,"schema":1}', encoding='utf-8')
        result = self.invoke('verify', '--score', score, '--records', out / 'records.bin', '--upload', out / 'upload.bin', '--output', self.root / 'bad_json')
        self.assertEqual(result.returncode, 1)


if __name__ == '__main__':
    unittest.main()
