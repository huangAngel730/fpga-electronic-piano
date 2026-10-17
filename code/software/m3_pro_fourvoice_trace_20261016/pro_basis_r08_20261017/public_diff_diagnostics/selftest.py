"""New diagnostic output tests using tiny B-format files, no old B tests."""
import importlib.util
from pathlib import Path


def fixture(c, directory, sample_bit=None, event_bit=None):
    directory.mkdir(parents=True, exist_ok=False)
    base = 1 << 4  # UART idle1, other twelve public bits0.
    lines = ['cycle,time_ps,rst_n,midi_rx,key_n,original,observer']
    for cycle in range(1, 6):
        observed = base ^ ((1 << sample_bit) if sample_bit is not None and cycle == 4 else 0)
        lines.append(f'{cycle},{12500+(cycle-1)*25000},1,1,11,{base:013b},{observed:013b}')
    (directory / 'trace.csv').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    events = ['time_ps,original,observer', f'37500,{base:013b},{base:013b}']
    if event_bit is not None:
        events.extend([f'40000,{base:013b},{base^(1<<event_bit):013b}', f'41000,{base:013b},{base:013b}'])
    events.append(f'112500,{base:013b},{base:013b}')
    (directory / 'events.csv').write_text('\n'.join(events) + '\n', encoding='utf-8', newline='\n')
    (directory / 'stdout.txt').write_text('EQUIV_END cycle=5\nEQUIV_EVENTS_END stop_ps=112500\n', encoding='utf-8', newline='\n')
    return {'schema': 'M3_R08_PUBLIC_DIFF_INPUT_V1', 'input_root': str(directory),
            'csv': 'trace.csv', 'events': 'events.csv', 'stdout': 'stdout.txt', 'start_cycle': 2, 'stop_cycle': 5,
            'allowed_differences': [], 'inputs_sha256': {k: c.identity(directory / n)['sha256']
                for k, n in (('csv', 'trace.csv'), ('events', 'events.csv'), ('stdout', 'stdout.txt'))},
            'source_identities': {'original': '1' * 64, 'observer': '2' * 64, 'origin': 'SYNTHETIC'}}


def run_case(case_id, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    p = Path(__file__).with_name('r08c18_diagnostics.py')
    s = importlib.util.spec_from_file_location('r08c18_test_engine', p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    c = m.shared()
    data = fixture(c, Path(output_dir) / 'input_files',
                   sample_bit=4 if case_id == 'T18_UART_DIFFERENCE' else (2 if case_id == 'T18_EARLIEST_EVENT' else None),
                   event_bit=2 if case_id in ('T18_EARLIEST_EVENT', 'T18_BETWEEN_SAMPLES') else None)
    expected = {'T18_EQUAL_NO_STAT': 'PENDING_NO_COMPLETE_STAT', 'T18_EARLIEST_EVENT': 'PUBLIC_DIFFERENCE_OR_CONTRACT',
                'T18_BETWEEN_SAMPLES': 'PUBLIC_DIFFERENCE_OR_CONTRACT', 'T18_UART_DIFFERENCE': 'PUBLIC_DIFFERENCE_OR_CONTRACT',
                'T18_WHITELIST_ATTEMPT': 'UNSUPPORTED_DIFFERENCE_WHITELIST', 'T18_REPLACED_EVENT_LOG': 'PUBLIC_DIFF_INPUT_SHA'}[case_id]
    if case_id == 'T18_WHITELIST_ATTEMPT': data['allowed_differences'] = [{'field': 'DIN', 'approved': True}]
    if case_id == 'T18_REPLACED_EVENT_LOG': data['inputs_sha256']['events'] = '0' * 64
    c.save(Path(output_dir) / 'INPUT_BEFORE_CALL.json', data)
    actual = c.call(m.analyze, data)
    c.save(Path(output_dir) / 'ACTUAL_BEFORE_ASSERT.json', actual)
    if case_id in ('T18_EARLIEST_EVENT', 'T18_BETWEEN_SAMPLES'):
        assert actual['first_difference']['time_ps'] == 40000
        assert actual['first_difference']['public_pins'] == ['DIN']
    if case_id == 'T18_UART_DIFFERENCE': assert actual['first_difference']['public_pins'] == ['UART_TX']
    if case_id == 'T18_EQUAL_NO_STAT': assert actual['original_observations'] == 'NOT_PUBLIC'
    return c.check_case(output_dir, data, actual, expected)
