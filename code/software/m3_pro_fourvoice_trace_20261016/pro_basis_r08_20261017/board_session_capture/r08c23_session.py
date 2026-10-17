"""Offline import only. Never opens a serial/instrument/programmer endpoint."""
import argparse
import importlib.util
import json
from pathlib import Path
import wave

ROLES = {'MIDI', 'UART', 'LA', 'WAV', 'SETTINGS', 'INPUT_PLAN', 'BITSTREAM',
         'SOURCE_MANIFEST', 'BOARD_IDENTITY', 'MEASUREMENT_PROFILE'}


def shared():
    p = Path(__file__).resolve().parents[1] / 'i2s_serial_compare/r08c_common.py'
    s = importlib.util.spec_from_file_location('r08c23_common', p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def inspect(data):
    c = shared()
    c.need(data.get('schema') == 'M3_R08_BOARD_SESSION_IMPORT_V1', 'BOARD_SESSION_SCHEMA')
    c.need(bool(data.get('session_id')) and data.get('origin') in ('SYNTHETIC', 'REAL_UNVERIFIED'), 'SESSION_ID_ORIGIN')
    records = data.get('files', [])
    roles = [r['role'] for r in records]
    c.need(set(roles) == ROLES and len(roles) == len(ROLES), 'MISSING_OR_DUPLICATE_RAW_INPUT', roles=roles)
    paths, indexed = {}, []
    for record in records:
        role = record['role']
        for key in ('session_id', 'fs_sha256', 'source_sha256', 'board_identity_sha256', 'timebase_id'):
            c.need(record.get(key) == data.get(key) and bool(data.get(key)), 'SESSION_BINDING_DIFFERENCE', role=role, field=key)
        c.need(record.get('original_unmodified') is True and record.get('format') == 'RAW_FILE', 'NOT_ORIGINAL_RAW', role=role)
        file = c.bounded_file(data['input_root'], record['path'])
        identity = c.identity(file)
        c.need(identity['sha256'] == record.get('sha256') and identity['bytes'] == record.get('bytes'), 'RAW_FILE_IDENTITY', role=role)
        paths[role] = file
        indexed.append({'role': role, **identity, 'session_id': data['session_id'], 'timebase_id': data['timebase_id']})
    for role, key in (('BITSTREAM', 'fs_sha256'), ('SOURCE_MANIFEST', 'source_sha256'), ('BOARD_IDENTITY', 'board_identity_sha256')):
        c.need(c.identity(paths[role])['sha256'] == data[key], 'SESSION_ARTIFACT_BINDING', role=role)
    c.need(paths['BITSTREAM'].suffix.lower() == '.fs', 'BITSTREAM_FILE_TYPE')
    settings = json.loads(paths['SETTINGS'].read_text(encoding='utf-8'))
    for key in ('session_id', 'fs_sha256', 'source_sha256', 'board_identity_sha256', 'timebase_id'):
        c.need(settings.get(key) == data[key], 'RAW_SETTINGS_BINDING', field=key)
    try:
        with wave.open(str(paths['WAV']), 'rb') as audio:
            frames, channels, width, rate = audio.getnframes(), audio.getnchannels(), audio.getsampwidth(), audio.getframerate()
            payload = audio.readframes(frames)
            c.need(frames > 0 and len(payload) == frames * channels * width, 'WAV_TRUNCATED')
    except (wave.Error, EOFError) as error:
        raise c.EvidenceError('RAW_WAV_REQUIRED', detail=str(error)) from error
    return c.report('INDEXED_SYNTHETIC_ONLY' if data['origin'] == 'SYNTHETIC' else 'PENDING_REAL_BOARD_SESSION_ADMISSION',
                    schema='M3_R08_BOARD_SESSION_INDEX_V1', session_id=data['session_id'], files=indexed,
                    wav={'frames': frames, 'channels': channels, 'sample_width': width, 'rate': rate,
                         'rate_is_not_FPGA_LRCLK_or_shared_timebase': True},
                    physical_identity_verified=False, hardware_operations=0)


def import_session(data, destination):
    c = shared()
    result = inspect(data)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    copied = []
    for item in result['files']:
        source = Path(item['path'])
        raw = source.read_bytes()
        c.need(c.sha(raw) == item['sha256'], 'RAW_CHANGED_DURING_IMPORT')
        target = destination / (item['role'] + source.suffix)
        with target.open('xb') as stream:
            stream.write(raw)
        c.need(c.identity(source)['sha256'] == item['sha256'], 'RAW_CHANGED_AFTER_IMPORT')
        copied.append({'role': item['role'], 'original': item, 'preserved_copy': c.identity(target)})
    result['preserved_originals'] = copied
    return result


def main():
    c = shared()
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args()
    data = json.loads(args.input.read_text(encoding='utf-8'))
    result = c.call(lambda value: import_session(value, args.output.parent / (args.output.stem + '_originals')), data)
    c.save(args.output, result)
    print(json.dumps({'status': result['status'], 'reason': result.get('reason')}))
    return 2 if result['status'] == 'REJECT' else (3 if result['status'].startswith('PENDING') else 0)


if __name__ == '__main__':
    raise SystemExit(main())
