"""R08 T13 new cases; import has no I/O. Only coordinator calls run_case."""
import importlib.util
from pathlib import Path


def fixture(swapped=False, padding=False):
    # Independent literal serial words: prefix-left0, right -2, left +1.
    # 6/7 half-period synthetic protocol fixture, not a 48kHz frame oracle.
    toggles, at = {}, 0
    for index in range(193):
        at += 7 if index % 2 == 0 else 6
        toggles[at] = index
    stop = at + 1
    falling_after_31 = next(c for c, i in toggles.items() if i == 61)
    falling_after_95 = next(c for c, i in toggles.items() if i == 189)
    pulses = {falling_after_31 - 1: (1, 0), falling_after_95 - 1: (2, 1)}
    rows, bclk, ws, din, rises = [], 0, 1, 0, 0
    for cycle in range(stop + 1):
        if cycle in toggles:
            bclk ^= 1
            if bclk:
                rises += 1
            else:
                if rises % 32 == 0:
                    ws = 0 if (rises // 32) % 2 else 1
                offset = rises % 32
                block = rises // 32
                word = 0 if block == 0 else ((1 if swapped else 0xfffe) if block % 2 else (0xfffe if swapped else 1))
                din = 0 if offset < 16 else ((word >> (31 - offset)) & 1)
                if padding and block == 1 and offset == 0:
                    din = 1
        row = {'cycle': cycle, 'epoch': 0, 'source_line': 40000 + cycle, 'time_ps': cycle * 25000,
               'rst_n': int(cycle != 0), 'bclk': bclk, 'ws': ws if cycle else 0, 'din': din,
               'frame_tick': int(cycle in pulses), 'tx_sample_valid': int(cycle in pulses)}
        if cycle in pulses:
            frame, hold = pulses[cycle]
            row.update(tx_metadata_valid=1, tx_req_id_valid=1, tx_startup_zero=0, tx_hold=hold,
                       tx_left=256, tx_right=-512, tx_req_id=0, tx_frame_id=frame)
        rows.append(row)
    return {'schema': 'M3_R08_SERIAL_ALIGNMENT_INPUT_V1', 'origin': 'SYNTHETIC',
            'protocol': 'PT8211_32BIT_SLOT_LSBJ16_WS_LOW_RIGHT_HIGH_LEFT', 'clock_hz': 40000000,
            'sample_phase': 'SYS_POSEDGE_PRE_NBA', 'first_phase_known': True,
            'quantization': 'SATURATE((PCM24+128)//256)',
            'accepted_requests': [{'epoch': 0, 'req_id': 0, 'A_cycle': 1}], 'rows': rows}


def run_case(case_id, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    p = Path(__file__).parent
    s = importlib.util.spec_from_file_location('r08c13_test_engine', p / 'r08c13_serial.py')
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    c = m.shared()
    data = fixture(swapped=case_id == 'T13_CHANNEL_SWAP', padding=case_id == 'T13_PADDING_PHASE')
    expected = {'T13_WORD_ALIGNMENT': 'UNKNOWN_SERIAL_PARTIAL', 'T13_CHANNEL_SWAP': 'PIN_SERIAL_PCM_OR_CHANNEL_MISMATCH',
                'T13_PADDING_PHASE': 'PIN_LSBJ_PADDING_OR_PHASE', 'T13_RESET_HALF': 'UNKNOWN_SERIAL_PARTIAL',
                'T13_FIRST_PHASE': 'UNKNOWN_SERIAL_FIRST_PHASE', 'T13_OTHER_PROTOCOL': 'PENDING_UNSUPPORTED_SERIAL_PROTOCOL',
                'T13_VALID_X': 'PENDING_TX_SAMPLE', 'T13_VALID_2': 'TX_SAMPLE_VALID_RANGE',
                'T13_FRAME_SAMPLE0': 'PENDING_TX_SAMPLE'}[case_id]
    if case_id == 'T13_RESET_HALF':
        data['rows'] = data['rows'][:801]
        data['rows'][-1].update(rst_n=0, bclk=0, ws=0, din=0)
    if case_id == 'T13_FIRST_PHASE':
        data['first_phase_known'] = False
    if case_id == 'T13_OTHER_PROTOCOL':
        data['protocol'] = 'I2S_ONE_BIT_DELAY_NOT_THIS_CONTRACT'
    if case_id == 'T13_VALID_X': data['rows'][100]['tx_sample_valid'] = 'x'
    if case_id == 'T13_VALID_2': data['rows'][100]['tx_sample_valid'] = 2
    if case_id == 'T13_FRAME_SAMPLE0':
        row = next(row for row in data['rows'] if row['frame_tick'])
        row['tx_sample_valid'] = 0
    c.save(Path(output_dir) / 'INPUT_BEFORE_CALL.json', data)
    actual = c.call(m.analyze, data)
    c.save(Path(output_dir) / 'ACTUAL_BEFORE_ASSERT.json', actual)
    if case_id == 'T13_WORD_ALIGNMENT':
        assert len(actual['complete_frames']) == 1
        frame = actual['complete_frames'][0]
        assert (frame['left'], frame['right'], frame['request_id']) == (1, -2, 0)
        assert actual['unknown'] == ['SERIAL_TAIL_INCOMPLETE']
    if case_id in ('T13_CHANNEL_SWAP', 'T13_PADDING_PHASE'):
        assert actual['first_difference']['first_bit_cycle'] is not None
    if case_id == 'T13_RESET_HALF':
        assert 'RESET_TRUNCATED_HALF_OR_FRAME' in actual['unknown']
    return c.check_case(output_dir, data, actual, expected)
