"""Incremental receipt-format tests; no HDL or old test groups run."""
import json
from pathlib import Path
import tempfile
import unittest

import b_harness as h


class RecoveryGateTests(unittest.TestCase):
    def setUp(self):
        self.receipt = json.loads((h.ROOT / 'code/output/'
            'm3_n32_a_function_recovery_run_20261014_02/receipt.json').read_bytes())
        self.relative = h.A_ALLOCATOR.relative_to(h.ROOT).as_posix()

    def check_receipt(self, value):
        with tempfile.TemporaryDirectory(dir=h.ROOT / 'code/output') as name:
            path = Path(name) / 'receipt.json'
            path.write_text(json.dumps(value), encoding='utf-8')
            return h.validate_a_gate(path, h.identity(path)['sha256'],
                h.identity(h.A_ALLOCATOR)['sha256'],
                'N32-A-FUNCTION-RECOVERY-20261014-R01')

    def test_actual_relative_receipt(self):
        self.assertEqual(self.check_receipt(self.receipt)['exit_code'], 0)

    def test_legacy_absolute_binding(self):
        after = self.receipt['identities_after']
        after[str(h.A_ALLOCATOR)] = after.pop(self.relative)
        self.check_receipt(self.receipt)

    def test_resigned_bad_relative_binding_rejected(self):
        self.receipt['identities_after'][self.relative]['sha256'] = '0' * 64
        with self.assertRaisesRegex(Exception, 'A_RECEIPT_ALLOCATOR_BINDING'):
            self.check_receipt(self.receipt)

    def test_conflicting_alias_rejected(self):
        self.receipt['identities_after'][str(h.A_ALLOCATOR)] = {'bytes': 0, 'sha256': '0' * 64}
        with self.assertRaisesRegex(Exception, 'A_RECEIPT_ALLOCATOR_BINDING'):
            self.check_receipt(self.receipt)


if __name__ == '__main__':
    unittest.main()
