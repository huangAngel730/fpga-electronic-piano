"""A1 synthetic four-solo/chord identities and scene-local math histories.

Only the new adapter is qualified here.  The signed parent generators/models
are imported in place; their historical test suites are never imported or run.
The inherited five-scene window is regenerated as an A1 metadata fixture.  It
is not a Pro source/ROM match, an independent capture, or an RTL result.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))

import solo_chord_vectors as signed_solo  # noqa: E402
import timbre_switch_pairs_R01 as signed_timbre  # noqa: E402
from oracle import DEPENDENCIES, delay, mixed  # noqa: E402


SCENES = signed_solo.SCENES
SAMPLE_COUNT = signed_solo.SAMPLE_COUNT
PENDING = 'PENDING_REAL_CAPTURE'
PROFILE = 'SYNTHETIC_ONLY_PRO_A1_IDENTITY_AND_HISTORY_INCREMENT'
SOURCE_KIND = 'SYNTHETIC_ONLY'
SCHEMA = 'M1_PRO_A1_SYNTHETIC_BUNDLE_V1'
PCM_MIN, PCM_MAX = -8388608, 8388607
EFFECT_CONFIG = dict(enable=True, depth=1024, delay_samples=1,
                     dry_q15=32767, wet_q15=16384, feedback_q15=0)
PRO_IDENTITY = dict(status=PENDING, pro_top_sha256=None,
                    pro_source_manifest_sha256=None, pro_reset_contract=None,
                    pro_rom_role_mapping=None, pro_independent_calendar_sha256=None,
                    pro_public_pcm_capture_sha256=None)
BOUNDARY = ('Frozen R06 arithmetic is a referenced basis only. New Pro top, '
            'reset/port contract, ROM role mapping and same-run independent '
            'calendar/public PCM are missing. No Pro RTL/board claim.')


def _require(condition, reason):
    if not condition:
        raise ValueError('PRO_A1_' + reason)


def _same(actual, expected):
    """Type-exact metadata equality: JSON bool is not an integer identity."""
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return (set(actual) == set(expected) and
                all(_same(actual[key], value) for key, value in expected.items()))
    if type(expected) is list:
        return (len(actual) == len(expected) and
                all(_same(left, right) for left, right in zip(actual, expected)))
    return actual == expected


def source_identity():
    """Read hashes; never substitute these inherited bytes for Pro identity."""
    paths = (Path(__file__), HERE / 'test_a1_vectors.py',
             PARENT / 'oracle.py', PARENT / 'solo_chord_vectors.py',
             PARENT / 'timbre_switch_pairs_R01.py', PARENT / 'DEPENDENCIES.json')
    return {path.relative_to(PARENT).as_posix():
            hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def _input_identity(name, lane_index):
    # This mapping is supplied by the signed generator, not by the candidate
    # row being checked. All successful NoteOns in this fixed window are gen1.
    mapping = signed_solo._mapping(name)
    if lane_index >= len(mapping):
        return None
    voice = mapping[lane_index]
    return dict(scene_id=name, source=voice['source'], channel=voice['channel'],
                note=voice['note'], generation=1)


def _mix_history(name, row):
    voices = [lane['voice_pcm24'] for lane in row['lanes']]
    value, clipped = mixed(voices)
    return dict(scene_id=name, epoch=row['epoch'], request_id=row['request_id'],
                accepted_mix_ordinal=row['request_id'], voice_pcm24=voices,
                sum_before_saturation=sum(voices), mixed_left=value,
                mixed_right=value, upstream_clip=clipped,
                operation_order='four voices -> sum -> PCM24 saturation -> effects')


def _effect_histories(name, rows):
    """Expose scene-local buffer reads/writes using unchanged T028 processing."""
    effects = [delay.DelayEffectFixed(EFFECT_CONFIG['depth']) for _ in range(2)]
    result = []
    for row in rows:
        histories = []
        for channel, effect in zip(('left', 'right'), effects):
            before = effect.wr_ptr
            read_pointer = (before - EFFECT_CONFIG['delay_samples']) % effect.depth
            delayed = effect.buffer[read_pointer]
            output = effect.process(row['mixed_' + channel],
                                    EFFECT_CONFIG['delay_samples'],
                                    EFFECT_CONFIG['dry_q15'],
                                    EFFECT_CONFIG['wet_q15'],
                                    EFFECT_CONFIG['feedback_q15'])
            index = 0 if channel == 'left' else 1
            histories.append(dict(
                scene_id=name, epoch=row['epoch'], request_id=row['request_id'],
                channel=channel, config=dict(EFFECT_CONFIG),
                accepted_ordinal=row['request_id'],
                delayed_source_request_id=(row['request_id'] - 1
                                           if row['request_id'] else None),
                read_pointer=read_pointer, write_pointer_before=before,
                write_pointer_after=effect.wr_ptr, delayed_pcm24=delayed,
                input_mixed_pcm24=row['mixed_' + channel],
                output_pcm24=output,
                feedback_buffer_written_pcm24=effect.buffer[before],
                effect_clip=row['effect_clip'][index],
                feedback_clip=row['feedback_clip'][index],
                final_clip=row['clipped'][index]))
        result.append(histories)
    return result


def build_bundle():
    """Regenerate inherited fixtures, then attach only new A1 identity/history."""
    _require(signed_solo.BASIS_CONTRACT_SHA256 ==
             signed_timbre.BASIS_CONTRACT_SHA256, 'INHERITED_CONTRACT_CONFLICT')
    scenes = signed_solo.build_bundle()
    for name, scene in scenes.items():
        histories = _effect_histories(name, scene['expected'])
        for row, history in zip(scene['expected'], histories):
            row.update(scene_id=name, source_kind=SOURCE_KIND,
                       actual_dut_result=PENDING,
                       mix_history=_mix_history(name, row), effect_history=history)
            for index, lane in enumerate(row['lanes']):
                lane['input_identity'] = _input_identity(name, index)
    bundle = dict(schema=SCHEMA, profile=PROFILE, source_kind=SOURCE_KIND,
                  actual_dut_result=PENDING, evidence_level='L0_SOFTWARE_REFERENCE',
                  pro_identity=dict(PRO_IDENTITY), boundary=BOUNDARY,
                  basis_contract_sha256=signed_solo.BASIS_CONTRACT_SHA256,
                  source_sha256=source_identity(), frozen_dependencies=DEPENDENCIES,
                  scenes=scenes)
    validate_bundle(bundle)
    return bundle


def validate_bundle(bundle):
    """Reject new metadata/math faults with zero PCM-LSB tolerance.

    Existing DDS/ADSR/ROM/mix checks remain owned by the imported validator.
    The new checks bind each lane to canonical scene/source/channel/note/gen,
    and independently replay each scene's accepted MIXED PCM effect history.
    """
    _require(type(bundle) is dict and bundle.get('schema') == SCHEMA,
             'BUNDLE_SCHEMA')
    for field, expected in (('profile', PROFILE), ('source_kind', SOURCE_KIND),
                            ('actual_dut_result', PENDING),
                            ('evidence_level', 'L0_SOFTWARE_REFERENCE'),
                            ('pro_identity', PRO_IDENTITY), ('boundary', BOUNDARY),
                            ('basis_contract_sha256', signed_solo.BASIS_CONTRACT_SHA256),
                            ('source_sha256', source_identity()),
                            ('frozen_dependencies', DEPENDENCIES)):
        _require(_same(bundle.get(field), expected), 'BUNDLE_IDENTITY:' + field)
    scenes = bundle.get('scenes')
    _require(type(scenes) is dict and set(scenes) == set(SCENES), 'EXACT_FIVE_SCENES')
    # Check input identity before acoustic math. A nonzero PCM value cannot
    # compensate for a wrong original source/channel/note/generation.
    for name in SCENES:
        scene = scenes[name]
        _require(type(scene) is dict, 'SCENE_OBJECT:' + name)
        rows = scene.get('expected')
        _require(type(rows) is list and len(rows) == SAMPLE_COUNT,
                 'ROW_COUNT:' + name)
        for index, row in enumerate(rows):
            where = name + ':' + str(index)
            _require(type(row) is dict and row.get('scene_id') == name and
                     row.get('source_kind') == SOURCE_KIND and
                     row.get('actual_dut_result') == PENDING, 'ROW_IDENTITY:' + where)
            lanes = row.get('lanes')
            _require(type(lanes) is list and len(lanes) == 4, 'FOUR_LANES:' + where)
            for lane_index, lane in enumerate(lanes):
                _require(type(lane) is dict, 'LANE_OBJECT:' + where)
                _require(_same(lane.get('input_identity'), _input_identity(name, lane_index)),
                         'INPUT_IDENTITY:' + where + ':' + str(lane_index))
                _require(type(lane.get('lane')) is int and lane['lane'] == lane_index,
                         'LANE_ORDER:' + where + ':' + str(lane_index))
    inherited = signed_solo.validate_bundle(scenes)
    effect_nonzero_history_rows, true_clip_rows = {}, {}
    for name in SCENES:
        rows = scenes[name]['expected']
        histories = _effect_histories(name, rows)
        for index, (row, history) in enumerate(zip(rows, histories)):
            where = name + ':' + str(index)
            _require(_same(row.get('mix_history'), _mix_history(name, row)),
                     'MIX_HISTORY:' + where)
            _require(_same(row.get('effect_history'), history), 'EFFECT_HISTORY:' + where)
            for channel_index, channel in enumerate(('left', 'right')):
                _require(history[channel_index]['output_pcm24'] == row[channel],
                         'EFFECT_REPLAY_PCM:' + where + ':' + channel)
        effect_nonzero_history_rows[name] = sum(
            any(item['delayed_pcm24'] != 0 for item in row['effect_history'])
            for row in rows)
        true_clip_rows[name] = sum(any(row['clipped']) for row in rows)
    return dict(schema='M1_PRO_A1_QUALIFICATION_V1', source_kind=SOURCE_KIND,
                result='SOFTWARE_A1_INCREMENT_VALIDATED', actual_dut_result=PENDING,
                evidence_level='L0_SOFTWARE_REFERENCE', profile=PROFILE,
                scenes=len(SCENES), samples_per_scene=SAMPLE_COUNT,
                total_samples=len(SCENES) * SAMPLE_COUNT, tolerance_pcm_lsb=0,
                identity_fields=['scene_id', 'source', 'channel', 'note', 'generation'],
                lane_order='solo lane0 maps to canonical all4 lane by note identity',
                effect_nonzero_history_rows=effect_nonzero_history_rows,
                observed_true_clip_rows=true_clip_rows,
                nonzero_clip_coverage_claimed=any(true_clip_rows.values()),
                real_capture_nonzero_clip_coverage_claimed=False,
                inherited_scene_validation=inherited,
                final_solo_sum_counterexample=inherited['final_solo_sum_counterexample'],
                pro_identity=dict(PRO_IDENTITY), boundary=BOUNDARY)


def _write_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def _files(directory):
    return {path.relative_to(directory).as_posix():
            dict(bytes=path.stat().st_size,
                 sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            for path in sorted(directory.rglob('*')) if path.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    allowed = (PARENT.parents[1] / 'docs/test/m1_r05_pcm_oracle_20261016/'
               'pro_successor_20261016/A1').resolve()
    _require(allowed in output.parents, 'OUTPUT_MUST_BE_NEW_CHILD_OF_A1')
    output.mkdir(parents=True, exist_ok=False)
    bundle = build_bundle()
    qualification = validate_bundle(bundle)
    for name in SCENES:
        scene = bundle['scenes'][name]
        folder = output / name
        folder.mkdir(exist_ok=False)
        _write_json(folder / 'STIMULUS_SYNTHETIC.json', scene['stimulus'])
        _write_json(folder / 'EXPECTED_PCM_AND_HISTORY_SYNTHETIC.json', scene['expected'])
        _write_json(folder / 'EVENT_DECISIONS_SYNTHETIC.json', scene['event_decisions'])
        columns = ['scene_id', 'source_kind', 'actual_dut_result', 'epoch', 'request_id',
                   'advance_cycle', 'mixed_left', 'mixed_right', 'left', 'right',
                   'upstream_clip', 'left_clip', 'right_clip']
        columns += ['lane' + str(lane) + '_' + field for lane in range(4)
                    for field in ('source', 'channel', 'note', 'generation',
                                  'timbre', 'fcw', 'phase_before', 'phase_after',
                                  'wave16', 'env_q15', 'voice_pcm24')]
        with (folder / 'PCM_SYNTHETIC.csv').open('x', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator='\n')
            writer.writeheader()
            for row in scene['expected']:
                record = {key: row[key] for key in columns if key in row}
                record.update(left_clip=row['clipped'][0], right_clip=row['clipped'][1])
                for lane_index, lane in enumerate(row['lanes']):
                    identity = lane['input_identity'] or {}
                    for field in ('source', 'channel', 'note', 'generation',
                                  'timbre', 'fcw', 'phase_before', 'phase_after',
                                  'wave16', 'env_q15', 'voice_pcm24'):
                        record['lane' + str(lane_index) + '_' + field] = (
                            identity.get(field) if field in ('source', 'channel', 'note')
                            else lane[field])
                writer.writerow(record)
    _write_json(output / 'QUALIFICATION_SYNTHETIC.json', qualification)
    _write_json(output / 'PRO_IDENTITY_PENDING.json', dict(PRO_IDENTITY, boundary=BOUNDARY))
    _write_json(output / 'MANIFEST.json', dict(
        schema=SCHEMA, source_kind=SOURCE_KIND, result='SOFTWARE_REFERENCE_GENERATED',
        actual_dut_result=PENDING, evidence_level='L0_SOFTWARE_REFERENCE',
        profile=PROFILE, source_sha256=source_identity(),
        basis_contract_sha256=bundle['basis_contract_sha256'],
        frozen_dependencies=DEPENDENCIES, clock_hz=40000000, sample_rate_hz=48000,
        scenes=list(SCENES), samples_per_scene=SAMPLE_COUNT,
        files=_files(output), pro_identity=dict(PRO_IDENTITY), boundary=BOUNDARY,
        algorithms_copied=False, old_test_suites_reexecuted=False,
        final_solo_pcm_may_be_added_as_chord_golden=False))
    print(json.dumps(dict(result='SOFTWARE_A1_INCREMENT_GENERATED',
                          actual_dut_result=PENDING, scenes=len(SCENES),
                          total_samples=len(SCENES) * SAMPLE_COUNT,
                          tolerance_pcm_lsb=0)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
