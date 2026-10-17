"""Exactly one newly authorized verbose compile; never execute its product."""
import json
from pathlib import Path
import sys
import time

import run_r09 as m


def main():
    m.require(len(sys.argv) == 1, 'NO_CALLER_ARGUMENTS_ALLOWED')
    authorization_path = m.HERE / 'R09_DIAG_AUTHORIZATION_20261017.json'
    authorization = json.loads(authorization_path.read_text(encoding='utf-8'))
    m.require(authorization['approved'] is True and authorization['scope'] == 'R09_DIAG_01_RAW_COMPILE_VERBOSE_ONLY', 'USER_SCOPE_REQUIRED')
    m.require(authorization['group_seconds'] == 20 and authorization['compile_seconds'] == 15 and
              authorization['compile_launches_max'] == 1 and authorization['retry_allowed'] is False, 'EXACT_BUDGET_REQUIRED')
    for key in ['VVP_allowed', 'boundary_allowed', 'EDA_allowed', 'device_allowed', 'old_budgets_restored']:
        m.require(authorization[key] is False, 'NO_EXTRA_PERMISSION:' + key)
    inputs = m.base_inputs()
    proof_path = m.OUT / 'SW_FIX_01/GROUP_RECEIPT.json'
    proof = json.loads(proof_path.read_text(encoding='utf-8'))
    m.require(proof['passed'] is True and proof['inputs'] == inputs and proof['inputs_unchanged'] is True, 'PROVEN_RUNTIME_CHANGED')
    original_admission_path = m.HERE / 'EXECUTION_ADMISSION_R09_UNIT01.json'
    original = json.loads(original_admission_path.read_text(encoding='utf-8'))
    tools = m.required_tool_files()
    m.require(tools == original['tool_files'], 'ORIGINAL_TOOL_SET_CHANGED')
    m.check_tool_startup_inputs()
    sources = m.unit_sources()
    selected = {name: sources[name] for name in m.UNITS['raw']['files']}
    for name, raw in selected.items():
        m.require({'bytes': len(raw), 'sha256': __import__('hashlib').sha256(raw).hexdigest()} == original['unit_source_identities'][name], 'RAW_SOURCE_CHANGED')
    original_step = m.OUT / 'UNIT_01/raw_compile/RECEIPT.json'
    previous = json.loads(original_step.read_text(encoding='utf-8'))
    expected = [str(m.IVERILOG), '-B', str(m.IVL), '-g2012', '-t', 'vvp', '-s', m.UNITS['raw']['top'],
                '-o', 'unit.vvp', *m.UNITS['raw']['files']]
    m.require(previous['argv'] == expected, 'ORIGINAL_ARGV_CHANGED')
    argv = expected[:1] + ['-v'] + expected[1:]
    inputs.update(tools)
    for path in [Path(__file__).resolve(), authorization_path, proof_path, original_admission_path, original_step, m.C7]:
        inputs[str(path)] = m.identity(path)
    group, deadline = m.begin_group('R09_DIAG_01', 20, inputs)
    source_dir = group / 'source'
    source_dir.mkdir()
    for name, raw in selected.items():
        path = source_dir / name
        path.write_bytes(raw)
        inputs[str(path)] = m.identity(path)
    admission_path = group / 'DIAGNOSTIC_ADMISSION.json'
    m.save(admission_path, {'scope': authorization['scope'], 'approved': True, 'argv': argv,
                            'original_argv': expected, 'inputs': dict(inputs), 'group_seconds': 20,
                            'compile_seconds': 15, 'environment': m.environment(tool=True),
                            'only_new_switch': '-v', 'no_product_execution': True, 'board_release_allowed': False})
    inputs[str(admission_path)] = m.identity(admission_path)
    operations = {'raw_compile_verbose': {'argv': argv, 'seconds': 15,
                   'stage_files': [(str(source_dir / name), name) for name in selected]}}
    runner = m.ExactRunner(m.HELPER, group, operations, inputs, m.environment(tool=True))
    receipt = None
    try:
        receipt = runner.execute('raw_compile_verbose', deadline)
    finally:
        result = {'scope': authorization['scope'], 'consumed': True, 'ended_utc': m.utc(),
                  'group_deadline_kept': time.monotonic() <= deadline, 'step_returned': receipt is not None,
                  'compiler_clean_exit': bool(receipt and receipt['clean_exit']),
                  'compiler_exit_code': receipt['root_exit_code'] if receipt else None,
                  'VVP_launches': 0, 'boundary_launches': 0, 'EDA_device_calls': 0,
                  'raw_unit_simulation_passed': False, 'board_release_allowed': False}
        if receipt:
            result['step_receipt'] = str(group / 'raw_compile_verbose/RECEIPT.json')
        m.save(group / 'GROUP_RECEIPT.json', result)
    print(json.dumps(result), flush=True)
    return 0 if receipt and receipt['clean_exit'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
