"""Bounded-memory B19 companion conversion; never produces canonical A/FRAME.

Each output retains the exact CSV input line, raw X/Z, physical line number
and stage. No candidate import or input I/O occurs at module import.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
from types import ModuleType

ROOT = Path(__file__).resolve().parents[6]
SOFT = ROOT / 'code/software/m3_pro_fourvoice_trace_20261016'
COMMON = SOFT / 'pro_basis_r08_20261017/coordinator/task_day4_completion_20261017/common.py'
COMMON_SHA = '55cb7481fe9c0870247a7d8b2453dea859f0f2e81879795cc0e34ffe8c996dca'
OLD = Path(__file__).resolve().parents[1] / 'c9_binding/c9_pair.py'
OLD_SHA = 'e4a11031826dbac28422f1973e23dc274185d8bcd80ec031faebf98656a38f13'
_COMMON = None


def shared():
    global _COMMON
    raw = COMMON.read_bytes()
    if hashlib.sha256(raw).hexdigest() != COMMON_SHA:
        raise ValueError('COMMON_SOURCE_SHA')
    if _COMMON is None:
        module = ModuleType('_c9_companion_completion_common')
        module.__file__ = str(COMMON)
        exec(compile(raw, str(COMMON), 'exec', dont_inherit=True), module.__dict__)
        _COMMON = module
    return _COMMON


def convert_files(csv_path, output_dir, max_input_bytes=16 * 1024**3,
                  max_output_bytes=64 * 1024**3, max_line_bytes=4096):
    c = shared()
    source = c.checked_descriptor(csv_path, allow_external=True) if isinstance(csv_path, dict) else c.no_alias(csv_path)
    before = c.artifact(source)
    c.require(type(max_input_bytes) is int and 0 < max_input_bytes <= 16 * 1024**3,
              'COMPANION_INPUT_BUDGET')
    c.require(type(max_output_bytes) is int and 0 < max_output_bytes <= 64 * 1024**3,
              'COMPANION_OUTPUT_BUDGET')
    c.require(type(max_line_bytes) is int and 128 <= max_line_bytes <= 65536,
              'COMPANION_LINE_BUDGET')
    c.require(before['bytes'] <= max_input_bytes, 'COMPANION_INPUT_BOUND')
    old = c.load_source(OLD, OLD_SHA)
    widths = old.COMPANION_WIDTHS
    header = ['cycle', 'time_ps'] + list(widths)
    out = c.output_directory(output_dir)
    c.write_json(out / 'INPUTS.json', {'csv': before, 'old_field_contract': c.artifact(OLD),
                                      'input_bound': max_input_bytes, 'output_bound': max_output_bytes,
                                      'line_bound': max_line_bytes})
    target = out / 'DIAGNOSTIC_ROWS.jsonl'
    digest, input_bytes, output_bytes, count = hashlib.sha256(), 0, 0, 0
    unknown_rows = 0
    first = last = previous = None
    try:
        with source.open('rb') as stream, target.open('xb') as output:
            line_number = 0
            while True:
                raw = stream.readline(max_line_bytes + 1)
                if not raw:
                    break
                line_number += 1
                c.require(len(raw) <= max_line_bytes, 'COMPANION_LINE_BOUND')
                input_bytes += len(raw)
                c.require(input_bytes <= max_input_bytes, 'COMPANION_INPUT_BOUND')
                digest.update(raw)
                c.require(raw.endswith(b'\n'), 'COMPANION_TRUNCATED_LINE')
                text = raw.decode('utf-8')
                columns = next(csv.reader([text], strict=True))
                if line_number == 1:
                    c.require(columns == header, 'COMPANION_COLUMNS')
                    continue
                c.require(len(columns) == len(header), 'COMPANION_CSV_WIDTH')
                original = dict(zip(header, columns))
                for key in ('cycle', 'time_ps'):
                    c.require(re.fullmatch(r'0|[1-9][0-9]*', original[key]) is not None,
                              'COMPANION_COORDINATE:' + key)
                cycle, at = int(original['cycle']), int(original['time_ps'])
                if previous is not None:
                    c.require(cycle == previous[0] + 1 and at == previous[1] + 25000,
                              'COMPANION_TIME_GAP')
                previous = cycle, at
                values, missing = {}, {}
                for key, width in widths.items():
                    bits = original[key]
                    c.require(len(bits) == width and re.fullmatch('[01xXzZ]+', bits),
                              'COMPANION_BITS:' + key)
                    if set(bits) <= {'0', '1'}:
                        values[key] = int(bits, 2)
                    else:
                        values[key] = None
                        missing[key] = 'OBSERVED_XZ_RETAINED'
                if missing:
                    unknown_rows += 1
                active = all(values[key] == 1 for key in ('rst_n', 'polyphonic_valid', 'apply_valid'))
                kind, valid = values['apply_kind'], values['router_apply_seq_valid']
                cause = 'INACTIVE_RAW_HELD_VALUES_UNINTERPRETED'
                if active and kind != 0:
                    cause = 'UNKNOWN_CAUSE'
                    if kind in (3, 4, 8):
                        c.require(valid in (0, None), 'INVALID_CAUSE_SENTINEL_VALID')
                        c.require(values['router_apply_seq'] in (0, None) and
                                  values['apply_data'] in (0, None), 'INVALID_CAUSE_SENTINEL_DATA')
                        cause = 'INVALID_CAUSE_SENTINEL_NOT_AN_INPUT_EVENT'
                    elif valid == 1:
                        cause = 'ROUTER_CAUSE_ONLY_INDEPENDENT_PLAN_MAPPING_PENDING'
                config = None
                if values['config_take'] == 1 and values['config_payload'] is not None:
                    payload = values['config_payload']
                    config = {key: (payload >> low) & ((1 << width) - 1)
                              for key, low, width in [('enable', 61, 1), ('delay_samples', 45, 16),
                                                      ('dry_gain', 30, 15), ('wet_gain', 15, 15),
                                                      ('feedback', 0, 15)]}
                row = {'schema': 'M3_R7B_C9_DIAGNOSTIC_STREAM_ROW_V1',
                       'source_line': line_number, 'cycle': cycle, 'time_ps': at,
                       'input_sha256': before['sha256'], 'raw_csv_line': text,
                       'fields': values, 'missing_reasons': missing, 'apply_cause': cause,
                       'config_on_actual_take': config, 'epoch': None,
                       'independent_apply_event_seq': None, 'audio_stable': None,
                       'stage_deduplicated': False}
                encoded = (json.dumps(row, separators=(',', ':'), ensure_ascii=False,
                                      allow_nan=False) + '\n').encode('utf-8')
                output_bytes += len(encoded)
                c.require(output_bytes <= max_output_bytes, 'COMPANION_OUTPUT_BOUND')
                output.write(encoded)
                count += 1
                coordinate = {'source_line': line_number, 'cycle': cycle, 'time_ps': at}
                first = first or coordinate
                last = coordinate
        c.require(count > 0, 'EMPTY_COMPANION_CAPTURE')
        c.require({'bytes': input_bytes, 'sha256': digest.hexdigest()} ==
                  {key: before[key] for key in ('bytes', 'sha256')}, 'COMPANION_READ_IDENTITY')
        c.require(c.artifact(source) == before, 'COMPANION_CHANGED_AFTER_READ')
        result = {'schema': 'M3_R7B_C9_DIAGNOSTIC_STREAM_REPORT_V1',
                  'status': 'STREAM_CONVERTED_INDEPENDENT_MAPPING_PENDING',
                  'input': before, 'input_bytes': input_bytes, 'output_bytes': output_bytes,
                  'rows': count, 'unknown_rows': unknown_rows, 'first': first, 'last': last,
                  'columns': header, 'input_above_64MiB': input_bytes > 64 * 1024**2,
                  'read_after_identity_equal': True, 'max_line_bytes': max_line_bytes,
                  'input_bound': max_input_bytes, 'output_bound': max_output_bytes,
                  'canonical74_produced': False, 'FRAME_PLAN_produced': False,
                  'pending': ['A_CANONICAL_CAPTURE', 'INDEPENDENT_PLAN_MAPPING',
                              'INDEPENDENT_RESET_EDGE_BINDING', 'AUDIO_STABLE_POLICY'],
                  'artifacts': {'diagnostic_rows': c.artifact(target)},
                  'real_pass': False, 'board_release_allowed': False}
        c.write_json(out / 'REPORT.json', result)
        result['artifacts']['report'] = c.artifact(out / 'REPORT.json')
        return result
    except Exception as error:
        c.write_json(out / 'FAILURE.json', {'status': 'REJECT', 'reason': str(error),
                                          'input': before, 'rows_written': count,
                                          'partial_outputs_retained': True,
                                          'real_pass': False, 'board_release_allowed': False})
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--max-input-bytes', type=int, default=16 * 1024**3)
    parser.add_argument('--max-output-bytes', type=int, default=64 * 1024**3)
    args = parser.parse_args()
    result = convert_files(args.csv, args.output, args.max_input_bytes, args.max_output_bytes)
    print(json.dumps({'status': result['status'], 'rows': result['rows'], 'real_pass': False}))
    return 3


if __name__ == '__main__':
    raise SystemExit(main())
