"""Read-only SMF audit oracle; independent from the production importer/codec."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import struct

REAL_SHA = 'c0a8cb9f1ba3496a00367786a2b4ee5e0580be7b4bfbf0891b75e3b7475f634c'
# Independently transcribed from original bytes 0x62..0x127, not imported JSON.
REAL_NOTES = [65, 74, 65, 72, 70, 70, 69, 70, 72, 70, 68,
              60, 69, 60, 67, 65, 65, 64, 65, 67, 65, 63]
REAL_DURATIONS = ([960] * 5 + [480] * 6) * 2


def smf_inventory(raw):
    """Audit complete events including unsupported ones; never normalize input."""
    if raw[:8] != b'MThd\0\0\0\6':
        raise ValueError('ORACLE_HEADER')
    form, count, ppqn = struct.unpack('>HHH', raw[8:14])
    if form not in (0, 1) or not ppqn or ppqn & 0x8000:
        raise ValueError('ORACLE_TIMEBASE')
    events, cursor = [], 14
    for track in range(count):
        if raw[cursor:cursor + 4] != b'MTrk':
            raise ValueError('ORACLE_TRACK')
        size = int.from_bytes(raw[cursor + 4:cursor + 8], 'big')
        pos, end = cursor + 8, cursor + 8 + size
        if end > len(raw):
            raise ValueError('ORACLE_TRUNCATED')
        tick, running, index, ended = 0, None, 0, False

        def take(n):
            nonlocal pos
            if pos + n > end:
                raise ValueError('ORACLE_TRUNCATED_EVENT')
            value = raw[pos:pos + n]
            pos += n
            return value

        def vlq():
            value = 0
            for _ in range(4):
                b = take(1)[0]
                value = (value << 7) | (b & 127)
                if b < 128:
                    return value
            raise ValueError('ORACLE_VLQ')

        while pos < end:
            offset = pos
            tick += vlq()
            status = take(1)[0]
            pending = b''
            if status < 128:
                if running is None:
                    raise ValueError('ORACLE_RUNNING_STATUS')
                pending, status = bytes([status]), running
            item = dict(track=track, index=index, midi_tick=tick,
                        file_byte_offset=offset, status=status)
            index += 1
            if status == 255:
                running = None
                kind = take(1)[0]
                payload = take(vlq())
                item.update(kind='meta', meta_type=kind, payload_hex=payload.hex())
                if kind == 47:
                    if payload or pos != end:
                        raise ValueError('ORACLE_EOT')
                    ended = True
            elif 128 <= status < 240:
                running = status
                n = 1 if status >> 4 in (12, 13) else 2
                payload = pending + take(n - len(pending))
                if any(b > 127 for b in payload):
                    raise ValueError('ORACLE_DATA')
                item.update(kind='channel', payload_hex=payload.hex())
            elif status in (240, 247):
                running = None
                item.update(kind='sysex', payload_hex=take(vlq()).hex())
            else:
                raise ValueError('ORACLE_SYSTEM_EVENT')
            events.append(item)
        if not ended:
            raise ValueError('ORACLE_MISSING_EOT')
        cursor = end
    if cursor != len(raw):
        raise ValueError('ORACLE_TRAILING_BYTES')
    return dict(format=form, tracks=count, ppqn=ppqn, events=events)


def expected_notes(inventory):
    ordered = sorted(inventory['events'],
                     key=lambda x: (x['midi_tick'], x['track'], x['index']))
    elapsed, last, tempo = Fraction(0), 0, 500000
    events, origins, tempos = [], [], []
    for item in ordered:
        tick = item['midi_tick']
        elapsed += Fraction((tick - last) * tempo, inventory['ppqn'] * 1000000)
        last = tick
        sample = elapsed * 48000
        rounded = (sample + Fraction(1, 2)).numerator // (sample + Fraction(1, 2)).denominator
        if item['kind'] == 'meta':
            if item['meta_type'] == 81:
                if inventory['format'] == 1 and item['track'] != 0:
                    raise ValueError('ORACLE_TEMPO_TRACK')
                tempo = int.from_bytes(bytes.fromhex(item['payload_hex']), 'big')
                if not tempo:
                    raise ValueError('ORACLE_TEMPO_ZERO')
                tempos.append(dict(midi_tick=tick, us_per_quarter=tempo))
            elif item['meta_type'] not in (*range(1, 10), 0, 47, 88, 89):
                raise ValueError('ORACLE_UNSUPPORTED_META')
            continue
        status = item['status']
        if item['kind'] != 'channel' or status >> 4 not in (8, 9):
            raise ValueError('ORACLE_UNSUPPORTED_SEMANTICS')
        note, velocity = bytes.fromhex(item['payload_hex'])
        events.append(dict(tick=rounded, type='note_off' if status >> 4 == 8 or velocity == 0 else 'note_on',
                           channel=status & 15, note=note, velocity=velocity))
        origins.append(dict(**item, sample_numerator=sample.numerator,
                            sample_denominator=sample.denominator, sample_tick=rounded))
    return events, origins, tempos


def check(midi, score, records, upload):
    inventory = smf_inventory(midi)
    expected, origins, tempos = expected_notes(inventory)
    sha = hashlib.sha256(midi).hexdigest()
    if sha == REAL_SHA:
        # A second oracle: literal note/duration table, independently hand-decoded.
        manual, sample = [], 0
        for note, duration in zip(REAL_NOTES, REAL_DURATIONS):
            manual.append(dict(tick=sample, type='note_on', channel=4, note=note, velocity=96))
            sample += duration * 25  # 48000 * 500000 / (960 * 1000000)
            manual.append(dict(tick=sample, type='note_off', channel=4, note=note, velocity=96))
        if expected != manual or sample != 384000:
            raise ValueError('ORACLE_LITERAL_TABLE_MISMATCH')
    if set(score) != {'schema', 'sample_hz', 'score_id', 'events'} or score['schema'] != 1 or score['sample_hz'] != 48000:
        raise ValueError('ORACLE_JSON_CONTRACT')
    if score['events'] != expected:
        raise ValueError('ORACLE_MIDI_JSON_MISMATCH')
    literal = b''.join(struct.pack('<IBBBB', e['tick'], e['type'] == 'note_off',
                                   e['channel'], e['note'], e['velocity']) for e in expected)
    if records != literal:
        raise ValueError('ORACLE_RECORD_BYTES_MISMATCH')
    # Independent bit-serial CRC and upload decoder from the published readback
    # tool; no encoder or production MIDI parser is used in this oracle.
    import sys
    decoder_dir = Path(__file__).resolve().parents[1] / 'score_midi_import_candidate_20261014'
    sys.path.insert(0, str(decoder_dir))
    from offline_readback import decode_upload
    sid, reconstructed, session = decode_upload(upload)
    if sid != score['score_id'] or reconstructed != literal:
        raise ValueError('ORACLE_UPLOAD_BYTES_MISMATCH')
    rows = [dict(output_index=i, expected=e, decoded={
        'tick': int.from_bytes(records[i * 8:i * 8 + 4], 'little'),
        'kind': records[i * 8 + 4], 'channel': records[i * 8 + 5],
        'note': records[i * 8 + 6], 'velocity': records[i * 8 + 7]},
        source=origin, record_hex=records[i * 8:i * 8 + 8].hex(), matched=True)
        for i, (e, origin) in enumerate(zip(expected, origins))]
    return dict(status='INDEPENDENT_MIDI_JSON_BYTES_PASS', midi_sha256=sha,
                midi_format=inventory['format'], tracks=inventory['tracks'], ppqn=inventory['ppqn'],
                tempo_map=tempos, default_us_per_quarter=500000, session=session,
                events_compared=len(rows), final_event_sample=expected[-1]['tick'],
                hardware_pass_claim=False, rows=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('midi', 'score', 'records', 'upload', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    try:
        result = check(args.midi.read_bytes(), json.loads(args.score.read_text(encoding='utf-8')),
                       args.records.read_bytes(), args.upload.read_bytes())
    except Exception as error:
        result = dict(status='FAIL', error=f'{type(error).__name__}: {error}')
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}))
    return int(result['status'] == 'FAIL')


if __name__ == '__main__':
    raise SystemExit(main())
