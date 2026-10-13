"""Plan-bound T052 control checker. This module never starts an HDL tool.

The SOFTWARE fixture mode cannot produce an RTL verification result. Actual mode
requires externally pinned preparation manifest, run receipt and approval hashes.
Those hashes must come from the authorized runner/M2, not from trace META labels.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
PUBLICATION = HERE.parents[1] / 'publication.py'
CALENDAR_SHA = '0fdf4bb1530453cbbce14136bcae082ca1ff28e04d96402065f4c916ecf36058'
PLAN_SHA = 'b2d0cb1ba0bf3cd4b2d636f3d4cb7ac286558238ae2b52c3e9e43ba54ee5ef02'
FROZEN_SOURCES = {
    'dut': '89ddb8b73bda6e5c83c7b617640cddf3294fb194a9b7955746c28a2e0f2eddeb',
    'rom': '5e1dbd3797f353686f5e567831b56d6dcf9bee55c423097b471ade93203e84b2',
    'dds': '3cd758e28da8f76a30da38cb2dfcd458db5743d4ea4f38e072a43d7f83719f04',
    'mixer': '93fb6e88e55ea84f2e322b0cf8b94a1a2c2e13618e302e7d24ec8657c92bb99a',
}
TRACKS = ('controls', 'observations', 'publications', 'resets')
SOFTWARE_ORIGIN = 'HANDWRITTEN_SOFTWARE_FIXTURE'
ACTUAL_ORIGIN = 'RTL_SIM_PUBLIC_PORTS_V1'
RESET_ORIGIN = 'RTL_SIM_RESET_SIGNAL_V1'
U32 = (1 << 32) - 1


class UnknownEvidence(ValueError):
    """Missing/open evidence cannot qualify the full control window."""


def need(condition, diagnostic, error=ValueError):
    if not condition:
        raise error(diagnostic)


def identity(path):
    raw = Path(path).read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def integer(value, low=0, high=U32):
    return type(value) is int and low <= value <= high


def same(actual, expected):
    """Deep equality that does not equate bool/float with JSON integers."""
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return set(actual) == set(expected) and all(
            same(actual[key], value) for key, value in expected.items())
    if type(expected) is list:
        return len(actual) == len(expected) and all(
            same(a, b) for a, b in zip(actual, expected))
    return actual == expected


def exact(row, keys, diagnostic):
    need(type(row) is dict and set(row) == set(keys.split()), diagnostic)


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def decode(raw):
    return json.loads(raw, object_pairs_hook=unique_pairs,
                      parse_constant=lambda _: need(False, 'NONFINITE_JSON'))


def read_json(path):
    return decode(Path(path).read_text(encoding='utf-8'))


def read_jsonl(path):
    lines = Path(path).read_text(encoding='utf-8').splitlines()
    need(lines and all(lines), 'EMPTY_JSONL_ROW')
    return [decode(line) for line in lines]


def source_identity(spec):
    need(type(spec) is dict and set(spec) in (
        {'path', 'bytes', 'sha256'}, {'path', 'member', 'bytes', 'sha256'}),
        'FILE_SPEC_FIELDS')
    need(type(spec['path']) is str and integer(spec['bytes'], 0, 1 << 40)
         and type(spec['sha256']) is str
         and re.fullmatch('[0-9a-f]{64}', spec['sha256']) is not None,
         'FILE_SPEC_TYPES')
    path = Path(spec['path'])
    if not path.is_absolute():
        path = ROOT / path
    if 'member' in spec:
        need(type(spec['member']) is str, 'ARCHIVE_MEMBER_TYPE')
        with zipfile.ZipFile(path) as archive:
            raw = archive.read(spec['member'])
        actual = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    else:
        actual = identity(path)
    need(same(actual, {key: spec[key] for key in ('bytes', 'sha256')}),
         'FILE_IDENTITY:' + spec['path'])
    return actual


def load_manifest(path, pinned_sha):
    need(type(pinned_sha) is str and identity(path)['sha256'] == pinned_sha,
         'MANIFEST_EXTERNAL_PIN')
    manifest = read_json(path)
    exact(manifest, 'schema execution_authorized plan calendar sources tools '
          'compile_argv run_argv', 'MANIFEST_FIELDS')
    need(manifest['schema'] == 'T052_P0_STATIC_COMBINATION_V2' and
         manifest['execution_authorized'] is False, 'PREPARATION_LOCK')
    need(source_identity(manifest['plan'])['sha256'] == PLAN_SHA, 'PLAN_SOURCE_SHA')
    need(source_identity(manifest['calendar'])['sha256'] == CALENDAR_SHA,
         'CALENDAR_SOURCE_SHA')
    exact(manifest['sources'], 'dut rom dds mixer tb observer driver_mem',
          'SOURCE_ROLES')
    for role, spec in manifest['sources'].items():
        actual = source_identity(spec)
        if role in FROZEN_SOURCES:
            need(actual['sha256'] == FROZEN_SOURCES[role], 'FROZEN_SOURCE:' + role)
    need(type(manifest['tools']) is dict and
         {'compile', 'runtime'} <= set(manifest['tools']), 'TOOL_ROLES')
    for spec in manifest['tools'].values():
        source_identity(spec)
    for name in ('compile_argv', 'run_argv'):
        argv = manifest[name]
        need(type(argv) is list and argv and all(type(v) is str for v in argv),
             'ARGV_TYPES:' + name)
    need(manifest['compile_argv'][0] == manifest['tools']['compile']['path'] and
         manifest['run_argv'][0] == manifest['tools']['runtime']['path'],
         'ARGV_TOOL_BINDING')
    return manifest


def expected_window(plan_path):
    """Compute the complete obligation set BEFORE opening any observed track."""
    need(identity(plan_path)['sha256'] == PLAN_SHA, 'FIXED_PLAN_SHA')
    need(identity(PUBLICATION)['sha256'] == CALENDAR_SHA, 'FROZEN_CALENDAR_SHA')
    spec = importlib.util.spec_from_file_location('t052_frozen_calendar', PUBLICATION)
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    plan = read_jsonl(plan_path)
    try:
        expected = model.calendar(plan)
    except ValueError as error:
        if str(error) == 'OPEN_REQUEST_AT_END':
            raise UnknownEvidence(str(error)) from error
        raise
    controls = [{**row, 'time': 10 + 20 * row['cycle']} for row in plan[1:-1]]
    pins = [{'cycle': pin['cycle'], 'time': 10 + 20 * pin['cycle'],
             'calc_ready': pin['calc_ready'], 'result_valid': pin['result_valid'],
             'result_req_id': pin['result_id']} for pin in expected['pins']]
    events = []
    for source, tag in (('accepted', 'ACCEPT'), ('cancelled', 'CANCEL'),
                        ('publications', 'PUBLISH')):
        for row in expected[source]:
            key = row['key']
            item = {'event': tag, 'cycle': row['cycle'],
                    'time': 10 + 20 * row['cycle'], 'epoch': key[0],
                    'serial': key[1], 'req_id': key[2]}
            if tag == 'CANCEL':
                item['reason'] = row['reason']
            if tag == 'PUBLISH':
                item['observed_req_id'] = key[2]
            events.append(item)
    events.sort(key=lambda row: row['cycle'])
    resets, previous = [], 1
    for row in controls:
        if row['rst_n'] != previous:
            resets.append({'event': 'RESET_EDGE', 'time': 20 * row['cycle'],
                           'cycle_visible_next': row['cycle'], 'rst_n': row['rst_n']})
        previous = row['rst_n']
    ledger = {'type': 'END', 'accepted': len(expected['accepted']),
              'published': len(expected['publications']),
              'cancelled': len(expected['cancelled']), 'open': 0}
    need(same(ledger, {'type': 'END', 'accepted': 6, 'published': 3,
                      'cancelled': 3, 'open': 0}), 'FROZEN_PLAN_LEDGER')
    end = {'type': 'END', 'last_cycle': 127, 'rows': 128}
    return {'controls': controls + [end], 'observations': pins + [end],
            'publications': events + [ledger],
            'resets': resets + [{'type': 'END', 'last_cycle': 127}]}


def metadata(manifest, track, fixture):
    origin = SOFTWARE_ORIGIN if fixture else (
        RESET_ORIGIN if track == 'resets' else ACTUAL_ORIGIN)
    row = {'type': 'META', 'origin': origin, 'sampling': 'PRE_NBA',
           'time_unit': '1ns', 'time_precision': '1ps',
           'clock_period_ns': 20, 'first_posedge_ns': 10,
           'plan_sha256': manifest['plan']['sha256'],
           'tool_sha256': manifest['tools']['runtime']['sha256']}
    for name in ('dut', 'rom', 'tb', 'observer'):
        row[name + '_sha256'] = manifest['sources'][name]['sha256']
    return row


def validate_rows(rows, expected, manifest, fixture):
    for track in TRACKS:
        actual = rows[track]
        need(actual and same(actual[0], metadata(manifest, track, fixture)),
             'SOURCE_META:' + track)
        # Missing edges/END or an explicitly open ledger are insufficient, never PASS.
        if len(actual) < len(expected[track]) + 1:
            raise UnknownEvidence('INCOMPLETE_WINDOW:' + track)
        end = actual[-1]
        if track == 'publications':
            exact(end, 'type accepted published cancelled open',
                  'END_FIELDS:publications')
            need(end['type'] == 'END', 'END_TYPE:publications')
            for name in ('accepted', 'published', 'cancelled', 'open'):
                need(integer(end[name]), 'END_INTEGER:' + name)
            need(end['open'] == 0, 'OPEN_REQUEST_AT_END', UnknownEvidence)
        elif track in ('controls', 'observations'):
            exact(end, 'type last_cycle rows', 'END_FIELDS:' + track)
            need(end['type'] == 'END' and integer(end['last_cycle']) and
                 integer(end['rows']), 'END_TYPES:' + track)
        else:
            exact(end, 'type last_cycle', 'END_FIELDS:resets')
            need(end['type'] == 'END' and integer(end['last_cycle']),
                 'END_TYPES:resets')
        need(len(actual) == len(expected[track]) + 1, 'EXTRA_RECORD:' + track)
        for index, (observed, reference) in enumerate(zip(actual[1:], expected[track])):
            if not same(observed, reference):
                tag = ('SOURCE_CALENDAR_PINS' if track == 'observations' else
                       'RESET_EDGE_COVERAGE' if track == 'resets' else
                       'INDEPENDENT_PUBLICATION_LEDGER' if track == 'publications' else
                       'CONTROL_PLAN_TIME')
                raise ValueError(tag + ':' + str(index))


def validate_run_receipt(path, pinned_sha, approval_sha, manifest_path, manifest,
                         track_paths):
    need(path is not None and pinned_sha is not None and approval_sha is not None,
         'ACTUAL_RUN_RECEIPT_REQUIRED')
    need(identity(path)['sha256'] == pinned_sha, 'RUN_RECEIPT_EXTERNAL_PIN')
    receipt = read_json(path)
    exact(receipt, 'schema evidence_kind approval_sha256 manifest_sha256 machine '
          'status exit_code timeout source_snapshots tools_before tools_after '
          'sources_before sources_after compile run artifacts', 'RUN_RECEIPT_FIELDS')
    need(receipt['schema'] == 'T052_PUBLIC_PORT_RUN_RECEIPT_V2' and
         receipt['evidence_kind'] == 'RTL_RUN' and
         receipt['approval_sha256'] == approval_sha and
         re.fullmatch('[0-9a-f]{64}', approval_sha) is not None and
         receipt['manifest_sha256'] == identity(manifest_path)['sha256'],
         'RUN_RECEIPT_IDENTITY')
    need(type(receipt['machine']) is str and receipt['machine'] and
         receipt['status'] == 'PASS' and type(receipt['exit_code']) is int and
         receipt['exit_code'] == 0 and receipt['timeout'] is False, 'RUN_NOT_SUCCESSFUL')
    sources = {role: {key: item[key] for key in ('bytes', 'sha256')}
               for role, item in manifest['sources'].items()}
    tools = {role: {key: item[key] for key in ('bytes', 'sha256')}
             for role, item in manifest['tools'].items()}
    need(same(receipt['sources_before'], sources) and
         same(receipt['sources_after'], sources), 'RUN_SOURCE_BEFORE_AFTER')
    need(same(receipt['tools_before'], tools) and same(receipt['tools_after'], tools),
         'RUN_TOOL_BEFORE_AFTER')
    need(type(receipt['source_snapshots']) is dict and
         set(receipt['source_snapshots']) == set(sources), 'RUN_SOURCE_SNAPSHOTS')
    for role, snapshot in receipt['source_snapshots'].items():
        need(same(source_identity(snapshot), sources[role]), 'RUN_SNAPSHOT:' + role)
    for label, argv in (('compile', manifest['compile_argv']), ('run', manifest['run_argv'])):
        step = receipt[label]
        exact(step, 'argv cwd exit_code timeout stdout stderr executable', 'STEP_FIELDS')
        need(same(step['argv'], argv) and type(step['cwd']) is str and
             Path(step['cwd']).is_absolute() and type(step['exit_code']) is int and
             step['exit_code'] == 0 and step['timeout'] is False, 'STEP_RESULT:' + label)
        source_identity(step['stdout'])
        source_identity(step['stderr'])
        role = 'compile' if label == 'compile' else 'runtime'
        need(same(source_identity(step['executable']), tools[role]), 'STEP_TOOL:' + label)
    need(type(receipt['artifacts']) is dict and set(receipt['artifacts']) == set(TRACKS),
         'RUN_ARTIFACT_ROLES')
    for role in TRACKS:
        artifact = receipt['artifacts'][role]
        need(same(source_identity(artifact), identity(track_paths[role])),
             'RUN_ARTIFACT_SHA:' + role)
        need(Path(artifact['path']).resolve() == Path(track_paths[role]).resolve(),
             'RUN_ARTIFACT_PATH:' + role)


def check(manifest_path, manifest_sha, plan_path, track_paths, fixture=False,
          receipt_path=None, receipt_sha=None, approval_sha=None):
    manifest = load_manifest(manifest_path, manifest_sha)
    expected = expected_window(plan_path)
    if not fixture:
        validate_run_receipt(receipt_path, receipt_sha, approval_sha, manifest_path,
                             manifest, track_paths)
    inputs = {str(path): identity(path) for path in [manifest_path, plan_path,
              *track_paths.values()] + ([receipt_path] if receipt_path else [])}
    rows = {name: read_jsonl(track_paths[name]) for name in TRACKS}
    validate_rows(rows, expected, manifest, fixture)
    need(inputs == {name: identity(name) for name in inputs}, 'INPUT_CHANGED')
    return {'status': 'SOFTWARE_FIXTURE_PASS' if fixture else 'RTL_CONTROL_WINDOW_PASS',
            'exit_code': 0, 'ledger': expected['publications'][-1],
            'expected_pins': 128, 'reset_edges': 4, 'inputs': inputs,
            'RTL_verified': not fixture, 'audio_math': 'NOT_RERUN',
            'T052_complete': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('fixture', 'actual'))
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha', required=True)
    parser.add_argument('--plan', type=Path, required=True)
    for name in TRACKS:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--receipt-sha')
    parser.add_argument('--approval-sha')
    args = parser.parse_args()
    try:
        result = check(args.manifest, args.manifest_sha, args.plan,
                       {name: getattr(args, name) for name in TRACKS},
                       fixture=args.mode == 'fixture', receipt_path=args.receipt,
                       receipt_sha=args.receipt_sha, approval_sha=args.approval_sha)
    except UnknownEvidence as error:
        result = {'status': 'UNKNOWN', 'exit_code': 3, 'diagnostic': str(error),
                  'T052_complete': False, 'RTL_verified': False}
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile) as error:
        result = {'status': 'FAIL', 'exit_code': 1, 'diagnostic': str(error),
                  'T052_complete': False, 'RTL_verified': False}
    print(json.dumps(result, sort_keys=True))
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
