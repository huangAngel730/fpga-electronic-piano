"""Only the new between-edge event-stream coverage; no initial 15 rerun."""
import csv
import json
from pathlib import Path
import sys

from equivalence import Reject, compare_events


def main():
    out = Path(sys.argv[1])
    out.mkdir(exist_ok=False)
    results = []
    equal = format(16, '013b')
    cases = [('equal_between_edges', None, equal, equal),
             ('between_edge_pa_pulse', 'FIRST_EVENT_DIFF', equal, format(24, '013b')),
             ('between_edge_tmds_pulse', 'FIRST_EVENT_DIFF', equal, format(16 | 128, '013b')),
             ('between_edge_unknown', 'EVENT_UNKNOWN', equal, 'x' + equal[1:])]
    for name, expected, original, observer in cases:
        folder = out / name
        folder.mkdir()
        rows = [(87500, equal, equal), (95000, original, observer), (100000, equal, equal)]
        with (folder / 'events.csv').open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream, lineterminator='\n')
            writer.writerow(['time_ps', 'original', 'observer'])
            writer.writerows(rows)
        (folder / 'stdout.txt').write_text('EQUIV_EVENTS_END stop_ps=112500\n', encoding='utf-8')
        try:
            result = compare_events(folder / 'events.csv', folder / 'stdout.txt', 87500, 112500)
            actual = None
        except Reject as error:
            result, actual = error.detail, error.code
        results.append({'case': name, 'expected': expected, 'actual': actual, 'detail': result})
        assert actual == expected and (actual is None or result['time_ps'] == 95000)
    summary = {'passed': True, 'new_cases': results, 'old_15_reexecuted': False,
               'HDL_executed': False, 'board_release_allowed': False}
    (out / 'SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': True, 'new_cases': len(results), 'old_15_reexecuted': False}))


if __name__ == '__main__':
    main()
