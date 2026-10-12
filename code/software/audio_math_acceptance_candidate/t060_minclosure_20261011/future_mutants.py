"""Future complete capture mutations; no RTL/tool execution or oracle inputs."""
import argparse
import json
from pathlib import Path


KINDS = {
    'retirement_reuse_wrong_generation': ('generations', 1),
    'accepted_panic_missing_off': ('off', 0),
    'frame_accepts_old_result': ('commit', 1),
    'advance_rolled_back': ('dds_phase', 78741068),
}


def matches(kind, row):
    if row.get('tag') != 'EDGE':
        return False
    return {
        'retirement_reuse_wrong_generation': row.get('generations') == 2,
        'accepted_panic_missing_off': row.get('cycle', 0) > 4072400 and row.get('off') == 1,
        'frame_accepts_old_result': row.get('cycle') == 1033,
        'advance_rolled_back': row.get('cycle') == 725,
    }[kind]


def mutate(capture, output, kind):
    hits, records, last = 0, 0, None
    with Path(capture).open(encoding='utf-8') as source, Path(output).open('x', encoding='utf-8', newline='\n') as target:
        for line in source:
            row = json.loads(line)
            if not hits and matches(kind, row):
                field, value = KINDS[kind]
                if row[field] == value:
                    raise ValueError('MUTANT_WOULD_NOT_CHANGE_FIELD')
                row[field] = value
                hits += 1
                line = json.dumps(row) + '\n'
            target.write(line)
            records += 1
            last = row.get('tag')
    if hits != 1 or last != 'END':
        raise ValueError('MUTANT_NOT_COMPLETE_ONE_TARGET')
    return dict(kind=kind, changed_fields=1, records=records, complete_END=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--kind', choices=KINDS, required=True)
    args = parser.parse_args()
    print(json.dumps(mutate(args.capture, args.output, args.kind)))
