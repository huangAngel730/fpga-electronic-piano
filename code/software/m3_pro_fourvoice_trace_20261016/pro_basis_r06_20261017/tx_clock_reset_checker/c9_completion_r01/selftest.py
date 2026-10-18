"""Six NEW canonical74-to-serial seam cases; coordinator-only execution.

Does not invoke old selftests. The original R6-5 function produces the only
FRAME_PLAN. The literal serial waveform is a synthetic interface fixture.
"""
import hashlib
import json
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[6]
SOFT = ROOT / 'code/software/m3_pro_fourvoice_trace_20261016'
COMMON = SOFT / 'pro_basis_r08_20261017/coordinator/task_day4_completion_20261017/common.py'
COMMON_SHA = '55cb7481fe9c0870247a7d8b2453dea859f0f2e81879795cc0e34ffe8c996dca'
SOURCE_SHA = 'c576a5c79169eb5e91d796775aec820260a5df0e47b5c4472acf8630f5dcc5b7'
GENERATOR = SOFT / 'pro_basis_r06_20261017/event_calendar/frame_plan_generator_candidate.py'
GENERATOR_SHA = '38592faebeeeb0a2022668785453760a5b58babd24af6ff18a96f15790597191'
RULES = ROOT / 'code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/r06_observer_20261017/FRAME_PLAN_RULES.json'
RULES_SHA = '3c968a151b0b5369f9dd95465761b2d87449c29975b1fca914f81fc5cfd01560'
PORT_MAP = ROOT / 'code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r07_20261017/public_capture_tb/c9_binding/PORT_MAP_C9.json'
PORT_MAP_SHA = '65a4fcca8b83ab72eaed3aaf5bf7cd48db18ad0691027aaaf57d1e9e4ced0807'


def shared():
    raw = COMMON.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == COMMON_SHA
    module = ModuleType('_c9_serial_seam_test_common')
    module.__file__ = str(COMMON)
    exec(compile(raw, str(COMMON), 'exec', dont_inherit=True), module.__dict__)
    return module


def fixture(c, engine, directory, case):
    reset_tail = case == 'C9S_RESET_PARTIAL_FINISH'
    stop = 1805 if reset_tail else 4000
    basis = directory / 'INDEPENDENT_BASIS.json'
    c.write_json(basis, {'origin': 'SYNTHETIC_INTERFACE_PLAN_NOT_DUT', 'case': case,
                         'PCM24': {'left': 768, 'right': -1024}, 'request_id': 0,
                         'clip_mask': 1, 'release_cycle': 4, 'finish_cycle': stop})
    epochs = [{'epoch': 0, 'window_kind': 'ACTIVE', 'reset_assert_cycle': 0,
               'release_cycle': 4, 'stop_cycle': 1800 if reset_tail else stop}]
    if reset_tail:
        epochs.append({'epoch': 1, 'window_kind': 'RESET_ONLY', 'reset_assert_cycle': 1801,
                       'release_cycle': None, 'stop_cycle': stop})
    independent = {'schema': 'M3_R06_FRAME_PLAN_GENERATOR_INPUT_V1',
                   'status': 'FROZEN_INDEPENDENT_INPUT', 'independent_of_observed_trace': True,
                   'source_identities': [{'path': c.artifact(basis)['path'],
                                          'sha256': c.identity(basis)['sha256']}],
                   'epochs': epochs, 'finish': {'epoch': int(reset_tail), 'cycle': stop}}
    source = directory / 'FRAME_INPUT.json'
    c.write_json(source, independent)
    assert c.identity(RULES)['sha256'] == RULES_SHA
    generator = c.load_source(GENERATOR, GENERATOR_SHA)
    documents = generator.build_documents(independent, c.read_json(RULES),
                                           c.identity(source)['sha256'], RULES_SHA)
    plan = documents['canonical']
    plan_path = directory / 'UNIQUE_FRAME_PLAN.json'
    c.write_json(plan_path, plan)
    old = c.load_source(engine.LEGACY66, engine.LEGACY66_SHA)
    names = tuple(old.CANONICAL_FIELDS) + tuple(engine.ADDED_FIELDS)
    frames = plan['epochs'][0]['cycles']
    frame_ordinals = {at: index for index, at in enumerate(frames)}
    F, A = frames[0], frames[0] + 2
    late = case == 'C9S_F_A_NEXT_FRAME_REJECT'
    result_cycle = frames[1] if late else F + 12
    commit_cycle = None if late else F + 13
    public = directory / 'PUBLIC_C9.jsonl'
    raw_source_sha = c.identity(basis)['sha256']
    assert c.identity(PORT_MAP)['sha256'] == PORT_MAP_SHA
    port_map = c.read_json(PORT_MAP)
    phase = bclk = ws = din = falls = word = 0
    sample = (None, 0, 0)
    with public.open('x', encoding='utf-8', newline='\n') as stream:
        for cycle in range(stop + 1):
            epoch = int(reset_tail and cycle >= 1801)
            rst = int(cycle >= 4 and not epoch)
            row = dict.fromkeys(names, 0)  # Explicit synthetic inactive values, never a real-row repair.
            row.update(cycle=cycle, epoch=epoch, rst_n=rst, pll_locked=rst, pa_en=0,
                       apply_event_seq=None, audio_stable=None, tx_req_id=None,
                       tx_metadata_valid=1, bclk=bclk if rst else 0,
                       ws=ws if rst else 0, din=din if rst else 0,
                       finish=int(cycle == stop))
            if rst and cycle in frame_ordinals:
                ordinal = frame_ordinals[cycle]
                startup = ordinal == 0
                row.update(frame_tick=1, tx_sample_valid=1, tx_frame_id=ordinal + 21,
                           tx_startup_zero=int(startup), tx_hold=int(ordinal >= 2),
                           tx_req_id_valid=int(not startup), tx_req_id=None if startup else 0,
                           tx_left=0 if startup else 768, tx_right=0 if startup else -1024,
                           tx_clip_mask=0 if startup else 1, tx_clip=int(not startup))
                if case == 'C9S_HOLD_DUAL_CLIP_REJECT' and ordinal == 2:
                    row['tx_clip_mask'] = 2  # Same OR, distinct provenance.
                sample = (row['tx_req_id'], row['tx_left'], row['tx_right'])
            if rst and cycle == A:
                row.update(req_valid=1, req_ready=1, req_id=0)
            if rst and cycle == result_cycle:
                row.update(result_valid=1, result_ready=1, result_id=0,
                           result_left=768, result_right=-1024, result_clip_mask=1)
            if rst and cycle == commit_cycle:
                row.update(commit=1, commit_id=0, commit_left=768,
                           commit_right=-1024, commit_clip=1)
            raw_ports = {name: '0' * spec['width'] for name, spec in port_map['raw_ports'].items()}
            for field, spec in port_map['normalized_mapping'].items():
                value = row[field]
                # Gated-unused request ID has explicit zero raw sentinel in this
                # SYNTHETIC fixture; no real unknown field is filled in.
                if field == 'tx_req_id' and value is None:
                    value = 0
                if type(value) is int:
                    raw_ports[spec['port']] = format(value & ((1 << spec['width']) - 1),
                                                      '0%db' % spec['width'])
            raw_ports.update(obs_core_clk='1', obs_polyphonic_valid='1', uart_tx='1')
            if case == 'C9S_UNKNOWN_FRAME_EXPECTATION_COVERAGE' and cycle == frames[1]:
                raw_ports['obs_polyphonic_valid'] = 'x'
            original = {'schema': 'M3_R7A_C9_PUBLIC_ROW_V1',
                        'origin': 'SYNTHETIC_SCHEMA_FIXTURE', 'capture_id': 'D4_C9_' + case,
                        'source': {'line': cycle + 1, 'cycle': cycle, 'epoch': epoch,
                                   'time_ps': 12500 + cycle * 25000, 'raw_sha256': raw_source_sha,
                                   'reset_edges_sha256': raw_source_sha, 'sampling_phase': 'POSEDGE_PRE_NBA'},
                        'fields': row, 'raw_ports': raw_ports,
                        'missing_reasons': {'apply_event_seq': 'INDEPENDENT_MAPPING_PENDING',
                                            'audio_stable': 'POLICY_PENDING'},
                        'events': [], 'semantics': {'apply_cause': 'INACTIVE_RAW_HELD_VALUES_UNINTERPRETED',
                                                    'stage_deduplicated': False,
                                                    'independent_plan_mapping': 'PENDING',
                                                    'config_on_actual_take': None,
                                                    'advance_frame_req_id_is_FRAME_F': False,
                                                    'advance_mask_source': 'PUBLIC_M1_LANE_TICK_ROUTE_NOT_REQUEST_ACCEPTANCE'}}
            stream.write(json.dumps(original, separators=(',', ':')) + '\n')
            if not rst:
                phase = bclk = ws = din = falls = word = 0
                sample = (None, 0, 0)
                continue
            phase += 659706977
            if phase >= 1 << 32:
                phase -= 1 << 32
                bclk ^= 1
                if bclk == 0:
                    falls += 1
                    offset = (falls - 1) % 32
                    if offset == 0:
                        ws = ((falls - 1) // 32) % 2
                        pcm = sample[1] if ws else sample[2]
                        word = max(-32768, min(32767, (pcm + 128) // 256)) & 65535
                        if case == 'C9S_SERIAL_PHASE_VALID_WORD_REJECT' and falls == 129:
                            word ^= 1
                    din = 0 if offset < 16 else (word >> (31 - offset)) & 1
    return public, plan_path, {'F': F, 'A': A, 'finish': stop}


def run_case(case_id, output_dir):
    expected = {'C9S_FULL74_HOLD_ID0_TAIL': 'UNKNOWN_SERIAL_PARTIAL',
                'C9S_HOLD_DUAL_CLIP_REJECT': 'HOLD_ID_PCM_CLIP_CHANGED_OR_RESET',
                'C9S_SERIAL_PHASE_VALID_WORD_REJECT': 'PIN_SERIAL_PCM_OR_CHANNEL_MISMATCH',
                'C9S_F_A_NEXT_FRAME_REJECT': 'REQUEST_OPEN_AT_NEXT_FRAME',
                'C9S_RESET_PARTIAL_FINISH': 'UNKNOWN_SERIAL_PARTIAL',
                'C9S_UNKNOWN_FRAME_EXPECTATION_COVERAGE': 'UNKNOWN_SERIAL_PARTIAL'}[case_id]
    c = shared()
    out = c.output_directory(output_dir)
    engine = c.load_source(Path(__file__).with_name('serial.py'), SOURCE_SHA)
    public, plan, coordinates = fixture(c, engine, out, case_id)
    scenario = None
    if case_id == 'C9S_UNKNOWN_FRAME_EXPECTATION_COVERAGE':
        basis = c.read_json(out / 'INDEPENDENT_BASIS.json')
        rows = []
        for ordinal, cycle in enumerate(c.read_json(plan)['epochs'][0]['cycles']):
            rows.append({'epoch': 0, 'cycle': cycle,
                         'tx_req_id': None if ordinal == 0 else basis['request_id'],
                         'tx_left': 0 if ordinal == 0 else basis['PCM24']['left'],
                         'tx_right': 0 if ordinal == 0 else basis['PCM24']['right'],
                         'tx_clip_mask': 0 if ordinal == 0 else basis['clip_mask'],
                         'tx_startup_zero': int(ordinal == 0), 'tx_hold': int(ordinal >= 2)})
        scenario = out / 'INDEPENDENT_TX_SCENARIO.json'
        c.write_json(scenario, {'schema': 'M3_R08_TX_SCENARIO_V1',
                               'FRAME_PLAN_generated': False, 'rows': rows,
                               'origin': 'SYNTHETIC_INTERFACE_PLAN_NOT_DUT'})
    c.write_json(out / 'INPUT_BEFORE_CALL.json', {'public': c.artifact(public),
                                                'plan': c.artifact(plan), 'coordinates': coordinates,
                                                'expected': expected})
    try:
        result = engine.analyze_files(public, plan, out / 'analysis', scenario)
        actual = result['status']
        c.write_json(out / 'ACTUAL_BEFORE_ASSERT.json', result)
    except ValueError as error:
        actual = str(error)
        result = {'status': 'REJECT', 'reason': actual, 'real_pass': False}
        c.write_json(out / 'ACTUAL_BEFORE_ASSERT.json', result)
    assert actual == expected, (expected, actual)
    if case_id == 'C9S_FULL74_HOLD_ID0_TAIL':
        assert result['counts']['new_tx'] == 1 and result['counts']['hold_tx'] == 2
        assert result['counts']['startup_tx'] == 1 and result['counts']['frames'] >= 3
        assert result['unknown'] == ['SERIAL_TAIL_INCOMPLETE']
        assert 'PENDING_TX_SELECTION_PLAN' in result['pending']
        decoded = list(c.iter_jsonl(out / 'analysis/SERIAL_FRAMES.jsonl'))
        assert sum(row['request_id'] == 0 and row['left'] == 3 and row['right'] == -4
                   for row in decoded) >= 2
    if case_id == 'C9S_RESET_PARTIAL_FINISH':
        assert result['counts']['reset_truncations'] == 1
        assert result['counts']['frames'] >= 1 and 'RESET_TRUNCATED_HALF_OR_FRAME' in result['unknown']
    if case_id == 'C9S_UNKNOWN_FRAME_EXPECTATION_COVERAGE':
        assert result['counts']['FRAME_F'] == 3
        assert result['unchecked_tx_expectations'] == 3
        assert 'UNKNOWN_FRAME_RESET_EPOCH' in result['unknown']
        assert 'TX_EXPECTATIONS_UNCHECKED_DUE_TO_UNKNOWN' in result['unknown']
        assert 'FRAME_INTERVAL_COVERAGE_GAP' in result['unknown']
        assert c.read_json(out / 'analysis/INPUTS.json')['expected_scenario'] == c.artifact(scenario)
    c.write_json(out / 'EXPECTATION.json', {'expected': expected, 'actual': actual})
    return {'status': 'CASE_EXPECTATION_MATCHED', 'case_id': case_id,
            'expected': expected, 'actual': actual, 'real_pass': False, 'board_release_allowed': False}
