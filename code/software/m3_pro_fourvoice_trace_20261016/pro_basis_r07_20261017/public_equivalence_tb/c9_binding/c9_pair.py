"""C9 static successor. No candidate imports, process launch or device API.

Assembly keeps old/new same-named M1 definitions in separate compilation
universes. Join only adapts raw paired captures to the existing B comparator.
No function is executed at import; all current cases remain NOT_RUN.
"""
import argparse
import csv
import hashlib
from itertools import zip_longest
import json
from pathlib import Path
import re

COMPANION_WIDTHS = {'rst_n': 1, 'polyphonic_valid': 1, 'apply_valid': 1, 'apply_kind': 4, 'apply_mask': 4,
                    'router_apply_seq_valid': 1, 'router_apply_seq': 32, 'apply_data': 64,
                    'advance_mask': 4, 'advance_frame_req_id': 32, 'config_valid': 1, 'config_ready': 1,
                    'config_take': 1, 'config_payload': 62, 'result_clip_mask': 2, 'effect_input_clip_mask': 2,
                    'upstream_clip_mask': 2, 'effect_clip_mask': 2, 'feedback_clip_mask': 2}


class BindingError(ValueError):
    pass


def need(value, reason):
    if not value:
        raise BindingError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def safe(base, relative):
    base = Path(base).resolve()
    target = (base / relative).resolve()
    need(target.is_relative_to(base) and target != base, 'PATH_ESCAPE')
    return target


def assemble(manifest_path, expected_sha, output):
    manifest_path, output = Path(manifest_path), Path(output)
    raw = manifest_path.read_bytes()
    need(sha(raw) == expected_sha, 'ASSEMBLY_BINDING_SHA')
    binding = json.loads(raw)
    need(binding['schema'] == 'M3_R7B_C9_SOURCE_BINDING_V1', 'BINDING_SCHEMA')
    need(binding['compile_universes_separate'] is True, 'FLAT_DUAL_FORBIDDEN')
    payloads = []
    for item in binding['staged_files']:
        source = safe(manifest_path.parent, item['stored_path'])
        body = source.read_bytes()
        need(len(body) == item['bytes'] and sha(body) == item['sha256'], 'STAGED_SOURCE_SHA')
        payloads.append((item, body))
    output.mkdir(parents=True, exist_ok=False)
    for item, body in payloads:
        target = safe(output, item['destination'])
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(body)
    result = {'schema': 'M3_R7B_C9_ASSEMBLY_REPORT_V1', 'status': 'STATIC_MATERIALIZED_NOT_COMPILED',
              'binding_sha256': expected_sha, 'lanes': binding['lanes'],
              'compile_universes_separate': True, 'HDL_executed': False, 'board_release_allowed': False}
    save(output / 'ASSEMBLY.json', result)
    return result


def rows(path, columns):
    with Path(path).open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        need(reader.fieldnames == columns, 'CSV_COLUMNS')
        for item in reader:
            need(None not in item and None not in item.values(), 'CSV_WIDTH')
            yield reader.line_num, item


def event_rows(path, anchor):
    previous, previous_pins, anchored = -1, None, False
    for line, item in rows(path, ['time_ps', 'pins']):
        need(re.fullmatch(r'0|[1-9][0-9]*', item['time_ps']), 'LANE_EVENT_TIME')
        at = int(item['time_ps'])
        pins = item['pins']
        need(at >= previous and re.fullmatch('[01xzXZ]{13}', pins), 'LANE_EVENT_FORMAT')
        need(at != previous or pins == previous_pins, 'EVENT_NOT_POSTPONED_STABLE')
        anchored |= at == anchor
        previous, previous_pins = at, pins
        yield at, pins
    need(anchored, 'MISSING_EVENT_ANCHOR')


def join_pair(data, output):
    """No comparison is signed here; resulting streams feed frozen B later."""
    base = Path(data['input_root'])
    identities = {}
    for role in ('input_plan', 'source_binding'):
        file = safe(base, data[role + '_path'])
        need(file_sha(file) == data[role + '_sha256'], 'PAIR_IDENTITY_SHA')
        identities[role] = file
    binding = json.loads(identities['source_binding'].read_text(encoding='utf-8'))
    need(binding.get('schema') == 'M3_R7B_C9_SOURCE_BINDING_V1'
         and binding.get('compile_universes_separate') is True, 'PAIR_BINDING_SCHEMA')
    for lane in ('original', 'observer'):
        plans = [item for item in binding['staged_files'] if item['destination'] == lane + '/plan.json']
        need(len(plans) == 1 and plans[0]['sha256'] == data['input_plan_sha256'], 'PAIR_PLAN_SOURCE_BINDING')
    paths = {}
    for lane in ('original', 'observer'):
        paths[lane] = {}
        for role in ('trace', 'events', 'stdout', 'receipt'):
            item = data[lane][role]
            file = safe(base, item['path'])
            need(file_sha(file) == item['sha256'], 'LANE_INPUT_SHA')
            paths[lane][role] = file
    columns = ['cycle', 'time_ps', 'rst_n', 'midi_rx', 'key_n', 'pins']
    traces = {lane: rows(p['trace'], columns) for lane, p in paths.items()}
    stop, start = data['stop_cycle'], data['start_cycle']
    need(type(start) is int and type(stop) is int and 1 <= start <= stop, 'WINDOW')
    expected_end_ps = 12500 + (stop - 1) * 25000
    for lane, p in paths.items():
        receipt = json.loads(p['receipt'].read_text(encoding='utf-8'))
        need(receipt.get('schema') == 'M3_R7B_C9_LANE_RECEIPT_V1' and receipt.get('exit_code') == 0
             and receipt.get('normal_exit') is True and receipt.get('timeout') is False, 'MISSING_NORMAL_EXIT_RECEIPT')
        for role in ('trace', 'events', 'stdout'):
            need(receipt.get(role + '_sha256') == data[lane][role]['sha256'], 'RECEIPT_STREAM_BINDING')
        need(receipt.get('input_plan_sha256') == data['input_plan_sha256']
             and receipt.get('source_binding_sha256') == data['source_binding_sha256'], 'RECEIPT_SOURCE_PLAN_BINDING')
        markers = re.findall(r'^LANE_END lane=(\w+) cycle=(\d+) time_ps=(\d+)$', p['stdout'].read_text(encoding='utf-8'), re.M)
        need(markers == [(lane, str(stop), str(expected_end_ps))], 'LANE_END_MARKER')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'combined.csv').open('x', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(columns[:-1] + ['original', 'observer'])
        count = 0
        for index, pair in enumerate(zip_longest(traces['original'], traces['observer']), 1):
            need(None not in pair and index <= stop, 'INCOMPLETE_LANE')
            (_, old), (_, new) = pair
            count = index
            need(old['cycle'] == new['cycle'] == str(index), 'LANE_CYCLE')
            need(old['time_ps'] == new['time_ps'] == str(12500 + (index - 1) * 25000), 'LANE_TIMEBASE')
            need(all(old[k] == new[k] for k in ('rst_n', 'midi_rx', 'key_n')), 'LANE_EXTERNAL_INPUT_DIFFERENCE')
            need(old['rst_n'] in ('0', '1') and old['midi_rx'] in ('0', '1') and old['key_n'] == '11', 'LANE_EXTERNAL_INPUT')
            need(all(re.fullmatch('[01xzXZ]{13}', row['pins']) for row in (old, new)), 'LANE_PIN_WIDTH')
            writer.writerow([old[k] for k in columns[:-1]] + [old['pins'], new['pins']])
        need(count == stop, 'INCOMPLETE_LANE')
    anchor = 12500 + (start - 1) * 25000
    events = {lane: iter(event_rows(p['events'], anchor)) for lane, p in paths.items()}
    heads = {lane: next(stream, None) for lane, stream in events.items()}
    current = {'original': None, 'observer': None}
    with (output / 'combined_events.csv').open('x', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['time_ps', 'original', 'observer'])
        while any(head is not None for head in heads.values()):
            at = min(head[0] for head in heads.values() if head is not None)
            for lane in current:
                while heads[lane] is not None and heads[lane][0] == at:
                    current[lane] = heads[lane][1]
                    heads[lane] = next(events[lane], None)
            if None in current.values():
                need(at < anchor, 'EVENT_INITIAL_STATE_MISSING')
                continue
            writer.writerow([at, current['original'], current['observer']])
    (output / 'combined_stdout.txt').write_text(f'EQUIV_END cycle={stop}\nEQUIV_EVENTS_END stop_ps={expected_end_ps}\n',
                                                encoding='utf-8', newline='\n')
    result = {'schema': 'M3_R7B_C9_JOIN_REPORT_V1', 'status': 'ADAPTED_PENDING_B_COMPARISON_AND_M2_AUTHORITY',
              'original_inputs': data, 'allowed_differences': [], 'original_obs': 'NOT_PUBLIC',
              'comparison_performed': False, 'real_equivalence_pass': False, 'board_release_allowed': False}
    save(output / 'JOIN_REPORT.json', result)
    return result


def companion_rows(data):
    """Lossless B diagnostics only; does not replace the unique A 74-field codec."""
    widths = COMPANION_WIDTHS
    need(data.get('widths') == widths, 'COMPANION_CONTRACT_WIDTHS')
    need(Path(data['csv']).stat().st_size <= 64 * 1024 * 1024, 'COMPANION_LIMIT_PENDING_STREAMING')
    need(file_sha(data['csv']) == data['sha256'], 'COMPANION_CAPTURE_SHA')
    parsed = []
    for source_line, raw in rows(data['csv'], ['cycle', 'time_ps'] + list(widths)):
        values, missing = {}, {}
        for field, width in widths.items():
            bits = raw[field]
            need(len(bits) == width and re.fullmatch('[01xzXZ]+', bits), 'COMPANION_BITS')
            values[field] = int(bits, 2) if set(bits) <= {'0', '1'} else None
            if values[field] is None: missing[field] = 'OBSERVED_XZ_RETAINED'
        active = values.get('rst_n') == values.get('polyphonic_valid') == values.get('apply_valid') == 1
        kind, valid = values.get('apply_kind'), values.get('router_apply_seq_valid')
        if active and kind in (3, 4, 8):
            need(valid in (0, None), 'INVALID_CAUSE_SENTINEL_VALID')
            need(values.get('router_apply_seq') in (0, None) and values.get('apply_data') in (0, None), 'INVALID_CAUSE_SENTINEL_DATA')
        parts = None
        if values.get('config_take') == 1 and values.get('config_payload') is not None:
            packed = values['config_payload']
            parts = {k: (packed >> low) & ((1 << width) - 1) for k, low, width in
                     (('enable', 61, 1), ('delay_samples', 45, 16), ('dry_gain', 30, 15), ('wet_gain', 15, 15), ('feedback', 0, 15))}
        parsed.append({'schema': 'M3_R7B_C9_DIAGNOSTIC_ROW_V1', 'source_line': source_line,
                       'cycle': int(raw['cycle']), 'time_ps': int(raw['time_ps']), 'epoch': None,
                       'original_csv_row': raw, 'fields': values, 'missing_reasons': missing,
                       'apply_active': active, 'cause_valid': active and valid == 1,
                       'independent_apply_event_seq': None, 'audio_stable': None, 'config_on_take': parts,
                       'pending': ['INDEPENDENT_PLAN_MAPPING', 'INDEPENDENT_RESET_EDGE_BINDING', 'AUDIO_STABLE_POLICY'],
                       'deduplicated': False})
    return {'schema': 'M3_R7B_C9_DIAGNOSTICS_V1', 'status': 'PENDING_A_CAPTURE_AND_INDEPENDENT_MAPPING',
            'rows': parsed, 'original_counterpart': 'NOT_PUBLIC', 'board_release_allowed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('assemble', 'join', 'companions'))
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--binding-sha')
    args = parser.parse_args()
    if args.action == 'assemble':
        result = assemble(args.input, args.binding_sha, args.output)
    elif args.action == 'join':
        result = join_pair(json.loads(args.input.read_text(encoding='utf-8')), args.output)
    else:
        result = companion_rows(json.loads(args.input.read_text(encoding='utf-8')))
        save(args.output, result)
    print(json.dumps({'status': result['status'], 'board_release_allowed': False}))
    return 3  # Preparation/diagnostic outputs never sign real equivalence.


if __name__ == '__main__':
    raise SystemExit(main())
