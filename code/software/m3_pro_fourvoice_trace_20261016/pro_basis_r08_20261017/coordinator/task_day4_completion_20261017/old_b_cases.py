"""Call the unchanged B C9 13-case definition with its original four args."""
import hashlib
import json
from pathlib import Path
from types import ModuleType
import sys

COMMON = Path(__file__).with_name('common.py')
raw = COMMON.read_bytes()
if hashlib.sha256(raw).hexdigest() != '55cb7481fe9c0870247a7d8b2453dea859f0f2e81879795cc0e34ffe8c996dca':
    raise ValueError('COMMON_SOURCE_CHANGED')
c = ModuleType('_d4_old_b_common')
c.__file__ = str(COMMON)
sys.modules[c.__name__] = c
exec(compile(raw, str(COMMON), 'exec'), c.__dict__)


def run_case(case_id, output_dir):
    binding = c.read_json(c.DOC / 'MODULE_BINDINGS.json')
    test = binding['legacy_b_selftest']
    source = binding['legacy_b_candidate']
    module = c.load_source(c.checked_descriptor(test), test['sha256'])
    result = module.run_case(case_id, output_dir, c.checked_descriptor(source), source['sha256'])
    c.require(result['matched'] is True, 'OLD_B_ASSERTION_NOT_MATCHED')
    return {'route': 'ORIGINAL_RUN_CASE_FOUR_ARGUMENTS', 'result': result,
            'selftest': test, 'candidate': source}
