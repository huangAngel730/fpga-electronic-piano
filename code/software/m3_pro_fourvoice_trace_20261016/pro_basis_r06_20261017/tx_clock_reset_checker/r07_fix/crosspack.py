"""Lossless views of actual R7-A / R6-5 contracts; no producer imports."""
import copy
import json

import serial_core as core
from boundaries import need

A_SCHEMA = 'M3_R7A_PUBLIC_ROW_V1'
CAL_SCHEMA = 'M3_R65_R07_CALENDAR_REPORT_V1'


def load_rows(path, profile, preservation):
    if profile != A_SCHEMA:
        return core.load_trace(path, profile)
    originals = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    preservation['r7a_rows'] = originals
    return adapt_rows(originals)


def known(value, label):
    if type(value) is not int:
        raise core.Pending('PENDING_UNSUPPORTED_PROFILE', label + ': unknown/null retained')
    return value


def adapt_rows(originals):
    need(bool(originals), 'EMPTY_TRACE')
    result, identity = [], None
    for index, original in enumerate(originals, 1):
        if original.get('schema') != A_SCHEMA:
            raise core.Pending('PENDING_UNSUPPORTED_PROFILE', 'R7-A schema')
        source, fields, ext = [original.get(k) for k in ('source', 'fields', 'extensions')]
        if not all(type(v) is dict for v in (source, fields, ext)):
            raise core.Reject('R7A_ROW_OBJECTS')
        if set(fields) != set(core.CANONICAL_FIELDS) or ext.get('schema') != 'M3_R7A_TX_EXTENSION_V1':
            raise core.Pending('PENDING_UNSUPPORTED_PROFILE', 'Unknown canonical/extension contract')
        need(source.get('sampling_phase') == 'POSEDGE_PRE_NBA', 'R7A_SAMPLING_PHASE')
        need(source.get('line') == index and source.get('cycle') == index - 1, 'R7A_ORIGINAL_COORDINATES')
        for name in ('cycle', 'epoch'):
            known(source.get(name), 'source.' + name)
            need(source[name] == fields[name], 'R7A_COORDINATE_MISMATCH', name)
        current = tuple(original.get(k) for k in ('capture_id', 'origin')) + tuple(source.get(k) for k in ('raw_sha256', 'reset_edges_sha256'))
        if identity is None:
            identity = current
        need(current == identity, 'R7A_CAPTURE_CHANGED')
        if original.get('origin') != 'SYNTHETIC_SCHEMA_FIXTURE':
            raise core.Pending('PENDING_SOURCE_PROVENANCE', 'HDL public origin requires trusted M2 admission')
        row = copy.deepcopy(fields)
        row.update(time_ps=known(source.get('time_ps'), 'source.time_ps'),
                   source_line=source['line'], __line=index, __capture_id=original.get('capture_id'))
        for name in ('rst_n', 'frame_tick', 'req_valid', 'req_ready', 'result_valid', 'result_ready', 'commit', 'tx_sample_valid', 'finish'):
            need(known(row[name], name) in (0, 1), 'R7A_FLAG', name)
        flags = {'FRAME_F': row['frame_tick'], 'ACCEPT_A': row['req_valid'] and row['req_ready'],
                 'RESULT_TRANSFER': row['result_valid'] and row['result_ready'],
                 'COMMIT': row['commit'], 'TX_ADOPT': row['tx_sample_valid']}
        expected = [name for name, value in flags.items() if row['rst_n'] and value]
        if row['finish']:
            expected.append('FINISH')
        need(type(original.get('events')) is list and original['events'] == expected, 'R7A_EVENT_FLAGS')
        # TX_ADOPT is the label for EVERY active TX sample, including STARTUP
        # and HOLD. Classification uses the explicit validity/startup/hold bits.
        for dest, src in {'tx_req_id_valid': 'obs_tx_req_id_valid', 'tx_metadata_valid': 'obs_tx_metadata_valid',
                          'tx_clip_mask': 'obs_tx_clip_mask', 'metadata_error': 'obs_metadata_error',
                          'frame_id_overflow': 'obs_frame_id_overflow'}.items():
            row[dest] = known(ext.get(src), 'extensions.' + src)
        row['tx_clip_any'] = row['tx_clip']
        result.append(row)
    return result


def adapt_calendar(calendar, rows):
    if calendar.get('schema') != CAL_SCHEMA:
        return calendar, []
    # The native report is an observed ledger, NOT an independent TX selection
    # oracle. Never synthesize an authoritative selection plan from tx_samples.
    pending = set(calendar.get('pending_reasons', []))
    pending.add('PENDING_TX_SELECTION_PLAN')
    need(all(row.get('__capture_id') == calendar.get('capture_id') for row in rows), 'R65_CAPTURE_ID')
    by_cycle = {row['cycle']: row for row in rows}
    if calendar.get('raw_frame_cancels') or calendar.get('business_cancels'):
        pending.add('PENDING_TRANSACTION_CANCEL_RULE')
    transactions = []
    for original in calendar.get('transactions', []):
        item = {'epoch': original.get('epoch'), 'req_id': original.get('req_id')}
        for dst, src in {'frame': 'F', 'first_valid': 'first_valid', 'accept': 'A',
                         'result': 'result', 'commit': 'commit', 'cancel': 'cancel'}.items():
            link = original.get(src)
            if link is None:
                item[dst + '_cycle'] = item[dst + '_source_line'] = None
            elif type(link) is dict and {'cycle', 'source_line'} <= set(link):
                item[dst + '_cycle'], item[dst + '_source_line'] = link['cycle'], link['source_line']
            else:
                raise core.Pending('PENDING_UNSUPPORTED_PROFILE', 'Unknown R6-5 link:' + src)
        for name in ('frame', 'first_valid', 'accept'):
            if item[name + '_cycle'] is None:
                raise core.Pending('PENDING_FA_LINK', name)
        if item['commit_cycle'] is None and item['cancel_cycle'] is None:
            raise core.Pending('PENDING_TRANSACTION_DISPOSITION')
        adoption = original.get('tx_adoption')
        if adoption is not None:
            if type(adoption) is not dict or not {'cycle', 'source_line'} <= set(adoption):
                raise core.Pending('PENDING_UNSUPPORTED_PROFILE', 'Unknown TX adoption link')
            row = by_cycle.get(adoption['cycle'])
            need(row is not None and row['source_line'] == adoption['source_line'], 'R65_TX_SOURCE_LINK')
            need(row['rst_n'] == row['tx_sample_valid'] == row['tx_req_id_valid'] == 1
                 and row['tx_startup_zero'] == row['tx_hold'] == 0 and row['tx_req_id'] == item['req_id']
                 and row['epoch'] == item['epoch'], 'R65_ADOPTION_FLAGS')
        transactions.append(item)
    observed = []
    for row in rows:
        if row['rst_n'] and row['tx_sample_valid']:
            kind = 'STARTUP' if row['tx_startup_zero'] else ('HOLD' if row['tx_hold'] else 'ADOPTION')
            observed.append({'kind': kind, 'epoch': row['epoch'], 'cycle': row['cycle'], 'source_line': row['source_line'],
                             'req_id': row['tx_req_id'], 'consumes_pending': kind == 'ADOPTION'})
    samples = calendar.get('tx_samples')
    if not isinstance(samples, list):
        raise core.Pending('PENDING_UNSUPPORTED_PROFILE', 'Missing observed TX samples')
    need([{key: item.get(key) for key in record} for item, record in zip(samples, observed)] == observed
         and len(samples) == len(observed), 'R65_OBSERVED_TX_LEDGER')
    return {'schema': 'M3_R07_FA_TRANSACTION_CALENDAR_V1',
            'authority': 'OBSERVED_R65_REPORT_NOT_AUTHORITY', 'independent_of_trace': False,
            'canonical_plan_id': calendar.get('frame_plan_id'), 'transactions': transactions,
            'native_observed_only': True}, sorted(pending)
