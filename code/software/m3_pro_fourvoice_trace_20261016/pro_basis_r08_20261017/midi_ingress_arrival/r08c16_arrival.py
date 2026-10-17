"""External MIDI edge 8N1 decoder and plan-arrival index. No parser simulation."""
from bisect import bisect_right
import importlib.util
from pathlib import Path


def shared():
    p = Path(__file__).resolve().parents[1] / 'i2s_serial_compare/r08c_common.py'
    s = importlib.util.spec_from_file_location('r08c16_common', p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def analyze(data):
    c = shared()
    c.need(data.get('schema') == 'M3_R08_MIDI_ARRIVAL_INPUT_V1', 'MIDI_ARRIVAL_SCHEMA')
    c.need(data.get('clock_hz') == 40000000 and data.get('baud') == 31250, 'MIDI_FROZEN_RATE')
    capture = data['capture']
    if capture.get('timebase_known') is not True:
        return c.report('UNKNOWN_MIDI_TIMEBASE')
    edges = capture['edges']
    start, finish = capture['start_cycle'], capture['finish_cycle']
    c.need(type(start) is int and type(finish) is int and 0 <= start < finish, 'MIDI_COVERAGE')
    c.need(capture.get('initial_level') == 1, 'MIDI_INITIAL_IDLE')
    times, levels, previous = [], [], start - 1
    for edge in edges:
        c.need(type(edge['cycle']) is int and previous < edge['cycle'] <= finish and edge['cycle'] >= start,
               'MIDI_EDGE_ORDER')
        c.need(edge['level'] in (0, 1) and type(edge['level']) is int, 'MIDI_UNKNOWN_EDGE')
        c.need(edge['level'] != (levels[-1] if levels else 1), 'MIDI_EDGE_NOT_CHANGE')
        c.need(type(edge['source_line']) is int and edge['source_line'] > 0, 'MIDI_SOURCE_LINE')
        times.append(edge['cycle']); levels.append(edge['level']); previous = edge['cycle']

    def level(at):
        index = bisect_right(times, at) - 1
        return levels[index] if index >= 0 else 1

    decoded, cursor = [], start
    for edge in edges:
        at = edge['cycle']
        if at < cursor or edge['level'] != 0:
            continue
        end = at + 12800
        if end > finish:
            return c.report('UNKNOWN_MIDI_TRUNCATED_BYTE', decoded=decoded, first_partial=edge)
        resets = [e for e in capture.get('resets', []) if at <= e['cycle'] < end and e['rst_n'] == 0]
        if resets:
            return c.report('UNKNOWN_MIDI_RESET_TRUNCATED', decoded=decoded, first_partial=edge, reset=resets[0])
        c.need(level(at + 640) == 0, 'MIDI_FALSE_START', source_line=edge['source_line'])
        value = sum(level(at + 640 + 1280 * (bit + 1)) << bit for bit in range(8))
        c.need(level(at + 12160) == 1, 'MIDI_STOP_BIT', source_line=edge['source_line'])
        decoded.append({'byte_seq': len(decoded), 'value': value, 'start_cycle': at,
                        'arrival_cycle': end, 'start_source_line': edge['source_line'],
                        'bit_centers': [at + 640 + 1280 * k for k in range(10)]})
        cursor = end
    plan = data.get('byte_plan')
    if plan is None and data.get('r62_byte_plan'):
        source = c.bounded_file(data['input_root'], data['r62_byte_plan'])
        c.need(c.identity(source)['sha256'] == data['r62_byte_plan_sha256'], 'R62_BYTE_PLAN_SHA')
        plan = []
        for number, text in enumerate(source.read_text(encoding='utf-8').splitlines(), 1):
            fields = text.split()
            c.need(len(fields) == 3, 'R62_BYTE_PLAN_COLUMNS', source_line=number)
            at, value, seq = int(fields[0]), int(fields[1], 16), int(fields[2])
            plan.append({'ordinal0': len(plan), 'byte_seq': seq, 'value': value,
                         'start_min_cycle': at, 'start_max_cycle': at, 'plan_source_line': number,
                         'event_seq': data.get('event_seq_by_byte_seq', {}).get(str(seq))})
    c.need(type(plan) is list, 'MISSING_BYTE_PLAN')
    c.need(len(plan) == len(decoded), 'MIDI_BYTE_COUNT', planned=len(plan), observed=len(decoded))
    for ordinal, (expected, actual) in enumerate(zip(plan, decoded)):
        c.need(expected['byte_seq'] == plan[0]['byte_seq'] + ordinal and expected['value'] == actual['value'],
               'MIDI_BYTE_DIFFERENCE', original=actual, planned=expected)
        c.need(expected['start_min_cycle'] <= actual['start_cycle'] <= expected['start_max_cycle'],
               'MIDI_ARRIVAL_WINDOW', original=actual, planned=expected)
        actual['event_seq'] = expected.get('event_seq')
        actual['ordinal0'], actual['byte_seq'] = ordinal, expected['byte_seq']
        actual['plan_source_line'] = expected.get('plan_source_line')
        actual['application_cycle'] = None
    return c.report('MIDI_ARRIVALS_MATCH_SYNTHETIC_ONLY' if data.get('origin') == 'SYNTHETIC' else 'PENDING_REAL_MIDI_PROVENANCE',
                    decoded=decoded, bit_cycles=1280, frame_cycles=12800,
                    event_seq_origin='PLAN_METADATA_NOT_OBSERVED_APPLICATION', original_edges=edges,
                    audio_rate_used=False)


if __name__ == '__main__':
    raise SystemExit(shared().cli(analyze))
