"""Render the frozen 128-edge JSONL input plan into the thin-TB memory image."""
import argparse
import hashlib
import json
from pathlib import Path


PLAN_SHA256 = 'b2d0cb1ba0bf3cd4b2d636f3d4cb7ac286558238ae2b52c3e9e43ba54ee5ef02'


def identity(path):
    raw = Path(path).read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def read_plan(path):
    path = Path(path)
    if identity(path)['sha256'] != PLAN_SHA256:
        raise ValueError('PLAN_SHA256')
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    if len(rows) != 130 or rows[0].get('type') != 'META' or rows[-1] != {
            'last_cycle': 127, 'type': 'END'}:
        raise ValueError('PLAN_WINDOW')
    return rows[1:-1]


def pack(row):
    fields = [
        (row['rst_n'], 1), (row['frame'], 1), (row['cancel'], 1),
        (row['sample_req'], 1), (row['req_id'], 32), (row['enable'], 1),
        (row['mask'], 4), *[(value, 32) for value in row['fcw']],
        (row['result_ready'], 1),
    ]
    value = 0
    width = 0
    for item, bits in fields:
        if type(item) is not int or not 0 <= item < (1 << bits):
            raise ValueError('PLAN_FIELD_RANGE')
        value = (value << bits) | item
        width += bits
    if width != 170:
        raise AssertionError('CONTROL_WIDTH')
    return f'{value:043x}'


def render(plan):
    rows = read_plan(plan)
    if [row['cycle'] for row in rows] != list(range(128)):
        raise ValueError('PLAN_CYCLE_GAP')
    return ''.join(pack(row) + '\n' for row in rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('OUTPUT_EXISTS')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(args.plan), encoding='ascii', newline='\n')
    print(json.dumps(identity(args.output), sort_keys=True))


if __name__ == '__main__':
    main()
