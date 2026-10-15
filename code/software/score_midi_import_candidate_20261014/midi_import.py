"""Strict local Standard MIDI File to frozen T057 note records; no serial I/O."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import struct
import sys
import types

SAMPLE_HZ = 48000
MAX_TICK = 0xFFFFFFFF
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TRACKS = 256
MAX_PARSED_EVENTS = 100000
MAX_META_BYTES = 65536
ROOT = Path(__file__).resolve().parents[3]
ENCODER = ROOT / 'code/software/score_transfer_v1/score_transfer.py'
PROTOCOL = ROOT / 'code/docs/hardware/score_transfer_v1/PROTOCOL.md'
ENCODER_SHA = '8e2a065dcea4fef997da2b0fda7e16a314c65c436b654903ca388be407ddfc07'
PROTOCOL_SHA = '431b5cd7ae678c97bcb0be720a775b51a031f096161a0dbef36bdeea5f41f15b'


class MidiImportError(ValueError):
    """A malformed or semantically unsupported local input."""


def fail(code, detail):
    raise MidiImportError(f'{code}: {detail}')


def identity(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


class Reader:
    def __init__(self, raw, label):
        self.raw, self.pos, self.label = raw, 0, label

    def take(self, count):
        if count < 0 or self.pos + count > len(self.raw):
            fail('TRUNCATED', f'{self.label} byte {self.pos}, need {count}')
        data = self.raw[self.pos:self.pos + count]
        self.pos += count
        return data

    def byte(self):
        return self.take(1)[0]

    def vlq(self):
        value = 0
        for _ in range(4):
            byte = self.byte()
            value = value * 128 + (byte & 127)
            if not byte & 128:
                return value
        fail('VLQ_LENGTH', f'{self.label} byte {self.pos}: more than four bytes')


def _read_track(raw, track, event_budget):
    reader = Reader(raw, f'track {track}')
    tick, running, index = 0, None, 0
    result = []
    while reader.pos < len(raw):
        offset = reader.pos
        tick += reader.vlq()
        if tick > MAX_TICK:
            fail('MIDI_TICK_RANGE', f'track {track} absolute tick exceeds u32')
        event_budget[0] += 1
        if event_budget[0] > MAX_PARSED_EVENTS:
            fail('EVENT_RESOURCE_LIMIT', str(MAX_PARSED_EVENTS))
        first = reader.byte()
        if first < 128:
            if running is None:
                fail('RUNNING_STATUS', f'track {track} byte {offset}')
            status, pending = running, bytes([first])
        else:
            status, pending = first, b''
        origin = {'midi_tick': tick, 'track': track, 'event_index': index,
                  'track_byte_offset': offset}
        index += 1
        if 0x80 <= status <= 0xEF:
            running = status
            kind, channel = status >> 4, status & 15
            size = 1 if kind in (0xC, 0xD) else 2
            data = pending + reader.take(size - len(pending))
            if any(value > 127 for value in data):
                fail('MIDI_DATA_BYTE', f'track {track} byte {offset}')
            if kind not in (8, 9):
                fail('UNSUPPORTED_CHANNEL_EVENT', f'0x{status:02x}, track {track}, tick {tick}')
            note, velocity = data
            event_type = 'note_off' if kind == 8 or velocity == 0 else 'note_on'
            result.append({**origin, 'kind': 'note', 'type': event_type,
                           'channel': channel, 'note': note, 'velocity': velocity})
        elif status == 0xFF:
            running = None
            meta_type = reader.byte()
            if meta_type > 127:
                fail('META_TYPE', f'0x{meta_type:02x}')
            size = reader.vlq()
            if size > MAX_META_BYTES:
                fail('META_RESOURCE_LIMIT', str(size))
            data = reader.take(size)
            if meta_type == 0x2F:
                if size != 0:
                    fail('END_OF_TRACK_LENGTH', str(size))
                if reader.pos != len(raw):
                    fail('TRAILING_TRACK_DATA', f'track {track}')
                result.append({**origin, 'kind': 'end'})
                return result
            if meta_type == 0x51:
                if size != 3 or int.from_bytes(data, 'big') == 0:
                    fail('TEMPO', 'need nonzero 3-byte microseconds per quarter')
                result.append({**origin, 'kind': 'tempo', 'us_per_quarter': int.from_bytes(data, 'big')})
            elif 1 <= meta_type <= 9:
                result.append({**origin, 'kind': 'annotation', 'meta_type': meta_type,
                               'payload': identity(data)})
            elif meta_type == 0:
                if size != 2 or tick != 0:
                    fail('SEQUENCE_NUMBER', 'need two bytes at MIDI tick 0')
                result.append({**origin, 'kind': 'annotation', 'meta_type': meta_type,
                               'payload': identity(data)})
            elif meta_type == 0x58:
                if size != 4 or data[0] == 0 or data[1] > 7:
                    fail('TIME_SIGNATURE', 'invalid length/numerator/denominator')
                result.append({**origin, 'kind': 'annotation', 'meta_type': meta_type,
                               'payload': identity(data)})
            elif meta_type == 0x59:
                if size != 2 or int.from_bytes(data[:1], 'big', signed=True) not in range(-7, 8) or data[1] > 1:
                    fail('KEY_SIGNATURE', 'invalid length/key/mode')
                result.append({**origin, 'kind': 'annotation', 'meta_type': meta_type,
                               'payload': identity(data)})
            else:
                fail('UNSUPPORTED_META', f'0x{meta_type:02x}, track {track}, tick {tick}')
        elif status in (0xF0, 0xF7):
            fail('UNSUPPORTED_SYSEX', f'track {track}, tick {tick}')
        else:
            fail('UNSUPPORTED_STATUS', f'0x{status:02x}, track {track}')
    fail('MISSING_END_OF_TRACK', f'track {track}')


def convert_midi(raw, score_id=1):
    """Return strict T057 document and source map. Time rounding: nearest, ties up."""
    if type(raw) is not bytes:
        fail('INPUT_TYPE', 'raw must be bytes')
    if type(score_id) is not int or not 0 <= score_id <= MAX_TICK:
        fail('SCORE_ID', 'need u32 integer')
    if len(raw) > MAX_FILE_BYTES:
        fail('FILE_RESOURCE_LIMIT', str(MAX_FILE_BYTES))
    reader = Reader(raw, 'file')
    if reader.take(4) != b'MThd':
        fail('HEADER_MAGIC', 'not an SMF MThd header')
    header_length = int.from_bytes(reader.take(4), 'big')
    if header_length != 6:
        fail('HEADER_LENGTH', 'only the standard six-byte header is supported')
    midi_format, tracks, ppqn = struct.unpack('>HHH', reader.take(6))
    if midi_format not in (0, 1):
        fail('MIDI_FORMAT', 'only simultaneous formats 0 and 1')
    if not 1 <= tracks <= MAX_TRACKS or (midi_format == 0 and tracks != 1):
        fail('TRACK_COUNT', str(tracks))
    if ppqn & 0x8000:
        fail('SMPTE_TIMEBASE', 'SMPTE division is unsupported')
    if ppqn == 0:
        fail('PPQN', 'division must be nonzero')
    parsed, event_budget = [], [0]
    for track in range(tracks):
        if reader.take(4) != b'MTrk':
            fail('TRACK_MAGIC', f'track {track}')
        length = int.from_bytes(reader.take(4), 'big')
        parsed.extend(_read_track(reader.take(length), track, event_budget))
    if reader.pos != len(raw):
        fail('TRAILING_FILE_DATA', f'byte {reader.pos}')
    parsed.sort(key=lambda event: (event['midi_tick'], event['track'], event['event_index']))
    tempo_values = defaultdict(set)
    for event in parsed:
        if event['kind'] == 'tempo':
            if midi_format == 1 and event['track'] != 0:
                fail('TEMPO_TRACK', 'format 1 tempo must be in conductor track 0')
            tempo_values[event['midi_tick']].add(event['us_per_quarter'])
    if any(len(values) > 1 for values in tempo_values.values()):
        fail('CONFLICTING_TEMPO', 'different tempi at the same absolute tick')
    tempo, previous, elapsed_numerator = 500000, 0, 0
    denominator = ppqn * 1000000
    events, origins, annotations, tempo_map, active = [], [], [], [], {}
    end_ticks = {}
    for event in parsed:
        tick = event['midi_tick']
        elapsed_numerator += (tick - previous) * tempo
        previous = tick
        sample_numerator = elapsed_numerator * SAMPLE_HZ
        sample_tick = (2 * sample_numerator + denominator) // (2 * denominator)
        if sample_tick > MAX_TICK:
            fail('SAMPLE_TICK_RANGE', f'MIDI tick {tick} converts outside u32')
        origin = {key: event[key] for key in ('midi_tick', 'track', 'event_index', 'track_byte_offset')}
        if event['kind'] == 'tempo':
            tempo = event['us_per_quarter']
            tempo_map.append({**origin, 'us_per_quarter': tempo})
        elif event['kind'] == 'note':
            key = event['channel'], event['note']
            if event['type'] == 'note_on':
                if key in active:
                    fail('OVERLAPPING_NOTE_IDENTITY', f'{key}; track identity cannot be carried by T057')
                active[key] = origin
            else:
                if key not in active:
                    fail('UNMATCHED_NOTE_OFF', f'{key}, track {event["track"]}')
                if active[key]['track'] != event['track']:
                    fail('CROSS_TRACK_NOTE_LIFETIME', f'{key}; note-on/off tracks differ')
                del active[key]
            events.append({'tick': sample_tick, **{key: event[key] for key in ('type', 'channel', 'note', 'velocity')}})
            origins.append({**origin, 'output_index': len(events) - 1,
                            'sample_tick': sample_tick,
                            'exact_sample_numerator': sample_numerator,
                            'exact_sample_denominator': denominator})
            if len(events) > 512:
                fail('CAPACITY', 'more than 512 note events; no truncation')
        elif event['kind'] == 'end':
            end_ticks[str(event['track'])] = {'midi_tick': tick, 'sample_tick': sample_tick}
        else:
            annotations.append({**origin, 'meta_type': event['meta_type'], 'payload': event['payload']})
    if active:
        fail('UNFINISHED_NOTE_ON', f'{len(active)} notes remain active; no invented NoteOff')
    if not events:
        fail('EMPTY_SCORE', 'need 1..512 note events')
    document = {'schema': 1, 'sample_hz': SAMPLE_HZ, 'score_id': score_id, 'events': events}
    provenance = {
        'input': identity(raw), 'midi_format': midi_format, 'tracks': tracks, 'ppqn': ppqn,
        'default_us_per_quarter': 500000, 'rounding': 'absolute exact rational, nearest sample, ties up',
        'stable_sort': ['midi_tick', 'track', 'event_index'], 'tempo_map': tempo_map,
        'event_origins': origins, 'annotations_not_encoded': annotations, 'track_end_times_not_encoded': end_ticks,
        'mapping': 'channel/note/velocity preserved; track remains provenance only; zero-velocity NoteOn becomes NoteOff',
        'scope': 'note-event transport only; no General MIDI instrument/percussion, playback, FPGA ACK or audio claim',
    }
    return document, provenance


def load_encoder():
    """Execute a verified original encoder buffer, without calling its serial CLI."""
    raw = ENCODER.read_bytes()
    if identity(raw)['sha256'] != ENCODER_SHA or identity(PROTOCOL.read_bytes())['sha256'] != PROTOCOL_SHA:
        fail('FROZEN_DEPENDENCY_IDENTITY', 'original T057 encoder or protocol changed')
    module = types.ModuleType('t057_frozen_codec')
    module.__file__ = str(ENCODER)
    exec(compile(raw, str(ENCODER), 'exec'), module.__dict__)
    return module


def _json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail('DUPLICATE_JSON_FIELD', str(key))
        result[key] = value
    return result


def _bounded_read(path, limit):
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        fail('VERIFY_RESOURCE_LIMIT', f'{path.name} exceeds {limit} bytes')
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    imp = commands.add_parser('import', help='import a local SMF; no network or serial')
    selection = imp.add_mutually_exclusive_group(required=True)
    selection.add_argument('--input', type=Path)
    selection.add_argument('--choose-file', action='store_true', help='open local file picker')
    imp.add_argument('--score-id', type=int, default=1)
    imp.add_argument('--session', type=int, default=1)
    imp.add_argument('--source-description', default='Local input; origin not independently verified')
    imp.add_argument('--license-note', default='Not supplied; redistribution rights not verified')
    imp.add_argument('--output', type=Path, required=True)
    check = commands.add_parser('verify', help='independently compare local score/records/upload')
    for option in ('score', 'records', 'upload', 'output'):
        check.add_argument('--' + option, type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        print(f'OUTPUT_REFUSED: {exc}', file=sys.stderr)
        return 2
    receipt = {'schema': 1, 'command': args.command, 'status': 'FAIL', 'exit_code': 1,
               'hardware_pass_claim': False, 'serial_calls': 0, 'network_calls': 0,
               'git_published': False, 'inputs': {}, 'artifacts': {}}
    try:
        from offline_readback import verify_roundtrip
        receipt['implementation'] = {
            str(path): identity(path.read_bytes()) for path in (
                Path(__file__).resolve(), Path(__file__).with_name('offline_readback.py').resolve(),
                Path(sys.executable).resolve())}
        receipt['python_version'] = sys.version
        if args.command == 'import':
            input_path = args.input
            if args.choose_file:
                import tkinter
                from tkinter import filedialog
                window = tkinter.Tk()
                window.withdraw()
                try:
                    selected = filedialog.askopenfilename(title='Choose local MIDI file', filetypes=[('MIDI', '*.mid *.midi'), ('All', '*')])
                finally:
                    window.destroy()
                if not selected:
                    fail('SELECTION_CANCELLED', 'no input file selected')
                input_path = Path(selected)
            input_path = input_path.resolve()
            with input_path.open('rb') as stream:
                raw = stream.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES:
                fail('FILE_RESOURCE_LIMIT', str(MAX_FILE_BYTES))
            receipt['inputs'][str(input_path)] = identity(raw)
            document, provenance = convert_midi(raw, args.score_id)
            provenance['source_description'] = args.source_description
            provenance['license_note'] = args.license_note
            codec = load_encoder()
            score_id, records = codec.encode_score(document)
            upload = b''.join(codec.upload_frames(score_id, records, args.session))
            receipt['readback'] = verify_roundtrip(document, records, upload)
            _json(output / 'score.json', document)
            _json(output / 'provenance.json', provenance)
            with (output / 'records.bin').open('xb') as stream:
                stream.write(records)
            with (output / 'upload.bin').open('xb') as stream:
                stream.write(upload)
            _json(output / 'readback.json', receipt['readback'])
            receipt['frozen_dependencies'] = {str(ENCODER): identity(ENCODER.read_bytes()), str(PROTOCOL): identity(PROTOCOL.read_bytes())}
            if receipt['frozen_dependencies'][str(ENCODER)]['sha256'] != ENCODER_SHA or receipt['frozen_dependencies'][str(PROTOCOL)]['sha256'] != PROTOCOL_SHA:
                fail('FROZEN_DEPENDENCY_IDENTITY', 'dependency changed during conversion')
        else:
            score_raw, records, upload = (_bounded_read(path, limit) for path, limit in zip(
                (args.score, args.records, args.upload), (2 * 1024 * 1024, 4096, 65536)))
            receipt['inputs'] = {str(path.resolve()): identity(raw) for path, raw in zip((args.score, args.records, args.upload), (score_raw, records, upload))}
            document = json.loads(score_raw.decode('utf-8'), object_pairs_hook=_unique_pairs)
            receipt['readback'] = verify_roundtrip(document, records, upload)
            _json(output / 'readback.json', receipt['readback'])
        receipt.update(status='OFFLINE_IMPORT_PASS' if args.command == 'import' else 'OFFLINE_VERIFY_PASS', exit_code=0)
    except Exception as exc:
        receipt['error'] = f'{type(exc).__name__}: {exc}'
    for path in sorted(output.iterdir()):
        if path.is_file():
            receipt['artifacts'][path.name] = identity(path.read_bytes())
    _json(output / 'receipt.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False))
    return receipt['exit_code']


if __name__ == '__main__':
    sys.exit(main())
