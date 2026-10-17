"""New T15 state lineage cases, no DSP arithmetic or private observations."""
import importlib.util
from pathlib import Path


def fixture():
    rows = []
    def row(cycle, **values):
        value = {'cycle': cycle, 'epoch': 0, 'source_line': 7000 + cycle, 'rst_n': 1,
                 'metadata_error': 0, 'frame_id_overflow': 0, **values}
        rows.append(value)
        return value
    def tx(rid=0, mask=1, hold=0):
        return {'valid': 1, 'metadata_valid': 1, 'id_valid': 1, 'req_id': rid, 'startup': 0,
                'hold': hold, 'left': 256, 'right': 512, 'clip_mask': mask, 'clip_any': 1}
    row(0, rst_n=0)
    row(1, tx={'valid': 1, 'metadata_valid': 1, 'id_valid': 0, 'req_id': None, 'startup': 1,
               'hold': 0, 'left': 0, 'right': 0, 'clip_mask': 0, 'clip_any': 0})
    row(10, result={'valid': 1, 'ready': 1, 'req_id': 0, 'left': 256, 'right': 512, 'clip_mask': 1})
    row(11, commit={'valid': 1, 'req_id': 0, 'left': 256, 'right': 512, 'clip_any': 1})
    row(20, tx=tx())
    row(21, tx=tx(hold=1))
    row(30, result={'valid': 1, 'ready': 1, 'req_id': 7, 'left': 256, 'right': 512, 'clip_mask': 2})
    row(31, commit={'valid': 1, 'req_id': 7, 'left': 256, 'right': 512, 'clip_any': 1})
    row(40, tx=tx(7, 2))
    row(41, tx=tx(7, 2, 1))
    return {'schema': 'M3_R08_CLIP_LINEAGE_INPUT_V1', 'origin': 'SYNTHETIC', 'rows': rows}


def run_case(case_id, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    p = Path(__file__).with_name('r08c15_lineage.py')
    s = importlib.util.spec_from_file_location('r08c15_test_engine', p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    c, data = m.shared(), fixture()
    expected = {'T15_RESULT_PENDING_HELD': 'LINEAGE_MATCH_SYNTHETIC_ONLY', 'T15_CLIP_SAME_OR': 'TX_LINEAGE_DIFFERENCE',
                'T15_METADATA_INVALID': 'PENDING_TX_METADATA', 'T15_OVERFLOW': 'PENDING_FRAME_ID_OVERFLOW',
                'T15_RESULT_MASK_MISSING': 'PENDING_RESULT_FIELDS', 'T15_SAME_EDGE_COMMIT_TX': 'COMMIT_NOT_BEFORE_ADOPTION',
                'T15_RESET_INVALIDATES_HELD': 'HOLD_WITHOUT_HELD', 'T15_SAME_PCM_OTHER_ID': 'TX_LINEAGE_DIFFERENCE',
                'T15_VALID_X': 'PENDING_OBSERVATION_VALIDITY', 'T15_VALID_2': 'OBSERVATION_FLAG_RANGE',
                'T15_RESULT_READY_X': 'PENDING_OBSERVATION_VALIDITY', 'T15_COMMIT_VALID_2': 'OBSERVATION_FLAG_RANGE',
                'T15_STARTUP_2': 'TX_LINEAGE_FLAG_RANGE', 'T15_HOLD_2': 'TX_LINEAGE_FLAG_RANGE',
                'T15_METADATA_VALID_2': 'TX_LINEAGE_FLAG_RANGE', 'T15_ID_VALID_2': 'TX_LINEAGE_FLAG_RANGE',
                'T15_CLIP_ANY_2': 'TX_LINEAGE_FLAG_RANGE', 'T15_METADATA_ERROR_X': 'PENDING_METADATA_FIELDS',
                'T15_OVERFLOW_2': 'LINEAGE_METADATA_FLAG_RANGE', 'T15_BOOL_FLAG': 'OBSERVATION_FLAG_RANGE'}[case_id]
    if case_id == 'T15_CLIP_SAME_OR': data['rows'][5]['tx']['clip_mask'] = 2
    if case_id == 'T15_METADATA_INVALID': data['rows'][4]['tx']['metadata_valid'] = 0
    if case_id == 'T15_OVERFLOW': data['rows'][8]['frame_id_overflow'] = 1
    if case_id == 'T15_RESULT_MASK_MISSING': data['rows'][2]['result']['clip_mask'] = None
    if case_id == 'T15_SAME_EDGE_COMMIT_TX':
        data['rows'][7]['tx'] = data['rows'][8]['tx']
        data['rows'].pop(8)
    if case_id == 'T15_RESET_INVALIDATES_HELD': data['rows'][4]['rst_n'] = 0
    if case_id == 'T15_SAME_PCM_OTHER_ID': data['rows'][5]['tx']['req_id'] = 7
    if case_id == 'T15_VALID_X': data['rows'][4]['tx']['valid'] = 'x'
    if case_id == 'T15_VALID_2': data['rows'][4]['tx']['valid'] = 2
    if case_id == 'T15_RESULT_READY_X': data['rows'][2]['result']['ready'] = 'x'
    if case_id == 'T15_COMMIT_VALID_2': data['rows'][3]['commit']['valid'] = 2
    if case_id == 'T15_STARTUP_2': data['rows'][1]['tx']['startup'] = 2
    if case_id == 'T15_HOLD_2': data['rows'][5]['tx']['hold'] = 2
    if case_id == 'T15_METADATA_VALID_2': data['rows'][4]['tx']['metadata_valid'] = 2
    if case_id == 'T15_ID_VALID_2': data['rows'][4]['tx']['id_valid'] = 2
    if case_id == 'T15_CLIP_ANY_2': data['rows'][5]['tx']['clip_any'] = 2
    if case_id == 'T15_METADATA_ERROR_X': data['rows'][4]['metadata_error'] = 'x'
    if case_id == 'T15_OVERFLOW_2': data['rows'][4]['frame_id_overflow'] = 2
    if case_id == 'T15_BOOL_FLAG': data['rows'][4]['tx']['valid'] = True
    c.save(Path(output_dir) / 'INPUT_BEFORE_CALL.json', data)
    actual = c.call(m.analyze, data)
    c.save(Path(output_dir) / 'ACTUAL_BEFORE_ASSERT.json', actual)
    if case_id == 'T15_RESULT_PENDING_HELD':
        held = [r for r in actual['ledger'] if r['kind'] == 'PENDING_TO_HELD']
        assert [(r['req_id'], r['clip_mask'], r['tx_clip']) for r in held] == [(0, 1, 1), (7, 2, 1)]
        assert held[0]['result_line'] == 7010 and held[0]['commit_line'] == 7011
        assert actual['derived_states_not_private_observations'] is True
    return c.check_case(output_dir, data, actual, expected)
