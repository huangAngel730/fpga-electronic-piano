"""New identity-only synthetic bundles shaped like the R7-A raw/end profiles."""
import json
from pathlib import Path
import shutil
import sys

from capture_provenance import DERIVED, ROLES, Reject, ident, parse, seal, sha, validate


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2) + '\n', encoding='utf-8')


def entry(root, name):
    item = ident(root / name)
    return {'path': name, 'bytes': item['bytes'], 'sha256': item['sha256']}


def fixture(root):
    root.mkdir()
    capture_id = 'SYNTHETIC_R7D_001'
    files = {role: role + '.json' for role in ROLES}
    files.update(driver='driver.txt', observer='observer.txt', raw_stdout='stdout.txt', raw_stderr='stderr.txt',
                 raw_trace='raw.jsonl', reset_edges='reset.jsonl', normalized='normalized.jsonl',
                 projection_tool='projection_tool.txt')
    for name, data in {'source.txt': 'SYNTHETIC_SOURCE_NOT_DUT\n', 'rom.txt': 'SYNTHETIC_ROM\n',
                       'tool.bin': 'NOT_AN_EXECUTABLE\n'}.items():
        (root / name).write_text(data, encoding='utf-8')
    for role in ROLES:
        (root / files[role]).write_text('SYNTHETIC_' + role + '\n', encoding='utf-8')
    for role, name in [('source_manifest', 'source.txt'), ('rom_manifest', 'rom.txt')]:
        dump(root / files[role], {'schema': 'M3_R7D_FILE_CLOSURE_V1', 'files': [entry(root, name)]})
    dump(root / files['tool_manifest'], {'schema': 'M3_R7D_FILE_CLOSURE_V1', 'files': [entry(root, 'tool.bin')],
        'argv': ['SYNTHETIC_NOT_EXECUTED', '--id', capture_id], 'cwd': 'SYNTHETIC_CWD', 'version': 'SYNTHETIC_V1'})
    dump(root / files['input_plan'], {'schema': 'SYNTHETIC_INPUT_PLAN', 'not_real_input': True})
    input_sha = ident(root / files['input_plan'])['sha256']
    plan = {'schema': 'M3_R7D_INDEPENDENT_WINDOW_V1', 'capture_id': capture_id, 'plan_stop_id': 'SYNTHETIC_STOP',
            'first_core_ps': 12500, 'core_period_ps': 25000, 'finish_cycle': 2, 'finish_time_ps': 62500,
            'row_count': 3, 'input_plan_sha256': input_sha}
    dump(root / files['window_plan'], plan)
    finish = {'schema': 'M3_R7A_END_V1', 'capture_id': capture_id, 'plan_stop_id': 'SYNTHETIC_STOP',
              'finish_cycle': 2, 'time_ps': 62500, 'row_count': 3, 'reason': 'PLANNED_WINDOW_END',
              'ledger_status': 'NOT_CHECKED_R6_5_REQUIRED', 'serial_tail_status': 'UNKNOWN_R6_6_REQUIRED'}
    dump(root / files['finish_receipt'], finish)
    (root / files['raw_stdout']).write_text(
        f'MONITOR_END capture_id={capture_id} cycle=2 time_ps=62500 rows=3 reason=PLANNED_WINDOW_END\n', encoding='utf-8')
    (root / files['raw_stderr']).write_bytes(b'')
    raw_rows = [{'schema': 'M3_R7A_RAW_CORE_ROW_V1', 'capture_id': capture_id,
                 'source_line': cycle + 1, 'cycle': cycle, 'time_ps': 12500 + cycle * 25000,
                 'epoch': None, 'epoch_reason': 'BIND_FROM_INDEPENDENT_RESET_EDGES',
                 'finish': int(cycle == 2), 'ports': {'obs_core_clk': '1', 'obs_rst_n': '0'}} for cycle in range(3)]
    (root / files['raw_trace']).write_text(''.join(json.dumps(row) + '\n' for row in raw_rows), encoding='utf-8')
    reset = {'schema': 'M3_R7A_RESET_SNAPSHOT_V1', 'capture_id': capture_id,
             'edge_seq': 1, 'time_ps': 0, 'kind': 'INITIAL', 'values': {'sys_rst_n': '0', 'obs_rst_n': '0', 'obs_pll_locked': '0'}}
    (root / files['reset_edges']).write_text(json.dumps(reset) + '\n', encoding='utf-8')
    normalized = [{'schema': 'M3_R7A_PUBLIC_ROW_V1', 'capture_id': capture_id, 'origin': 'SYNTHETIC_SCHEMA_FIXTURE',
                   'source': {'raw_sha256': ident(root / files['raw_trace'])['sha256'],
                              'reset_edges_sha256': ident(root / files['reset_edges'])['sha256'],
                              'line': row['source_line'], 'cycle': row['cycle'], 'time_ps': row['time_ps'],
                              'epoch': 0, 'sampling_phase': 'POSEDGE_PRE_NBA'},
                   'fields': {}, 'extensions': {}, 'missing_reasons': {'fixture': 'IDENTITY_LINK_ONLY_NOT_FULL_A_SCHEMA_TEST'},
                   'events': []} for row in raw_rows]
    (root / files['normalized']).write_text(''.join(json.dumps(row) + '\n' for row in normalized), encoding='utf-8')
    artifacts = {role: entry(root, files[role]) for role in ROLES}
    projection = {'schema': 'M3_R7D_DERIVATION_LINKS_V1', 'capture_id': capture_id,
                  'projection_tool_sha256': artifacts['projection_tool']['sha256'],
                  'bindings': {role: artifacts[role]['sha256'] for role in ('raw_trace', 'reset_edges', 'input_plan', 'window_plan')},
                  'outputs': {role: artifacts[role]['sha256'] for role in DERIVED}}
    dump(root / files['projection_manifest'], projection)
    artifacts['projection_manifest'] = entry(root, files['projection_manifest'])
    linked = ('source_manifest rom_manifest driver observer tool_manifest input_plan window_plan '
              'raw_stdout raw_stderr raw_trace reset_edges finish_receipt').split()
    execution = {'schema': 'M3_R7D_DECLARED_EXECUTION_V1', 'capture_id': capture_id,
                 'argv': ['SYNTHETIC_NOT_EXECUTED', '--id', capture_id], 'cwd': 'SYNTHETIC_CWD',
                 'bindings': {role: artifacts[role]['sha256'] for role in linked},
                 'exit_code': 0, 'timeout': False, 'cleanup_complete': True,
                 'consumption': {'pid': 1, 'group_id': 'SYNTHETIC_DECLARED_NOT_REAL_PID',
                                 'started_utc': '2026-10-17T00:00:00+00:00', 'ended_utc': '2026-10-17T00:00:01+00:00'}}
    dump(root / files['execution_receipt'], execution)
    artifacts['execution_receipt'] = entry(root, files['execution_receipt'])
    manifest = {'schema': 'M3_R7D_CAPTURE_MANIFEST_V1', 'capture_id': capture_id,
                'kind': 'SYNTHETIC_PROVENANCE_TEST', 'artifacts': artifacts}
    dump(root / 'capture.json', manifest)
    return root / 'capture.json'


def refresh(root):
    manifest = parse((root / 'capture.json').read_bytes())
    artifacts = manifest['artifacts']
    for role, old in artifacts.items():
        artifacts[role] = entry(root, old['path'])
    execution = parse((root / artifacts['execution_receipt']['path']).read_bytes())
    execution['bindings'] = {role: artifacts[role]['sha256'] for role in execution['bindings']}
    dump(root / artifacts['execution_receipt']['path'], execution)
    artifacts['execution_receipt'] = entry(root, artifacts['execution_receipt']['path'])
    dump(root / 'capture.json', manifest)


def change_json(root, role, mutate):
    manifest = parse((root / 'capture.json').read_bytes())
    path = root / manifest['artifacts'][role]['path']
    obj = parse(path.read_bytes())
    mutate(obj)
    dump(path, obj)
    refresh(root)


def change_row(root, role, mutate):
    manifest = parse((root / 'capture.json').read_bytes())
    path = root / manifest['artifacts'][role]['path']
    rows = [parse(line) for line in path.read_text(encoding='utf-8').splitlines()]
    mutate(rows)
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    refresh(root)


def main():
    out = Path(sys.argv[1])
    out.mkdir(exist_ok=False)
    base = out / 'base'
    fixture(base)
    baseline = validate(base / 'capture.json', ident(base / 'capture.json')['sha256'])
    results = []

    def case(name, expected, mutate=None, prior=None, seal_positive=False):
        root = out / name
        shutil.copytree(base, root)
        if mutate:
            mutate(root)
        try:
            if seal_positive:
                result = seal(root / 'capture.json', ident(root / 'capture.json')['sha256'], out / 'sealed', out / 'registry')
                detail = {'archive': result['archive'], 'CRC_member_SHA_verified': result['CRC_member_SHA_verified']}
            else:
                result = validate(root / 'capture.json', ident(root / 'capture.json')['sha256'], prior)
                detail = {'status': result['status'], 'rows': result['rows']}
            actual = None
        except Reject as error:
            actual, detail = error.code, {}
        results.append({'case': name, 'expected': expected, 'actual': actual, 'detail': detail})
        dump(out / 'CASES.json', results)
        assert expected == actual, (name, expected, actual)

    case('zero_based_A_raw_normalized_and_seal', None, seal_positive=True)
    case('swap_source_file', 'ARTIFACT_IDENTITY', lambda r: (r / 'source.txt').write_bytes(b'CHANGED'))
    case('swap_log', 'ARTIFACT_IDENTITY', lambda r: (r / 'stdout.txt').write_bytes(b'CHANGED'))
    case('edit_projection', 'ARTIFACT_IDENTITY', lambda r: (r / 'd3_projection.json').write_bytes(b'CHANGED'))
    def missing_input(root):
        manifest = parse((root / 'capture.json').read_bytes())
        del manifest['artifacts']['input_plan']
        dump(root / 'capture.json', manifest)
    case('missing_input', 'MISSING_OR_EXTRA_ARTIFACT_ROLE', missing_input)
    case('wrong_finish', 'FINISH_PLAN_MISMATCH', lambda r: change_json(r, 'finish_receipt', lambda p: p.update(time_ps=62501)))
    case('failed_execution', 'EXECUTION_NOT_SUCCESS', lambda r: change_json(r, 'execution_receipt', lambda p: p.update(exit_code=1)))
    case('changed_argv', 'EXECUTION_ARGV_CWD', lambda r: change_json(r, 'execution_receipt', lambda p: p.update(argv=['OTHER'])))
    case('wrong_raw_capture', 'RAW_CAPTURE_ID_SCHEMA', lambda r: change_row(r, 'raw_trace', lambda rows: rows[0].update(capture_id='OTHER')))
    case('wrong_normalized_capture', 'NORMALIZED_CAPTURE_ID_SCHEMA', lambda r: change_row(r, 'normalized', lambda rows: rows[0].update(capture_id='OTHER')))
    case('wrong_normalized_raw_sha', 'NORMALIZED_SOURCE_HASH', lambda r: change_row(r, 'normalized', lambda rows: rows[0]['source'].update(raw_sha256='0' * 64)))
    case('normalized_line_outside', 'NORMALIZED_SOURCE_COORDINATES', lambda r: change_row(r, 'normalized', lambda rows: rows[0]['source'].update(line=99)))
    case('wrong_projection_link', 'PROJECTION_LINK_MISMATCH', lambda r: change_json(r, 'projection_manifest', lambda p: p['bindings'].update(raw_trace='0' * 64)))
    case('same_capture_new_source', 'CAPTURE_ID_REBIND', lambda r: change_json(r, 'source_manifest', lambda p: p.update(schema='CHANGED')), prior=baseline['signature'])
    case('missing_reset_body', 'ARTIFACT_MISSING_OR_ESCAPE', lambda r: (r / 'reset.jsonl').rename(r / 'reset_missing.bin'))
    case('duplicate_end', 'MONITOR_END_NOT_UNIQUE_OR_WRONG', lambda r: ((r / 'stdout.txt').write_text((r / 'stdout.txt').read_text(encoding='utf-8') * 2, encoding='utf-8'), refresh(r)))
    case('no_real_finish_flag', 'RAW_FINISH', lambda r: change_row(r, 'raw_trace', lambda rows: rows[-1].update(finish=0)))
    case('wrong_window_input', 'WINDOW_PLAN_BINDING', lambda r: change_json(r, 'window_plan', lambda p: p.update(input_plan_sha256='0' * 64)))
    case('normalized_missing_row', 'NORMALIZED_SOURCE_COVERAGE', lambda r: change_row(r, 'normalized', lambda rows: rows.pop()))
    case('one_based_raw_rejected', 'RAW_ROW_SEQUENCE', lambda r: change_row(r, 'raw_trace', lambda rows: rows[0].update(cycle=1)))
    def extra_approval(root):
        manifest = parse((root / 'capture.json').read_bytes())
        manifest['approved'] = True
        dump(root / 'capture.json', manifest)
    case('cannot_self_approve', 'MANIFEST_FIELDS', extra_approval)
    def escape_path(root):
        manifest = parse((root / 'capture.json').read_bytes())
        manifest['artifacts']['input_plan']['path'] = '../outside.json'
        dump(root / 'capture.json', manifest)
    case('path_escape', 'ARTIFACT_PATH', escape_path)
    dump(out / 'SUMMARY.json', {'passed': True, 'new_cases': len(results), 'HDL_EDA_hardware_calls': 0,
         'capture_kind': 'SYNTHETIC_PROVENANCE_TEST', 'real_capture_present': False,
         'authority_authenticated': False, 'board_release_allowed': False})
    print(json.dumps({'passed': True, 'new_cases': len(results), 'real_capture_present': False}))


if __name__ == '__main__':
    main()
