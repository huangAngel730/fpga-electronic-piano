"""New H23 offline-only synthetic raw files; no device sessions opened."""
import importlib.util
import json
from pathlib import Path
import wave


def fixture(c, directory):
    directory.mkdir(parents=True, exist_ok=False)
    bodies = {'MIDI': ('midi.bin', bytes([0x90, 60, 64])), 'UART': ('uart.bin', b'SYNTHETIC UART BYTES\r\n'),
              'LA': ('la.csv', b'cycle,midi,bclk,ws,din\n0,1,0,0,0\n'),
              'INPUT_PLAN': ('plan.json', b'{"synthetic":true,"bytes":[144,60,64]}\n'),
              'BITSTREAM': ('fixture.fs', b'SYNTHETIC_NOT_A_PROGRAMMABLE_BITSTREAM\n'),
              'SOURCE_MANIFEST': ('sources.json', b'{"synthetic":true,"source":"fixture-only"}\n'),
              'BOARD_IDENTITY': ('board.json', b'{"synthetic":true,"unit":"NOT_A_REAL_BOARD"}\n'),
              'MEASUREMENT_PROFILE': ('profile.json', b'{"synthetic":true,"calibration":"NOT_PHYSICAL"}\n')}
    for name, raw in bodies.values(): (directory / name).write_bytes(raw)
    with wave.open(str(directory / 'audio.wav'), 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(48000)
        audio.writeframes(b'\x00\x00\x01\x00\xff\xff\x00\x00' * 4)
    common = {'session_id': 'SYNTHETIC_H23_NEW_SESSION', 'fs_sha256': c.identity(directory / 'fixture.fs')['sha256'],
              'source_sha256': c.identity(directory / 'sources.json')['sha256'],
              'board_identity_sha256': c.identity(directory / 'board.json')['sha256'], 'timebase_id': 'SYNTH_TRIGGER_23'}
    (directory / 'settings.json').write_text(json.dumps(common) + '\n', encoding='utf-8', newline='\n')
    files = []
    for role, name in [(role, value[0]) for role, value in bodies.items()] + [('WAV', 'audio.wav'), ('SETTINGS', 'settings.json')]:
        identity = c.identity(directory / name)
        files.append({'role': role, 'path': name, 'bytes': identity['bytes'], 'sha256': identity['sha256'],
                      'format': 'RAW_FILE', 'original_unmodified': True, **common})
    return {'schema': 'M3_R08_BOARD_SESSION_IMPORT_V1', 'origin': 'SYNTHETIC',
            'input_root': str(directory), 'files': files, **common}


def run_case(case_id, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    p = Path(__file__).with_name('r08c23_session.py')
    s = importlib.util.spec_from_file_location('r08c23_test_engine', p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    c = m.shared(); directory = Path(output_dir)
    data = fixture(c, directory / 'input_files')
    expected = {'H23_PRESERVE_RAW_FILES': 'INDEXED_SYNTHETIC_ONLY', 'H23_WRONG_SESSION': 'SESSION_BINDING_DIFFERENCE',
                'H23_REPLACED_UART': 'RAW_FILE_IDENTITY', 'H23_MISSING_MIDI': 'MISSING_OR_DUPLICATE_RAW_INPUT',
                'H23_WRONG_FS': 'SESSION_BINDING_DIFFERENCE', 'H23_PATH_ESCAPE': 'PATH_ESCAPE',
                'H23_SCREENSHOT_NOT_AUDIO': 'RAW_WAV_REQUIRED', 'H23_REAL_UNVERIFIED': 'PENDING_REAL_BOARD_SESSION_ADMISSION'}[case_id]
    by_role = {r['role']: r for r in data['files']}
    if case_id == 'H23_WRONG_SESSION': by_role['UART']['session_id'] = 'OTHER_SESSION'
    if case_id == 'H23_REPLACED_UART': (directory / 'input_files/uart.bin').write_bytes(b'REPLACED\n')
    if case_id == 'H23_MISSING_MIDI': data['files'] = [r for r in data['files'] if r['role'] != 'MIDI']
    if case_id == 'H23_WRONG_FS': data['fs_sha256'] = '0' * 64
    if case_id == 'H23_PATH_ESCAPE': by_role['MIDI']['path'] = '../escape.bin'
    if case_id == 'H23_SCREENSHOT_NOT_AUDIO':
        (directory / 'input_files/audio.wav').write_bytes(b'\x89PNG\r\n\x1a\nSCREENSHOT_NOT_WAVE')
        record = by_role['WAV']; identity = c.identity(directory / 'input_files/audio.wav')
        record['sha256'], record['bytes'] = identity['sha256'], identity['bytes']
    if case_id == 'H23_REAL_UNVERIFIED': data['origin'] = 'REAL_UNVERIFIED'
    c.save(Path(output_dir) / 'INPUT_BEFORE_CALL.json', data)
    actual = c.call(lambda value: m.import_session(value, directory / 'preserved_originals'), data)
    c.save(Path(output_dir) / 'ACTUAL_BEFORE_ASSERT.json', actual)
    if case_id in ('H23_PRESERVE_RAW_FILES', 'H23_REAL_UNVERIFIED'):
        assert len(actual['preserved_originals']) == 10
        assert all(item['original']['sha256'] == item['preserved_copy']['sha256'] for item in actual['preserved_originals'])
        assert actual['physical_identity_verified'] is False and actual['hardware_operations'] == 0
    return c.check_case(output_dir, data, actual, expected)
