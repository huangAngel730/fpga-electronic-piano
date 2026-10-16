"""Matched Program-change software references using the existing Reference.

The applied-event and DSP calendar is synthetic, not UART transmission timing,
router latency, an actual R06 capture, or FFT/physical evidence. Neither audio
algorithms nor capture tools are replaced here. All real-DUT results stay
PENDING_REAL_CAPTURE. Program changes select future successful NoteOns only.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from oracle import DEPENDENCIES, PIANO, TRIANGLE, Reference, adsr, delay, mixed


SCENES = ('control_pc0', 'switch_ch0_pc1')
SAMPLE_COUNT = 256
MIDI_SOURCE_ID = 0
PENDING = 'PENDING_REAL_CAPTURE'
PROFILE = 'SYNTHETIC_SETTLED_PC_PAIR_NOT_UART_ROUTER_OR_REAL_R06'
BASIS_CONTRACT_SHA256 = 'f7373c1be0d70b9bb45800738b8a992efadd854c1cb1aecf82910f3644cf091e'
MASK32 = (1 << 32) - 1
PCM_MIN, PCM_MAX = -8388608, 8388607
# note, channel, raw MIDI velocity7, expanded velocity10, first active sample,
# frozen base FCW. Physical lane order follows these four successful NoteOns.
VOICES = ((60, 0, 127, 1023, 0, 23409859),
          (63, 1, 96, 774, 0, 27839171),
          (67, 0, 112, 903, 80, 35075158),
          (70, 1, 80, 645, 96, 41711627))


def _require(condition, reason):
    if not condition:
        raise ValueError('TIMBRE_PAIR_' + reason)


def _integer(value, low, high, reason):
    _require(type(value) is int and low <= value <= high, reason)
    return value


def _tick(index):
    return 128 + 833 * index + index // 3


def _note(cycle, note, channel, raw7, velocity):
    return dict(kind='note_on', cycle=cycle, source=MIDI_SOURCE_ID,
                channel=channel, note=note, raw7=raw7, velocity=velocity)


def _program(index, program):
    return dict(kind='program', cycle=_tick(index) - 64,
                source=MIDI_SOURCE_ID, channel=0, program=program)


def _stimulus(name):
    switching = name == 'switch_ch0_pc1'
    events = {64: _program(64, 1 if switching else 0),
              80: _note(_tick(80) - 64, 67, 0, 112, 903),
              96: _note(_tick(96) - 64, 70, 1, 80, 645),
              112: _program(112, 127),
              128: _note(_tick(128) - 64, 67, 0, 112, 903),
              160: _program(160, 0),
              176: _note(_tick(176) - 64, 67, 0, 112, 903)}
    rows = [dict(kind='reset', cycle=0),
            dict(kind='config', cycle=16, enable=True, delay=1,
                 dry=32767, wet=16384, feedback=0),
            _note(32, 60, 0, 127, 1023), _note(48, 63, 1, 96, 774)]
    for index in range(SAMPLE_COUNT):
        if index in events:
            rows.append(events[index])
        rows.append(dict(kind='sample', advance_cycle=_tick(index), request_id=index,
                         postprocess_accept_cycle=_tick(index) + 7,
                         effect_accepted=True, publish=True))
    return dict(schema='M1_TIMBRE_PC_PAIR_STIMULUS_V1', scene_id=name,
                source_kind='SYNTHETIC_ONLY', actual_dut_result=PENDING,
                profile=PROFILE, clock_hz=40000000, sample_rate_hz=48000,
                event_cycle_meaning='independent applied edge, not UART send/accept time',
                rows=rows)


def _mapping():
    return [dict(lane=index, source=MIDI_SOURCE_ID, channel=voice[1], note=voice[0],
                 raw7=voice[2], expanded10=voice[3], first_active_sample=voice[4],
                 base_fcw=voice[5], frequency_hz=voice[5] * 48000 / 2**32)
            for index, voice in enumerate(VOICES)]


def build_pairs():
    """Generate exactly two scenes through the existing frozen-dependency model."""
    pairs = {}
    for name in SCENES:
        ref = Reference()
        stimulus = _stimulus(name)
        expected, decisions = [], []
        for action in stimulus['rows'][1:]:
            values = {key: value for key, value in action.items()
                      if key not in ('kind', 'raw7')}
            if action['kind'] == 'config':
                values['length'] = values.pop('delay')
                ref.config_accept(**values)
            elif action['kind'] == 'sample':
                row = ref.sample(**values)
                row.update(scene_id=name, source_kind='SYNTHETIC_ONLY',
                           actual_dut_result=PENDING)
                expected.append(row)
            else:
                decisions.append(ref.event(kind=action['kind'], **values))
        pairs[name] = dict(schema='M1_TIMBRE_PC_PAIR_SCENE_V1', scene_id=name,
                           source_kind='SYNTHETIC_ONLY', actual_dut_result=PENDING,
                           profile=PROFILE, mapping=_mapping(), stimulus=stimulus,
                           event_decisions=decisions, expected=expected)
    validate_pairs(pairs)
    return pairs


def _validate_decisions(scene, name):
    actions = [row for row in scene['stimulus']['rows'] if row['kind'] in ('program', 'note_on')]
    decisions = scene.get('event_decisions')
    _require(type(decisions) is list and len(decisions) == len(actions), 'EVENT_DECISION_COUNT')
    for action, decision in zip(actions, decisions):
        _require(type(decision) is dict, 'EVENT_DECISION_OBJECT')
        for key, wanted in (('epoch', 0), ('apply_cycle', action['cycle']),
                            ('kind', action['kind']), ('source', MIDI_SOURCE_ID),
                            ('channel', action['channel']), ('note', action.get('note', 60)),
                            ('velocity10', action.get('velocity', 0)),
                            ('program', action.get('program', 0))):
            _require(decision.get(key) == wanted, 'EVENT_APPLICATION:' + name + ':' + key)
        if action['kind'] == 'program':
            label = 'ignored_program' if action['program'] == 127 else 'program'
            _require(decision.get('decision') == label, 'PC127_IGNORED:' + name)
        else:
            raw7 = _integer(action.get('raw7'), 1, 127, 'RAW_MIDI_VELOCITY')
            _require(action['velocity'] == ((raw7 << 3) | (raw7 >> 4)), 'MIDI_VELOCITY_EXPANSION')
            lane = next(index for index, voice in enumerate(VOICES) if voice[0] == action['note'])
            generation = (2 if action['cycle'] == _tick(128) - 64 else
                          3 if action['cycle'] == _tick(176) - 64 else 1)
            _require(decision.get('decision') == ('retrigger' if generation > 1 else 'new') and
                     decision.get('lane') == lane and decision.get('generation') == generation,
                     'ALLOCATION_OR_RETRIGGER:' + name)


def validate_pairs(pairs):
    """Validate this fixed pair only; never authenticate/reconstruct a capture.

    The original Reference provides oscillator/ADSR evolution. This increment
    checks fixed identity/phase/calendar and paired latch/isolation semantics;
    gain, mixer and T028 checks reuse their existing frozen math functions.
    """
    _require(type(pairs) is dict and set(pairs) == set(SCENES), 'EXACT_TWO_SCENES')
    for name in SCENES:
        scene = pairs[name]
        _require(type(scene) is dict and scene.get('schema') == 'M1_TIMBRE_PC_PAIR_SCENE_V1' and
                 scene.get('scene_id') == name and scene.get('profile') == PROFILE and
                 scene.get('source_kind') == 'SYNTHETIC_ONLY' and
                 scene.get('actual_dut_result') == PENDING, 'SCENE_IDENTITY:' + name)
        _require(scene.get('mapping') == _mapping(), 'VOICE_MAPPING:' + name)
        _require(scene.get('stimulus') == _stimulus(name), 'FIXED_INPUT_CALENDAR:' + name)
        _validate_decisions(scene, name)
        rows = scene.get('expected')
        _require(type(rows) is list and len(rows) == SAMPLE_COUNT, 'FIXED_ROW_COUNT:' + name)
        effects = [delay.DelayEffectFixed(1024), delay.DelayEffectFixed(1024)]
        for index, row in enumerate(rows):
            _require(type(row) is dict, 'ROW_OBJECT:' + name)
            _require(row.get('scene_id') == name and row.get('actual_dut_result') == PENDING and
                     row.get('source_kind') == 'SYNTHETIC_ONLY' and
                     row.get('calendar_kind') == 'SYNTHETIC_SETTLED_EVENT', 'ROW_IDENTITY:' + name)
            for field, wanted in (('epoch', 0), ('request_id', index),
                                  ('advance_cycle', _tick(index)),
                                  ('snapshot_cycle', _tick(index) + 5),
                                  ('postprocess_accept_cycle', _tick(index) + 7),
                                  ('retired_mask', 0)):
                _integer(row.get(field), 0, 2**63 - 1, 'ROW_INTEGER:' + field)
                _require(row[field] == wanted, 'SAMPLE_CALENDAR:' + name + ':' + field)
            _require(row.get('effect_accepted') is True and row.get('expected_publish') is True,
                     'ACCEPTED_PUBLISHED_PROFILE:' + name)
            lanes = row.get('lanes')
            _require(type(lanes) is list and len(lanes) == 4, 'FOUR_LANE_RECORDS:' + name)
            voices = []
            for lane_index, (lane, voice) in enumerate(zip(lanes, VOICES)):
                _require(type(lane) is dict, 'LANE_OBJECT:' + name)
                note, channel, raw7, velocity, start, base_fcw = voice
                active = index >= start
                fcw = base_fcw if active else 0
                count = index - start if active else 0
                generation = ((3 if index >= 176 else 2 if index >= 128 else 1)
                              if lane_index == 2 and active else int(active))
                timbre = int(name == 'switch_ch0_pc1' and lane_index == 2 and 80 <= index < 176)
                _require(lane.get('lane') == lane_index and type(lane.get('lane')) is int,
                         'LANE_ORDER:' + name)
                identity = [MIDI_SOURCE_ID, channel, note, 'active'] if active else None
                _require(lane.get('identity') == identity, 'LANE_IDENTITY:' + name)
                _require(type(lane.get('timbre')) is int and lane['timbre'] == timbre,
                         'HELD_TIMBRE_OR_CHANNEL_ISOLATION:' + name)
                for field, wanted in (('generation', generation), ('velocity10', velocity if active else 0),
                                      ('fcw', fcw), ('phase_before', count * fcw & MASK32),
                                      ('phase_after', (count + 1) * fcw & MASK32 if active else 0)):
                    _integer(lane.get(field), 0, MASK32, 'LANE_INTEGER:' + field)
                    _require(lane[field] == wanted, 'GENERATION_FCW_OR_PHASE:' + name + ':' + field)
                _require(type(lane.get('frequency_hz')) in (int, float) and
                         lane['frequency_hz'] == fcw * 48000 / 2**32, 'FREQUENCY:' + name)
                # This 256-sample prefix stays within every occupied lane's
                # frozen Piano attack duration, including the hidden oscillator
                # that continues advancing while Triangle is selected.
                table = 0 if active else 3
                _require(type(lane.get('piano_table')) is int and lane['piano_table'] == table,
                         'FROZEN_PIANO_ATTACK_PREFIX:' + name)
                address = lane['phase_before'] >> 22 if timbre else (table << 8) | (lane['phase_after'] >> 24)
                wave = TRIANGLE[address] if timbre else PIANO[address]
                _require(type(lane.get('rom_address')) is int and lane['rom_address'] == address and
                         type(lane.get('wave16')) is int and lane['wave16'] == wave,
                         'SELECTED_WAVE:' + name)
                level = _integer(lane.get('level_q16'), 0, 0x7fffffff, 'ENVELOPE_LEVEL')
                envelope = _integer(lane.get('env_q15'), 0, 32767, 'ENVELOPE_Q15')
                _require(envelope == level >> 16, 'ENVELOPE_FORMAT:' + name)
                state = _integer(lane.get('adsr_state'), 0, 4, 'ADSR_STATE')
                if not active:
                    _require(level == envelope == state == 0, 'EMPTY_ENVELOPE:' + name)
                pcm = adsr.voice_pcm(wave, envelope) if active else 0
                _require(type(lane.get('voice_pcm24')) is int and lane['voice_pcm24'] == pcm,
                         'FROZEN_GAIN_MATH:' + name)
                voices.append(pcm)
            value, upstream_clip = mixed(voices)
            _require(type(row.get('upstream_clip')) is bool and row['upstream_clip'] == upstream_clip,
                     'UPSTREAM_CLIP:' + name)
            for channel, field in enumerate(('left', 'right')):
                _require(type(row.get('mixed_' + field)) is int and row['mixed_' + field] == value,
                         'FROZEN_MIX_MATH:' + name)
                effect = effects[channel]
                delayed = effect.buffer[(effect.wr_ptr - 1) % effect.depth]
                # Metadata uses the unsaturated sum; sample math itself stays
                # in the unchanged T028 reference, with scene-local history.
                raw = (value * 32767 >> 15) + (delayed * 16384 >> 15)
                clipped = raw < PCM_MIN or raw > PCM_MAX
                wanted = effect.process(value, 1, 32767, 16384, 0)
                _require(type(row.get(field)) is int and row[field] == wanted,
                         'FROZEN_EFFECT_RESULT:' + name + ':' + field)
                for flag, wanted_flag in (('effect_clip', clipped), ('feedback_clip', False),
                                          ('clipped', upstream_clip or clipped)):
                    flags = row.get(flag)
                    _require(type(flags) is list and len(flags) == 2 and
                             type(flags[channel]) is bool and flags[channel] == wanted_flag,
                             'CLIP_METADATA:' + name + ':' + flag)

    control = pairs['control_pc0']['expected']
    switched = pairs['switch_ch0_pc1']['expected']
    invariant_fields = ('identity', 'generation', 'velocity10', 'fcw', 'frequency_hz',
                        'phase_before', 'phase_after', 'piano_table', 'level_q16', 'env_q15', 'adsr_state')
    sound_fields = ('mixed_left', 'mixed_right', 'left', 'right', 'upstream_clip',
                    'effect_clip', 'feedback_clip', 'clipped')
    witnesses = {}
    windows = (('new_note_after_pc1', 80, 112), ('held_through_pc127', 112, 128),
               ('retrigger_after_ignored_pc127', 128, 160), ('held_through_pc0', 160, 176))
    for index, (before, after) in enumerate(zip(control, switched)):
        for lane_index in (0, 1, 3):
            _require(before['lanes'][lane_index] == after['lanes'][lane_index],
                     'OTHER_VOICE_CHANGED:' + str(lane_index))
        for field in invariant_fields:
            _require(before['lanes'][2][field] == after['lanes'][2][field],
                     'LANE2_NON_TIMBRE_STATE_CHANGED:' + field)
        if index < 80:
            _require(all(before[field] == after[field] for field in sound_fields),
                     'PC_CHANGED_HELD_PCM_BEFORE_NEW_NOTE')
        if index >= 176:
            _require(before['lanes'][2] == after['lanes'][2] and
                     before['mixed_left'] == after['mixed_left'] and
                     before['mixed_right'] == after['mixed_right'], 'PC0_RETRIGGER_DID_NOT_RESTORE_MIX')
        if index >= 177:
            _require(all(before[field] == after[field] for field in sound_fields),
                     'DELAY1_DID_NOT_RESTORE_AFTER_ONE_ACCEPTED_SAMPLE')
        different_wave = before['lanes'][2]['wave16'] != after['lanes'][2]['wave16']
        different_voice = before['lanes'][2]['voice_pcm24'] != after['lanes'][2]['voice_pcm24']
        for label, first, stop in windows:
            if first <= index < stop and different_wave and different_voice and label not in witnesses:
                witnesses[label] = dict(source_kind='SOFTWARE_REFERENCE_ONLY', actual_dut_result=PENDING,
                    sample=index, advance_cycle=_tick(index),
                    control_lane2=before['lanes'][2], switched_lane2=after['lanes'][2],
                    control_mixed=before['mixed_left'], switched_mixed=after['mixed_left'],
                    control_output=before['left'], switched_output=after['left'])
    _require(set(witnesses) == {window[0] for window in windows}, 'NO_NONVACUOUS_TIMBRE_WITNESS')
    output_difference = next((dict(sample=index, control_left=control[index]['left'],
                                  switched_left=switched[index]['left'])
                              for index in range(80, 176)
                              if control[index]['left'] != switched[index]['left']), None)
    _require(output_difference is not None, 'NO_NONVACUOUS_EFFECT_OUTPUT_DIFFERENCE')
    return dict(schema='M1_TIMBRE_PC_PAIR_QUALIFICATION_V1', source_kind='SOFTWARE_REFERENCE_ONLY',
        actual_dut_result=PENDING, profile=PROFILE, scenes=2, samples_per_scene=SAMPLE_COUNT,
        total_samples=2 * SAMPLE_COUNT, tolerance_pcm_lsb=0,
        held_note_pc_only_equal_window=[64, 79],
        isolated_lanes_equal_entire_window=[0, 1, 3],
        lane2_triangle_vs_piano_window=[80, 175],
        ignored_pc127_preserved_future_selection=True,
        pc0_preserves_held_triangle_window=[160, 175],
        phase_continuous_retrigger_samples=[128, 176],
        lane2_generation_at_retrigger=[2, 3],
        mixed_equal_from_sample=176, effected_equal_from_sample=177,
        transition_sample176=dict(control_mixed=control[176]['mixed_left'],
            switched_mixed=switched[176]['mixed_left'], control_output=control[176]['left'],
            switched_output=switched[176]['left'],
            output_equal=control[176]['left'] == switched[176]['left'],
            boundary='One previous accepted mixed sample may still differ at sample176'),
        witnesses=witnesses, effect_output_difference=output_difference,
        boundary='Synthetic applied-event calendar; no UART/router delay or real DUT/FFT assertion')


def _write_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def _files(directory):
    return {path.relative_to(directory).as_posix():
            dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            for path in sorted(directory.rglob('*')) if path.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    pairs = build_pairs()
    qualification = validate_pairs(pairs)
    for name in SCENES:
        scene = pairs[name]
        folder = output / name
        folder.mkdir(exist_ok=False)
        _write_json(folder / 'STIMULUS.json', scene['stimulus'])
        _write_json(folder / 'EXPECTED_PCM.json', scene['expected'])
        _write_json(folder / 'EVENT_DECISIONS.json', dict(
            scene_id=name, actual_dut_result=PENDING, source_kind='SOFTWARE_REFERENCE_ONLY',
            rows=scene['event_decisions']))
        columns = ['scene_id', 'actual_dut_result', 'request_id', 'advance_cycle',
                   'mixed_left', 'mixed_right', 'left', 'right', 'upstream_clip',
                   'lane0_pcm', 'lane1_pcm', 'lane2_pcm', 'lane3_pcm',
                   'lane2_timbre', 'lane2_generation', 'lane2_phase_before', 'lane2_env_q15']
        with (folder / 'PCM.csv').open('x', encoding='ascii', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator='\n')
            writer.writeheader()
            for row in scene['expected']:
                record = {key: row[key] for key in columns if key in row}
                record.update({'lane' + str(index) + '_pcm': lane['voice_pcm24']
                               for index, lane in enumerate(row['lanes'])})
                record.update({'lane2_' + field: row['lanes'][2][field]
                               for field in ('timbre', 'generation', 'phase_before', 'env_q15')})
                writer.writerow(record)
        _write_json(folder / 'MANIFEST.json', dict(
            schema='M1_TIMBRE_PC_PAIR_SCENE_MANIFEST_V1', scene_id=name,
            actual_dut_result=PENDING, source_kind='SYNTHETIC_ONLY', profile=PROFILE,
            mapping=scene['mapping'], samples=SAMPLE_COUNT, files=_files(folder)))
    _write_json(output / 'QUALIFICATION.json', qualification)
    source_paths = [Path(__file__), Path(__file__).with_name('oracle.py'),
                    Path(__file__).with_name('test_timbre_switch_pairs_R01.py')]
    sources = {str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in source_paths}
    _write_json(output / 'MANIFEST.json', dict(
        schema='M1_TIMBRE_PC_PAIR_BUNDLE_MANIFEST_V1', result='SOFTWARE_REFERENCE_GENERATED',
        actual_dut_result=PENDING, source_kind='SYNTHETIC_ONLY', profile=PROFILE,
        basis_contract_sha256=BASIS_CONTRACT_SHA256,
        clock_hz=40000000, sample_rate_hz=48000, scenes=list(SCENES),
        samples_per_scene=SAMPLE_COUNT, dependency_identity=DEPENDENCIES,
        source_sha256=sources, files=_files(output),
        boundary='No real capture, UART transmission timing, router latency, or physical/FFT result'))
    print(json.dumps(dict(result='SOFTWARE_REFERENCE_GENERATED', actual_dut_result=PENDING,
                          scenes=2, samples=2 * SAMPLE_COUNT,
                          timbre_witnesses=len(qualification['witnesses']),
                          mixed_equal_from=176, effected_equal_from=177)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
