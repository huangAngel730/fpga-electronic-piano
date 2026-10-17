"""External-pin/8N1 STAT checker; never authenticates a producer or runs HDL."""
import argparse
import csv
import json
from pathlib import Path
import re

FIELDS = ('active_voice_count clip_count event_fifo_level event_fifo_high_watermark '
          'event_fifo_overflow audio_underrun max_processing_cycles').split()
STAT = re.compile('STAT ' + ' '.join(k + r'=0x([0-9A-Fa-f]{8})' for k in FIELDS) + r'\r\n')


class Reject(ValueError):
    def __init__(self, code, **detail):
        self.code, self.detail = code, detail
        super().__init__(code)


def need(ok, code, **detail):
    if not ok:
        raise Reject(code, **detail)


class UART:
    def __init__(self, bit_cycles=347):
        self.period = bit_cycles
        self.start = None
        self.previous = 1
        self.value = 0
        self.bit = 0
        self.bytes = bytearray()
        self.segments = []

    def feed(self, cycle, level, rst_n=1):
        if not rst_n:
            if self.bytes:
                self.segments.append(bytes(self.bytes))
                self.bytes.clear()
            self.start, self.previous = None, 1
            return
        if self.start is None:
            if self.previous == 1 and level == 0:
                self.start, self.bit, self.value = cycle, -1, 0
        else:
            target = self.start + self.period // 2 + (self.bit + 1) * self.period
            if cycle == target:
                if self.bit == -1:
                    need(level == 0, 'UART_FALSE_START', cycle=cycle)
                elif self.bit < 8:
                    self.value |= level << self.bit
                else:
                    need(level == 1, 'UART_STOP', cycle=cycle)
                    self.bytes.append(self.value)
                    self.start = None
                self.bit += 1
        self.previous = level


def stat_records(data):
    try:
        text = bytes(data).decode('ascii')
    except UnicodeError as exc:
        raise Reject('UART_NON_ASCII') from exc
    lines = text.splitlines(keepends=True)
    records = []
    for line in lines:
        if not line.endswith('\n'):
            break  # Retained incomplete tail is not a complete STAT report.
        match = STAT.fullmatch(line)
        need(match is not None, 'STAT_FORMAT', line=line)
        records.append(dict(zip(FIELDS, (int(v, 16) for v in match.groups()))))
    return records


def compare(csv_path, stdout_path, start=1200, stop=12000000):
    need(type(start) is int and 1 <= start <= stop, 'WINDOW')
    raw = Path(stdout_path).read_text(encoding='utf-8')
    need(re.findall(r'^EQUIV_END cycle=(\d+)$', raw, re.M) == [str(stop)], 'END_MARKER')
    decoders = [UART(), UART()]
    count = 0
    with Path(csv_path).open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        need(reader.fieldnames == ['cycle', 'time_ps', 'rst_n', 'midi_rx', 'key_n', 'original', 'observer'], 'COLUMNS')
        for row in reader:
            count += 1
            need(set(row) == set(reader.fieldnames) and None not in row.values(), 'ROW_WIDTH')
            need(row['cycle'] == str(count) and count <= stop, 'CYCLE', line=reader.line_num)
            need(row['time_ps'] == str(12500 + (count - 1) * 25000), 'TIME', cycle=count)
            need(row['rst_n'] in ('0', '1') and row['midi_rx'] in ('0', '1') and row['key_n'] == '11', 'EXTERNAL_INPUT', cycle=count)
            values = [row[k] for k in ('original', 'observer')]
            need(all(re.fullmatch('[01xzXZ]{13}', v) for v in values), 'PIN_WIDTH', cycle=count)
            if count >= start:
                need(all(set(v) <= {'0', '1'} for v in values), 'UNKNOWN_OUTPUT', cycle=count)
                need(values[0] == values[1], 'FIRST_OUTPUT_DIFF', cycle=count,
                     original=values[0], observer=values[1], csv_line=reader.line_num)
            for decoder, value in zip(decoders, values):
                if set(value) <= {'0', '1'}:
                    decoder.feed(count, int(value[-5]), int(row['rst_n']))
                else:
                    decoder.feed(count, 1, 0)
    need(count == stop, 'WINDOW_INCOMPLETE', actual=count, expected=stop)
    segments = [d.segments + [bytes(d.bytes)] for d in decoders]
    records = [[record for segment in parts for record in stat_records(segment)] for parts in segments]
    need(records[0] == records[1], 'STAT_DIFF')
    need((segments[0], decoders[0].start) == (segments[1], decoders[1].start), 'UART_TAIL_DIFF')
    return {'status': 'EXTERNAL_PINS_EQUAL_STAT_PRESENT' if records[0] else 'PENDING_NO_COMPLETE_STAT',
            'cycles': count, 'stat_reports': len(records[0]), 'stat': records[0],
            'uart_tail_incomplete': decoders[0].start is not None,
            'uart_segments_hex': [segment.hex() for segment in segments[0]],
            'old_obs_fields': 'NOT_PUBLIC', 'real_equivalence_pass': False,
            'pin_coverage': '40MHZ_SAMPLES_ONLY_EVENT_STREAM_REQUIRED',
            'producer_authenticity': 'UNKNOWN', 'board_release_allowed': False}


def compare_events(path, stdout_path, start_ps=29987500, stop_ps=299999987500):
    text = Path(stdout_path).read_text(encoding='utf-8')
    need(re.findall(r'^EQUIV_EVENTS_END stop_ps=(\d+)$', text, re.M) == [str(stop_ps)], 'EVENT_END')
    previous_time, previous_values, anchored, count = -1, None, False, 0
    with Path(path).open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        need(reader.fieldnames == ['time_ps', 'original', 'observer'], 'EVENT_COLUMNS')
        for row in reader:
            need(None not in row and None not in row.values(), 'EVENT_ROW_WIDTH')
            need(re.fullmatch(r'0|[1-9][0-9]*', row['time_ps']) is not None, 'EVENT_TIME')
            time_ps = int(row['time_ps'])
            values = row['original'], row['observer']
            need(time_ps >= previous_time, 'EVENT_TIME_ORDER')
            need(all(re.fullmatch('[01xzXZ]{13}', v) for v in values), 'EVENT_PIN_WIDTH')
            if time_ps == previous_time:
                need(values == previous_values, 'EVENT_NOT_POSTPONED_STABLE', time_ps=time_ps)
            previous_time, previous_values = time_ps, values
            anchored |= time_ps == start_ps
            if start_ps <= time_ps <= stop_ps:
                need(all(set(v) <= {'0', '1'} for v in values), 'EVENT_UNKNOWN', time_ps=time_ps, csv_line=reader.line_num)
                need(values[0] == values[1], 'FIRST_EVENT_DIFF', time_ps=time_ps,
                     original=values[0], observer=values[1], csv_line=reader.line_num)
                count += 1
    need(anchored and count > 0, 'EVENT_WINDOW_START_MISSING')
    return {'status': 'PUBLIC_POSTPONED_EVENTS_EQUAL', 'checked_rows': count,
            'window_ps': [start_ps, stop_ps], 'region': 'POSTPONED_SAME_TIMESTAMP_COALESCED',
            'scope': 'STABLE_SIMULATION_TIMESTAMPS_NOT_DELTA_GLITCH_OR_PHYSICAL_PROOF'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', required=True)
    ap.add_argument('--stdout', required=True)
    ap.add_argument('--events', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    try:
        result, code = compare(args.csv, args.stdout), 0
        result['events'] = compare_events(args.events, args.stdout)
    except (Reject, OSError) as error:
        result, code = {'status': 'REJECT', 'first_difference': str(error),
                        'detail': getattr(error, 'detail', {})}, 1
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
