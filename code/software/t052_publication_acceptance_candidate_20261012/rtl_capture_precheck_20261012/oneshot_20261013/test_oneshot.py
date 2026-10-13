"""Only new preparation/permission guards; no P0 replay or tool invocation."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
loader = importlib.util.spec_from_file_location('oneshot', HERE / 'oneshot.py')
m = importlib.util.module_from_spec(loader)
loader.loader.exec_module(m)


class Guards(unittest.TestCase):
    def test_no_permission_cannot_reach_preflight(self):
        with patch.object(m, 'verify', side_effect=AssertionError('MUST_NOT_REACH')):
            with self.assertRaisesRegex(ValueError, 'M2_EXACT_PERMISSION_REQUIRED'):
                m.execute(None, None, None, None)

    def test_config_pin_checked_before_contents(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'config.json'
            path.write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'CONFIG_EXTERNAL_PIN'):
                m.verify(path, '0' * 64)

    def test_wrong_machine_rejected_before_tools(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'config.json'
            m.write(path, {'schema': m.SCHEMA, 'execution_authorized': False,
                           'machine': 'NOT_THIS_HOST'})
            with self.assertRaisesRegex(ValueError, 'MACHINE_IDENTITY'):
                m.verify(path, m.identity(path)['sha256'])

    def test_prepare_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'OUTPUT_EXISTS'):
                m.prepare(Path(temp), None)

    def test_permission_exact_config_calls_budget_and_types(self):
        # These are local SOFTWARE permit-validator inputs, never execute inputs.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config_path = root / 'config.json'
            config = {'machine': 'SOFTWARE_ONLY', 'calls': {'compile': 1, 'run': 1, 'check': 1},
                      'budgets_seconds': m.BUDGETS}
            m.write(config_path, config)
            approval = {'schema': 'T052_128_ONESHOT_APPROVAL_V1',
                        'scope': 'ONE_COMPILE_ONE_128_EDGE_RUN_ONE_CHECK', 'approved': True,
                        'config_sha256': m.identity(config_path)['sha256'],
                        'machine': config['machine'], 'calls': config['calls'],
                        'budgets_seconds': config['budgets_seconds'],
                        'accept_static_dependency_inventory': True}
            cases = [('normal', None, None), ('bad_config', 'config_sha256', '0' * 64),
                     ('approved_integer', 'approved', 1), ('wrong_host', 'machine', 'OTHER'),
                     ('call_count', 'calls', {'compile': 2, 'run': 1, 'check': 1}),
                     ('budget', 'budgets_seconds', {**m.BUDGETS, 'total': 301}),
                     ('load_claim', 'accept_static_dependency_inventory', False)]
            for name, key, value in cases:
                candidate = copy.deepcopy(approval)
                if key:
                    candidate[key] = value
                path = root / (name + '.json')
                m.write(path, candidate)
                with self.subTest(case=name):
                    if key:
                        with self.assertRaisesRegex(ValueError, 'APPROVAL_EXACT_SCOPE'):
                            m.require_permit(path, m.identity(path)['sha256'], config_path, config)
                    else:
                        m.require_permit(path, m.identity(path)['sha256'], config_path, config)
                    with self.assertRaisesRegex(ValueError, 'APPROVAL_EXTERNAL_PIN'):
                        m.require_permit(path, '0' * 64, config_path, config)

    def test_environment_restored_on_failure(self):
        before = dict(os.environ)
        with self.assertRaisesRegex(RuntimeError, 'injected'):
            with m.environment({'TEST_ISOLATED_ONLY': '1'}):
                self.assertEqual(dict(os.environ), {'TEST_ISOLATED_ONLY': '1'})
                raise RuntimeError('injected')
        self.assertEqual(dict(os.environ), before)

    def test_duplicate_json_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'bad.json'
            path.write_text('{"approved":false,"approved":true}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'DUPLICATE_JSON_KEY'):
                m.read(path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
