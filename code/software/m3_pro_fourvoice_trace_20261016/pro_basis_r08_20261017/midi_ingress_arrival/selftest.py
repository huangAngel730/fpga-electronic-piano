"""New external-edge arrival fixtures; no old MIDI event tests invoked."""
import importlib.util
from pathlib import Path


def fixture(bad_stop=False):
    values = [0x90, 60, 64, 0x91, 64, 80, 0x92, 67, 96, 0x93, 72, 112]
    edges, plan, previous = [], [], 1
    for index, value in enumerate(values):
        start = 100 + index * 14000
        bits = [0] + [(value >> bit) & 1 for bit in range(8)] + [0 if bad_stop and index == 0 else 1, 1]
        for bit, level in enumerate(bits):
            if level != previous:
                edges.append({'cycle': start + bit * 1280, 'level': level, 'source_line': len(edges) + 100})
                previous = level
        plan.append({'byte_seq': index, 'value': value, 'start_min_cycle': start - 2,
                     'start_max_cycle': start + 2, 'event_seq': index // 3})
    return {'schema': 'M3_R08_MIDI_ARRIVAL_INPUT_V1', 'origin': 'SYNTHETIC', 'clock_hz': 40000000, 'baud': 31250,
            'capture': {'timebase_known': True, 'initial_level': 1, 'start_cycle': 0,
                        'finish_cycle': 100 + 11 * 14000 + 14000, 'edges': edges, 'resets': []}, 'byte_plan': plan}


def run_case(case_id, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    p = Path(__file__).with_name('r08c16_arrival.py')
    s = importlib.util.spec_from_file_location('r08c16_test_engine', p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    c, data = m.shared(), fixture(bad_stop=case_id == 'T16_STOP_BIT')
    expected = {'T16_FOUR_SERIAL_NOTES': 'MIDI_ARRIVALS_MATCH_SYNTHETIC_ONLY', 'T16_WRONG_BYTE': 'MIDI_BYTE_DIFFERENCE',
                'T16_FIRST_BYTE_WINDOW': 'MIDI_ARRIVAL_WINDOW', 'T16_STOP_BIT': 'MIDI_STOP_BIT',
                'T16_TRUNCATION': 'UNKNOWN_MIDI_TRUNCATED_BYTE', 'T16_RESET_TRUNCATION': 'UNKNOWN_MIDI_RESET_TRUNCATED',
                'T16_UNKNOWN_TIMEBASE': 'UNKNOWN_MIDI_TIMEBASE', 'T16_DRV_PLAN_INPUT': 'MIDI_ARRIVALS_MATCH_SYNTHETIC_ONLY',
                'T16_DRV_PLAN_SHA': 'R62_BYTE_PLAN_SHA'}[case_id]
    if case_id == 'T16_WRONG_BYTE': data['byte_plan'][0]['value'] = 0x80
    if case_id == 'T16_FIRST_BYTE_WINDOW': data['byte_plan'][0]['start_max_cycle'] = 99
    if case_id == 'T16_TRUNCATION':
        data['capture']['finish_cycle'] = 10000
        data['capture']['edges'] = [edge for edge in data['capture']['edges'] if edge['cycle'] <= 10000]
    if case_id == 'T16_RESET_TRUNCATION': data['capture']['resets'] = [{'cycle': 5000, 'rst_n': 0, 'source_line': 900}]
    if case_id == 'T16_UNKNOWN_TIMEBASE': data['capture']['timebase_known'] = False
    if case_id in ('T16_DRV_PLAN_INPUT', 'T16_DRV_PLAN_SHA'):
        file = Path(output_dir) / 'new_fixture_bytes.drv'
        file.write_text(''.join(f"{item['start_min_cycle']+2} {item['value']:02x} {i+1}\n"
                                for i, item in enumerate(data.pop('byte_plan'))), encoding='utf-8', newline='\n')
        data.update(input_root=str(output_dir), r62_byte_plan=file.name,
                    r62_byte_plan_sha256=c.identity(file)['sha256'])
        if case_id == 'T16_DRV_PLAN_SHA': data['r62_byte_plan_sha256'] = '0' * 64
    c.save(Path(output_dir) / 'INPUT_BEFORE_CALL.json', data)
    actual = c.call(m.analyze, data)
    c.save(Path(output_dir) / 'ACTUAL_BEFORE_ASSERT.json', actual)
    if case_id == 'T16_FOUR_SERIAL_NOTES':
        arrivals = [item['arrival_cycle'] for item in actual['decoded'] if item['byte_seq'] in (2, 5, 8, 11)]
        assert len(arrivals) == len(set(arrivals)) == 4 and arrivals == sorted(arrivals)
        assert actual['bit_cycles'] == 1280 and all(item['application_cycle'] is None for item in actual['decoded'])
    if case_id == 'T16_DRV_PLAN_INPUT':
        assert [r['byte_seq'] for r in actual['decoded']] == list(range(1, 13))
        assert [r['plan_source_line'] for r in actual['decoded']] == list(range(1, 13))
    return c.check_case(output_dir, data, actual, expected)
