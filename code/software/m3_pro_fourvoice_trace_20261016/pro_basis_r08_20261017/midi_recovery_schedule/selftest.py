"""New normative schedules, no parser RTL or old R6-2 fixture executed."""
import importlib.util
from pathlib import Path


def run_case(case_id, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    p = Path(__file__).with_name('r08c17_schedule.py')
    s = importlib.util.spec_from_file_location('r08c17_test_engine', p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    c = m.shared()
    scenario = {'T17_RUNNING_REALTIME_ZERO': 'running_realtime_zero_velocity',
                'T17_HALF_MESSAGE_RESET': 'half_message_reset_new_status',
                'T17_SYSEX_RESYNC': 'sysex_illegal_status_resync',
                'T17_UNBOUND_UART_POLICY': 'malformed_uart_stop_policy',
                'T17_POLICY_SHA': 'running_realtime_zero_velocity',
                'T17_OVERLAPPING_BYTES': 'running_realtime_zero_velocity'}[case_id]
    data = {'schema': 'M3_R08_RECOVERY_SCHEDULE_REQUEST_V1', 'scenario': scenario,
            'parser_sha256': m.PARSER_SHA, 'first_cycle': 6000, 'byte_spacing': 15000}
    expected = ('UNRESOLVED_RECOVERY_POLICY' if case_id == 'T17_UNBOUND_UART_POLICY' else
                'PARSER_POLICY_IDENTITY' if case_id == 'T17_POLICY_SHA' else
                'BYTE_SCHEDULE_OVERLAP' if case_id == 'T17_OVERLAPPING_BYTES' else 'RECOVERY_PLAN_GENERATED_SYNTHETIC')
    if case_id == 'T17_POLICY_SHA': data['parser_sha256'] = '0' * 64
    if case_id == 'T17_OVERLAPPING_BYTES': data['byte_spacing'] = 10000
    c.save(Path(output_dir) / 'INPUT_BEFORE_CALL.json', data)
    actual = c.call(m.analyze, data)
    c.save(Path(output_dir) / 'ACTUAL_BEFORE_ASSERT.json', actual)
    if case_id == 'T17_RUNNING_REALTIME_ZERO':
        assert actual['expected_message_semantics'][1]['kind'] == 'NOTE_OFF'
        assert actual['expected_message_semantics'][1]['after_byte_seq'] == 6
    if case_id == 'T17_HALF_MESSAGE_RESET':
        assert len(actual['resets']) == 2 and len(actual['expected_message_semantics']) == 1
        assert actual['expected_message_semantics'][0]['note'] == 75
    if actual['status'] == 'RECOVERY_PLAN_GENERATED_SYNTHETIC':
        assert actual['actual_application_time'].startswith('UNRESOLVED') and actual['internal_ready_driven'] is False
    return c.check_case(output_dir, data, actual, expected)
