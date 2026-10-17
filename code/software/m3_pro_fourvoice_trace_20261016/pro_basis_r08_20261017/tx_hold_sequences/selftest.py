"""New T14 independent sequences; no imports/IO until run_case."""
import importlib.util
from pathlib import Path


def fixture():
    actions = [{'cycle': 1, 'kind': 'STARTUP'},
               {'cycle': 5, 'kind': 'COMMIT', 'req_id': 0, 'left': 256, 'right': 512, 'clip_mask': 1},
               {'cycle': 10, 'kind': 'NEW', 'req_id': 0}, {'cycle': 11, 'kind': 'CLOSE_TRANSACTION'},
               {'cycle': 20, 'kind': 'HOLD'}, {'cycle': 30, 'kind': 'HOLD'},
               {'cycle': 35, 'kind': 'COMMIT', 'req_id': 7, 'left': 256, 'right': 512, 'clip_mask': 1},
               {'cycle': 40, 'kind': 'NEW', 'req_id': 7}, {'cycle': 50, 'kind': 'HOLD'},
               {'cycle': 60, 'kind': 'RESET'}, {'cycle': 61, 'kind': 'STARTUP'}]
    expected = []
    for cycle, epoch, kind, rid in ((1, 0, 'STARTUP', None), (10, 0, 'NEW', 0), (20, 0, 'HOLD', 0),
                                     (30, 0, 'HOLD', 0), (40, 0, 'NEW', 7), (50, 0, 'HOLD', 7), (61, 1, 'STARTUP', None)):
        startup = kind == 'STARTUP'
        expected.append({'epoch': epoch, 'cycle': cycle, 'tx_sample_valid': 1,
                         'tx_req_id_valid': int(not startup), 'tx_metadata_valid': 1, 'tx_req_id': rid,
                         'tx_left': 0 if startup else 256, 'tx_right': 0 if startup else 512,
                         'tx_clip_mask': 0 if startup else 1, 'tx_clip': int(not startup),
                         'tx_hold': int(kind == 'HOLD'), 'tx_startup_zero': int(startup),
                         'metadata_error': 0, 'frame_id_overflow': 0})
    return {'plan': {'schema': 'M3_R08_INDEPENDENT_TX_SCENARIO_PLAN_V1',
                     'origin': 'SYNTHETIC_INDEPENDENT_PLAN', 'actions': actions}, 'observed': expected}


def run_case(case_id, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    p = Path(__file__).with_name('r08c14_sequences.py')
    s = importlib.util.spec_from_file_location('r08c14_test_engine', p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    c, data = m.shared(), fixture()
    expected = {'T14_INDEPENDENT_HELD': 'SCENARIO_MATCH_SYNTHETIC', 'T14_SAME_PCM_OTHER_ID': 'TX_SCENARIO_DIFFERENCE',
                'T14_HOLD_CLIP_CHANGE': 'TX_SCENARIO_DIFFERENCE', 'T14_STARTUP_ID0': 'TX_SCENARIO_DIFFERENCE',
                'T14_HOLD_AFTER_RESET': 'HOLD_AFTER_RESET_OR_STARTUP', 'T14_TRACE_DERIVED': 'SCENARIO_NOT_INDEPENDENT'}[case_id]
    if case_id == 'T14_SAME_PCM_OTHER_ID': data['observed'][2]['tx_req_id'] = 7
    if case_id == 'T14_HOLD_CLIP_CHANGE': data['observed'][2]['tx_clip_mask'] = 2
    if case_id == 'T14_STARTUP_ID0': data['observed'][0]['tx_req_id'] = 0
    if case_id == 'T14_HOLD_AFTER_RESET': data['plan']['actions'][-1]['kind'] = 'HOLD'
    if case_id == 'T14_TRACE_DERIVED': data['plan']['observed_rows'] = []
    c.save(Path(output_dir) / 'INPUT_BEFORE_CALL.json', data)
    actual = c.call(m.analyze, data)
    c.save(Path(output_dir) / 'ACTUAL_BEFORE_ASSERT.json', actual)
    if case_id == 'T14_INDEPENDENT_HELD':
        generated = actual['expected']['rows']
        assert [row['tx_req_id'] for row in generated] == [None, 0, 0, 0, 7, 7, None]
        assert sum(row['consumes_pending'] for row in generated) == 2
        assert actual['independent_requests_generated'] == 0
    return c.check_case(output_dir, data, actual, expected)
