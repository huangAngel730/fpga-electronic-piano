"""New chain seams and independent provenance counterexamples only."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import ModuleType
import sys

COMMON = Path(__file__).with_name('common.py')
raw = COMMON.read_bytes()
if hashlib.sha256(raw).hexdigest() != '55cb7481fe9c0870247a7d8b2453dea859f0f2e81879795cc0e34ffe8c996dca':
    raise ValueError('COMMON_SOURCE_CHANGED')
c = ModuleType('_d4_root_test_common')
c.__file__ = str(COMMON)
sys.modules[c.__name__] = c
exec(compile(raw, str(COMMON), 'exec'), c.__dict__)

CASE_IDS = ('D4_PREPARE_NO_PRIOR_CAPTURE', 'D4_IDLE_CHAIN_PENDING',
            'D4_SOURCE_VALUE_TAMPER_REJECT', 'D4_WINDOW_SHIFT_REJECT',
            'D4_DUPLICATE_END_REJECT', 'D4_FRAME_INPUT_IDENTITY_REJECT',
            'D4_APPLICATION_WINDOW_MISMATCH_REJECT')
M2 = c.ROOT / 'code/docs/test/m2_138k_pro_fourvoice_candidate_20261016'
SOURCE = M2 / 'r06_public_chain_20261017/c9_m1_semantics_20261017/SOURCE_CLOSURE_R06C9.zip'
RULES = M2 / 'r06_observer_20261017/FRAME_PLAN_RULES.json'
APP = c.ROOT / ('code/docs/test/m3_pro_fourvoice_trace_20261016/'
    'pro_basis_r08_20261017/build_admission_bundle/c9_completion_r01/APPLICATION_REQUEST.json')
FIXTURE = c.ROOT / ('code/tb/board/m3_pro_fourvoice_trace_20261016/'
    'pro_basis_r07_20261017/public_capture_tb/c9_binding')


def _modules():
    binding = c.read_json(c.DOC / 'MODULE_BINDINGS.json')
    return {name: c.load_source(c.checked_descriptor(desc), desc['sha256'])
            for name, desc in binding['modules'].items()}


def _fixture(out, prepare=False):
    # The independent reset/window/stop is written before any raw fixture is
    # opened. Seven idle cycles deliberately provide no numerical/audio pass.
    scenario = out / 'INDEPENDENT_SCENARIO.json'
    c.write_json(scenario, {'origin': 'SYNTHETIC_INDEPENDENT_SCENARIO',
        'release_cycle': 0, 'stop_cycle': 6, 'first_core_ps': 25000,
        'core_period_ps': 25000, 'expected_frames': []})
    midi = out / 'MIDI_PLAN.json'
    c.write_json(midi, {'schema': 'M3_D4_SYNTHETIC_EMPTY_INPUT_PLAN_V1',
        'origin': 'SYNTHETIC_INDEPENDENT_SCENARIO', 'events': [],
        'not_actual_MIDI_or_driver_verification': True})
    frame_input = out / 'FRAME_INPUT.json'
    c.write_json(frame_input, {'schema': 'M3_R06_FRAME_PLAN_GENERATOR_INPUT_V1',
        'status': 'FROZEN_INDEPENDENT_INPUT', 'independent_of_observed_trace': True,
        'source_identities': [{key: c.artifact(path)[key] for key in ('path', 'sha256')}
                              for path in (scenario, SOURCE)],
        'epochs': [{'epoch': 0, 'reset_assert_cycle': 0, 'release_cycle': 0,
                    'stop_cycle': 6, 'window_kind': 'ACTIVE'}],
        'finish': {'epoch': 0, 'cycle': 6}})
    request = {'schema': 'M3_C9_CHAIN_REQUEST_V1', 'mode': 'PREPARE' if prepare else 'PROCESS_CAPTURE',
        'capture_id': 'C9_SYNTHETIC_NOT_REAL', 'origin': 'SYNTHETIC_SCHEMA_FIXTURE',
        'synthetic_application_example': True,
        'module_bindings': c.artifact(c.DOC / 'MODULE_BINDINGS.json'),
        'source_contract_refs': [c.artifact(SOURCE)],
        'inputs': {'frame_input': c.artifact(frame_input), 'frame_rules': c.artifact(RULES),
                   'midi_plan': c.artifact(midi), 'application_request': c.artifact(APP)}}
    if prepare:
        return request
    window = out / 'WINDOW.json'
    c.write_json(window, {'schema': 'M3_R7D_INDEPENDENT_WINDOW_V1',
        'capture_id': request['capture_id'], 'plan_stop_id': 'D4_IDLE_STOP',
        'input_plan_sha256': c.identity(midi)['sha256'], 'first_core_ps': 25000,
        'core_period_ps': 25000, 'row_count': 7, 'finish_cycle': 6, 'finish_time_ps': 175000})
    original = list(c.iter_jsonl(FIXTURE / 'C9_SYNTHETIC.raw.jsonl'))
    c.require(len(original) == 7, 'FROZEN_SMALL_FIXTURE_COUNT')
    template = original[-1]
    raw_path = out / 'RAW.jsonl'
    with raw_path.open('x', encoding='utf-8', newline='\n') as sink:
        for cycle in range(7):
            row = copy.deepcopy(template)
            row.update(source_line=cycle + 1, cycle=cycle, time_ps=(cycle + 1) * 25000,
                       finish=int(cycle == 6))
            sink.write(json.dumps(row, separators=(',', ':')) + '\n')
    end = out / 'END.json'
    c.write_json(end, {'schema': 'M3_R7A_END_V1', 'capture_id': request['capture_id'],
        'plan_stop_id': 'D4_IDLE_STOP', 'finish_cycle': 6, 'time_ps': 175000,
        'row_count': 7, 'reason': 'PLANNED_WINDOW_END',
        'ledger_status': 'NOT_CHECKED_R6_5_REQUIRED', 'serial_tail_status': 'UNKNOWN_R6_6_REQUIRED'})
    stdout = out / 'CAPTURE_STDOUT.txt'
    stdout.write_text('MONITOR_END capture_id=C9_SYNTHETIC_NOT_REAL cycle=6 '
        'time_ps=175000 rows=7 reason=PLANNED_WINDOW_END\n', encoding='utf-8', newline='\n')
    request['inputs'].update(raw=c.artifact(raw_path), resets=c.artifact(FIXTURE / 'C9_SYNTHETIC.resets.jsonl'),
        end=c.artifact(end), stdout=c.artifact(stdout), window_plan=c.artifact(window))
    return request


def run_case(case_id, output_dir):
    c.require(case_id in CASE_IDS, 'UNKNOWN_ROOT_CASE')
    out = c.output_directory(output_dir)
    request = _fixture(out, case_id == 'D4_PREPARE_NO_PRIOR_CAPTURE')
    c.write_json(out / 'INPUT_REQUEST.json', request)
    modules = _modules()
    if case_id in ('D4_PREPARE_NO_PRIOR_CAPTURE', 'D4_IDLE_CHAIN_PENDING', 'D4_APPLICATION_WINDOW_MISMATCH_REJECT'):
        binding = c.read_json(c.DOC / 'MODULE_BINDINGS.json')['chain']
        chain = c.load_source(c.checked_descriptor(binding), binding['sha256'])
        if case_id == 'D4_APPLICATION_WINDOW_MISMATCH_REJECT':
            request['synthetic_application_example'] = False
            request['origin'] = 'HDL_PUBLIC_CAPTURE_UNVERIFIED'
            try:
                chain.process(request, out / 'chain')
            except (ValueError, RuntimeError) as error:
                c.require('APPLICATION_CAPTURE_WINDOW_MISMATCH' in str(error), 'APPLICATION_WINDOW_REJECT')
                c.write_json(out / 'RESULT.json', {'case_id': case_id, 'actual_reject': str(error)})
                return {'case_id': case_id, 'status': 'PASS'}
            raise AssertionError('APPLICATION_WINDOW_MUST_REJECT')
        report = chain.process(request, out / 'chain')
        c.require(report['execution_allowed'] is False and report['real_verified'] is False,
                  'CHAIN_FALSE_AUTHORITY')
        if case_id == 'D4_PREPARE_NO_PRIOR_CAPTURE':
            c.require(report['summary']['capture'] == 'NOT_RUN' and 'raw' not in request['inputs'],
                      'FIRST_CAPTURE_CIRCULAR_DEPENDENCY')
        else:
            c.require(report['summary']['rows'] == 7 and report['summary']['missing_math_roles'] == ['execution_receipt'],
                      'IDLE_CHAIN_MUST_REMAIN_MATH_PENDING')
            c.require(report['summary']['provenance'] == 'SYNTHETIC_CHAIN_BOUND', 'IDLE_PROVENANCE')
    else:
        paths = {key: c.checked_descriptor(value) for key, value in request['inputs'].items()}
        modules['frame_generator'].generate(paths['frame_input'], paths['frame_rules'], out / 'unique_plan')
        converted = modules['stream'].convert_files(paths['raw'], paths['resets'], paths['end'],
            paths['stdout'], out / 'capture', origin=request['origin'])
        artifacts = {'public_rows': converted['artifacts']['public_rows'],
                     'frame_plan': c.artifact(out / 'unique_plan/UNIQUE_FRAME_PLAN.json')}
        expected = {'D4_SOURCE_VALUE_TAMPER_REJECT': 'NORMALIZED_RAW_VALUE:result_left',
            'D4_WINDOW_SHIFT_REJECT': 'END_WINDOW_MISMATCH',
            'D4_DUPLICATE_END_REJECT': 'UNIQUE_ACTUAL_MONITOR_END',
            'D4_FRAME_INPUT_IDENTITY_REJECT': 'FRAME_PLAN_INPUT_RULES_BINDING'}[case_id]
        if case_id == 'D4_SOURCE_VALUE_TAMPER_REJECT':
            changed = out / 'VALUE_TAMPER.jsonl'
            with changed.open('x', encoding='utf-8', newline='\n') as sink:
                for number, row in enumerate(c.iter_jsonl(c.checked_descriptor(artifacts['public_rows']))):
                    if number == 3:
                        row['fields']['result_left'] = 123
                    sink.write(json.dumps(row) + '\n')
            artifacts['public_rows'] = c.artifact(changed)
        elif case_id == 'D4_WINDOW_SHIFT_REJECT':
            value = c.read_json(paths['window_plan'])
            value['first_core_ps'] += 1
            value['finish_time_ps'] += 1
            changed = out / 'SHIFTED_WINDOW.json'
            c.write_json(changed, value)
            request['inputs']['window_plan'] = c.artifact(changed)
        elif case_id == 'D4_DUPLICATE_END_REJECT':
            changed = out / 'DUPLICATE_END.txt'
            changed.write_text(paths['stdout'].read_text(encoding='utf-8') * 2,
                               encoding='utf-8', newline='\n')
            request['inputs']['stdout'] = c.artifact(changed)
        else:
            changed = out / 'OTHER_FRAME_INPUT.json'
            value = c.read_json(paths['frame_input'])
            value['description'] = 'different frozen independent input'
            c.write_json(changed, value)
            request['inputs']['frame_input'] = c.artifact(changed)
        try:
            modules['provenance'].validate_capture(request, artifacts, out / 'provenance')
        except (ValueError, RuntimeError) as error:
            c.require(expected in str(error), 'EXPECTED_REJECT_MISMATCH:' + str(error))
            report = {'expected_reject': expected, 'actual_reject': str(error)}
        else:
            raise AssertionError('EXPECTED_REJECT:' + expected)
    c.write_json(out / 'RESULT.json', {'case_id': case_id, 'status': 'PASS', 'report': report})
    return {'case_id': case_id, 'status': 'PASS', 'real_verified': False}
