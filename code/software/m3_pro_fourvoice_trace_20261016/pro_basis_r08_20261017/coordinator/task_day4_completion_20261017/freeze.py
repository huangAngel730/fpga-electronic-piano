"""Metadata-only freeze/reconciliation. Never imports candidate modules."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[6]
SUFFIX = 'm3_pro_fourvoice_trace_20261016'
SW = ROOT / 'code/software' / SUFFIX
TB = ROOT / 'code/tb/board' / SUFFIX
BASE = ROOT / 'code/docs/test' / SUFFIX
DOC = BASE / 'pro_basis_r08_20261017/coordinator/task_day4_completion_20261017'
OWN = Path(__file__).parent
AUDIT = DOC.parent / 'task_day4_intake_20261017/REMAINDER_AUDIT.json'
AUDIT_SHA = '9f3e2b55ec2f525ca2bfbdbdd187011d1c041ddb80a96338e6f68fe231f9f016'


def ident(path):
    h, size = hashlib.sha256(), 0
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            size += len(block)
            h.update(block)
    return {'bytes': size, 'sha256': h.hexdigest()}


def desc(path):
    return {'path': Path(path).relative_to(ROOT).as_posix(), **ident(path)}


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def bindings():
    relatives = {
        'application': 'pro_basis_r08_20261017/build_admission_bundle/c9_completion_r01/assembler.py',
        'stream': 'pro_basis_r07_20261017/public_capture_tb/c9_completion_r01/c9_stream.py',
        'codec': 'pro_basis_r08_20261017/capture_csv_codec/c9_completion_r01/c9_codec.py',
        'intake': 'pro_basis_r06_20261017/normalized_intake/c9_completion_r01/intake_adapter.py',
        'math': 'pro_basis_r07_20261017/oracle_bundle_bridge/c9_completion_r01/math_bundle.py',
        'serial': 'pro_basis_r06_20261017/tx_clock_reset_checker/c9_completion_r01/serial.py',
        'frame_generator': 'pro_basis_r06_20261017/event_calendar/frame_plan_generator_candidate.py',
        'calendar': 'pro_basis_r06_20261017/event_calendar/r07_fix/calendar_r07_fix_candidate.py',
        'provenance': str((OWN / 'provenance.py').relative_to(SW)),
    }
    return {'schema': 'M3_C9_CHAIN_MODULE_BINDINGS_V1',
            'modules': {name: desc(SW / path) for name, path in relatives.items()},
            'chain': desc(OWN / 'chain.py'),
            'legacy_b_selftest': desc(SW / 'pro_basis_r07_20261017/public_equivalence_tb/c9_binding/selftest.py'),
            'legacy_b_candidate': desc(SW / 'pro_basis_r07_20261017/public_equivalence_tb/c9_binding/c9_pair.py')}


def all_cases():
    assert ident(AUDIT)['sha256'] == AUDIT_SHA, 'ORIGINAL_REMAINDER_AUDIT_CHANGED'
    audit = load(AUDIT)['unrun_software']
    result = []
    def add(component, manifest, selftest, wanted=None):
        data = load(manifest)
        selected = data['cases']
        if wanted is not None:
            selected = [case for case in selected if case.get('id', case.get('name')) in wanted]
            assert len(selected) == len(wanted), component
        for case in selected:
            result.append({'component': component, 'id': case.get('id', case.get('name')),
                'selftest': Path(selftest).relative_to(ROOT).as_posix(),
                'case_manifest': Path(manifest).relative_to(ROOT).as_posix(), 'definition': case})
    for component in dict.fromkeys(case['component'] for case in audit['R08']['cases']):
        add('OLD_R08_' + component, TB / 'pro_basis_r08_20261017' / component / 'CASES.json',
            SW / 'pro_basis_r08_20261017' / component / 'selftest.py',
            {case['id'] for case in audit['R08']['cases'] if case['component'] == component})
    for item in result:
        old = next(case for case in audit['R08']['cases'] if case['id'] == item['id']
                   and item['component'] == 'OLD_R08_' + case['component'])
        assert item['definition']['expected'] == old['expected'], 'ORIGINAL_R08_EXPECTED_CHANGED'
    original_manifest = audit['old_R7C']['manifest']
    assert desc(ROOT / original_manifest['path']) == original_manifest, 'ORIGINAL_R7C_MANIFEST_CHANGED'
    add('OLD_R7C_CALLABLE', ROOT / original_manifest['path'],
        SW / 'pro_basis_r07_20261017/oracle_bundle_bridge/c9_completion_r01/pending_only.py',
        {case['name'] for case in audit['old_R7C']['cases']})
    assert [item['definition'] for item in result if item['component'] == 'OLD_R7C_CALLABLE'] == audit['old_R7C']['cases']
    for item in audit['C9_new_definitions']:
        component = item['component']
        assert desc(ROOT / item['manifest']['path']) == item['manifest'], 'ORIGINAL_C9_MANIFEST_CHANGED:' + component
        assert load(ROOT / item['manifest']['path'])['cases'] == item['cases'], 'ORIGINAL_C9_DEFINITIONS_CHANGED:' + component
        if component == 'public_port_map':
            selftest = SW / 'pro_basis_r08_20261017/public_port_map/c9_binding/selftest.py'
        elif component == 'public_equivalence_tb':
            selftest = OWN / 'old_b_cases.py'
        else:
            selftest = SW / 'pro_basis_r07_20261017' / component / 'c9_binding/selftest.py'
        add('OLD_C9_' + component, ROOT / item['manifest']['path'], selftest)
    assert len(result) == 75, len(result)
    add('NEW_A', TB / 'pro_basis_r08_20261017/build_admission_bundle/c9_completion_r01/CASES.json',
        SW / 'pro_basis_r08_20261017/build_admission_bundle/c9_completion_r01/selftest.py')
    for package in ('pro_basis_r07_20261017/public_capture_tb', 'pro_basis_r08_20261017/capture_csv_codec',
                    'pro_basis_r06_20261017/normalized_intake', 'pro_basis_r07_20261017/oracle_bundle_bridge'):
        add('NEW_B_' + Path(package).name, TB / package / 'c9_completion_r01/CASES.json',
            SW / 'pro_basis_r07_20261017/public_capture_tb/c9_completion_r01/selftest.py')
    add('NEW_C', TB / 'pro_basis_r06_20261017/tx_clock_reset_checker/c9_completion_r01/CASES.json',
        SW / 'pro_basis_r06_20261017/tx_clock_reset_checker/c9_completion_r01/selftest.py')
    add('NEW_C_COMPANION', TB / 'pro_basis_r07_20261017/public_equivalence_tb/c9_completion_r01/CASES.json',
        SW / 'pro_basis_r07_20261017/public_equivalence_tb/c9_completion_r01/selftest.py')
    add('NEW_ROOT', DOC / 'CASES.json', OWN / 'selftest.py')
    # Let all small seam checks complete before the two actual >64MiB cases.
    result.sort(key=lambda case: ('GT64' in case['id'].upper() or 'LARGE' in case['id'].upper()))
    return result


def inputs():
    for base in (SW, TB, BASE):
        for path in sorted(base.rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            if any(part == 'coordinator' or part.startswith('coordinator_') for part in path.relative_to(base).parts):
                continue
            yield path
    for path in sorted(OWN.glob('*.py')):
        yield path
    for name in ('START.md', 'CASES.json', 'MODULE_BINDINGS.json'):
        yield DOC / name
    for relative in ('m2_138k_pro_fourvoice_candidate_20261016/r06_public_chain_20261017',
                     'm2_138k_pro_fourvoice_candidate_20261016/r06_observer_20261017',
                     'm2_m1_noteon_erratum_20261017',
                     'm1_r05_pcm_oracle_20261016/pro_r06_20261017/oracle_adapter'):
        for path in sorted((ROOT / 'code/docs/test' / relative).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                yield path
    yield OWN.parent / 'run_group.py'
    yield AUDIT
    # C9 public-port checks bind the actual newly published M2 observer RTL,
    # which postdates the inherited old tracked-baseline lookup.
    for path in sorted((ROOT / 'code/rtl/board/m2_138k_pro_fourvoice_candidate_20261016').rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            yield path


def freeze(label, repair_keys, basis, refresh_bindings=False):
    assert label.isalnum() and (not repair_keys or basis)
    if not (DOC / 'MODULE_BINDINGS.json').exists():
        save(DOC / 'MODULE_BINDINGS.json', bindings())
    else:
        current_bindings = load(DOC / 'MODULE_BINDINGS.json')
        next_bindings = bindings()
        if current_bindings != next_bindings:
            assert refresh_bindings and repair_keys, 'MODULE_BINDINGS_NEED_EXPLICIT_REFRESH'
            save(DOC / ('MODULE_BINDINGS_BEFORE_' + label + '.json'), current_bindings)
            (DOC / 'MODULE_BINDINGS.json').write_text(json.dumps(next_bindings, indent=2, ensure_ascii=False) + '\n',
                                                    encoding='utf-8', newline='\n')
    cases = all_cases()
    ledger_path = DOC / 'CONSUMPTION.json'
    if repair_keys:
        cases = [case for case in cases if case['component'] + ':' + case['id'] in repair_keys]
        assert {case['component'] + ':' + case['id'] for case in cases} == set(repair_keys)
    elif not ledger_path.exists():
        save(ledger_path, {'schema': 'M3_C9_D4_CONSUMPTION_V1', 'group': 'TASK_DAY4_REMAINDER_SW',
            'initial_consumed': 0, 'repair_consumed': 0, 'status': 'NOT_STARTED',
            'remaining_case_keys': [case['component'] + ':' + case['id'] for case in cases],
            'old_consumption_restored': False, 'runs': []})
    folder = DOC / ('FREEZE_' + label)
    folder.mkdir(exist_ok=False)
    # Old baseline identities are lookup-only; every actual candidate read is
    # checked against its frozen SHA. Current candidate/dependency bytes below
    # supersede the old baseline. Unread inherited entries are not test claims.
    frozen = load(DOC.parent / 'TRACKED_BASELINE.json')
    external = {}
    for path in (BASE / 'pro_basis_r08_20261017').glob('*/EXTERNAL_INPUTS.json'):
        for item in load(path)['files']:
            file = Path(item['path'])
            assert file.is_absolute() and file.is_file() and not file.is_symlink() and not file.is_junction()
            actual = ident(file)
            assert actual == {key: item[key] for key in ('bytes', 'sha256')}
            external[str(file.resolve())] = actual
    archived = {}
    base_originals = None
    initial_archived = {}
    if repair_keys:
        initial_manifest = load(DOC / 'FREEZE_R01/FROZEN_FILES.json')
        initial_archived = initial_manifest['archived_files']
        base_originals = desc(DOC / 'FREEZE_R01/INPUTS.zip')
        assert base_originals == initial_manifest['archive'], 'INITIAL_ORIGINAL_ARCHIVE_CHANGED'
    archive_path = folder / 'INPUTS.zip'
    with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for path in dict.fromkeys(inputs()):
            rel = path.relative_to(ROOT).as_posix()
            expected = ident(path)
            frozen[rel] = expected
            if initial_archived.get(rel) != expected:
                archive.write(path, rel)
                archived[rel] = expected
            assert ident(path) == expected, 'INPUT_CHANGED_DURING_FREEZE:' + rel
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(archived)
    manifest_path = folder / 'FROZEN_FILES.json'
    save(manifest_path, {'schema': 'M3_C9_D4_FROZEN_INPUTS_V1', 'files': frozen,
        'external_files': external, 'archived_files': archived, 'archive': desc(archive_path),
        'base_originals': base_originals,
        'external_policy': 'READ_HASH_ONLY_NEVER_LOADED_OR_REDISTRIBUTED',
        'inherited_unread_entries_not_assertions': True})
    runner = (OWN / 'run_group.py').resolve()
    spec_path = (folder / 'SPEC.json').resolve()
    spec = {'schema': 'M3_C9_D4_RUN_SPEC_V1', 'group': 'TASK_DAY4_REMAINDER_SW',
        'phase': 'repair' if repair_keys else 'initial', 'limit_s': 60 if repair_keys else 120,
        'python': ident(sys.executable), 'entry': ident(runner),
        'argv': [sys.executable, '-B', '-X', 'utf8', str(runner), str(spec_path)], 'cwd': str(ROOT),
        'output': str((ROOT / 'code/output/m3_c9_complete_d4_20261017' / label).resolve()),
        'frozen_manifest': desc(manifest_path), 'cases': cases,
        'repair_case_keys': repair_keys, 'defect_basis': basis,
        'repository_import_policy': 'EXACT_FROZEN_SOURCE_BYTES_NO_PYC',
        'candidate_subprocess_allowed': False, 'HDL_EDA_device_allowed': False}
    save(spec_path, spec)
    print(json.dumps({'spec': str(spec_path), 'cases': len(cases), 'archived_files': len(archived),
                      'inputs_zip': desc(archive_path)}, ensure_ascii=False))


def reconcile(output, actual_exit_code):
    assert actual_exit_code is not None, 'ACTUAL_PROCESS_EXIT_REQUIRED'
    output = Path(output).resolve()
    receipt_path = output / 'RECEIPT.json'
    if not receipt_path.exists():
        receipt_path = output / 'TIMEOUT_SNAPSHOT.json'
    receipt = load(receipt_path)
    markers = [name for name in ('TIMEOUT_SNAPSHOT.json', 'DEADLINE_DURING_FINAL_RECEIPT.json')
               if (output / name).exists()]
    actual_spec = load(output / 'SPEC.json')
    assert receipt['argv'] == actual_spec['argv'] and receipt['group'] == actual_spec['group']
    timed_out = actual_exit_code == 124 or receipt['exit_code'] == 124 or bool(markers)
    effective_exit = 124 if timed_out else actual_exit_code
    assert effective_exit != 0 or receipt['exit_code'] == 0, 'PROCESS_RECEIPT_EXIT_MISMATCH'
    ledger_path = DOC / 'CONSUMPTION.json'
    ledger = load(ledger_path)
    assert ledger['current_output'] == output.relative_to(ROOT).as_posix()
    assert not any(run['output'] == ledger['current_output'] for run in ledger['runs'])
    matched = {item['component'] + ':' + item['id'] for item in receipt['results'] if item['assertion'] == 'MATCHED'}
    ledger['remaining_case_keys'] = [key for key in ledger['remaining_case_keys'] if key not in matched]
    ledger['status'] = ('PASS_LIMITED_SOFTWARE' if not ledger['remaining_case_keys'] and effective_exit == 0
                        else ('TIMEOUT_PARTIAL' if timed_out else 'FAIL_PARTIAL'))
    ledger['runs'].append({'output': ledger['current_output'], 'receipt': desc(receipt_path),
        'exit_code': effective_exit, 'actual_process_exit': actual_exit_code,
        'timeout_markers': markers, 'spec': desc(output / 'SPEC.json'), 'elapsed_s': receipt['elapsed_s'],
        'matched': len(matched), 'remaining': len(ledger['remaining_case_keys'])})
    history = DOC / ('CONSUMPTION_AFTER_' + output.name + '.json')
    save(history, ledger)
    ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(ledger['runs'][-1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label')
    parser.add_argument('--repair-key', action='append', default=[])
    parser.add_argument('--basis', default='')
    parser.add_argument('--reconcile', type=Path)
    parser.add_argument('--actual-exit-code', type=int)
    parser.add_argument('--refresh-bindings', action='store_true')
    args = parser.parse_args()
    if args.reconcile:
        reconcile(args.reconcile, args.actual_exit_code)
    else:
        freeze(args.label, args.repair_key, args.basis, args.refresh_bindings)


if __name__ == '__main__':
    main()
