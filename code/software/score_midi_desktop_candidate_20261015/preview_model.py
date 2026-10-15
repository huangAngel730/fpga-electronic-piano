"""Independent offline preview validation; no network, serial, or playback."""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import struct
import types

ROOT = Path(__file__).resolve().parents[3]
IMPORTER_DIR = ROOT / 'code/software/score_midi_import_candidate_20261014'
FROZEN = {
    IMPORTER_DIR / 'midi_import.py': '9564bb16b540fc5f1ad8b47a1508082df8936c9f2c32f10f1009bc5e513df1c1',
    IMPORTER_DIR / 'offline_readback.py': '8562c81fa69cb5f8128dfd99267ac2056df1209d015885cb74d9ebc4b076bae4',
    ROOT / 'code/software/score_transfer_v1/score_transfer.py': '8e2a065dcea4fef997da2b0fda7e16a314c65c436b654903ca388be407ddfc07',
    ROOT / 'code/docs/hardware/score_transfer_v1/PROTOCOL.md': '431b5cd7ae678c97bcb0be720a775b51a031f096161a0dbef36bdeea5f41f15b',
}
ARTIFACTS = ('score.json', 'provenance.json', 'records.bin', 'upload.bin', 'readback.json')
MAX_WINDOWS_FILE_UNITS = 259  # MAX_PATH=260 includes the terminating NUL.
MAX_WINDOWS_DIRECTORY_UNITS = 247  # Portable CreateDirectory reserve, without NUL.


class PreviewError(ValueError):
    """Untrusted or semantically inconsistent preview material."""


def identity(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def windows_path_units(path):
    """Windows length is UTF-16 code units, not Python Unicode code points."""
    return len(str(path).encode('utf-16-le')) // 2


def validate_windows_path(path, directory=False, label='path', reject_final_symlink=False):
    """Conservative common contract independent of registry/EXE longPathAware.

    Do not enable system policy, rewrite dependencies, use extended namespaces,
    or remap drives to make a frozen CLI accept an otherwise unsupported path.
    """
    absolute = Path(os.path.abspath(os.fspath(path)))
    if os.name != 'nt':
        if reject_final_symlink and absolute.is_symlink():
            raise PreviewError('INPUT_FILE_SYMLINK: final file link refused: ' + str(absolute))
        return absolute.resolve()
    limit = MAX_WINDOWS_DIRECTORY_UNITS if directory else MAX_WINDOWS_FILE_UNITS

    def check(candidate):
        text = str(candidate)
        units = windows_path_units(text)
        if text.startswith(('\\\\?\\', '\\\\.\\')):
            raise PreviewError(f'WINDOWS_PATH_LIMIT: {label}; extended/device namespace unsupported; {text}')
        if units > limit or any(windows_path_units(part) > 255 for part in candidate.parts[1:]):
            raise PreviewError(f'WINDOWS_PATH_LIMIT: {label}; UTF16={units}, maximum={limit}; '
                               f'choose a shorter workspace/input/export path; no tool started; {text}')

    # Check lexical length before resolve() can itself raise WinError 206, and
    # check again after resolving links so a short alias cannot hide a long path.
    check(absolute)
    if reject_final_symlink and absolute.is_symlink():
        raise PreviewError('INPUT_FILE_SYMLINK: final file link refused: ' + str(absolute))
    resolved = absolute.resolve()
    check(resolved)
    return resolved


def checked_read(path, maximum=16 * 1024 * 1024):
    path = validate_windows_path(path, label='input/artifact', reject_final_symlink=True)
    if path.is_symlink() or not path.is_file():
        raise PreviewError('INPUT_FILE: regular non-symlink file required: ' + str(path))
    with path.open('rb') as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise PreviewError('FILE_RESOURCE_LIMIT: ' + str(path))
    return raw


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise PreviewError('DUPLICATE_JSON_FIELD: ' + str(key))
        result[key] = value
    return result


def strict_json(raw):
    return json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(
                          PreviewError('JSON_CONSTANT: ' + value)))


def frozen_snapshot():
    result = {}
    for path, expected in FROZEN.items():
        raw = checked_read(path)
        actual = identity(raw)
        if actual['sha256'] != expected:
            raise PreviewError('FROZEN_DEPENDENCY_IDENTITY: ' + str(path))
        result[str(path)] = actual
    return result


def _decoder():
    frozen_snapshot()
    path = IMPORTER_DIR / 'offline_readback.py'
    raw = checked_read(path)
    if identity(raw)['sha256'] != FROZEN[path]:
        raise PreviewError('FROZEN_DEPENDENCY_IDENTITY: decoder changed')
    module = types.ModuleType('desktop_independent_readback')
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def _source_events(raw):
    """Separate byte walker and Fraction timeline, not production MIDI parser."""
    if len(raw) < 14 or raw[:8] != b'MThd\0\0\0\6':
        raise PreviewError('PREVIEW_SMF_HEADER')
    form, count, ppqn = struct.unpack('>HHH', raw[8:14])
    if form not in (0, 1) or not 1 <= count <= 256 or (form == 0 and count != 1):
        raise PreviewError('PREVIEW_SMF_FORMAT_TRACKS')
    if not ppqn or ppqn & 0x8000:
        raise PreviewError('PREVIEW_SMF_TIMEBASE')
    position, entries = 14, []
    for track in range(count):
        if raw[position:position + 4] != b'MTrk' or position + 8 > len(raw):
            raise PreviewError('PREVIEW_TRACK_HEADER')
        length = int.from_bytes(raw[position + 4:position + 8], 'big')
        start = position + 8
        end = start + length
        if end > len(raw):
            raise PreviewError('PREVIEW_TRACK_TRUNCATED')
        cursor, tick, running, index, ended = start, 0, None, 0, False

        def take(size):
            nonlocal cursor
            if size < 0 or cursor + size > end:
                raise PreviewError('PREVIEW_EVENT_TRUNCATED')
            value = raw[cursor:cursor + size]
            cursor += size
            return value

        def vlq():
            value = 0
            for _ in range(4):
                octet = take(1)[0]
                value = (value << 7) | (octet & 127)
                if octet < 128:
                    return value
            raise PreviewError('PREVIEW_VLQ_LENGTH')

        while cursor < end:
            offset = cursor - start
            tick += vlq()
            if tick > 0xffffffff or len(entries) >= 100000:
                raise PreviewError('PREVIEW_EVENT_RESOURCE_LIMIT')
            first = take(1)[0]
            pending = b''
            if first < 128:
                if running is None:
                    raise PreviewError('PREVIEW_RUNNING_STATUS')
                status, pending = running, bytes([first])
            else:
                status = first
            item = dict(midi_tick=tick, track=track, event_index=index,
                        track_byte_offset=offset)
            index += 1
            if 128 <= status <= 239:
                running = status
                if status >> 4 not in (8, 9):
                    raise PreviewError('PREVIEW_UNSUPPORTED_CHANNEL_EVENT')
                note, velocity = pending + take(2 - len(pending))
                if note > 127 or velocity > 127:
                    raise PreviewError('PREVIEW_DATA_BYTE')
                item.update(kind='note', type='note_off' if status >> 4 == 8 or velocity == 0 else 'note_on',
                            channel=status & 15, note=note, velocity=velocity)
            elif status == 255:
                running = None
                meta = take(1)[0]
                size = vlq()
                if size > 65536:
                    raise PreviewError('PREVIEW_META_RESOURCE_LIMIT')
                payload = take(size)
                if meta == 47:
                    if payload or cursor != end:
                        raise PreviewError('PREVIEW_EOT')
                    item['kind'] = 'end'
                    ended = True
                elif meta == 81:
                    if size != 3 or not int.from_bytes(payload, 'big') or (form == 1 and track != 0):
                        raise PreviewError('PREVIEW_TEMPO')
                    item.update(kind='tempo', us_per_quarter=int.from_bytes(payload, 'big'))
                elif meta in (*range(1, 10), 0, 88, 89):
                    if meta == 0 and (size != 2 or tick != 0):
                        raise PreviewError('PREVIEW_SEQUENCE_NUMBER')
                    if meta == 88 and (size != 4 or payload[0] == 0 or payload[1] > 7):
                        raise PreviewError('PREVIEW_TIME_SIGNATURE')
                    if meta == 89 and (size != 2 or int.from_bytes(payload[:1], 'big', signed=True) not in range(-7, 8) or payload[1] > 1):
                        raise PreviewError('PREVIEW_KEY_SIGNATURE')
                    item.update(kind='annotation', meta_type=meta, payload=identity(payload))
                else:
                    raise PreviewError('PREVIEW_UNSUPPORTED_META')
            else:
                raise PreviewError('PREVIEW_UNSUPPORTED_STATUS')
            entries.append(item)
        if not ended:
            raise PreviewError('PREVIEW_MISSING_EOT')
        position = end
    if position != len(raw):
        raise PreviewError('PREVIEW_TRAILING_FILE_DATA')
    entries.sort(key=lambda event: (event['midi_tick'], event['track'], event['event_index']))
    elapsed, previous, tempo = Fraction(0), 0, 500000
    events, origins, tempos, annotations, ends, active = [], [], [], [], {}, {}
    tempo_at_tick = {}
    for entry in entries:
        tick = entry['midi_tick']
        elapsed += Fraction((tick - previous) * tempo, ppqn * 1000000)
        previous = tick
        samples = elapsed * 48000
        rounded = (samples.numerator * 2 + samples.denominator) // (samples.denominator * 2)
        if rounded > 0xffffffff:
            raise PreviewError('PREVIEW_SAMPLE_RANGE')
        origin = {key: entry[key] for key in ('midi_tick', 'track', 'event_index', 'track_byte_offset')}
        if entry['kind'] == 'tempo':
            tempo = entry['us_per_quarter']
            if tick in tempo_at_tick and tempo_at_tick[tick] != tempo:
                raise PreviewError('PREVIEW_CONFLICTING_TEMPO')
            tempo_at_tick[tick] = tempo
            tempos.append(dict(**origin, us_per_quarter=tempo))
        elif entry['kind'] == 'note':
            key = (entry['channel'], entry['note'])
            if entry['type'] == 'note_on':
                if key in active:
                    raise PreviewError('PREVIEW_OVERLAPPING_NOTE')
                active[key] = entry['track']
            else:
                if key not in active or active[key] != entry['track']:
                    raise PreviewError('PREVIEW_NOTE_LIFETIME')
                del active[key]
            events.append(dict(tick=rounded, **{key: entry[key] for key in ('type', 'channel', 'note', 'velocity')}))
            origins.append(dict(**origin, output_index=len(events) - 1,
                                sample_tick=rounded, exact=samples))
        elif entry['kind'] == 'end':
            ends[str(entry['track'])] = dict(midi_tick=tick, sample_tick=rounded)
        else:
            annotations.append(dict(**origin, meta_type=entry['meta_type'], payload=entry['payload']))
    if active or not 1 <= len(events) <= 512:
        raise PreviewError('PREVIEW_NOTE_LIFETIME_CAPACITY')
    return dict(midi_format=form, tracks=count, ppqn=ppqn, events=events,
                origins=origins, tempos=tempos, annotations=annotations, ends=ends)


def load_preview(stage, source, expected_input=None):
    """Bind source bytes, original successful receipt, JSON, records and frames."""
    stage = validate_windows_path(stage, directory=True, label='preview stage')
    source = validate_windows_path(source, label='preview source', reject_final_symlink=True)
    raw = checked_read(source)
    input_id = identity(raw)
    if expected_input is not None and input_id != expected_input:
        raise PreviewError('INPUT_CHANGED: source differs from selected bytes')
    frozen = frozen_snapshot()
    files = {name: checked_read(stage / name, 2 * 1024 * 1024) for name in (*ARTIFACTS, 'receipt.json')}
    receipt = strict_json(files['receipt.json'])
    if (receipt.get('status') != 'OFFLINE_IMPORT_PASS' or receipt.get('exit_code') != 0
            or receipt.get('command') != 'import' or receipt.get('serial_calls') != 0
            or receipt.get('network_calls') != 0 or receipt.get('hardware_pass_claim') is not False):
        raise PreviewError('IMPORT_RECEIPT_REJECTED')
    if receipt.get('inputs') != {str(source): input_id}:
        raise PreviewError('IMPORT_INPUT_IDENTITY')
    for name in ARTIFACTS:
        if receipt.get('artifacts', {}).get(name) != identity(files[name]):
            raise PreviewError('ARTIFACT_IDENTITY: ' + name)
    for path in (IMPORTER_DIR / 'midi_import.py', IMPORTER_DIR / 'offline_readback.py'):
        if receipt.get('implementation', {}).get(str(path)) != frozen[str(path)]:
            raise PreviewError('IMPORT_IMPLEMENTATION_IDENTITY: ' + str(path))
    for path in (ROOT / 'code/software/score_transfer_v1/score_transfer.py',
                 ROOT / 'code/docs/hardware/score_transfer_v1/PROTOCOL.md'):
        if receipt.get('frozen_dependencies', {}).get(str(path)) != frozen[str(path)]:
            raise PreviewError('IMPORT_FROZEN_IDENTITY: ' + str(path))
    document = strict_json(files['score.json'])
    provenance = strict_json(files['provenance.json'])
    decoder = _decoder()
    checked = decoder.verify_roundtrip(document, files['records.bin'], files['upload.bin'])
    if strict_json(files['readback.json']) != checked or receipt.get('readback') != checked:
        raise PreviewError('READBACK_RECEIPT_MISMATCH')
    inventory = _source_events(raw)
    if document['events'] != inventory['events']:
        raise PreviewError('SOURCE_EVENT_MISMATCH')
    if (provenance.get('input') != input_id
            or any(provenance.get(key) != inventory[key] for key in ('midi_format', 'tracks', 'ppqn'))
            or provenance.get('default_us_per_quarter') != 500000
            or provenance.get('stable_sort') != ['midi_tick', 'track', 'event_index']
            or provenance.get('rounding') != 'absolute exact rational, nearest sample, ties up'
            or provenance.get('tempo_map') != inventory['tempos']
            or provenance.get('annotations_not_encoded') != inventory['annotations']
            or provenance.get('track_end_times_not_encoded') != inventory['ends']):
        raise PreviewError('PROVENANCE_MISMATCH')
    original_origins = provenance.get('event_origins')
    if type(original_origins) is not list or len(original_origins) != len(inventory['events']):
        raise PreviewError('PROVENANCE_ORIGINS')
    rows = []
    for index, (event, origin, original) in enumerate(zip(inventory['events'], inventory['origins'], original_origins)):
        for key, value in origin.items():
            if key != 'exact' and original.get(key) != value:
                raise PreviewError('PROVENANCE_EVENT_ORIGIN')
        numerator = original.get('exact_sample_numerator')
        denominator = original.get('exact_sample_denominator')
        if type(numerator) is not int or type(denominator) is not int or denominator <= 0 or Fraction(numerator, denominator) != origin['exact']:
            raise PreviewError('PROVENANCE_EXACT_TIME')
        rows.append(dict(index=index, **{key: value for key, value in origin.items() if key != 'exact'},
                         exact_sample_numerator=numerator, exact_sample_denominator=denominator,
                         **{key: event[key] for key in ('type', 'channel', 'note', 'velocity')},
                         record_hex=files['records.bin'][index * 8:index * 8 + 8].hex()))
    count = len(rows)
    final = rows[-1]['sample_tick']
    result = dict(schema=1, status='OFFLINE_PREVIEW_PASS', source=str(source), input=input_id,
                  midi_format=inventory['midi_format'], tracks=inventory['tracks'], ppqn=inventory['ppqn'],
                  sample_hz=48000, score_id=document['score_id'], session=checked['session'],
                  event_count=count, capacity=512, remaining=512 - count, last_event_sample=final,
                  last_event_seconds=f'{final / 48000:.9f}', default_us_per_quarter=500000,
                  tempo_map=inventory['tempos'], rows=rows, score=document,
                  source_description=provenance.get('source_description', ''),
                  license_note=provenance.get('license_note', ''),
                  identities={name: identity(data) for name, data in files.items()},
                  frozen_dependencies=frozen, serial_calls=0, network_calls=0, hardware_pass_claim=False,
                  timing='absolute exact rational; nearest sample, ties up',
                  scope='Offline note-event preview only; no playback, FPGA ACK or audio claim')
    if frozen_snapshot() != frozen or identity(checked_read(source)) != input_id:
        raise PreviewError('INPUT_OR_DEPENDENCY_CHANGED_DURING_PREVIEW')
    return result
