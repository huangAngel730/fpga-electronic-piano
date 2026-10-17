"""Fixed R09 entry point: new software group, then two admitted HDL units."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import zipfile

from owned_unit_runtime import ExactRunner, FixtureAbort, identity, no_reparse, save, utc

if sys.flags.optimize:
    raise PermissionError('OPTIMIZED_MODE_IS_NOT_AUTHORIZED')

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
OUT = ROOT / 'code/output/m2_unit_execution_c8_20261017'
HELPER = ROOT / 'code/software/t052_runner_acceptance_candidate_20261012/windows_job.py'
FIXTURE = HERE / 'unit_fixture.py'
PYTHON = Path(sys.executable).resolve()
SIDE = ROOT / 'code/rtl/board/m2_138k_pro_fourvoice_candidate_20261016/r06_observer_20261017'
TB = ROOT / 'code/tb/board/m2_138k_pro_fourvoice_candidate_20261016/r06_observer_20261017/c7_continue_20261017'
C7 = ROOT / 'code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/r06_public_chain_20261017/c7_continue_20261017/SOURCE_CLOSURE_R06C7.zip'
C7_SHA = 'd191132ad9eae52fd35e4c1bd17d598e5204d3d7c4b8bdd3ca3a423e37eff226'
IVERILOG = Path('D:/Gowin/oss-cad-suite/bin/iverilog.exe')
VVP = Path('D:/Gowin/oss-cad-suite/bin/vvp.exe')
IVL = Path('D:/Gowin/oss-cad-suite/lib/ivl')
TOOL_FILES_SOURCE = OUT / 'tool_inventory/TOOL_FILES.json'
TOOL_BINDING_SOURCE = OUT / 'tool_inventory/TOOL_RUNTIME_BINDING.json'
TOOL_FILES_SHA = 'c2a79e3eb6086bab7d689b56944e722b86145aae4b905d65273f6df9131383a5'
TOOL_BINDING_SHA = 'ccb5cf0935f2d33428ba3adff1e82d507911255a02be3f72725f1c4b8276cef5'
UNITS = {
    'raw': {'top': 'tb_m2_r06_raw_cancel_reason', 'marker': 'PASS raw_cancel_reason checks=7',
            'files': ['m2_r06_raw_cancel_reason.sv', 'tb_m2_r06_raw_cancel_reason.sv']},
    'boundary': {'top': 'tb_m2_r06_tx_identity_boundary_c7', 'marker': 'PASS M2_R06_SIDECAR_BOUNDARY_C7 ',
                 'files': ['pcm_result_hold.sv', 'pcm_frame_buffer.sv', 'm2_r06_tx_identity_sidecar.sv',
                           'tb_m2_r06_tx_identity_boundary_c7.sv']},
}


def require(condition, reason):
    if not condition:
        raise PermissionError(reason)


def required_tool_files():
    require(identity(TOOL_FILES_SOURCE)['sha256'] == TOOL_FILES_SHA, 'FIXED_TOOL_CATALOG_CHANGED')
    require(identity(TOOL_BINDING_SOURCE)['sha256'] == TOOL_BINDING_SHA, 'FIXED_TOOL_BINDING_CHANGED')
    files = json.loads(TOOL_FILES_SOURCE.read_text(encoding='utf-8'))['files']
    binding = json.loads(TOOL_BINDING_SOURCE.read_text(encoding='utf-8'))
    rows = binding['full_ivl_directory_catalog_not_execution_permission']
    for row in rows:
        expected = {key: row[key] for key in ('bytes', 'sha256')}
        require(row['path'] not in files or files[row['path']] == expected, 'CONFLICTING_TOOL_CATALOG')
        files[row['path']] = expected
    require(len(files) == 50 and len(rows) == 36, 'FIXED_TOOL_CATALOG_COUNT')
    require({str(p.resolve()).casefold() for p in IVL.rglob('*') if p.is_file()} ==
            {str(Path(row['path']).resolve()).casefold() for row in rows}, 'IVL_DIRECTORY_MEMBERS_CHANGED')
    for path, expected in files.items():
        no_reparse(path)
        require(identity(path) == expected, 'TOOL_FILE_CHANGED:' + path)
    return files


def check_tool_startup_inputs():
    import winreg
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            try:
                with winreg.OpenKey(hive, r'Software\Microsoft\Command Processor', 0, winreg.KEY_READ | view) as key:
                    try:
                        winreg.QueryValueEx(key, 'AutoRun')
                    except FileNotFoundError:
                        continue
                    raise PermissionError('COMMAND_PROCESSOR_AUTORUN_PRESENT')
            except FileNotFoundError:
                pass
    for path in [IVERILOG, VVP, IVL / 'ivl.exe', IVL / 'ivlpp.exe', Path(environment()['COMSPEC'])]:
        for suffix in ('.local', '.manifest'):
            require(not Path(str(path) + suffix).exists(), 'TOOL_SIDECAR_PRESENT:' + str(path) + suffix)


def product_vpi_binding(product, tools):
    raw = product.read_text(encoding='utf-8')
    entries = re.findall(r'^\s*:vpi_module\s+"([^"]+)"\s*;', raw, re.M)
    require(bool(entries), 'NO_VPI_MODULE_BINDING_IN_PRODUCT')
    allowed = {str(Path(path).resolve()).casefold(): expected for path, expected in tools.items()
               if Path(path).suffix.lower() == '.vpi' and Path(path).parent.resolve() == IVL.resolve()}
    result = []
    for path in entries:
        resolved = no_reparse(Path(path).resolve(strict=True))
        key = str(resolved).casefold()
        require(key in allowed and identity(resolved) == allowed[key], 'UNBOUND_VPI_MODULE:' + path)
        result.append({'product_spelling': path, 'resolved': str(resolved), **identity(resolved)})
    require(len({row['resolved'].casefold() for row in result}) == len(result), 'DUPLICATE_VPI_REQUEST')
    return result


def base_inputs():
    paths = [Path(__file__), HERE / 'owned_unit_runtime.py', FIXTURE, HELPER, PYTHON]
    python_dll = PYTHON.parent / ('python%d%d.dll' % sys.version_info[:2])
    if python_dll.is_file():
        paths.append(python_dll)
    return {str(path.resolve()): identity(path) for path in paths}


def environment(tool=False):
    windows = Path(os.environ['SystemRoot']).resolve()
    result = {'SystemRoot': str(windows), 'WINDIR': str(windows),
              'COMSPEC': str(windows / 'System32/cmd.exe'),
              'PATH': str(windows / 'System32'), 'PYTHONIOENCODING': 'utf-8'}
    if tool:
        result['PATH'] = os.pathsep.join([str(IVERILOG.parent), str(IVL.parent), result['PATH']])
    return result


def begin_group(name, seconds, inputs):
    OUT.mkdir(parents=True, exist_ok=True)
    no_reparse(OUT)
    group = OUT / name
    group.mkdir(exist_ok=False)
    with (group / 'CONSUMED.json').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps({'scope': 'R09_' + name, 'consumed_before_any_launch': True,
                                 'started_utc': utc(), 'group_seconds': seconds,
                                 'inputs': inputs, 'old_budgets_restored': False}, indent=2) + '\n')
    return group, time.monotonic() + seconds


def lifecycle_ok(receipt):
    return all(receipt.get(key) is True for key in ['job_empty_before_close', 'root_handle_signaled',
                                                   'root_handle_closed', 'streams_closed_after_job_empty',
                                                   'inputs_unchanged', 'group_deadline_kept', 'receipt_complete']) and 'cleanup_error' not in receipt


def software():
    inputs = base_inputs()
    group, deadline = begin_group('SW_01', 90, inputs)
    modes = ['normal', 'nonzero', 'orphan', 'timeout', 'flood']
    operations = {mode: {'argv': [str(PYTHON), '-I', '-S', '-B', str(FIXTURE), mode],
                         'seconds': 2 if mode == 'timeout' else 4, 'software_fixture': True,
                         'log_watermark': 32768 if mode == 'flood' else 1048576}
                  for mode in modes}
    operations['pre_attach_abort'] = {'argv': [str(PYTHON), '-I', '-S', '-B', str(FIXTURE), 'normal'],
                                      'seconds': 4, 'software_fixture': True}
    for name in ('tail_log_guard', 'abort_receipt_error'):
        operations[name] = {'argv': [str(PYTHON), '-I', '-S', '-B', str(FIXTURE), 'normal'],
                            'seconds': 4, 'software_fixture': True, 'log_watermark': 32768}
    runner = ExactRunner(HELPER, group, operations, inputs, environment())
    results = {}
    passed = False
    try:
        changed = dict(operations['normal'])
        changed['argv'] = [str(PYTHON), '-c', 'raise SystemExit(0)']
        try:
            runner.validate_request('normal', changed)
            raise AssertionError('TAMPERED_OPERATION_ACCEPTED')
        except PermissionError:
            results['changed_argv_rejected_before_launch'] = True
        try:
            runner.validate_request('arbitrary_command')
            raise AssertionError('UNKNOWN_OPERATION_ACCEPTED')
        except PermissionError:
            results['unknown_operation_rejected_before_launch'] = True
        expected = {'normal': ('ROOT_AND_JOB_EXITED', 0), 'nonzero': ('ROOT_AND_JOB_EXITED', 7),
                    'orphan': ('JOB_NONEMPTY_AFTER_ROOT_EXIT', 0), 'timeout': ('TIMEOUT', None),
                    'flood': ('LOG_WATERMARK', None)}
        for mode in modes:
            receipt = runner.execute(mode, deadline)
            reason, code = expected[mode]
            assert receipt['stop_reason'] == reason and lifecycle_ok(receipt), (mode, receipt)
            if code is not None:
                assert receipt['root_exit_code'] == code
            assert receipt['clean_exit'] == (mode == 'normal')
            if mode in ('orphan', 'timeout'):
                assert receipt['accounting_before_cleanup']['total_processes'] >= 3
                assert not list((group / mode).glob('ESCAPED_*'))
            if mode == 'normal':
                assert (group / mode / 'stdout.raw').read_text(encoding='utf-8').strip() == 'R09_NEW_STDOUT'
                assert (group / mode / 'stderr.raw').read_text(encoding='utf-8').strip() == 'R09_NEW_STDERR'
            results[mode] = {'expected_behavior_met': True, 'receipt': str(group / mode / 'RECEIPT.json')}
            print(json.dumps({'software_case': mode, 'expected_behavior_met': True}), flush=True)
        receipt = runner.execute('tail_log_guard', deadline, software_fault_tail_log=True)
        require(lifecycle_ok(receipt) and receipt['stop_reason'] == 'LOG_WATERMARK_FINAL' and
                receipt['log_limit_observed'] and not receipt['clean_exit'], 'TAIL_LOG_GUARD_FAILED')
        results['tail_log_guard'] = {'expected_behavior_met': True, 'receipt': str(group / 'tail_log_guard/RECEIPT.json')}
        try:
            runner.execute('pre_attach_abort', deadline, software_fault_before_attach=True)
            raise AssertionError('BASE_EXCEPTION_NOT_RERAISED')
        except FixtureAbort:
            receipt = json.loads((group / 'pre_attach_abort/RECEIPT.json').read_text(encoding='utf-8'))
            assert lifecycle_ok(receipt) and receipt['stop_reason'] == 'EXCEPTION'
            assert receipt['cleanup'] == 'CURRENT_UNATTACHED_POPEN_HANDLE_KILL_AND_WAIT'
            assert not receipt['job_attached'] and not receipt['clean_exit']
            results['pre_attach_abort'] = {'expected_behavior_met': True, 'receipt': str(group / 'pre_attach_abort/RECEIPT.json')}
        try:
            runner.execute('abort_receipt_error', deadline, software_fault_before_attach=True, software_fault_receipt=True)
            raise AssertionError('PRIMARY_ABORT_NOT_PRESERVED')
        except FixtureAbort:
            receipt = json.loads((group / 'abort_receipt_error/FINALIZATION_FAILURE.json').read_text(encoding='utf-8'))
            require(receipt['error'].startswith('FixtureAbort:') and not receipt['receipt_complete'] and
                    not receipt['clean_exit'] and receipt['job_empty_before_close'] and receipt['root_handle_closed'] and
                    any('FIXTURE_RECEIPT_WRITE_FAILURE' in value for value in receipt['finalization_errors']),
                    'PRIMARY_ABORT_OR_CLEANUP_EVIDENCE_LOST')
            require(not (group / 'abort_receipt_error/RECEIPT.json').exists(), 'INCOMPLETE_RECEIPT_MISLABELLED')
            results['abort_receipt_error'] = {'expected_behavior_met': True, 'receipt': str(group / 'abort_receipt_error/FINALIZATION_FAILURE.json')}
        try:
            runner.execute('normal', deadline)
            raise AssertionError('REPEATED_STEP_ACCEPTED')
        except FileExistsError:
            results['duplicate_step_rejected_before_launch'] = True
        passed = True
    finally:
        result = {'scope': 'R09_EXECUTOR_SW01', 'passed': passed, 'results': results,
                  'inputs': inputs, 'inputs_unchanged': all(identity(path) == expected for path, expected in inputs.items()),
                  'ended_utc': utc(), 'group_deadline_kept': time.monotonic() <= deadline,
                  'HDL_calls': 0, 'old_executor_changed': False, 'board_release_allowed': False}
        result['passed'] = passed and result['inputs_unchanged'] and result['group_deadline_kept']
        save(group / 'GROUP_RECEIPT.json', result)
    print(json.dumps({'software_group_passed': result['passed'], 'receipt': str(group / 'GROUP_RECEIPT.json')}), flush=True)
    return 0 if result['passed'] else 1


def unit_sources():
    if identity(C7)['sha256'] != C7_SHA:
        raise PermissionError('C7_ARCHIVE_IDENTITY')
    with zipfile.ZipFile(C7) as archive:
        manifest = json.loads(archive.read('MANIFEST.json'))
        result = {}
        for name in ['pcm_result_hold.sv', 'pcm_frame_buffer.sv']:
            member = 'inputs/sources/' + name
            raw = archive.read(member)
            require({'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} == manifest['payloads'][member], 'C7_MEMBER_CHANGED')
            result[name] = raw
    for rel in [SIDE / 'c7_continue_20261017/m2_r06_raw_cancel_reason.sv',
                TB / 'tb_m2_r06_raw_cancel_reason.sv', SIDE / 'm2_r06_tx_identity_sidecar.sv',
                TB / 'tb_m2_r06_tx_identity_boundary_c7.sv']:
        result[rel.name] = rel.read_bytes()
    admission_c7 = ROOT / 'code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/r06_public_chain_20261017/c7_continue_20261017/UNIT_ADMISSION_R06C7.json'
    old = json.loads(admission_c7.read_text(encoding='utf-8'))['unit_inputs']
    for key, expected in old.items():
        name = key.rsplit('/', 1)[-1]
        require({'bytes': len(result[name]), 'sha256': hashlib.sha256(result[name]).hexdigest()} == expected, 'UNIT_SOURCE_CHANGED:' + name)
    return result


def units():
    # This file is produced by M2 only after the new software proof/tool freeze.
    admission_path = HERE / 'EXECUTION_ADMISSION_R09_UNIT01.json'
    admission = json.loads(admission_path.read_text(encoding='utf-8'))
    inputs = base_inputs()
    require(admission['approved'] is True and admission['scope'] == 'R09_UNIT01_RAW_AND_BOUNDARY_ONLY', 'UNIT_SCOPE_NOT_APPROVED')
    require(admission['runner_inputs'] == inputs, 'APPROVED_RUNNER_CHANGED')
    proof_path = OUT / 'SW_FIX_01/GROUP_RECEIPT.json'
    require(identity(proof_path) == admission['software_proof_identity'], 'SOFTWARE_PROOF_CHANGED')
    proof = json.loads(proof_path.read_text(encoding='utf-8'))
    require(proof['scope'] == 'R09_EXECUTOR_SW01' and proof['passed'] is True and proof['inputs_unchanged'] is True and
            proof['group_deadline_kept'] is True and proof['inputs'] == inputs, 'SOFTWARE_PROOF_NOT_FOR_CURRENT_RUNNER')
    tools = required_tool_files()
    require(admission['tool_files'] == tools, 'ADMISSION_TOOL_CATALOG_INCOMPLETE_OR_CHANGED')
    check_tool_startup_inputs()
    for path, expected in tools.items():
        inputs[path] = expected
    sources = unit_sources()
    require({name: {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} for name, raw in sources.items()} == admission['unit_source_identities'], 'APPROVED_UNIT_SOURCE_SET_CHANGED')
    inputs[str(proof_path)] = identity(proof_path)
    inputs[str(TOOL_FILES_SOURCE)] = identity(TOOL_FILES_SOURCE)
    inputs[str(TOOL_BINDING_SOURCE)] = identity(TOOL_BINDING_SOURCE)
    inputs[str(admission_path)] = identity(admission_path)
    inputs[str(C7)] = identity(C7)
    group, deadline = begin_group('UNIT_01', 60, inputs)
    source_root = group / 'source'
    source_root.mkdir()
    for name, raw in sources.items():
        (source_root / name).write_bytes(raw)
        inputs[str(source_root / name)] = identity(source_root / name)
    operations = {}
    for key, spec in UNITS.items():
        operations[key + '_compile'] = {
            'argv': [str(IVERILOG), '-B', str(IVL), '-g2012', '-t', 'vvp', '-s', spec['top'], '-o', 'unit.vvp', *spec['files']],
            'seconds': 15, 'stage_files': [(str(source_root / name), name) for name in spec['files']]}
    runner = ExactRunner(HELPER, group, operations, inputs, environment(tool=True))
    results = {}
    passed = False
    try:
        for key, spec in UNITS.items():
            compile_receipt = runner.execute(key + '_compile', deadline)
            require(compile_receipt['clean_exit'] and lifecycle_ok(compile_receipt), 'COMPILE_FAILED:' + key)
            product = group / (key + '_compile') / 'unit.vvp'
            require(product.is_file() and product.stat().st_size > 0, 'COMPILE_PRODUCT_MISSING:' + key)
            vpi = product_vpi_binding(product, tools)
            save(group / (key + '_compile') / 'PRE_RUNTIME_VPI_BINDING.json', vpi)
            runner.inputs[str(product)] = identity(product)
            operations[key + '_run'] = {'argv': [str(VVP), '-M-', '-M', str(IVL), str(product)], 'seconds': 10}
            run_receipt = runner.execute(key + '_run', deadline)
            require(run_receipt['clean_exit'] and lifecycle_ok(run_receipt), 'SIMULATION_FAILED:' + key)
            stdout = (group / (key + '_run') / 'stdout.raw').read_text(encoding='utf-8')
            require(spec['marker'] in stdout, 'TB_PASS_MARKER_MISSING:' + key)
            results[key] = {'passed': True, 'compile_receipt': str(group / (key + '_compile') / 'RECEIPT.json'),
                            'run_receipt': str(group / (key + '_run') / 'RECEIPT.json'), 'product': identity(product),
                            'stdout': stdout, 'VPI_binding': vpi}
            print(json.dumps({'unit': key, 'passed': True, 'stdout': stdout}), flush=True)
        passed = True
    finally:
        result = {'scope': 'R09_UNIT01_RAW_AND_BOUNDARY_ONLY', 'passed': passed, 'results': results,
                  'ended_utc': utc(), 'group_deadline_kept': time.monotonic() <= deadline,
                  'board_release_allowed': False, 'full_chain_executed': False}
        result['passed'] = passed and result['group_deadline_kept']
        save(group / 'GROUP_RECEIPT.json', result)
    return 0 if result['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['software', 'units'])
    args = parser.parse_args()
    return software() if args.phase == 'software' else units()


if __name__ == '__main__':
    raise SystemExit(main())
