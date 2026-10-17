"""Identity-only capture validator/sealer; no authenticity or execution approval."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

ROLES = ('source_manifest rom_manifest driver observer tool_manifest execution_receipt '
         'raw_stdout raw_stderr input_plan window_plan reset_edges frame_plan raw_trace '
         'normalized d3_projection b2_projection pcm tx_sidecar projection_tool projection_manifest finish_receipt').split()
DERIVED = ('normalized d3_projection b2_projection pcm tx_sidecar frame_plan').split()


class Reject(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def need(ok, code):
    if not ok:
        raise Reject(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def ident(path):
    p = Path(path)
    data = p.read_bytes()
    return {'path': str(p), 'bytes': len(data), 'sha256': sha(data)}


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, 'DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def parse(raw):
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(Reject('NONFINITE_JSON')))


def exact(obj, keys, code):
    need(type(obj) is dict and set(obj) == set(keys), code)


def integer(value, low=0):
    return type(value) is int and value >= low


def validate(manifest_path, expected_sha, prior=None):
    manifest_path = Path(manifest_path).resolve()
    raw_manifest = manifest_path.read_bytes()
    need(re.fullmatch('[0-9a-f]{64}', expected_sha or '') is not None and sha(raw_manifest) == expected_sha, 'MANIFEST_SHA')
    manifest = parse(raw_manifest)
    exact(manifest, ('schema', 'capture_id', 'kind', 'artifacts'), 'MANIFEST_FIELDS')
    need(manifest['schema'] == 'M3_R7D_CAPTURE_MANIFEST_V1', 'MANIFEST_SCHEMA')
    capture_id = manifest['capture_id']
    need(type(capture_id) is str and re.fullmatch('[A-Za-z0-9_.-]{1,96}', capture_id) is not None
         and capture_id not in ('.', '..'), 'CAPTURE_ID')
    need(manifest['kind'] in ('SYNTHETIC_PROVENANCE_TEST', 'DECLARED_REAL_PENDING_M2'), 'KIND')
    exact(manifest['artifacts'], ROLES, 'MISSING_OR_EXTRA_ARTIFACT_ROLE')
    base = manifest_path.parent
    files = {}

    def bound(entry):
        exact(entry, ('path', 'bytes', 'sha256'), 'ARTIFACT_FIELDS')
        name = entry['path']
        need(type(name) is str and name and '\\' not in name and ':' not in name and '\x00' not in name,
             'ARTIFACT_PATH')
        rel = PurePosixPath(name)
        need(not rel.is_absolute() and all(part not in ('', '.', '..') for part in name.split('/')), 'ARTIFACT_PATH')
        need(name.casefold() not in ('capture_manifest.json', 'manifest.json'), 'RESERVED_PATH')
        p = (base / name).resolve()
        need(p.is_relative_to(base) and p.is_file(), 'ARTIFACT_MISSING_OR_ESCAPE')
        need(integer(entry['bytes']) and entry['bytes'] <= 128 * 1024 * 1024, 'ARTIFACT_SIZE')
        need(re.fullmatch('[0-9a-f]{64}', entry['sha256'] or '') is not None, 'ARTIFACT_SHA_FORMAT')
        actual = ident(p)
        need(actual['bytes'] == entry['bytes'] and actual['sha256'] == entry['sha256'], 'ARTIFACT_IDENTITY')
        if name.casefold() in files:
            need(files[name.casefold()]['relative'] == name and files[name.casefold()]['sha256'] == entry['sha256'], 'PATH_ALIAS')
        files[name.casefold()] = {**actual, 'relative': name}
        return p

    paths = {role: bound(entry) for role, entry in manifest['artifacts'].items()}
    need(len({p for p in paths.values()}) == len(ROLES), 'ROLE_ALIAS')
    digests = {role: entry['sha256'] for role, entry in manifest['artifacts'].items()}
    signature = {'capture_id': capture_id, 'manifest_sha256': expected_sha,
                 'source_sha256': digests['source_manifest'], 'rom_sha256': digests['rom_manifest'],
                 'tool_sha256': digests['tool_manifest'], 'raw_sha256': digests['raw_trace']}
    if prior is not None:
        need(prior == signature, 'CAPTURE_ID_REBIND')
    docs = {role: parse(paths[role].read_bytes()) for role in (
        'source_manifest', 'rom_manifest', 'tool_manifest', 'execution_receipt',
        'window_plan', 'projection_manifest', 'finish_receipt')}
    for role in ('source_manifest', 'rom_manifest', 'tool_manifest'):
        obj = docs[role]
        keys = ('schema', 'files', 'argv', 'cwd', 'version') if role == 'tool_manifest' else ('schema', 'files')
        exact(obj, keys, 'CLOSURE_FIELDS_' + role)
        need(obj['schema'] == 'M3_R7D_FILE_CLOSURE_V1', 'CLOSURE_SCHEMA')
        need(type(obj['files']) is list and len(obj['files']) > 0, 'EMPTY_CLOSURE')
        listed = [bound(item) for item in obj['files']]
        need(len(set(listed)) == len(listed), 'DUPLICATE_CLOSURE_FILE')
    tool = docs['tool_manifest']
    need(type(tool['argv']) is list and tool['argv'] and all(type(a) is str and a for a in tool['argv']), 'ARGV')
    need(type(tool['cwd']) is str and tool['cwd'] and type(tool['version']) is str and tool['version'], 'TOOL_DESCRIPTION')
    execution = docs['execution_receipt']
    exact(execution, ('schema', 'capture_id', 'argv', 'cwd', 'bindings', 'exit_code', 'timeout',
                      'cleanup_complete', 'consumption'), 'EXECUTION_FIELDS')
    need(execution['schema'] == 'M3_R7D_DECLARED_EXECUTION_V1' and execution['capture_id'] == capture_id, 'EXECUTION_CAPTURE_ID')
    need(execution['argv'] == tool['argv'] and execution['cwd'] == tool['cwd'], 'EXECUTION_ARGV_CWD')
    linked = ('source_manifest rom_manifest driver observer tool_manifest input_plan window_plan '
              'raw_stdout raw_stderr raw_trace reset_edges finish_receipt').split()
    need(execution['bindings'] == {role: digests[role] for role in linked}, 'EXECUTION_BINDINGS')
    need(type(execution['exit_code']) is int and execution['exit_code'] == 0 and execution['timeout'] is False
         and execution['cleanup_complete'] is True, 'EXECUTION_NOT_SUCCESS')
    consumed = execution['consumption']
    exact(consumed, ('pid', 'group_id', 'started_utc', 'ended_utc'), 'CONSUMPTION_FIELDS')
    need(integer(consumed['pid'], 1) and type(consumed['group_id']) is str and consumed['group_id'], 'CONSUMPTION')
    try:
        begin, end = [datetime.fromisoformat(consumed[key]) for key in ('started_utc', 'ended_utc')]
        need(begin.utcoffset() is not None and end.utcoffset() is not None and end >= begin, 'CONSUMPTION_TIME')
    except (TypeError, ValueError) as error:
        raise Reject('CONSUMPTION_TIME') from error
    plan, finish = docs['window_plan'], docs['finish_receipt']
    exact(plan, ('schema', 'capture_id', 'plan_stop_id', 'first_core_ps', 'core_period_ps',
                 'finish_cycle', 'finish_time_ps', 'row_count', 'input_plan_sha256'), 'WINDOW_PLAN_FIELDS')
    need(plan['schema'] == 'M3_R7D_INDEPENDENT_WINDOW_V1' and plan['capture_id'] == capture_id
         and plan['input_plan_sha256'] == digests['input_plan'], 'WINDOW_PLAN_BINDING')
    need(type(plan['plan_stop_id']) is str and plan['plan_stop_id'] and
         all(integer(plan[key], 1) for key in ('first_core_ps', 'core_period_ps', 'finish_time_ps', 'row_count'))
         and integer(plan['finish_cycle']),
         'WINDOW_PLAN_VALUES')
    need(plan['finish_cycle'] == plan['row_count'] - 1 and plan['finish_time_ps'] == plan['first_core_ps'] +
         plan['finish_cycle'] * plan['core_period_ps'], 'WINDOW_PLAN_TIME')
    exact(finish, ('schema', 'capture_id', 'plan_stop_id', 'finish_cycle', 'time_ps', 'row_count',
                   'reason', 'ledger_status', 'serial_tail_status'), 'FINISH_FIELDS')
    need(finish['schema'] == 'M3_R7A_END_V1' and finish['capture_id'] == capture_id
         and finish['plan_stop_id'] == plan['plan_stop_id'] and finish['reason'] == 'PLANNED_WINDOW_END', 'FINISH_ID_REASON')
    need((finish['finish_cycle'], finish['time_ps'], finish['row_count']) ==
         (plan['finish_cycle'], plan['finish_time_ps'], plan['row_count']), 'FINISH_PLAN_MISMATCH')
    need(type(finish['ledger_status']) is str and type(finish['serial_tail_status']) is str, 'FINISH_STATUS')
    stdout = paths['raw_stdout'].read_text(encoding='utf-8')
    marker = (f"MONITOR_END capture_id={capture_id} cycle={plan['finish_cycle']} "
              f"time_ps={plan['finish_time_ps']} rows={plan['row_count']} reason=PLANNED_WINDOW_END")
    need(len(re.findall(r'\bMONITOR_END\b', stdout)) == 1 and marker in stdout.splitlines(), 'MONITOR_END_NOT_UNIQUE_OR_WRONG')
    count = 0
    with paths['raw_trace'].open(encoding='utf-8') as stream:
        for line in stream:
            row = parse(line)
            count += 1
            need(row.get('schema') == 'M3_R7A_RAW_CORE_ROW_V1' and row.get('capture_id') == capture_id, 'RAW_CAPTURE_ID_SCHEMA')
            need(type(row.get('source_line')) is int and type(row.get('cycle')) is int and type(row.get('time_ps')) is int
                 and row.get('source_line') == count and row.get('cycle') == count - 1
                 and row.get('time_ps') == plan['first_core_ps'] + (count - 1) * plan['core_period_ps'], 'RAW_ROW_SEQUENCE')
            need(type(row.get('finish')) is int and row['finish'] == int(count == plan['row_count']), 'RAW_FINISH')
            need(type(row.get('ports')) is dict, 'RAW_PORTS')
    need(count == plan['row_count'], 'RAW_WINDOW_INCOMPLETE')
    # Re-open both streams in lockstep: normalized lines must point to the
    # actual A raw bytes and source coordinates, not merely claim outer hashes.
    normalized_count = 0
    with paths['normalized'].open(encoding='utf-8') as normalized_stream, paths['raw_trace'].open(encoding='utf-8') as raw_stream:
        for line in normalized_stream:
            normalized_count += 1
            row = parse(line)
            raw_line = raw_stream.readline()
            need(bool(raw_line), 'NORMALIZED_SOURCE_LINE_OUTSIDE_RAW')
            original = parse(raw_line)
            need(row.get('schema') == 'M3_R7A_PUBLIC_ROW_V1' and row.get('capture_id') == capture_id, 'NORMALIZED_CAPTURE_ID_SCHEMA')
            source = row.get('source')
            need(type(source) is dict and source.get('raw_sha256') == digests['raw_trace']
                 and source.get('reset_edges_sha256') == digests['reset_edges'], 'NORMALIZED_SOURCE_HASH')
            need(all(type(source.get(key)) is int for key in ('line', 'cycle', 'time_ps'))
                 and source.get('line') == original['source_line'] == normalized_count
                 and source.get('cycle') == original['cycle'] and source.get('time_ps') == original['time_ps']
                 and source.get('sampling_phase') == 'POSEDGE_PRE_NBA', 'NORMALIZED_SOURCE_COORDINATES')
        need(not raw_stream.readline() and normalized_count == count, 'NORMALIZED_SOURCE_COVERAGE')
    reset_count = 0
    with paths['reset_edges'].open(encoding='utf-8') as stream:
        for line in stream:
            row = parse(line)
            reset_count += 1
            need(row.get('capture_id') == capture_id and row.get('schema') == 'M3_R7A_RESET_SNAPSHOT_V1', 'RESET_CAPTURE_ID_SCHEMA')
    need(reset_count > 0, 'RESET_EDGES_EMPTY')
    projection = docs['projection_manifest']
    exact(projection, ('schema', 'capture_id', 'projection_tool_sha256', 'bindings', 'outputs'), 'PROJECTION_FIELDS')
    need(projection['schema'] == 'M3_R7D_DERIVATION_LINKS_V1' and projection['capture_id'] == capture_id,
         'PROJECTION_CAPTURE_ID')
    need(projection['projection_tool_sha256'] == digests['projection_tool'], 'PROJECTION_TOOL')
    need(projection['bindings'] == {role: digests[role] for role in ('raw_trace', 'reset_edges', 'input_plan', 'window_plan')}
         and projection['outputs'] == {role: digests[role] for role in DERIVED}, 'PROJECTION_LINK_MISMATCH')
    need(sha(manifest_path.read_bytes()) == expected_sha, 'MANIFEST_CHANGED')
    need(all(ident(item['path'])['sha256'] == item['sha256'] for item in files.values()), 'INPUT_CHANGED')
    return {'status': 'STRUCTURE_IDENTITY_MATCH_ONLY_REAL_PENDING', 'capture_id': capture_id,
            'signature': signature, 'files': list(files.values()), 'manifest': ident(manifest_path),
            'declared_kind': manifest['kind'], 'rows': count,
            'closure_content': 'LISTED_FILES_CHECKED_NOT_COMPLETENESS_OR_ELABORATION_PROOF',
            'projection_semantics': 'NOT_RECOMPUTED_R6_CHECKERS_OWNED',
            'window_independence': 'DECLARED_NOT_AUTHENTICATED',
            'tool_execution_authenticity': 'UNKNOWN', 'M2_admission': 'PENDING',
            'pro_dut_pass': False, 'board_release_allowed': False}


def seal(manifest_path, expected_sha, output, registry, prior_sha=None):
    registry, output = Path(registry), Path(output)
    raw = parse(Path(manifest_path).read_bytes())
    capture_id = raw.get('capture_id', '')
    need(type(capture_id) is str and re.fullmatch('[A-Za-z0-9_.-]{1,96}', capture_id) is not None
         and capture_id not in ('.', '..'), 'CAPTURE_ID')
    record_path = registry / (capture_id + '.json')
    prior = None
    if record_path.exists():
        need(prior_sha is not None and ident(record_path)['sha256'] == prior_sha, 'REGISTRY_SHA_REQUIRED')
        prior = parse(record_path.read_bytes())
    result = validate(manifest_path, expected_sha, prior)
    output.mkdir(exist_ok=False, parents=True)
    registry.mkdir(exist_ok=True, parents=True)
    archive = output / (capture_id + '.zip')
    payloads = [{'member': item['relative'], 'bytes': item['bytes'], 'sha256': item['sha256']}
                for item in result['files']]
    payloads.append({'member': 'CAPTURE_MANIFEST.json', 'bytes': result['manifest']['bytes'],
                     'sha256': result['manifest']['sha256']})
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for item in result['files']:
            data = Path(item['path']).read_bytes()
            need(sha(data) == item['sha256'], 'SEAL_INPUT_CHANGED')
            z.writestr(item['relative'], data)
        data = Path(manifest_path).read_bytes()
        need(sha(data) == expected_sha, 'SEAL_MANIFEST_CHANGED')
        z.writestr('CAPTURE_MANIFEST.json', data)
        z.writestr('MANIFEST.json', json.dumps({'capture_id': capture_id, 'payloads': payloads}, indent=2) + '\n')
    with zipfile.ZipFile(archive) as z:
        need(z.testzip() is None and len(z.namelist()) == len(payloads) + 1, 'ZIP_INTEGRITY')
        for item in payloads:
            data = z.read(item['member'])
            need(len(data) == item['bytes'] and sha(data) == item['sha256'], 'ZIP_MEMBER_IDENTITY')
    if prior is None:
        with record_path.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(result['signature'], stream, indent=2)
            stream.write('\n')
    result['archive'] = ident(archive)
    result['registry_record'] = ident(record_path)
    result['CRC_member_SHA_verified'] = True
    (output / 'SEAL_RECEIPT.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', required=True)
    ap.add_argument('--expected-sha', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--registry', required=True)
    ap.add_argument('--registry-sha')
    args = ap.parse_args()
    try:
        result = seal(args.manifest, args.expected_sha, args.output, args.registry, args.registry_sha)
        print(json.dumps({'status': result['status'], 'archive': result['archive'], 'board_release_allowed': False}))
        return 0
    except (Reject, OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'status': 'REJECT', 'first_failure': str(error), 'board_release_allowed': False}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
