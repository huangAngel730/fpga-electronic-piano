"""Merge full canonical/raw/index streams with all three sparse histories."""
import hashlib
from itertools import zip_longest
from identity_guard import require
from stream_io import canonical


class SparseHistory:
    def __init__(self, records, role):
        self.rows, self.role = iter(records), role
        self.current, self.previous = next(self.rows, None), 0

    def expect(self, line, expected):
        if self.current is not None:
            key = self.current[2].get('source', {}).get('line')
            require(type(key) is int and key > self.previous, 'HISTORY_ORDER', self.role)
            require(key >= line, 'HISTORY_COVERAGE_MISMATCH', self.role)
        else:
            key = None
        if expected is None:
            require(key != line, 'HISTORY_COVERAGE_MISMATCH', self.role)
            return
        require(key == line, 'HISTORY_COVERAGE_MISMATCH', self.role)
        require(self.current[2] == expected, 'HISTORY_CONTENT_MISMATCH', self.role)
        self.previous = key
        self.current = next(self.rows, None)
        if self.current is not None:
            require(self.current[2].get('source', {}).get('line') != key,
                    'HISTORY_DUPLICATE_SOURCE', self.role)

    def finish(self):
        require(self.current is None, 'HISTORY_EXTRA_AT_EOF', self.role)


def handshake(valid, ready):
    if type(valid) is int and valid == 0 or type(ready) is int and ready == 0:
        return False
    return True if type(valid) is int and valid == 1 and type(ready) is int and ready == 1 else None


def joined(streams, capture, stream_helper, dependencies, geometry):
    histories = {key: SparseHistory(streams[key].records(), key)
                 for key in ('fx_history', 'advance_history', 'input_apply_history')}
    prior_time, identity, count = -1, None, 0
    raw_sha = streams['raw_capture'].desc['sha256']
    for public, raw, index, line_index in zip_longest(streams['public_rows'].records(),
                                        streams['raw_capture'].records(),
                                        streams['row_index'].records(),
                                        streams['line_index'].records()):
        require(None not in (public, raw, index, line_index), 'PUBLIC_POSEDGE_COVERAGE_GAP')
        number, physical, row = public
        require(number == raw[0] == index[0] == line_index[0], 'PUBLIC_POSEDGE_COVERAGE_GAP')
        stream_helper.validate_public_row(row, number, dependencies)
        fields, source = row['fields'], row['source']
        physical_identity = line_index[2]
        require(set(physical_identity) == {'line', 'cycle', 'epoch', 'raw_line_sha256', 'public_line_sha256'}
                and physical_identity['line'] == number and physical_identity['cycle'] == fields['cycle']
                and physical_identity['epoch'] == fields['epoch'], 'PHYSICAL_LINE_INDEX_SOURCE', number)
        require(physical_identity['public_line_sha256'] == hashlib.sha256(physical).hexdigest(),
                'PUBLIC_LINE_SHA', number)
        require(physical_identity['raw_line_sha256'] == hashlib.sha256(raw[1]).hexdigest(),
                'RAW_LINE_SHA', number)
        require(row['capture_id'] == capture and source['raw_sha256'] == raw_sha,
                'MIXED_CAPTURE_IDENTITY', number)
        current = row['capture_id'], row['origin'], source['raw_sha256'], source['reset_edges_sha256']
        identity = current if identity is None else identity
        require(current == identity, 'MIXED_CAPTURE_IDENTITY', number)
        require(type(source['time_ps']) is int and source['time_ps'] > prior_time
                and source['time_ps'] == geometry['first_posedge_ps']
                + (number - 1) * geometry['period_ps'], 'C9_TIME_SEQUENCE', number)
        prior_time = source['time_ps']
        require(raw[2].get('schema') == 'M3_R7A_C9_RAW_CORE_ROW_V1'
                and raw[2].get('ports') == row['raw_ports']
                and raw[2].get('finish') == fields['finish'], 'RAW_PUBLIC_FIELD_MISMATCH', number)
        merged = {**source, 'canonical_row_content_sha256': hashlib.sha256(canonical(row)).hexdigest()}
        lane = dependencies['bridge']._lane_advance(fields['advance_mask'])
        classification = dependencies['bridge']._apply_classification(fields)
        expected_index = dict(source=merged, canonical_row=row, frame_f_raw=fields['frame_tick'],
            actual_accept_a=handshake(fields['req_valid'], fields['req_ready']),
            advance_request_tag=fields['advance_frame_req_id'], lane_advance=lane,
            apply_classification=classification, independent_apply_event_seq=None,
            expected_pcm=None, actual_pcm_is_golden=False,
            math_status='PENDING_M1_MODEL_AND_INDEPENDENT_PLAN')
        require(index[2] == expected_index, 'CANONICAL_CONTENT_SHA', number)
        fx = None
        if fields['effect_input_valid'] != 0 or fields['config_take'] != 0:
            fx = dict(source=merged, actual_effect_input={name: fields[name] for name in (
                'effect_input_valid', 'effect_input_ready', 'effect_input_id',
                'effect_input_left', 'effect_input_right', 'effect_input_clip_mask')},
                actual_config={name: fields[name] for name in ('config_take', 'config_payload')},
                config_components=row['semantics'].get('config_on_actual_take'),
                actual_clips={name: fields[name] for name in (
                    'upstream_clip_mask', 'effect_clip_mask', 'feedback_clip_mask')},
                expected_fx_input=None, status='OBSERVATION_ONLY_NOT_GOLDEN')
        advances = None
        if fields['advance_mask'] != 0:
            advances = dict(source=merged, advance=lane, request_tag=fields['advance_frame_req_id'],
                req_id=fields['req_id'], commit_observed_same_row=fields['commit'],
                cancel_raw=fields['cancel'], retained_even_if_unpublished_or_cancelled=True)
        events = None
        if fields['event_valid'] != 0 or fields['apply_valid'] != 0:
            events = dict(source=merged,
                actual_input={name: fields[name] for name in ('event_valid', 'event_ready', 'event_data')},
                actual_stage={name: fields[name] for name in ('apply_valid', 'apply_data', 'apply_kind',
                    'apply_mask', 'router_apply_seq', 'router_apply_seq_valid')},
                classification=classification, independent_apply_event_seq=None,
                status='PENDING_INDEPENDENT_INPUT_PLAN_MAPPING')
        for key, expected in zip(histories, (fx, advances, events)):
            histories[key].expect(number, expected)
        require(fields['finish'] == int(number == geometry['row_count']),
                'FINISH_MUST_BE_UNIQUE_FINAL_ROW', number)
        count += 1
        yield row
    require(count == geometry['row_count'], 'PUBLIC_POSEDGE_COVERAGE_GAP')
    for history in histories.values():
        history.finish()
