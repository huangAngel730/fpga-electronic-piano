"""Fail-closed, source-bound Pro trace intake; no acquisition or DUT claim."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
DECODER = ROOT / 'code/software/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/RESUME_R02/consume_capture.py'
DECODER_SHA = 'da91462e8421719e09ffab60d7bbe38d4ee05ac1793ea70e1f09c7a69ccda0cb'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decoder():
    require(sha(DECODER) == DECODER_SHA, 'LEGACY_DECODER_SHA')
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('m3_pinned_decoder', DECODER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def integer(value, name, minimum=0):
    require(type(value) is int and value >= minimum, 'INTEGER_' + name)


def intake(manifest_path, expected_sha):
    manifest_path = Path(manifest_path).resolve()
    require(sha(manifest_path) == expected_sha, 'MANIFEST_SHA')
    legacy = decoder()
    parse = legacy.parse_json
    manifest = parse(manifest_path.read_text(encoding='utf-8'))
    require(set(manifest) == {'schema', 'provenance', 'clock_hz', 'sampling_phase', 'package', 'artifacts'}, 'MANIFEST_FIELDS')
    require(manifest['schema'] == 'M3_PRO_INTAKE_V1', 'MANIFEST_SCHEMA')
    require(manifest['provenance'] in ('SYNTHETIC_FIXTURE', 'DECLARED_REAL_PENDING_M2'), 'PROVENANCE')
    require(manifest['package'] == 'FPG676' and manifest['clock_hz'] == 40000000, 'CLOCK_OR_PACKAGE_CONTRACT')
    require(manifest['sampling_phase'] == 'SYS_EDGE_ORDERED_EVENTS_V1', 'SAMPLING_PHASE_CONTRACT')
    require(type(manifest['artifacts']) is list, 'ARTIFACTS_TYPE')
    artifacts = {}
    identities = []
    base = manifest_path.parent
    for entry in manifest['artifacts']:
        require(type(entry) is dict and set(entry) == {'role', 'path', 'bytes', 'sha256'}, 'ARTIFACT_FIELDS')
        role = entry['role']
        require(role not in artifacts and role in ('source', 'rom', 'contract', 'calendar', 'trace'), 'ARTIFACT_ROLE')
        require(type(entry['path']) is str and not Path(entry['path']).is_absolute(), 'ARTIFACT_PATH')
        path = (base / entry['path']).resolve()
        require(path.is_relative_to(base) and path.is_file(), 'ARTIFACT_PATH_OR_MISSING')
        integer(entry['bytes'], 'ARTIFACT_BYTES')
        require(path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256'], 'ARTIFACT_SHA_' + role)
        artifacts[role] = path
        identities.append(entry)
    require(set(artifacts) == {'source', 'rom', 'contract', 'calendar', 'trace'}, 'ARTIFACT_ROLES_MISSING')
    contract = parse(artifacts['contract'].read_text(encoding='utf-8'))
    require(contract == {'schema': 'M3_PRO_OBSERVER_REQUIREMENTS_V1', 'package': 'FPG676',
                         'clock_hz': 40000000, 'sampling_phase': 'SYS_EDGE_ORDERED_EVENTS_V1',
                         'pa_active': 1, 'identity_only': True}, 'CONTRACT_CONTENT')
    calendar = parse(artifacts['calendar'].read_text(encoding='utf-8'))
    require(set(calendar) == {'schema', 'provenance', 'requests'} and calendar['schema'] == 'M3_PRO_INTAKE_CALENDAR_V1', 'CALENDAR_FIELDS')
    require(calendar['provenance'] == manifest['provenance'] and type(calendar['requests']) is list, 'CALENDAR_PROVENANCE')
    expected = {}
    for entry in calendar['requests']:
        require(type(entry) is dict and set(entry) == {'epoch', 'req_id', 'cycle', 'lane_mask'}, 'CALENDAR_REQUEST_FIELDS')
        for name in ('epoch', 'req_id', 'cycle', 'lane_mask'):
            integer(entry[name], name)
        key = (entry['epoch'], entry['req_id'])
        require(key not in expected and entry['lane_mask'] == 15, 'CALENDAR_REQUEST_IDENTITY')
        expected[key] = entry
    fields = {
        'RESET': 'kind cycle epoch', 'FRAME': 'kind cycle epoch frame_id',
        'REQUEST': 'kind cycle epoch req_id lane_mask', 'ACCEPT': 'kind cycle epoch req_id',
        'LANE_TICK': 'kind cycle epoch req_id lane',
        'RETURN': 'kind cycle epoch req_id left right', 'CONSUME': 'kind cycle epoch req_id frame_id',
        'CANCEL': 'kind cycle epoch req_id', 'PA': 'kind cycle epoch rst_n stable pa_en',
        'END': 'kind cycle epoch'}
    ledger, observed, frame_ids, gaps = {}, set(), set(), []
    cycle, epoch, last_frame, frame_id, ended, resets = -1, -1, None, None, False, 0
    consumed = 0
    with artifacts['trace'].open(encoding='utf-8') as stream:
        for line_number, line in enumerate(stream, 1):
            row = parse(line)
            kind = row.get('kind')
            require(not ended and kind in fields and set(row) == set(fields[kind].split()), f'ROW_FIELDS_OR_AFTER_END_{line_number}')
            for name, value in row.items():
                if name != 'kind' and name not in ('left', 'right'):
                    integer(value, name)
            require(row['cycle'] >= cycle, f'CYCLE_ORDER_{line_number}')
            cycle = row['cycle']
            if kind == 'RESET':
                require(row['epoch'] == epoch + 1, 'RESET_EPOCH')
                for item in ledger.values():
                    if item['state'] not in ('CONSUMED', 'CANCELED'):
                        require(item.get('due_cycle') is None, 'RESET_UNCONSUMED_DUE_FRAME')
                        require(cycle - item['request_cycle'] < 834, 'RESET_AFTER_UNOBSERVED_DEADLINE')
                        item['state'] = 'CANCELED'
                epoch, last_frame, frame_id = row['epoch'], None, None
                resets += 1
                continue
            require(row['epoch'] == epoch and epoch >= 0, 'OLD_OR_MISSING_EPOCH')
            if kind == 'FRAME':
                key = (epoch, row['frame_id'])
                require(key not in frame_ids, 'DUPLICATE_FRAME')
                require(frame_id is None or row['frame_id'] == frame_id + 1, 'MISSING_FRAME')
                if last_frame is not None:
                    require(cycle - last_frame in (833, 834), 'FRAME_CADENCE')
                    gaps.append(cycle - last_frame)
                for item in ledger.values():
                    if item['epoch'] == epoch and item['state'] == 'CANCELED' and item.get('cancel_cycle') is not None and item['request_cycle'] == last_frame:
                        require(item['cancel_cycle'] < cycle, 'CANCEL_NOT_STRICTLY_BEFORE_FRAME')
                    if item['epoch'] == epoch and item['state'] in ('REQUESTED', 'ACCEPTED'):
                        raise ValueError('MISSED_NEXT_FRAME_DEADLINE')
                    if item['epoch'] == epoch and item['state'] == 'RETURNED':
                        require(item.get('due_cycle') is None, 'MISSING_CONSUME_AT_DUE_FRAME')
                        require(item['return_cycle'] < cycle, 'RETURN_NOT_STRICTLY_BEFORE_FRAME')
                        item['due_cycle'] = cycle
                frame_ids.add(key)
                last_frame, frame_id = cycle, row['frame_id']
            elif kind == 'PA':
                require(all(row[n] in (0, 1) for n in ('rst_n', 'stable', 'pa_en')), 'PA_BINARY')
                require(row['pa_en'] == int(bool(row['rst_n'] and row['stable'])), 'PA_POLARITY_OR_UNSTABLE')
            elif kind == 'END':
                require(all(v['state'] in ('CONSUMED', 'CANCELED') for v in ledger.values()), 'UNFINISHED_TRANSACTION')
                ended = True
            else:
                key = (epoch, row['req_id'])
                if kind == 'REQUEST':
                    require(key in expected and key not in observed, 'UNEXPECTED_OR_DUPLICATE_REQUEST')
                    e = expected[key]
                    require(row['lane_mask'] == e['lane_mask'] and cycle == e['cycle'], 'INDEPENDENT_CALENDAR_MISMATCH')
                    require(last_frame is not None and cycle == last_frame, 'REQUEST_FRAME_ORIGIN')
                    observed.add(key)
                    ledger[key] = {'epoch': epoch, 'state': 'REQUESTED', 'lanes': set(), 'request_cycle': cycle}
                    continue
                require(key in ledger, 'UNKNOWN_REQUEST')
                item = ledger[key]
                if kind == 'ACCEPT':
                    require(item['state'] == 'REQUESTED', 'DUPLICATE_OR_LATE_ACCEPT')
                    item['state'] = 'ACCEPTED'
                elif kind == 'LANE_TICK':
                    require(item['state'] == 'ACCEPTED' and row['lane'] in range(4) and row['lane'] not in item['lanes'], 'WRONG_OR_DUPLICATE_LANE')
                    item['lanes'].add(row['lane'])
                elif kind == 'RETURN':
                    require(item['state'] == 'ACCEPTED' and item['lanes'] == {0, 1, 2, 3}, 'RETURN_STATE_OR_MISSING_LANE')
                    legacy.quantize(row['left'])
                    legacy.quantize(row['right'])
                    item['state'] = 'RETURNED'
                    item['return_cycle'] = cycle
                elif kind == 'CONSUME':
                    require(item['state'] == 'RETURNED', 'CONSUME_CANCELED_OR_UNRETURNED')
                    require(row['frame_id'] == frame_id and cycle == last_frame, 'CONSUME_FRAME_ID')
                    require(item.get('due_cycle') == cycle, 'CONSUME_NOT_AT_DUE_FRAME')
                    require(cycle - item['request_cycle'] in (833, 834), 'CONSUME_DEADLINE')
                    item['state'] = 'CONSUMED'
                    consumed += 1
                elif kind == 'CANCEL':
                    require(item['state'] in ('REQUESTED', 'ACCEPTED', 'RETURNED'), 'CANCEL_STATE')
                    require(item.get('due_cycle') is None, 'CANCEL_AFTER_DUE_FRAME')
                    item['state'] = 'CANCELED'
                    item['cancel_cycle'] = cycle
    require(ended and observed == set(expected) and consumed > 0 and resets > 0, 'INCOMPLETE_CAPTURE_OR_CALENDAR')
    require(sha(manifest_path) == expected_sha, 'MANIFEST_CHANGED_DURING_READ')
    for entry in identities:
        path = artifacts[entry['role']]
        require(path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256'], 'ARTIFACT_CHANGED_DURING_READ')
    return {'status': 'INTAKE_FIXTURE_PASS' if manifest['provenance'] == 'SYNTHETIC_FIXTURE' else 'INTAKE_STRUCTURE_ONLY_PENDING_M2',
            'level': 'L1', 'board_release_allowed': False, 'pro_dut_pass': False,
            'provenance': manifest['provenance'], 'manifest_sha256': expected_sha,
            'artifacts': identities, 'consumed': consumed, 'frame_gaps': gaps,
            'legacy_decoder_sha256': DECODER_SHA, 'real_trace_status': 'PENDING_PRO_SOURCE_OR_TRACE'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(intake(args.manifest, args.sha256), ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'REJECT', 'first_failure': str(exc), 'pro_dut_pass': False, 'board_release_allowed': False}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
