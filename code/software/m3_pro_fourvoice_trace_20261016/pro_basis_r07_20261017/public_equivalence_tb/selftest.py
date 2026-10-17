"""New R7-B synthetic checks and static assembly, not previous R06 tests."""
import copy
import csv
import json
from pathlib import Path
import sys

from assembly import assemble
from equivalence import FIELDS, Reject, UART, compare, stat_records


def main():
    out = Path(sys.argv[1])
    out.mkdir(exist_ok=False)
    receipts = []

    def case(name, expected, function):
        try:
            result = function()
            actual = None
        except Reject as error:
            result, actual = error.detail, error.code
        receipts.append({'case': name, 'expected': expected, 'actual': actual, 'result': result})
        (out / 'CASES.json').write_text(json.dumps(receipts, indent=2) + '\n', encoding='utf-8')
        assert actual == expected, (name, expected, actual)

    rows = [{'cycle': str(i), 'time_ps': str(12500 + (i - 1) * 25000),
             'rst_n': '1', 'midi_rx': '1', 'key_n': '11',
             'original': format(16, '013b'), 'observer': format(16, '013b')}
            for i in range(1, 25)]

    def run_csv(name, mutate=None, marker='EQUIV_END cycle=24\n'):
        folder = out / name
        folder.mkdir()
        selected = copy.deepcopy(rows)
        if mutate:
            mutate(selected)
        with (folder / 'raw.csv').open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(selected)
        (folder / 'stdout.txt').write_text(marker, encoding='utf-8')
        result = compare(folder / 'raw.csv', folder / 'stdout.txt', start=3, stop=24)
        assert result['status'] == 'PENDING_NO_COMPLETE_STAT'
        return result

    case('same_external_pins_no_stat_is_pending', None, lambda: run_csv('equal'))
    case('pin_first_difference', 'FIRST_OUTPUT_DIFF', lambda: run_csv('pin_diff', lambda r: r[11].update(observer=format(17, '013b'))))
    case('unknown_after_window', 'UNKNOWN_OUTPUT', lambda: run_csv('unknown', lambda r: r[4].update(observer='x' * 13)))
    case('cycle_gap', 'CYCLE', lambda: run_csv('gap', lambda r: r.pop(5)))
    case('wrong_timebase', 'TIME', lambda: run_csv('time', lambda r: r[5].update(time_ps='0')))
    case('wrong_external_input', 'EXTERNAL_INPUT', lambda: run_csv('input', lambda r: r[7].update(key_n='00')))
    case('incomplete_window', 'WINDOW_INCOMPLETE', lambda: run_csv('tail', lambda r: r.pop()))
    case('missing_end', 'END_MARKER', lambda: run_csv('end', marker=''))
    case('duplicate_end', 'END_MARKER', lambda: run_csv('dup_end', marker='EQUIV_END cycle=24\n' * 2))

    def uart_stat():
        line = ('STAT ' + ' '.join(f'{field}=0x00000000' for field in FIELDS) + '\r\n').encode('ascii')
        decoder = UART()
        cycle = 0
        for value in line:
            for bit in [0] + [(value >> i) & 1 for i in range(8)] + [1]:
                for _ in range(347):
                    decoder.feed(cycle, bit)
                    cycle += 1
        records = stat_records(decoder.bytes)
        assert len(records) == 1 and set(records[0]) == set(FIELDS)
        return {'decoded_bytes': len(decoder.bytes), 'reports': records, 'profile': 'SYNTHETIC_40M_115200_FLOOR347'}

    case('actual_uart_8n1_stat_parser', None, uart_stat)
    case('stat_bad_format', 'STAT_FORMAT', lambda: stat_records(b'DIAG bad\r\n'))

    def bad_stop():
        decoder = UART(3)
        for cycle in range(31):
            decoder.feed(cycle, 0)
    case('uart_stop_error', 'UART_STOP', bad_stop)

    def reset_truncation():
        decoder = UART(3)
        for cycle in range(9):
            decoder.feed(cycle, 0)
        decoder.feed(9, 0, rst_n=0)
        assert decoder.start is None and not decoder.bytes
        return {'partial_byte': 'RESET_TRUNCATED_NOT_A_STAT'}
    case('reset_truncates_partial_uart', None, reset_truncation)
    case('real_frozen_assembly_requires_dds_decision', None, lambda: assemble(out / 'assembly'))
    case('source_archive_swap', 'ARCHIVE_SHA', lambda: assemble(out / 'wrong_archive', '0' * 64))
    summary = {'passed': True, 'cases': len(receipts), 'HDL_calls': 0,
               'level': 'L1_NEW_SOFTWARE_FIXTURE_ONLY_TB_L0_UNCOMPILED',
               'real_equivalence_pass': False, 'board_release_allowed': False}
    (out / 'SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
