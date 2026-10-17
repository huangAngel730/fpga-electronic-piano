"""Result->commit->pending->held->TX provenance; no DSP golden arithmetic."""
import importlib.util
from pathlib import Path


def shared():
    p = Path(__file__).resolve().parents[1] / 'i2s_serial_compare/r08c_common.py'
    s = importlib.util.spec_from_file_location('r08c15_common', p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def analyze(data):
    c = shared()
    c.need(data.get('schema') == 'M3_R08_CLIP_LINEAGE_INPUT_V1', 'LINEAGE_SCHEMA')
    returned, pending, held, ledger = {}, None, None, []
    prior, epoch = -1, None
    for row in data['rows']:
        if row.get('schema') == 'M3_R7A_PUBLIC_ROW_V1':
            raw = c.public_view(row)
            row = {**{k: raw[k] for k in ('cycle', 'epoch', 'source_line', 'rst_n', 'metadata_error', 'frame_id_overflow')},
                   'result': {'valid': raw['result_valid'], 'ready': raw['result_ready'], 'req_id': raw['result_id'],
                              'left': raw['result_left'], 'right': raw['result_right'], 'clip_mask': raw['result_clip_mask']},
                   'commit': {'valid': raw['commit'], 'req_id': raw['commit_id'], 'left': raw['commit_left'],
                              'right': raw['commit_right'], 'clip_any': raw['commit_clip']},
                   'tx': {'valid': raw['tx_sample_valid'], 'metadata_valid': raw['tx_metadata_valid'],
                          'id_valid': raw['tx_req_id_valid'], 'req_id': raw['tx_req_id'], 'startup': raw['tx_startup_zero'],
                          'hold': raw['tx_hold'], 'left': raw['tx_left'], 'right': raw['tx_right'],
                          'clip_mask': raw['tx_clip_mask'], 'clip_any': raw['tx_clip']}}
        cycle, line, now_epoch = row['cycle'], row['source_line'], row['epoch']
        c.need(type(cycle) is int and cycle > prior and type(line) is int and line > 0, 'LINEAGE_COORDINATE')
        prior = cycle
        if row.get('rst_n') is None or isinstance(row.get('rst_n'), str) or now_epoch is None:
            return c.report('PENDING_RESET_VALIDITY', ledger=ledger, original_rows=data['rows'])
        c.need(type(row['rst_n']) is int and row['rst_n'] in (0, 1), 'LINEAGE_RESET_FLAG_RANGE')
        if row['rst_n'] == 0:
            returned, pending, held = {}, None, None
            epoch = now_epoch
            ledger.append({'cycle': cycle, 'source_line': line, 'kind': 'RESET_CLEAR'})
            continue
        c.need(epoch is None or epoch == now_epoch, 'EPOCH_CHANGE_WITHOUT_RESET')
        epoch = now_epoch
        if any(value is not None and any(value.get(k) is None or (isinstance(value.get(k), str)
                                          and any(char in value[k].lower() for char in ('x', 'z'))) for k in keys)
               for value, keys in ((row.get('result'), ('valid', 'ready')), (row.get('commit'), ('valid',)),
                                   (row.get('tx'), ('valid',)))):
            return c.report('PENDING_OBSERVATION_VALIDITY', original_rows=data['rows'], source_line=line, ledger=ledger)
        for value, keys in ((row.get('result'), ('valid', 'ready')), (row.get('commit'), ('valid',)), (row.get('tx'), ('valid',))):
            if value is not None:
                c.need(all(type(value[k]) is int and value[k] in (0, 1) for k in keys), 'OBSERVATION_FLAG_RANGE')
        for field in ('metadata_error', 'frame_id_overflow'):
            if row.get(field) is None or isinstance(row.get(field), str):
                return c.report('PENDING_METADATA_FIELDS', ledger=ledger, original_rows=data['rows'])
            c.need(type(row[field]) is int and row[field] in (0, 1), 'LINEAGE_METADATA_FLAG_RANGE', field=field)
        c.need(row['metadata_error'] == 0, 'METADATA_ERROR', source_line=line)
        if row['frame_id_overflow']:
            return c.report('PENDING_FRAME_ID_OVERFLOW', ledger=ledger, source_line=line)
        result = row.get('result')
        if result and result.get('valid') == result.get('ready') == 1:
            if any(result.get(k) is None for k in ('req_id', 'left', 'right', 'clip_mask')):
                return c.report('PENDING_RESULT_FIELDS', source_line=line, ledger=ledger)
            c.need(type(result['clip_mask']) is int and result['clip_mask'] in range(4), 'RESULT_CLIP')
            c.need(type(result['req_id']) is int and 0 <= result['req_id'] <= 0xffffffff, 'RESULT_REQUEST_ID')
            c.need(all(type(result[k]) is int and -(1 << 23) <= result[k] < (1 << 23) for k in ('left', 'right')), 'RESULT_PCM24')
            key = epoch, result['req_id']
            c.need(key not in returned, 'DUPLICATE_RESULT_ID')
            returned[key] = {**result, 'result_line': line, 'result_cycle': cycle}
        commit = row.get('commit')
        if commit and commit.get('valid') == 1:
            if any(commit.get(k) is None for k in ('req_id', 'left', 'right', 'clip_any')):
                return c.report('PENDING_COMMIT_METADATA', source_line=line, ledger=ledger)
            c.need(type(commit['clip_any']) is int and commit['clip_any'] in (0, 1), 'COMMIT_CLIP_FLAG_RANGE')
            c.need(type(commit['req_id']) is int and 0 <= commit['req_id'] <= 0xffffffff, 'COMMIT_REQUEST_ID')
            key = epoch, commit.get('req_id')
            c.need(key in returned, 'COMMIT_WITHOUT_RESULT', source_line=line)
            value = returned.pop(key)
            c.need(pending is None, 'PENDING_OVERWRITE', source_line=line)
            c.need(all(commit.get(k) == value[k] for k in ('left', 'right')), 'COMMIT_PCM')
            if commit.get('clip_mask') is not None:
                c.need(commit['clip_mask'] == value['clip_mask'], 'COMMIT_DUAL_CLIP')
            c.need(commit.get('clip_any') == int(bool(value['clip_mask'])), 'COMMIT_CLIP_OR')
            pending = {**value, 'commit_cycle': cycle, 'commit_line': line}
            ledger.append({'kind': 'RESULT_TO_PENDING', 'req_id': key[1], 'result_line': value['result_line'],
                           'commit_line': line, 'clip_mask': value['clip_mask'],
                           'mask_origin': 'RESULT_HANDSHAKE; NOT_CLAIMED_PRIVATE_PENDING_OBSERVATION'})
        tx = row.get('tx')
        if not tx or tx.get('valid') != 1:
            continue
        fields = ('metadata_valid', 'id_valid', 'startup', 'hold', 'left', 'right', 'clip_mask', 'clip_any')
        if any(tx.get(k) is None or isinstance(tx.get(k), str) for k in fields):
            return c.report('PENDING_TX_METADATA', source_line=line, ledger=ledger)
        c.need(all(type(tx[k]) is int and tx[k] in (0, 1) for k in ('metadata_valid', 'id_valid', 'startup', 'hold', 'clip_any')),
               'TX_LINEAGE_FLAG_RANGE', source_line=line)
        if tx['metadata_valid'] != 1:
            return c.report('PENDING_TX_METADATA', source_line=line, ledger=ledger)
        c.need(type(tx['clip_mask']) is int and tx['clip_mask'] in range(4)
               and tx['clip_any'] == int(bool(tx['clip_mask'])), 'TX_CLIP_OR')
        if tx['startup']:
            c.need(tx['id_valid'] == 0 and tx.get('req_id') is None and not tx['hold']
                   and tx['left'] == tx['right'] == tx['clip_mask'] == 0 and held is None, 'STARTUP_ID_DATA')
            ledger.append({'kind': 'STARTUP_NO_REQUEST', 'tx_line': line})
            continue
        c.need(tx['id_valid'] == 1 and type(tx.get('req_id')) is int, 'TX_ID_VALIDITY')
        value = held if tx['hold'] else pending
        c.need(value is not None, 'HOLD_WITHOUT_HELD' if tx['hold'] else 'TX_WITHOUT_PENDING', source_line=line)
        c.need(value['commit_cycle'] < cycle, 'COMMIT_NOT_BEFORE_ADOPTION', source_line=line)
        for k in ('req_id', 'left', 'right', 'clip_mask'):
            c.need(tx[k] == value[k], 'TX_LINEAGE_DIFFERENCE', field=k, source_line=line,
                   expected=value[k], actual=tx[k])
        ledger.append({'kind': 'HOLD' if tx['hold'] else 'PENDING_TO_HELD', 'tx_line': line,
                       'req_id': tx['req_id'], 'clip_mask': tx['clip_mask'], 'tx_clip': tx['clip_any'],
                       'result_line': value['result_line'], 'commit_line': value['commit_line']})
        if not tx['hold']:
            held, pending = pending, None
    return c.report('LINEAGE_MATCH_SYNTHETIC_ONLY' if data.get('origin') == 'SYNTHETIC' else 'PENDING_REAL_LINEAGE_ADMISSION',
                    ledger=ledger, derived_states_not_private_observations=True,
                    unfinished_pending=pending is not None, original_rows=data['rows'])


if __name__ == '__main__':
    raise SystemExit(shared().cli(analyze))
