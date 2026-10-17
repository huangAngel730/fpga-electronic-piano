"""Three NEW streaming seams, including a real >64MiB synthetic CSV file.

Only coordinator invokes run_case. No old T27 or C9 thirteen cases are run.
"""
import hashlib
import json
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[6]
SOFT = ROOT / 'code/software/m3_pro_fourvoice_trace_20261016'
COMMON = SOFT / 'pro_basis_r08_20261017/coordinator/task_day4_completion_20261017/common.py'
COMMON_SHA = '55cb7481fe9c0870247a7d8b2453dea859f0f2e81879795cc0e34ffe8c996dca'
SOURCE_SHA = '1097e36730ced98362ef73f1f7005c9de996e37ecc7d3f51c245aecef30feac9'


def shared():
    raw = COMMON.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == COMMON_SHA
    module = ModuleType('_c9_companion_seam_test_common')
    module.__file__ = str(COMMON)
    exec(compile(raw, str(COMMON), 'exec', dont_inherit=True), module.__dict__)
    return module


def line(cycle, widths, unknown=False):
    values = dict.fromkeys(widths, 0)
    values.update(rst_n=1, polyphonic_valid=1, router_apply_seq=7,
                  upstream_clip_mask=1, effect_clip_mask=2, feedback_clip_mask=3)
    if cycle in (4095, 4096):
        values.update(apply_valid=1, apply_kind=1 if cycle == 4095 else 2,
                      router_apply_seq_valid=1, apply_data=123456, apply_mask=3)
    if cycle == 4096:
        values.update(config_take=1, config_payload=(1 << 61) | (42 << 45) | (123 << 30) | 456)
    columns = [str(cycle), str(12500 + cycle * 25000)]
    columns += [('x' if unknown and key == 'router_apply_seq_valid' else
                 format(values[key], '0%db' % width)) for key, width in widths.items()]
    return ','.join(columns) + '\n'


def run_case(case_id, output_dir):
    expected = {'C9C_ACTUAL_LARGE_FILE_XZ_STAGE_TAIL': 'STREAM_CONVERTED_INDEPENDENT_MAPPING_PENDING',
                'C9C_TRUNCATED_FINAL_RECORD': 'COMPANION_TRUNCATED_LINE',
                'C9C_OUTPUT_BOUND_RETAINS_PARTIAL': 'COMPANION_OUTPUT_BOUND'}[case_id]
    c = shared()
    out = c.output_directory(output_dir)
    engine = c.load_source(Path(__file__).with_name('companions.py'), SOURCE_SHA)
    old = c.load_source(engine.OLD, engine.OLD_SHA)
    widths = old.COMPANION_WIDTHS
    source = out / 'COMPANIONS.csv'
    large = case_id == 'C9C_ACTUAL_LARGE_FILE_XZ_STAGE_TAIL'
    total, count = 0, 0
    with source.open('xb') as stream:
        header = (','.join(['cycle', 'time_ps'] + list(widths)) + '\n').encode('ascii')
        stream.write(header)
        total += len(header)
        while (total < 64 * 1024**2 + 4096 if large else count < 2):
            raw = line(count, widths).encode('ascii')
            stream.write(raw)
            total += len(raw)
            count += 1
        raw = line(count, widths, unknown=large).encode('ascii')
        if case_id == 'C9C_TRUNCATED_FINAL_RECORD':
            raw = raw[:-1]
        stream.write(raw)
        count += 1
    before = c.artifact(source)
    c.write_json(out / 'INPUT_BEFORE_CALL.json', {'source': before, 'rows_written': count,
                                                'actual_input_above_64MiB': before['bytes'] > 64 * 1024**2,
                                                'expected': expected})
    try:
        result = engine.convert_files(source, out / 'converted', max_input_bytes=80 * 1024**2,
                                      max_output_bytes=512 * 1024**2 if large else
                                      (500 if case_id == 'C9C_OUTPUT_BOUND_RETAINS_PARTIAL' else 1024**2))
        actual = result['status']
        c.write_json(out / 'ACTUAL_BEFORE_ASSERT.json', result)
    except ValueError as error:
        actual = str(error)
        result = {'status': 'REJECT', 'reason': actual}
        c.write_json(out / 'ACTUAL_BEFORE_ASSERT.json', result)
    assert actual == expected, (expected, actual)
    assert c.artifact(source) == before
    if large:
        assert before['bytes'] > 64 * 1024**2 and result['rows'] == count
        assert result['input_above_64MiB'] is True and result['read_after_identity_equal'] is True
        seen, stages, last = 0, [], None
        for row in c.iter_jsonl(out / 'converted/DIAGNOSTIC_ROWS.jsonl'):
            seen += 1
            last = row
            if row['cycle'] in (4095, 4096):
                stages.append(row)
        assert seen == count and last['source_line'] == count + 1
        assert last['fields']['router_apply_seq_valid'] is None
        assert last['raw_csv_line'] == line(count - 1, widths, unknown=True)
        assert last['independent_apply_event_seq'] is None and last['epoch'] is None
        assert [r['fields']['apply_kind'] for r in stages] == [1, 2]
        assert [r['fields']['router_apply_seq'] for r in stages] == [7, 7]
        assert all(r['stage_deduplicated'] is False for r in stages)
        assert stages[1]['config_on_actual_take'] == {'enable': 1, 'delay_samples': 42,
                                                      'dry_gain': 123, 'wet_gain': 0, 'feedback': 456}
        assert [last['fields'][name] for name in
                ('upstream_clip_mask', 'effect_clip_mask', 'feedback_clip_mask')] == [1, 2, 3]
    else:
        failure = c.read_json(out / 'converted/FAILURE.json')
        assert failure['partial_outputs_retained'] is True
        assert (out / 'converted/DIAGNOSTIC_ROWS.jsonl').exists()
        if case_id == 'C9C_TRUNCATED_FINAL_RECORD':
            assert failure['rows_written'] == 2
    c.write_json(out / 'EXPECTATION.json', {'expected': expected, 'actual': actual})
    return {'status': 'CASE_EXPECTATION_MATCHED', 'case_id': case_id,
            'expected': expected, 'actual': actual, 'real_pass': False, 'board_release_allowed': False}
