"""Independent explicit TX selection scenarios, not a FRAME_PLAN producer."""
import copy
import importlib.util
from pathlib import Path


def shared():
    p = Path(__file__).resolve().parents[1] / 'i2s_serial_compare/r08c_common.py'
    s = importlib.util.spec_from_file_location('r08c14_common', p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def generate(data):
    c = shared()
    c.need(data.get('schema') == 'M3_R08_INDEPENDENT_TX_SCENARIO_PLAN_V1', 'SCENARIO_SCHEMA')
    c.need(data.get('origin') == 'SYNTHETIC_INDEPENDENT_PLAN' and 'observed_rows' not in data, 'SCENARIO_NOT_INDEPENDENT')
    pending, held, rows, history = {}, None, [], []
    prior, epoch = -1, 0
    for index, event in enumerate(data['actions'], 1):
        cycle = event['cycle']
        c.need(type(cycle) is int and cycle > prior, 'ACTION_ORDER')
        prior = cycle
        kind = event['kind']
        if kind == 'RESET':
            pending, held, epoch = {}, None, epoch + 1
            history.append({'source_action': index, 'cycle': cycle, 'kind': 'RESET_INVALIDATES_PENDING_HELD'})
            continue
        if kind == 'COMMIT':
            rid = event['req_id']
            c.need(type(rid) is int and 0 <= rid <= 0xffffffff and rid not in pending, 'PLAN_ID')
            c.need(type(event['clip_mask']) is int and event['clip_mask'] in range(4), 'PLAN_CLIP')
            pending[rid] = {k: event[k] for k in ('req_id', 'left', 'right', 'clip_mask')}
            pending[rid]['commit_cycle'] = cycle
            continue
        if kind == 'CLOSE_TRANSACTION':
            history.append({'cycle': cycle, 'source_action': index, 'kind': 'TRANSACTION_CLOSED_HELD_RETAINED'})
            continue
        c.need(kind in ('STARTUP', 'NEW', 'HOLD'), 'ACTION_KIND')
        if kind == 'STARTUP':
            c.need(held is None and not pending, 'STARTUP_AFTER_AUDIO')
            value = {'req_id': None, 'left': 0, 'right': 0, 'clip_mask': 0}
        elif kind == 'NEW':
            rid = event['req_id']
            c.need(rid in pending, 'NO_INDEPENDENT_COMMIT')
            held = pending.pop(rid)
            c.need(held['commit_cycle'] < cycle, 'COMMIT_NOT_BEFORE_TX')
            value = held
        else:
            c.need(held is not None, 'HOLD_AFTER_RESET_OR_STARTUP')
            value = held
        rows.append({'epoch': epoch, 'cycle': cycle, 'source_action': index,
                     'tx_sample_valid': 1, 'tx_req_id_valid': int(kind != 'STARTUP'),
                     'tx_metadata_valid': 1, 'tx_req_id': value['req_id'],
                     'tx_left': value['left'], 'tx_right': value['right'],
                     'tx_clip_mask': value['clip_mask'], 'tx_clip': int(bool(value['clip_mask'])),
                     'tx_hold': int(kind == 'HOLD'), 'tx_startup_zero': int(kind == 'STARTUP'),
                     'metadata_error': 0, 'frame_id_overflow': 0,
                     'consumes_pending': kind == 'NEW', 'kind': kind})
    return c.report('SCENARIO_GENERATED_SYNTHETIC', schema='M3_R08_TX_SCENARIO_V1', rows=rows,
                    history=history, FRAME_PLAN_generated=False,
                    join_contract='TX SIDECAR SCENARIO ONLY; join by original epoch/cycle to full public capture; missing fields remain null')


def analyze(data):
    c = shared()
    generated = generate(data['plan'])
    observed = data.get('observed')
    if observed is None:
        return generated
    c.need(len(observed) == len(generated['rows']), 'TX_SCENARIO_LENGTH')
    for index, (actual, expected) in enumerate(zip(observed, generated['rows']), 1):
        for key, value in expected.items():
            if key not in ('source_action', 'kind', 'consumes_pending'):
                c.need(key in actual and actual[key] == value, 'TX_SCENARIO_DIFFERENCE',
                       row=index, field=key, expected=value, actual=actual.get(key))
    return c.report('SCENARIO_MATCH_SYNTHETIC', expected=generated, independent_requests_generated=0)


if __name__ == '__main__':
    raise SystemExit(shared().cli(analyze))
