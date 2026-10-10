"""Extend the frozen T057 UART vectors; original sources remain read-only."""
import importlib.util
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[3]
LEGACY = ROOT / 'code/tb/input/score_transfer_candidate'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(out):
    old = load(LEGACY / 'vectors.py', 'original_uart_vectors')
    expected = old.build(out)
    lines = (out / 'plan.txt').read_text(encoding='ascii')
    cases = expected['cases']
    state = dict(cases[-1])

    def append(label, raw=None, publish=None, received=None, active=None, op='S'):
        nonlocal state, lines
        state = dict(state)
        state.update(id=len(cases)+1, label=label, op=op,
                     raw=raw.hex() if raw else None, error=0, last_error=0)
        if publish:
            sid, records = publish
            state.update(score_id=sid, committed_count=len(records)//8,
                         pulses=state['pulses']+1)
        if received is not None:
            state['received'] = received
        if active is not None:
            state['active'] = active
        cases.append(state)
        lines += f'{op} {state["id"]} {len(raw) if raw else 0}\n'
        if raw:
            lines += ' '.join(f'{b:02x}' for b in raw)+'\n'

    for sid, count in ((19, 1), (20, 33)):
        doc = old.score(sid, count)
        expected['scores'][str(sid)] = doc
        _, records = old.pc.encode_score(doc)
        (out / f'score{sid}.json').write_text(json.dumps(doc)+'\n', encoding='utf-8')
        begin = struct.pack('<IHHHI', sid, count, len(records), old.pc.crc(records), 48000)
        append(f'ram{sid}_begin', old.pc.frame(1, sid, 0, payload=begin), received=0, active=1)
        offset, seq = 0, 1
        while offset < len(records):
            # First byte then 128-byte payload crosses every byte-lane boundary.
            length = 1 if offset == 0 else 128
            part = records[offset:offset+length]
            append(f'ram{sid}_data{seq}', old.pc.frame(2, sid, seq, offset, part),
                   received=offset+len(part))
            offset += len(part)
            seq += 1
        append(f'ram{sid}_commit', old.pc.frame(3, sid, seq), publish=(sid, records), active=0)
        append(f'ram{sid}_public', op='Q')
        for index in range(count):
            append(f'ram{sid}_read{index}', old.pc.frame(6, sid, index, index))
    (out / 'plan.txt').write_text(lines, encoding='ascii')
    (out / 'expected.json').write_text(json.dumps(expected, indent=2)+'\n', encoding='utf-8')
    # Independently assemble public truth from source JSON, not PC record bytes.
    oracle = []
    for case in cases:
        oracle.append(f'{case["id"]} {case["committed_count"]} {case["pulses"]} {case["score_id"]}\n')
        if case['committed_count']:
            for event in expected['scores'][str(case['score_id'])]['events']:
                raw = event['tick'].to_bytes(4, 'little') + bytes((
                    int(event['type']=='note_off' or event['velocity']==0),
                    event['channel'], event['note'], event['velocity']))
                oracle.append(f'{int.from_bytes(raw,"little"):016x}\n')
    (out / 'public_oracle.txt').write_text(''.join(oracle), encoding='ascii')
    return expected
