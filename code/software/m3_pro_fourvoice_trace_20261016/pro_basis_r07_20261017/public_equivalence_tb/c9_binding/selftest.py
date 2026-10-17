"""Deferred C9 software cases. NOT_RUN; this file grants no execution budget.

Only run_case(), after a separate exact-source execution admission, loads the
candidate from verified source bytes. No pycache/import of candidate modules.
Each case retains input files and candidate result or rejection before checks.
"""
import csv
import hashlib
import json
from pathlib import Path
import types


def dump(file, value):
    Path(file).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def write_csv(file, columns, records):
    with Path(file).open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator='\n')
        writer.writeheader()
        writer.writerows(records)


def load_exact(source, expected_sha):
    source = Path(source)
    body = source.read_bytes()
    assert hashlib.sha256(body).hexdigest() == expected_sha
    candidate = types.ModuleType('c9_pair_deferred_exact_source')
    candidate.__file__ = str(source)
    exec(compile(body, str(source), 'exec'), candidate.__dict__)
    return candidate


def diagnostic_fixture(module, directory, case):
    widths = dict(module.COMPANION_WIDTHS)

    def row(cycle, **updates):
        values = {key: 0 for key in widths}
        values.update(rst_n=1, polyphonic_valid=1, apply_valid=1)
        values.update(updates)
        result = {'cycle': str(cycle), 'time_ps': str(12500 + (cycle - 1) * 25000)}
        result.update({key: (value if isinstance(value, str) else format(value, '0%db' % width))
                       for key, width in widths.items() for value in [values[key]]})
        return result

    records = [row(1, apply_kind=1, apply_mask=1, router_apply_seq_valid=1,
                   router_apply_seq=7, apply_data=123)]
    if case == 'same_seq_two_stages':
        records.append(row(2, apply_kind=2, apply_mask=1, router_apply_seq_valid=1,
                           router_apply_seq=7, apply_data=123))
    elif case == 'invalid_cause_sentinels':
        records = [row(index, apply_kind=kind) for index, kind in enumerate((3, 4, 8), 1)]
    elif case == 'idle_held_data':
        records = [row(1, apply_valid=0, apply_kind=0, apply_data=123, router_apply_seq=7)]
    elif case == 'config_only_on_take':
        packed = (1 << 61) | (123 << 45) | (234 << 30) | (345 << 15) | 456
        records = [row(1, config_take=0, config_payload=packed),
                   row(2, config_take=1, config_payload=packed)]
    elif case == 'distinct_clip_masks':
        records = [row(1, upstream_clip_mask=1, effect_clip_mask=2, feedback_clip_mask=3)]
    elif case == 'unknown_valid_retained':
        records[0]['router_apply_seq_valid'] = 'x'
    elif case == 'reset_qualification':
        records = [row(1, rst_n=0, apply_kind=1, router_apply_seq_valid=1, apply_data=123),
                   row(2, polyphonic_valid=0, apply_kind=1, router_apply_seq_valid=1, apply_data=123)]
    elif case == 'sentinel_valid_rejected':
        records = [row(1, apply_kind=3, router_apply_seq_valid=1)]
    elif case != 'width_contract_rejected':
        raise ValueError('UNKNOWN_CASE')
    capture = directory / 'companions.csv'
    write_csv(capture, ['cycle', 'time_ps'] + list(widths), records)
    data = {'csv': str(capture), 'sha256': hashlib.sha256(capture.read_bytes()).hexdigest(),
            'widths': widths}
    if case == 'width_contract_rejected':
        data['widths']['config_payload'] = 61
    return data


def join_fixture(directory, case):
    plan = directory / 'synthetic_plan.json'
    dump(plan, {'synthetic_only': True, 'case': case})
    plan_sha = hashlib.sha256(plan.read_bytes()).hexdigest()
    binding = directory / 'synthetic_binding.json'
    dump(binding, {'schema': 'M3_R7B_C9_SOURCE_BINDING_V1', 'compile_universes_separate': True,
                   'staged_files': [{'destination': lane + '/plan.json', 'sha256': plan_sha}
                                    for lane in ('original', 'observer')]})
    data = {'input_root': str(directory), 'start_cycle': 1, 'stop_cycle': 2,
            'input_plan_path': plan.name, 'input_plan_sha256': plan_sha,
            'source_binding_path': binding.name,
            'source_binding_sha256': hashlib.sha256(binding.read_bytes()).hexdigest()}
    for lane in ('original', 'observer'):
        capture = []
        for cycle in (1, 2):
            capture.append({'cycle': str(cycle), 'time_ps': str(12500 + (cycle - 1) * 25000),
                            'rst_n': '1', 'midi_rx': '1', 'key_n': '11', 'pins': '0' * 13})
        if lane == 'observer':
            if case == 'join_phase_rejected':
                capture[1]['time_ps'] = '37501'
            elif case == 'join_input_rejected':
                capture[1]['midi_rx'] = '0'
            elif case == 'join_pin_difference_preserved':
                capture[1]['pins'] = '0' * 12 + '1'
        trace = directory / (lane + '.csv')
        event = directory / (lane + '_events.csv')
        stdout = directory / (lane + '_stdout.txt')
        write_csv(trace, ['cycle', 'time_ps', 'rst_n', 'midi_rx', 'key_n', 'pins'], capture)
        write_csv(event, ['time_ps', 'pins'], [{'time_ps': '12500', 'pins': '0' * 13}])
        stdout.write_text('LANE_END lane=%s cycle=2 time_ps=37500\n' % lane, encoding='utf-8')
        data[lane] = {}
        receipt = {'schema': 'M3_R7B_C9_LANE_RECEIPT_V1', 'exit_code': 0,
                   'normal_exit': True, 'timeout': False,
                   'input_plan_sha256': data['input_plan_sha256'],
                   'source_binding_sha256': data['source_binding_sha256']}
        for role, file in [('trace', trace), ('events', event), ('stdout', stdout)]:
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            data[lane][role] = {'path': file.name, 'sha256': digest}
            receipt[role + '_sha256'] = digest
        if lane == 'observer' and case == 'join_timeout_rejected':
            receipt['timeout'] = True
        file = directory / (lane + '_receipt.json')
        dump(file, receipt)
        data[lane]['receipt'] = {'path': file.name,
                                  'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}
    return data


def run_case(case, output, candidate_source, expected_source_sha):
    """One exact case only. Call requires new authorization; never called here."""
    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=False)
    module = load_exact(candidate_source, expected_source_sha)
    data = (join_fixture(directory, case) if case.startswith('join_') else
            diagnostic_fixture(module, directory, case))
    dump(directory / 'INPUT.json', data)
    expected_errors = {'sentinel_valid_rejected': 'INVALID_CAUSE_SENTINEL_VALID',
                       'width_contract_rejected': 'COMPANION_CONTRACT_WIDTHS',
                       'join_phase_rejected': 'LANE_TIMEBASE',
                       'join_input_rejected': 'LANE_EXTERNAL_INPUT_DIFFERENCE',
                       'join_timeout_rejected': 'MISSING_NORMAL_EXIT_RECEIPT'}
    try:
        result = (module.join_pair(data, directory / 'joined') if case.startswith('join_') else
                  module.companion_rows(data))
        dump(directory / 'ACTUAL.json', result)
    except module.BindingError as error:
        dump(directory / 'REJECTION.json', {'reason': str(error)})
        assert str(error) == expected_errors.get(case)
        return {'case': case, 'matched': True, 'rejected': str(error)}
    assert case not in expected_errors
    if case.startswith('join_'):
        assert result['comparison_performed'] is False and result['real_equivalence_pass'] is False
        if case == 'join_pin_difference_preserved':
            with (directory / 'joined/combined.csv').open(encoding='utf-8', newline='') as stream:
                actual = list(csv.DictReader(stream))
            assert actual[1]['original'] != actual[1]['observer']
    else:
        actual = result['rows']
        assert all(row['independent_apply_event_seq'] is None and row['audio_stable'] is None
                   and row['epoch'] is None and row['deduplicated'] is False for row in actual)
        if case == 'same_seq_two_stages':
            assert len(actual) == 2 and [row['fields']['apply_kind'] for row in actual] == [1, 2]
            assert [row['fields']['router_apply_seq'] for row in actual] == [7, 7]
        elif case == 'invalid_cause_sentinels':
            assert len(actual) == 3 and all(row['cause_valid'] is False for row in actual)
        elif case == 'idle_held_data':
            assert actual[0]['apply_active'] is False and actual[0]['fields']['apply_data'] == 123
        elif case == 'config_only_on_take':
            assert actual[0]['config_on_take'] is None
            assert actual[1]['config_on_take'] == {'enable': 1, 'delay_samples': 123,
                                                   'dry_gain': 234, 'wet_gain': 345, 'feedback': 456}
        elif case == 'distinct_clip_masks':
            assert [actual[0]['fields'][key] for key in
                    ('upstream_clip_mask', 'effect_clip_mask', 'feedback_clip_mask')] == [1, 2, 3]
        elif case == 'unknown_valid_retained':
            assert actual[0]['fields']['router_apply_seq_valid'] is None
            assert actual[0]['original_csv_row']['router_apply_seq_valid'] == 'x'
        elif case == 'reset_qualification':
            assert len(actual) == 2 and all(row['apply_active'] is False and
                                          row['cause_valid'] is False for row in actual)
    return {'case': case, 'matched': True, 'real_equivalence_pass': False}
