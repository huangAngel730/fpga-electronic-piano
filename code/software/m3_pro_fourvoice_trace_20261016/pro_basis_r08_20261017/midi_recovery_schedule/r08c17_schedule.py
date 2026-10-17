"""New external schedules referencing frozen C6 parser policy, not a toy parser."""
import importlib.util
from pathlib import Path

PARSER_SHA = '336d867856a7b3956d524105137c035ec2637fea936538979182669987212071'
SCENARIOS = {
    'running_realtime_zero_velocity': {
        'bytes': [0x92, 67, 0xF8, 100, 69, 0xFA, 0, 0x82, 67, 32],
        'messages': [{'after_byte_seq': 3, 'kind': 'NOTE_ON', 'channel': 2, 'note': 67, 'velocity7': 100},
                     {'after_byte_seq': 6, 'kind': 'NOTE_OFF', 'channel': 2, 'note': 69, 'velocity7': 0},
                     {'after_byte_seq': 9, 'kind': 'NOTE_OFF', 'channel': 2, 'note': 67, 'velocity7': 32}],
        'refs': ['is_realtime_status', 'channel_data_pending', 'make_note_event']},
    'half_message_reset_new_status': {
        'bytes': [0x90, 72, 100, 0x90, 75, 96], 'reset_after_byte_seq': 1,
        'messages': [{'after_byte_seq': 5, 'kind': 'NOTE_ON', 'channel': 0, 'note': 75, 'velocity7': 96}],
        'refs': ['if (!rst_n)', 'running_status', 'channel_data_pending']},
    'sysex_illegal_status_resync': {
        'bytes': [0xF0, 1, 2, 0x93, 70, 88],
        'messages': [{'after_byte_seq': 5, 'kind': 'NOTE_ON', 'channel': 3, 'note': 70, 'velocity7': 88}],
        'refs': ['else if (sysex_active)', 'sysex_active', 'running_status']},
    'malformed_uart_stop_policy': {
        'bytes': [0x90, 70, 80], 'messages': [], 'unresolved': ['UART_BAD_STOP_TO_midi_byte_error_POLICY_NOT_BOUND'],
        'refs': ['midi_byte_error']},
}


def shared():
    p = Path(__file__).resolve().parents[1] / 'i2s_serial_compare/r08c_common.py'
    s = importlib.util.spec_from_file_location('r08c17_common', p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def analyze(data):
    c = shared()
    c.need(data.get('schema') == 'M3_R08_RECOVERY_SCHEDULE_REQUEST_V1', 'RECOVERY_SCHEDULE_SCHEMA')
    c.need(data.get('scenario') in SCENARIOS, 'UNKNOWN_RECOVERY_SCENARIO')
    c.need(data.get('parser_sha256') == PARSER_SHA, 'PARSER_POLICY_IDENTITY')
    root = Path(__file__).resolve().parents[5]
    spec = root / 'code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/midi_recovery_schedule/SPEC_ORIGINALS/midi_event_parser.sv'
    c.need(c.identity(spec)['sha256'] == PARSER_SHA, 'PARSER_POLICY_BYTES')
    scenario = SCENARIOS[data['scenario']]
    first, spacing = data['first_cycle'], data['byte_spacing']
    c.need(type(first) is int and first >= 0 and type(spacing) is int and spacing >= 14000, 'BYTE_SCHEDULE_OVERLAP')
    byte_plan = [{'byte_seq': i, 'value': value, 'start_cycle': first + i * spacing,
                  'arrival_not_before_cycle': first + i * spacing + 12800,
                  'event_application_cycle': None} for i, value in enumerate(scenario['bytes'])]
    resets = []
    if 'reset_after_byte_seq' in scenario:
        end = byte_plan[scenario['reset_after_byte_seq']]['arrival_not_before_cycle']
        resets = [{'cycle': end + 100, 'rst_n': 0}, {'cycle': end + 300, 'rst_n': 1}]
    lines = spec.read_text(encoding='utf-8').splitlines()
    refs = [{'text': text, 'source_lines': [i for i, line in enumerate(lines, 1) if text in line]}
            for text in scenario['refs'] if text != 'make_note_event']
    unresolved = scenario.get('unresolved', [])
    return c.report('UNRESOLVED_RECOVERY_POLICY' if unresolved else 'RECOVERY_PLAN_GENERATED_SYNTHETIC',
                    schema='M3_R08_EXTERNAL_MIDI_RECOVERY_PLAN_V1', clock_hz=40000000, baud=31250,
                    byte_plan=byte_plan, resets=resets, parser_policy=c.identity(spec), policy_refs=refs,
                    expected_message_semantics=scenario['messages'], unresolved=unresolved,
                    note_on_zero_reference='Frozen C6 audio_defs_pkg.make_note_event: velocity0 maps NOTE_OFF',
                    actual_application_time='UNRESOLVED_NO_CAPTURE', slot_retire_expectations=None,
                    internal_ready_driven=False, old_R62_events_reexecuted=False)


if __name__ == '__main__':
    raise SystemExit(shared().cli(analyze))
