"""Static and future-capture checks for the T052 128-edge public-port successor.

This module never invokes an HDL compiler or simulator. The `capture` mode only
checks files produced by a separately authorized run.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from render_control_mem import PLAN_SHA256, pack, read_plan


ROOT = HERE.parents[3]
ACTUAL_ORIGIN = 'RTL_SIM_PUBLIC_PORTS_V1'
DUT_SHA256 = '89ddb8b73bda6e5c83c7b617640cddf3294fb194a9b7955746c28a2e0f2eddeb'
ROM_SHA256 = '5e1dbd3797f353686f5e567831b56d6dcf9bee55c423097b471ade93203e84b2'
RAW_SHA256 = '86704ddd20ee755d3d77ebe7a1379f3a8f2992e9a867a251fc1e3574ff4817a0'
READONLY_SHA256 = '4e05dbd1803672ea6e37bb65a161ad9f184d2047b37790c777990b229a39ab3e'
U32 = (1 << 32) - 1


class InsufficientEvidence(ValueError):
    """Evidence cannot be called PASS, but is not a functional mismatch."""


def need(condition, diagnostic, exception=ValueError):
    if not condition:
        raise exception(diagnostic)


def identity(path):
    raw = Path(path).read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def read_jsonl(path):
    lines = Path(path).read_text(encoding='utf-8').splitlines()
    need(lines and all(lines), 'EMPTY_JSONL_ROW')
    return [json.loads(line, object_pairs_hook=unique_pairs,
                       parse_constant=lambda _: need(False, 'NONFINITE'))
            for line in lines]


def exact(row, keys, diagnostic='SCHEMA_FIELDS'):
    need(type(row) is dict and set(row) == set(keys), diagnostic)


def integer(value, low=0, high=U32):
    return type(value) is int and low <= value <= high


def load_manifest(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'),
                      object_pairs_hook=unique_pairs)
    need(data['execution_authorized'] is False, 'EXECUTION_MUST_REMAIN_LOCKED')
    need(data['plan_sha256'] == PLAN_SHA256, 'MANIFEST_PLAN_SHA')
    need(data['dut_sha256'] == DUT_SHA256, 'MANIFEST_DUT_SHA')
    need(data['rom_sha256'] == ROM_SHA256, 'MANIFEST_ROM_SHA')
    return data


def validate_plan(plan, driver_mem):
    rows = read_plan(plan)
    lines = Path(driver_mem).read_text(encoding='ascii').splitlines()
    need(len(lines) == 128, 'DRIVER_MEM_ROWS')
    need(lines == [pack(row) for row in rows], 'DRIVER_MEM_PLAN_MISMATCH')
    return rows


def validate_archive(path, expected_sha, members):
    need(identity(path)['sha256'] == expected_sha, 'ARCHIVE_SHA:' + Path(path).name)
    with zipfile.ZipFile(path) as archive:
        need(archive.testzip() is None, 'ARCHIVE_CRC:' + Path(path).name)
        for name, expected in members.items():
            raw = archive.read(name)
            actual = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            need(actual == expected, 'ARCHIVE_MEMBER:' + name)


def validate_static(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    manifest = load_manifest(manifest_path)
    for relative, expected in manifest['tracked_files'].items():
        path = ROOT / relative
        need(identity(path) == expected, 'TRACKED_FILE_SHA:' + relative)
    rows = validate_plan(ROOT / manifest['plan_path'], ROOT / manifest['driver_mem_path'])
    validate_archive(ROOT / manifest['raw_archive']['path'], RAW_SHA256,
                     manifest['raw_archive']['members'])
    validate_archive(ROOT / manifest['readonly_archive']['path'], READONLY_SHA256,
                     manifest['readonly_archive']['members'])
    tb = (ROOT / manifest['tb_path']).read_text(encoding='utf-8')
    observer = (ROOT / manifest['observer_path']).read_text(encoding='utf-8')
    need('dut.' not in tb and 'dut.' not in observer and '$root.' not in observer,
         'INTERNAL_HIERARCHICAL_ACCESS')
    need('apply_control(controls[cycle + 1])' in tb and
         'result_valid && result_ready' in observer and
         'frame_tick || cancel' in observer and 'always @(rst_n)' in observer,
         'STATIC_CONTRACT_MARKER')
    need(manifest['planned_execution']['authorized'] is False and
         manifest['planned_execution']['rtl_runs'] == 0,
         'PLANNED_EXECUTION_LOCK')
    return {
        'status': 'STATIC_PREPARATION_PASS',
        'exit_code': 0,
        'plan_rows': len(rows),
        'plan_sha256': PLAN_SHA256,
        'dut_sha256': DUT_SHA256,
        'rom_sha256': ROM_SHA256,
        'RTL_runs': 0,
        'EDA_runs': 0,
        'T052_complete': False,
    }


def validate_track_meta(meta, required):
    need(meta.get('type') == 'META' and meta.get('origin') == ACTUAL_ORIGIN,
         'ACTUAL_SOURCE_ORIGIN')
    need(meta.get('sampling', 'PRE_NBA') == 'PRE_NBA', 'SAMPLING_NOT_PRE_NBA')
    for key, value in required.items():
        need(meta.get(key) == value, 'CAPTURE_IDENTITY:' + key)


def validate_capture(manifest_path, plan_path, controls_path, observations_path,
                     publications_path, resets_path):
    """Check a future real trace without using missing outputs as cancellation."""
    manifest = load_manifest(manifest_path)
    plan = read_plan(plan_path)
    controls = read_jsonl(controls_path)
    observations = read_jsonl(observations_path)
    publications = read_jsonl(publications_path)
    resets = read_jsonl(resets_path)
    required = {'dut_sha256': DUT_SHA256, 'plan_sha256': PLAN_SHA256}
    validate_track_meta(controls[0], required)
    validate_track_meta(observations[0], required)
    validate_track_meta(publications[0], required)
    need(resets[0].get('type') == 'META' and
         resets[0].get('origin') == 'RTL_SIM_RESET_SIGNAL_V1' and
         all(resets[0].get(key) == value for key, value in required.items()),
         'RESET_SOURCE_ORIGIN')
    need(len(controls) == 130 and len(observations) == 130,
         'CAPTURE_WINDOW_INCOMPLETE', InsufficientEvidence)
    need(controls[-1] == {'type': 'END', 'last_cycle': 127, 'rows': 128} and
         observations[-1] == {'type': 'END', 'last_cycle': 127, 'rows': 128},
         'CAPTURE_END', InsufficientEvidence)

    control_rows = controls[1:-1]
    output_rows = observations[1:-1]
    for cycle, (expected, control, output) in enumerate(zip(plan, control_rows, output_rows)):
        exact(control, {'cycle', 'time', 'rst_n', 'frame', 'cancel', 'sample_req',
                        'req_id', 'enable', 'mask', 'fcw', 'result_ready'})
        exact(output, {'cycle', 'time', 'calc_ready', 'result_valid', 'result_req_id'})
        need(control['cycle'] == output['cycle'] == cycle and
             control['time'] == output['time'] and integer(control['time']),
             'CYCLE_OR_TIME')
        need(all(integer(control[key], 0, 1) for key in
                 ('rst_n', 'frame', 'cancel', 'sample_req', 'enable', 'result_ready')) and
             all(integer(output[key], 0, 1) for key in ('calc_ready', 'result_valid')),
             'STRICT_FLAG_01')
        projected = {key: control[key] for key in
                     ('cycle', 'rst_n', 'frame', 'cancel', 'sample_req', 'req_id',
                      'enable', 'mask', 'fcw', 'result_ready')}
        need(projected == expected, 'CONTROL_PLAN_DRIFT:' + str(cycle))
        need(integer(output['result_req_id']), 'RESULT_ID_RANGE')

    transitions = []
    previous = 1
    for row in control_rows:
        if row['rst_n'] != previous:
            transitions.append((row['cycle'], row['rst_n'], row['time']))
        previous = row['rst_n']
    reset_rows = resets[1:-1]
    need(resets[-1] == {'type': 'END', 'last_cycle': 127},
         'RESET_END', InsufficientEvidence)
    need(len(reset_rows) == len(transitions), 'RESET_EDGE_COVERAGE', InsufficientEvidence)
    for actual, (cycle, level, observed_time) in zip(reset_rows, transitions):
        exact(actual, {'event', 'time', 'cycle_visible_next', 'rst_n'})
        need(actual['event'] == 'RESET_EDGE' and actual['cycle_visible_next'] == cycle and
             actual['rst_n'] == level and integer(actual['time']) and
             actual['time'] <= observed_time, 'RESET_EDGE_MAPPING')

    derived = []
    epoch = 0
    serial = 0
    pending = None
    previous = 1
    accepted = published = cancelled = 0
    for control, output in zip(control_rows, output_rows):
        cycle, now = control['cycle'], control['time']
        if not control['rst_n']:
            if previous:
                epoch += 1
                serial = 0
            if pending is not None:
                derived.append({'event': 'CANCEL', 'cycle': cycle, 'time': now,
                                'epoch': pending[0], 'serial': pending[1],
                                'req_id': pending[2], 'reason': 'reset'})
                cancelled += 1
            pending = None
        elif control['frame'] or control['cancel']:
            if pending is not None:
                derived.append({'event': 'CANCEL', 'cycle': cycle, 'time': now,
                                'epoch': pending[0], 'serial': pending[1],
                                'req_id': pending[2],
                                'reason': 'frame' if control['frame'] else 'cancel'})
                cancelled += 1
            pending = None
        else:
            if output['result_valid'] and control['result_ready']:
                need(pending is not None, 'ORPHAN_PUBLICATION')
                derived.append({'event': 'PUBLISH', 'cycle': cycle, 'time': now,
                                'epoch': pending[0], 'serial': pending[1],
                                'req_id': pending[2],
                                'observed_req_id': output['result_req_id']})
                need(output['result_req_id'] == pending[2], 'PUBLICATION_ID_MISMATCH')
                published += 1
                pending = None
            if control['sample_req'] and output['calc_ready']:
                need(pending is None, 'MULTIPLE_OPEN_REQUESTS')
                serial += 1
                pending = (epoch, serial, control['req_id'])
                derived.append({'event': 'ACCEPT', 'cycle': cycle, 'time': now,
                                'epoch': epoch, 'serial': serial,
                                'req_id': control['req_id']})
                accepted += 1
        previous = control['rst_n']

    need(pending is None, 'OPEN_REQUEST_AT_END', InsufficientEvidence)
    need(publications[1:-1] == derived, 'PUBLICATION_EVENT_MISMATCH')
    expected_end = {'type': 'END', 'accepted': accepted, 'published': published,
                    'cancelled': cancelled, 'open': 0}
    need(publications[-1] == expected_end, 'PUBLICATION_END_COUNT')
    return {
        'status': 'RTL_PUBLIC_CONTROL_CAPTURE_PASS',
        'exit_code': 0,
        'ledger': expected_end,
        'scope': '128_EDGE_PUBLIC_PORT_CONTROL_ONLY',
        'audio_math': 'NOT_RERUN',
        'T052_complete': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    static = sub.add_parser('static')
    static.add_argument('--manifest', required=True, type=Path)
    capture = sub.add_parser('capture')
    capture.add_argument('--manifest', required=True, type=Path)
    capture.add_argument('--plan', required=True, type=Path)
    capture.add_argument('--controls', required=True, type=Path)
    capture.add_argument('--observations', required=True, type=Path)
    capture.add_argument('--publications', required=True, type=Path)
    capture.add_argument('--resets', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.mode == 'static':
            result = validate_static(args.manifest)
        else:
            result = validate_capture(args.manifest, args.plan, args.controls,
                                      args.observations, args.publications, args.resets)
    except InsufficientEvidence as error:
        result = {'status': 'UNKNOWN', 'exit_code': 3, 'diagnostic': str(error),
                  'T052_complete': False}
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile) as error:
        result = {'status': 'FAIL', 'exit_code': 1, 'diagnostic': str(error),
                  'T052_complete': False}
    print(json.dumps(result, sort_keys=True))
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
