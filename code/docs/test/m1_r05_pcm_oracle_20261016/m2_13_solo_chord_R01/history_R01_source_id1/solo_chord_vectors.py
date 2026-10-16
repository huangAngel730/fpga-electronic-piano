"""Five matched SOLO/ALL4 software references for the frozen R06 arithmetic.

The calendar is synthetic, not the R06 MIDI testbench's actual schedule. The
application cycles are not UART bit/byte transmission times. This
module reuses Reference and never parses a DUT trace or runs an old test suite.
The five independent resets make solo slot 0 comparable to its mapped ALL4
slot. Final effected solo outputs must not be added to predict ALL4 output.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from oracle import DEPENDENCIES, PIANO, TRIANGLE, Reference


SAMPLE_COUNT = 256
PCM_MIN, PCM_MAX = -8388608, 8388607
MASK32 = (1 << 32) - 1
# note, exact FCW, velocity10, timbre, applied NoteOn cycle
PARTS = ((60, 23409859, 1023, 0, 32),
         (63, 27839171, 903, 1, 64),
         (67, 35075158, 774, 1, 80),
         (70, 41711627, 645, 1, 96))
RAW7 = (127, 112, 96, 80)
SCENES = ('solo60', 'solo63', 'solo67', 'solo70', 'all4')
PROFILE = 'SYNTHETIC_SETTLED_EVENT_NOT_R06_TB_OR_FFT'
PENDING = 'PENDING_REAL_CAPTURE'
BASIS_CONTRACT_SHA256 = 'f7373c1be0d70b9bb45800738b8a992efadd854c1cb1aecf82910f3644cf091e'


def _require(condition, reason):
    if not condition:
        raise ValueError('SOLO_CHORD_' + reason)


def _integer(value, low, high, reason):
    _require(type(value) is int and low <= value <= high, reason)
    return value


def _sat24(value):
    return max(PCM_MIN, min(PCM_MAX, value))


def _selected(name):
    return PARTS if name == 'all4' else tuple(p for p in PARTS if name == 'solo' + str(p[0]))


def _ticks():
    cycle = 128
    result = []
    for index in range(SAMPLE_COUNT):
        result.append(cycle)
        cycle += (833, 833, 834)[index % 3]
    return result


def _mapping(name):
    return [dict(note=p[0], fcw=p[1], raw7=RAW7[PARTS.index(p)],
                 expanded10=p[2], velocity10=p[2], timbre=p[3],
                 apply_cycle=p[4], solo_lane=0, all_lane=PARTS.index(p),
                 scene_lane=index, source=1, channel=0,
                 frequency_hz=p[1] * 48000 / 2**32)
            for index, p in enumerate(_selected(name))]


def _stimulus(name):
    events = [dict(kind='note_on', cycle=p[4], source=1, channel=0,
                   note=p[0], velocity=p[2]) for p in _selected(name)]
    # Keep the same Program event even in solo60: its sounding Piano is latched.
    events.append(dict(kind='program', cycle=48, source=1, channel=0, program=1))
    events.sort(key=lambda row: row['cycle'])
    rows = [dict(kind='reset', cycle=0),
            dict(kind='config', cycle=16, enable=True, delay=1,
                 dry=32767, wet=16384, feedback=0)] + events
    rows += [dict(kind='sample', advance_cycle=cycle, request_id=index,
                  effect_accepted=True, publish=True,
                  postprocess_accept_cycle=cycle + 7)
             for index, cycle in enumerate(_ticks())]
    return dict(schema='M1_SOLO_CHORD_STIMULUS_V1', scene_id=name, source_kind='SYNTHETIC_ONLY',
                profile=PROFILE, clock_hz=40000000, sample_rate_hz=48000,
                actual_dut_result=PENDING, rows=rows)


def build_bundle():
    """Return exactly five independently reset scene records; no DUT inputs."""
    bundle = {}
    for name in SCENES:
        ref = Reference()  # Already reset at cycle 0, epoch 0.
        stimulus = _stimulus(name)
        expected, decisions = [], []
        for action in stimulus['rows'][1:]:
            values = {key: value for key, value in action.items() if key != 'kind'}
            if action['kind'] == 'config':
                values['length'] = values.pop('delay')
                ref.config_accept(**values)
            elif action['kind'] == 'sample':
                expected.append(ref.sample(**values))
            else:
                decisions.append(ref.event(kind=action['kind'], **values))
        bundle[name] = dict(schema='M1_SOLO_CHORD_SCENE_V1', scene_id=name,
                            profile=PROFILE, actual_dut_result=PENDING,
                            mapping=_mapping(name), stimulus=stimulus,
                            event_decisions=decisions, expected=expected)
    validate_bundle(bundle)
    return bundle


def validate_bundle(bundle):
    """Check the fixed profile and independent gain/mix/delay invariants.

    ADSR/Piano evolution is supplied by the frozen Reference, not reimplemented
    here. Identity-mapped SOLO/ALL4 states must agree. Phase, ROM addressing,
    Q15 floor, pre-effect saturation and each scene's accepted history are
    checked explicitly. This is software qualification, never DUT evidence.
    """
    _require(type(bundle) is dict and set(bundle) == set(SCENES), 'EXACT_FIVE_SCENES')
    ticks = _ticks()
    coverage = {}
    for name in SCENES:
        scene = bundle[name]
        _require(type(scene) is dict, 'SCENE_OBJECT:' + name)
        _require(scene.get('schema') == 'M1_SOLO_CHORD_SCENE_V1' and
                 scene.get('scene_id') == name and scene.get('profile') == PROFILE and
                 scene.get('actual_dut_result') == PENDING, 'SCENE_IDENTITY:' + name)
        _require(scene.get('mapping') == _mapping(name), 'NOTE_MAPPING:' + name)
        for mapping in scene['mapping']:
            raw7 = _integer(mapping.get('raw7'), 1, 127, 'RAW_MIDI_VELOCITY')
            expanded = _integer(mapping.get('expanded10'), 1, 1023, 'EXPANDED_MIDI_VELOCITY')
            _require(expanded == (raw7 << 3 | raw7 >> 4) == mapping['velocity10'],
                     'MIDI_VELOCITY_EXPANSION:' + name)
        _require(scene.get('stimulus') == _stimulus(name), 'INPUT_CALENDAR:' + name)
        rows = scene.get('expected')
        _require(type(rows) is list and len(rows) == SAMPLE_COUNT, 'ROW_COUNT:' + name)
        selected = _selected(name)
        histories = [0, 0]
        nonzero = [0] * len(selected)
        for index, row in enumerate(rows):
            _require(type(row) is dict, 'ROW_OBJECT:' + name)
            for key, wanted in (('epoch', 0), ('request_id', index),
                                ('advance_cycle', ticks[index]),
                                ('snapshot_cycle', ticks[index] + 5),
                                ('postprocess_accept_cycle', ticks[index] + 7),
                                ('retired_mask', 0)):
                _integer(row.get(key), 0, 2**63 - 1, 'ROW_INTEGER:' + key)
                _require(row[key] == wanted, 'SAMPLE_CALENDAR:' + name + ':' + key)
            _require(row.get('calendar_kind') == 'SYNTHETIC_SETTLED_EVENT' and
                     row.get('effect_accepted') is True and
                     row.get('expected_publish') is True, 'SAMPLE_PROFILE:' + name)
            lanes = row.get('lanes')
            _require(type(lanes) is list and len(lanes) == 4, 'FOUR_LANES:' + name)
            voices = []
            for lane_index, lane in enumerate(lanes):
                _require(type(lane) is dict, 'LANE_OBJECT:' + name)
                _integer(lane.get('lane'), 0, 3, 'LANE_INDEX')
                _require(lane['lane'] == lane_index, 'LANE_ORDER:' + name)
                part = selected[lane_index] if lane_index < len(selected) else None
                note, fcw, velocity, timbre, unused_cycle = part or (None, 0, 0, 0, 0)
                identity = [1, 0, note, 'active'] if part else None
                _require(lane.get('identity') == identity, 'LANE_IDENTITY:' + name)
                for key, wanted in (('fcw', fcw), ('velocity10', velocity),
                                    ('timbre', timbre), ('generation', int(bool(part))),
                                    ('phase_before', index * fcw & MASK32),
                                    ('phase_after', (index + 1) * fcw & MASK32)):
                    _integer(lane.get(key), 0, MASK32, 'LANE_INTEGER:' + key)
                    _require(lane[key] == wanted, 'PHASE_OR_FCW:' + name + ':' + key)
                _require(type(lane.get('frequency_hz')) in (int, float) and
                         lane['frequency_hz'] == fcw * 48000 / 2**32,
                         'FREQUENCY:' + name)
                # All selected notes are below 1500 Hz, and 256 ticks is less
                # than every selected velocity's frozen Piano attack duration.
                table = 0 if part else 3
                _require(type(lane.get('piano_table')) is int and lane['piano_table'] == table,
                         'PIANO_ATTACK_PREFIX:' + name)
                address = lane['phase_before'] >> 22 if timbre else (table << 8) | (lane['phase_after'] >> 24)
                wave = TRIANGLE[address] if timbre else PIANO[address]
                _require(type(lane.get('rom_address')) is int and lane['rom_address'] == address,
                         'ROM_ADDRESS:' + name)
                _require(type(lane.get('wave16')) is int and lane['wave16'] == wave,
                         'ROM_SAMPLE:' + name)
                level = _integer(lane.get('level_q16'), 0, 0x7fffffff, 'LEVEL_Q16')
                env = _integer(lane.get('env_q15'), 0, 32767, 'ENV_Q15')
                _require(env == level >> 16, 'ENVELOPE_FORMAT:' + name)
                _integer(lane.get('adsr_state'), 0, 4, 'ADSR_STATE')
                if not part:
                    _require(level == env == lane['adsr_state'] == 0, 'EMPTY_ENVELOPE:' + name)
                voice = ((wave * env) >> 15) << 8 if part else 0
                _require(type(lane.get('voice_pcm24')) is int and lane['voice_pcm24'] == voice,
                         'GAIN_FLOOR:' + name)
                voices.append(voice)
                if part and voice:
                    nonzero[lane_index] += 1
            total = sum(voices)  # Four contributions first; saturation follows.
            mixed = _sat24(total)
            upstream = total < PCM_MIN or total > PCM_MAX
            _require(type(row.get('upstream_clip')) is bool and row['upstream_clip'] == upstream,
                     'UPSTREAM_CLIP:' + name)
            for channel, key in enumerate(('left', 'right')):
                _require(type(row.get('mixed_' + key)) is int and row['mixed_' + key] == mixed,
                         'FOUR_VOICE_MIX:' + name)
                # feedback=0, delay=1: one previous accepted MIXED PCM per
                # independent scene/channel, not the previous solo output.
                raw = (mixed * 32767 >> 15) + (histories[channel] * 16384 >> 15)
                effect_clip = raw < PCM_MIN or raw > PCM_MAX
                _require(type(row.get(key)) is int and row[key] == _sat24(raw),
                         'INDEPENDENT_DELAY_HISTORY:' + name + ':' + key)
                for flag, wanted in (('effect_clip', effect_clip),
                                     ('feedback_clip', False),
                                     ('clipped', upstream or effect_clip)):
                    flags = row.get(flag)
                    _require(type(flags) is list and len(flags) == 2 and
                             type(flags[channel]) is bool and flags[channel] == wanted,
                             'CLIP_METADATA:' + name + ':' + flag)
                histories[channel] = mixed
        _require(all(count > 0 for count in nonzero), 'NONVACUOUS_CONTRIBUTIONS:' + name)
        coverage[name] = dict(samples=len(rows), selected_notes=[p[0] for p in selected],
                              selected_lane_nonzero_rows=nonzero)

    fields = ('identity', 'generation', 'timbre', 'velocity10', 'fcw',
              'frequency_hz', 'phase_before', 'phase_after', 'piano_table',
              'rom_address', 'wave16', 'level_q16', 'env_q15', 'adsr_state', 'voice_pcm24')
    witness = None
    for index in range(SAMPLE_COUNT):
        all_row = bundle['all4']['expected'][index]
        solo_rows = [bundle['solo' + str(p[0])]['expected'][index] for p in PARTS]
        for lane_index, solo_row in enumerate(solo_rows):
            for field in fields:
                _require(solo_row['lanes'][0][field] == all_row['lanes'][lane_index][field],
                         'SOLO_ALL_IDENTITY_MAPPING:' + field)
        # Record a real generated software row showing non-distributive Q15
        # rounding/saturation. Never require equality of these final outputs.
        solo_sum = sum(row['left'] for row in solo_rows)
        if witness is None and solo_sum != all_row['left']:
            witness = dict(source_kind='SOFTWARE_REFERENCE_ONLY', actual_dut_result=PENDING,
                           request_id=index, advance_cycle=all_row['advance_cycle'],
                           solo_effected_left=[row['left'] for row in solo_rows],
                           sum_solo_effected_left=solo_sum,
                           saturated_sum_solo_effected_left=_sat24(solo_sum),
                           all4_effected_left=all_row['left'],
                           all4_mixed_left=all_row['mixed_left'],
                           reason='sum(each rounded/effected solo) is not the ALL4 golden')
    return dict(schema='M1_SOLO_CHORD_VALIDATION_V1', profile=PROFILE,
                actual_dut_result=PENDING, scene_count=5, total_samples=5 * SAMPLE_COUNT,
                tolerance_pcm_lsb=0, coverage=coverage,
                final_solo_sum_counterexample=witness,
                witness_status='FOUND' if witness is not None else 'NONE_IN_FIXED_WINDOW')


def _normalised(rows):
    return [dict(epoch=row['epoch'], request_id=row['request_id'],
                 lane_pcm=[lane['voice_pcm24'] for lane in row['lanes']],
                 generation=[lane['generation'] for lane in row['lanes']],
                 left=row['left'], right=row['right'], clipped=row['clipped']) for row in rows]


def _write_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    bundle = build_bundle()
    validation = validate_bundle(bundle)
    for name in SCENES:
        scene = bundle[name]
        folder = output / name
        folder.mkdir(exist_ok=False)
        _write_json(folder / 'STIMULUS.json', scene['stimulus'])
        _write_json(folder / 'EXPECTED_PCM.json', scene['expected'])
        _write_json(folder / 'NORMALIZED_MATH.json', _normalised(scene['expected']))
        _write_json(folder / 'EVENT_DECISIONS.json', scene['event_decisions'])
        columns = ['request_id', 'advance_cycle', 'left', 'right', 'mixed_left',
                   'mixed_right', 'upstream_clip', 'lane0_pcm', 'lane1_pcm',
                   'lane2_pcm', 'lane3_pcm']
        with (folder / 'PCM.csv').open('x', encoding='ascii', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator='\n')
            writer.writeheader()
            for row in scene['expected']:
                record = {key: row[key] for key in columns if key in row}
                record.update({'lane' + str(i) + '_pcm': lane['voice_pcm24']
                               for i, lane in enumerate(row['lanes'])})
                writer.writerow(record)
    _write_json(output / 'VALIDATION.json', validation)
    _write_json(output / 'SOLO_SUM_EFFECT_WITNESS.json',
                dict(status=validation['witness_status'], actual_dut_result=PENDING,
                     witness=validation['final_solo_sum_counterexample']))
    files = {path.relative_to(output).as_posix():
             dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
             for path in sorted(output.rglob('*')) if path.is_file()}
    sources = {str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in (Path(__file__), Path(__file__).with_name('oracle.py'))}
    _write_json(output / 'MANIFEST.json', dict(
        schema='M1_SOLO_CHORD_SOFTWARE_BUNDLE_V1', result='SOFTWARE_REFERENCE_GENERATED',
        actual_dut_result=PENDING, profile=PROFILE, clock_hz=40000000, sample_rate_hz=48000,
        basis_contract_sha256=BASIS_CONTRACT_SHA256,
        samples_per_scene=SAMPLE_COUNT, scenes={name: _mapping(name) for name in SCENES},
        all_noteons_before_same_first_dsp_sample=True, simultaneous_frontend_event_edges=False,
        dependencies=DEPENDENCIES, source_sha256=sources, files=files,
        validation=validation, boundary='Synthetic settled calendar; no real R06 capture or FFT proof'))
    print(json.dumps(dict(result='SOFTWARE_REFERENCE_GENERATED', actual_dut_result=PENDING,
                          scenes=len(bundle), samples=5 * SAMPLE_COUNT,
                          witness_status=validation['witness_status'])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
