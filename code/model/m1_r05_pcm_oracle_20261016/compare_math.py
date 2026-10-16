"""Exact comparison of normalized arithmetic rows, not an RTL trace parser.

M3 owns real capture, its completeness, and independently mapping the input
calendar. Synthetic positive equality exercises this comparison entrance only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys


KEYS = {'epoch', 'request_id', 'lane_pcm', 'generation', 'left', 'right', 'clipped'}


def pairs(rows):
    result = {}
    for key, value in rows:
        if key in result:
            raise ValueError('DUPLICATE_JSON_KEY:' + key)
        result[key] = value
    return result


def read(path):
    def bad_constant(value):
        raise ValueError('NONFINITE_NUMBER:' + value)
    rows = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs,
                      parse_constant=bad_constant)
    if type(rows) is not list or not rows:
        raise ValueError('NONEMPTY_MATH_ROWS_REQUIRED')
    seen = set()
    for row in rows:
        if type(row) is not dict or set(row) != KEYS:
            raise ValueError('MATH_FIELDS')
        if any(type(row[k]) is not int or not 0 <= row[k] <= 0xffffffff for k in ('epoch', 'request_id')):
            raise ValueError('MATH_ID_RANGE')
        key = row['epoch'], row['request_id']
        if key in seen:
            raise ValueError('DUPLICATE_MATH_ID')
        seen.add(key)
        for field in ('lane_pcm', 'generation', 'clipped'):
            count = 2 if field == 'clipped' else 4
            if type(row[field]) is not list or len(row[field]) != count:
                raise ValueError('MATH_VECTOR_SHAPE:' + field)
        if any(type(x) is not int or not -8388608 <= x <= 8388607 for x in row['lane_pcm'] + [row['left'], row['right']]):
            raise ValueError('MATH_PCM24_RANGE')
        if any(type(x) is not int or not 0 <= x <= 0xffffffff for x in row['generation']):
            raise ValueError('MATH_GENERATION_RANGE')
        if any(type(x) is not bool for x in row['clipped']):
            raise ValueError('MATH_CLIP_BOOL')
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected', type=Path, required=True)
    parser.add_argument('--actual', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = {'schema': 'M1_NORMALIZED_PCM_MATH_COMPARISON_V1',
              'scope': 'NUMERIC_ROW_EQUALITY_ONLY_NOT_CAPTURE_AUTHENTICATION',
              'actual_dut_result': 'PENDING_REAL_CAPTURE', 'accepted': False}
    try:
        expected, actual = read(args.expected), read(args.actual)
        if len(expected) != len(actual):
            raise ValueError('MATH_ROW_COUNT')
        for index, (wanted, got) in enumerate(zip(expected, actual)):
            for field in sorted(KEYS):
                if wanted[field] != got[field]:
                    report['first_difference'] = {'row': index, 'field': field,
                                                  'expected': wanted[field], 'actual': got[field]}
                    raise ValueError('MATH_MISMATCH')
        report.update(accepted=True, rows_compared=len(expected))
    except (ValueError, OSError, UnicodeError) as exc:
        report['failure'] = str(exc)
    report['inputs'] = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in (args.expected, args.actual) if p.is_file()}
    try:
        with args.output.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    except OSError as exc:
        print('COMPARISON_OUTPUT_NOT_WRITTEN:' + type(exc).__name__, file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['accepted'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
