"""Pinned M1 closure and normal-window R05 reference adapter; no HDL calls.

Golden generation takes controls, reset/frame/request timing, never PCM outputs.
Unsupported overlap/cancellation is rejected, not approximated or filtered out.
Frozen M1 arithmetic is loaded from verified archive bytes, never the worktree.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import types
import zipfile

from analyze_existing import STAGE, PINS, identity, parse, decode_event

PACKAGE = Path('E:/FPGA/GAOYUNFPGA/Callback3/chat9/M1_Failure判据修复与R05支援交接_20261015.zip')
PACKAGE_SHA = '842fa8f75356090440a5e8237acafc209620d114f9e3c0ce2eab5ffdf30862da'
ALGORITHM = 'algorithm_reference/M1_双音色与立体声延迟完整链_20261014.zip'
ALGORITHM_SHA = '5c18926ae307301e91ec0e44dcf4a48b2fb57adec71ad46c494b14df59913b06'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, diagnostic):
    if not ok:
        raise ValueError(diagnostic)


def load_module(name, data):
    module = types.ModuleType(name)
    module.__file__ = 'verified-M1-archive/' + name + '.py'
    sys.modules[name] = module
    exec(compile(data, module.__file__, 'exec'), module.__dict__)
    return module


def closure():
    blob = PACKAGE.read_bytes()
    require(len(blob) == 750224 and sha(blob) == PACKAGE_SHA, 'M1_PACKAGE_IDENTITY')
    z = zipfile.ZipFile(io.BytesIO(blob))
    require(z.testzip() is None and len(set(z.namelist())) == len(z.namelist()), 'M1_CRC_OR_DUPLICATE')
    manifest = parse(z.read('MANIFEST.json').decode('utf-8'))
    names = set()
    for item in manifest['members']:
        data = z.read(item['path'])
        require(len(data) == item['bytes'] and sha(data) == item['sha256'], 'M1_MEMBER:' + item['path'])
        names.add(item['path'])
    require(names | {'MANIFEST.json'} == set(z.namelist()), 'M1_MEMBER_SET')
    algorithm = z.read(ALGORITHM)
    require(len(algorithm) == 416469 and sha(algorithm) == ALGORITHM_SHA, 'M1_ALGORITHM_IDENTITY')
    a = zipfile.ZipFile(io.BytesIO(algorithm))
    require(a.testzip() is None, 'M1_ALGORITHM_CRC')
    bindings = parse(z.read('INPUT_AND_ALGORITHM_IDENTITY.json').decode('utf-8'))
    checked = []
    for entry in bindings['m1_frozen_bindings'] + bindings['rom']:
        member = entry.get('member', entry.get('path'))
        expected = entry.get('r05_sha256', entry.get('sha256'))
        actual = identity(STAGE / member.removeprefix('inputs/'))
        require(actual['sha256'] == expected, 'EXECUTED_BINDING:' + member)
        checked.append(actual)
    for entry in bindings['frozen_models_and_auxiliary_rom']:
        data = z.read(entry['copy'])
        require(len(data) == entry['bytes'] and sha(data) == entry['sha256'], 'MODEL_IDENTITY')
    dds = load_module('dds_model', z.read('algorithm_reference/frozen/dds_model.py'))
    env = load_module('chat9_frozen_envelope', z.read('algorithm_reference/frozen/envelope_model.py'))
    alloc = load_module('chat9_frozen_allocator', z.read('algorithm_reference/frozen/allocator_oracle.py'))
    delay_member = 'code/model/m1_timbre_delay_chain_candidate_20261014/delay_effect_fixed.py'
    delay = load_module('chat9_frozen_delay', a.read(delay_member))
    report = {'package': identity(PACKAGE), 'manifest_members_verified': len(names),
              'algorithm_sha256': sha(algorithm), 'bindings': checked,
              'model_members': bindings['frozen_models_and_auxiliary_rom'],
              'delay_member': delay_member, 'delay_sha256': sha(a.read(delay_member)),
              'old_missing_package_resolved': True}
    return (dds, env, alloc, delay), report


def rom(name):
    text = (STAGE / 'rom' / name).read_text(encoding='ascii')
    return [int(word, 16) for line in text.splitlines()
            for word in line.split('//')[0].split()]


def read_inputs():
    # Identity pins are gates; malformed or different capture requires a new plan.
    for name in ('REAL_INPUTS.jsonl', 'REAL_CAPTURE.jsonl'):
        require(identity(STAGE / name)['sha256'] == PINS[STAGE / name], 'CAPTURE_IDENTITY')
    controls, config, resets = [], [], []
    last_rst = None
    with (STAGE / 'REAL_INPUTS.jsonl').open(encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            row = parse(line)
            if row['kind'] != 'TICK':
                continue
            cycle = row['cycle']
            if row['rst_n'] != last_rst:
                resets.append((cycle, row['rst_n']))
                last_rst = row['rst_n']
            if row['rst_n'] and row['event_valid'] and row['event_ready']:
                controls.append((cycle, decode_event(row['event_data_hex']), number))
            if row['rst_n'] and row['config_valid'] and row['config_ready']:
                config.append(cycle)
    requests, frames, observed = [], [], []
    with (STAGE / 'REAL_CAPTURE.jsonl').open(encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            row = parse(line)
            if row['kind'] != 'TICK':
                continue
            if row['frame_tick']:
                frames.append(row['cycle'])
            if row['request_accept']:
                requests.append({'cycle': row['cycle'], 'id': row['request_id'], 'epoch': row['epoch']})
            if row['commit']:
                observed.append({'cycle': row['cycle'], 'id': row['committed_id'], 'epoch': row['epoch'],
                                 'left': row['left'], 'right': row['right'], 'clip': row['clipped'],
                                 'source_line': number})
    return controls, config, resets, requests, frames, observed


def golden(models, controls, config, resets, requests, frames):
    """Normal, isolated request windows only. No observed result enters here.

    Source FSM: request r -> WAIT r+1 -> SETTLE countdown -> CAPTURE r+9,
    control output r+13 -> pitch launch r+14/output r+21 -> tick r+23,
    SNAPSHOT r+28 -> mix register r+29 -> effect take r+30 -> output r+33,
    result_hold accepts r+34 -> buffer commit pre-NBA r+35.
    """
    dds, env, alloc, delay = models
    require(requests and config == [83], 'UNSUPPORTED_CONFIG_CALENDAR')
    require(resets[0][1] == 0 and len(resets) == 3 and resets[1][1] == 1
            and resets[2][1] == 0, 'UNSUPPORTED_RESET_CALENDAR')
    require(all(r['epoch'] == 0 for r in requests), 'UNSUPPORTED_EPOCH')
    require([r['id'] for r in requests] == list(range(1, len(requests) + 1)), 'REQUEST_ID_SEQUENCE')
    for r in requests:
        c = r['cycle']
        require(c - 2 in frames and config[0] < c, 'REQUEST_NOT_NORMAL_FRAME')
        require(not any(c <= f <= c + 35 for f in frames), 'UNSUPPORTED_FRAME_OVERLAP')
        require(resets[1][0] < c and c + 35 < resets[2][0], 'UNSUPPORTED_RESET_OVERLAP')
        require(not any(c - 5 <= e <= c + 35 for e, _, _ in controls), 'UNSUPPORTED_DISPATCH_OVERLAP')
    require(all(b['cycle'] - a['cycle'] > 35 for a, b in zip(requests, requests[1:])), 'REQUEST_OVERLAP')
    events = []
    for c, d, line in controls:
        require(d['source_id'] == 0 and d['channel'] == 0, 'UNSUPPORTED_IDENTITY')
        if d['event_type'] == 4 and d['control_id'] == 5 and d['control_value'] <= 1:
            events.append((c + 1, 'program', (d, line)))
        else:
            require(d['event_type'] == 0 and d['velocity'] > 0, 'UNSUPPORTED_CONTROL')
            events.append((c + 4, 'note', (d, line)))
    for r in requests:
        events += [(r['cycle'] + 23, 'tick', r), (r['cycle'] + 28, 'snapshot', r),
                   (r['cycle'] + 30, 'effect', r)]
    gain, piano, triangle = rom('velocity_gain_rom.mem'), rom('piano_band_4x256_8191.mem'), rom('triangle_wavetable.hex')
    octaves, sub, sine = rom('oct_ratio_q16.mem'), rom('sub_ratio_q16.mem'), rom('lfo_sine_q15.mem')
    allocator = alloc.Oracle()
    envelopes = [env.Envelope(gain) for _ in range(4)]
    for envelope in envelopes:
        envelope.reset(resets[1][0] - 1)
    oscillators = [dds.PianoDDS() for _ in range(4)]
    slots = [None] * 4
    waves = [0] * 4
    program = 0
    generations = [0] * 4
    effect = delay.DelayEffectFixed(1024)
    tokens, results, allocations = {}, [], []
    for c, tag, value in sorted(events, key=lambda x: x[0]):
        if tag == 'program':
            program = value[0]['control_value']
        elif tag == 'note':
            d, line = value
            _, lane, _, _, kind = allocator.step(1, 1, 0, d['source_id'], d['channel'], d['note_number'], 0)
            generations[lane] += 1
            fcw = dds.note_fcw(d['note_number'])
            slots[lane] = dict(note=d['note_number'], velocity=d['velocity'], program=program,
                               generation=generations[lane], base_fcw=fcw)
            envelopes[lane].quiet_until(c)
            envelopes[lane].edge(on=True, velocity=d['velocity'])
            oscillators[lane].edge(fcw, d['velocity'], note_on=True)
            allocations.append(dict(input_line=line, voice_note_on_cycle=c, lane=lane, kind=kind, **slots[lane]))
        elif tag == 'tick':
            for i in range(4):
                slot = slots[i]
                fcw = dds.pitch_mod(slot['base_fcw'], 0, 0, 2, 0, octaves, sub, sine) if slot else 0
                before = oscillators[i].edge(fcw, slot['velocity'] if slot else 0, tick=True)
                # Piano continuous ROM + three registers settle before SNAPSHOT.
                # Triangle captures pre-increment phase on tick and holds E+4.
                address = before['phase_acc'] >> 22
                waves[i] = dds.signed(triangle[address], 16) if slot and slot['program'] else dds.signed(
                    piano[(oscillators[i].active_table << 8) | (oscillators[i].phase >> 24)], 16)
                envelopes[i].quiet_until(c)
                envelopes[i].edge(tick=True)
        elif tag == 'snapshot':
            lanes = []
            for i in range(4):
                envelopes[i].quiet_until(c)
                level = envelopes[i].snapshot()['envelope']
                lanes.append(dict(lane=i, slot=slots[i].copy() if slots[i] else None,
                                  phase=oscillators[i].phase, wave=waves[i], envelope=level,
                                  pcm=env.voice_pcm(waves[i], level) if slots[i] else 0))
                envelopes[i].edge()
            mixed, clip = env.mix_pcm([lane['pcm'] for lane in lanes])
            tokens[value['id']] = (mixed, clip, lanes)
        elif tag == 'effect':
            mixed, clip, lanes = tokens[value['id']]
            raw = (mixed * 32767 >> 15) + (effect.buffer[(effect.wr_ptr - 1) % 1024] * 16384 >> 15)
            output = effect.process(mixed, 1, 32767, 16384, 0)
            results.append(dict(epoch=value['epoch'], id=value['id'], cycle=value['cycle'] + 35,
                                effect_accept_cycle=c, left=output, right=output,
                                clip=int(clip or output != raw), mixed=mixed, lanes=lanes))
    return results, allocations


def compare(expected, actual):
    require(len(expected) == len(actual), 'PCM_COMPLETENESS')
    for e, a in zip(expected, actual):
        for field in ('epoch', 'id', 'cycle', 'left', 'right', 'clip'):
            require(e[field] == a[field], f'PCM_{field.upper()}:id{e["id"]}:expected{e[field]}:actual{a[field]}')


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    models, report = closure()
    (args.output / 'CLOSURE.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    controls, config, resets, requests, frames, observed = read_inputs()
    expected, allocations = golden(models, controls, config, resets, requests, frames)
    (args.output / 'GOLDEN.json').write_text(json.dumps({'allocations': allocations, 'results': expected}, indent=2), encoding='utf-8')
    compare(expected, observed)
    result = dict(status='PASS_SCOPED_R05_PCM_REPLAY', compared=len(expected),
                  effect_accepts_derived=len(expected), allocations=allocations,
                  model_trace_not_lane_observation=True, general_cancel_hold_coverage=False,
                  new_RTL_calls=0, board_release_allowed=False)
    (args.output / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
