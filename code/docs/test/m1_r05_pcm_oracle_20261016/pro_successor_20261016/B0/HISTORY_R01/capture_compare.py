"""Strict, zero-LSB B0 adapter for the already signed settled R06 Reference.

This module does not reconstruct a Pro scheduler or infer inputs from DUT DSP
state.  REAL is deliberately pending until a Pro source/ROM/port-reset mapping
is independently signed and its original artifact hash is admitted below.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parents[2]
CONTRACT = ROOT / 'code/docs/test/m1_r05_pcm_oracle_20261016/REFERENCE_CONTRACT.json'
PROFILE = 'R06_SETTLED_SIMULTANEOUS_LANE_TICKS_V1'
PINNED = {
    'oracle.py': 'cb2cda8b6c9c17d7e5f93be4e48407383173934437c0592d2da64f778535d4a3',
    'DEPENDENCIES.json': 'fb9c0ffaec3b9e001cb2255256565dae49d573155da62473bea2e592716a28de',
    'REFERENCE_CONTRACT.json': 'f7373c1be0d70b9bb45800738b8a992efadd854c1cb1aecf82910f3644cf091e',
}
# No Pro mapping has been supplied/signed in M2/17.  Presence or self-declared
# approval of an arbitrary JSON file must never turn fixture equality into RTL.
APPROVED_PRO_MAP_SHA256 = frozenset()
COUNTS = ('calendar_rows', 'public_pcm_rows', 'resets', 'events', 'lane_ticks',
          'effect_accepts', 'config_accepts', 'cancels')
MAX_CYCLE = 2**63 - 1
MAX_ID = 2**32 - 1
MAX_JSON_BYTES = 32 * 1024 * 1024
_REFERENCE = None


class ContractError(ValueError):
    """Unusable input; do not proceed to PCM arithmetic comparison."""


def fail(code, where):
    raise ContractError(code + ':' + where)


def fields(value, required, where, optional=()):
    if type(value) is not dict:
        fail('OBJECT_REQUIRED', where)
    missing = set(required) - value.keys()
    extra = value.keys() - set(required) - set(optional)
    if missing:
        fail('MISSING_FIELDS', where + ':' + ','.join(sorted(missing)))
    if extra:
        fail('UNKNOWN_FIELDS', where + ':' + ','.join(sorted(extra)))
    return value


def number(value, low, high, where):
    if type(value) is not int or not low <= value <= high:
        fail('INTEGER_RANGE', where)
    return value


def flag(value, where):
    if type(value) is not bool:
        fail('BOOL_REQUIRED', where)
    return value


def label(value, where):
    if type(value) is not str or not value or len(value) > 256:
        fail('NONEMPTY_STRING_REQUIRED', where)
    return value


def sequence(value, where):
    if type(value) is not list:
        fail('ARRAY_REQUIRED', where)
    return value


def sha(value, where):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        fail('SHA256_REQUIRED', where)
    return value


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail('DUPLICATE_JSON_KEY', key)
        result[key] = value
    return result


def _noninteger(value):
    fail('NONINTEGER_JSON_NUMBER', value)


def read_json(path):
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_JSON_BYTES:
            fail('JSON_TOO_LARGE', str(path))
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                          parse_float=_noninteger, parse_constant=_noninteger)
    except (UnicodeError, json.JSONDecodeError, OSError) as error:
        raise ContractError('UNREADABLE_JSON:' + str(path) + ':' + str(error)) from error


def signed_reference_bindings():
    """Verify original bytes before importing the signed arithmetic module."""
    for name, expected in PINNED.items():
        path = CONTRACT if name == 'REFERENCE_CONTRACT.json' else PARENT / name
        if not path.is_file() or digest(path) != expected:
            fail('SIGNED_REFERENCE_DRIFT', name)
    dependencies = read_json(PARENT / 'DEPENDENCIES.json')
    frozen = {}
    for row in dependencies['files']:
        path = PARENT / row['path']
        if not path.is_file() or digest(path) != row['sha256']:
            fail('SIGNED_ROM_OR_SOURCE_DRIFT', row['path'])
        frozen[row['path']] = row['sha256']
    return {'signed_files': dict(PINNED), 'frozen_files': frozen}


def reference_class():
    global _REFERENCE
    signed_reference_bindings()
    if _REFERENCE is None:
        name = '_m1_pro_b0_signed_reference'
        spec = importlib.util.spec_from_file_location(name, PARENT / 'oracle.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        _REFERENCE = module.Reference
    return _REFERENCE


def artifact(desc, base, where, missing):
    fields(desc, ('path', 'sha256', 'bytes'), where)
    name = label(desc['path'], where + '.path')
    expected = sha(desc['sha256'], where + '.sha256')
    size = number(desc['bytes'], 0, MAX_JSON_BYTES, where + '.bytes')
    relative = Path(name)
    if relative.is_absolute() or relative.drive or '..' in relative.parts:
        fail('ARTIFACT_PATH_MUST_STAY_IN_BUNDLE', where)
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()):
        fail('ARTIFACT_PATH_ESCAPE', where)
    if not path.is_file():
        missing.append(where + ':ORIGINAL_FILE_MISSING')
        return None
    if path.stat().st_size != size or digest(path) != expected:
        fail('ORIGINAL_FILE_SHA_OR_SIZE_MISMATCH', where)
    return path


def identity(row, where):
    fields(row, ('lane', 'source', 'channel', 'note', 'generation'), where)
    number(row['lane'], 0, 3, where + '.lane')
    number(row['generation'], 0, MAX_ID, where + '.generation')
    values = [row[key] for key in ('source', 'channel', 'note')]
    if all(value is None for value in values):
        return row
    if any(value is None for value in values):
        fail('PARTIAL_LANE_IDENTITY', where)
    number(row['source'], 0, 15, where + '.source')
    number(row['channel'], 0, 15, where + '.channel')
    number(row['note'], 0, 127, where + '.note')
    return row


def identities(rows, where):
    sequence(rows, where)
    if len(rows) != 4:
        fail('EXACTLY_FOUR_LANE_IDENTITIES_REQUIRED', where)
    for lane, row in enumerate(rows):
        identity(row, where + '[' + str(lane) + ']')
        if row['lane'] != lane:
            fail('LANE_ORDER_OR_DUPLICATE', where)
    return rows


def expected_identities(sample):
    result = []
    for lane in sample['lanes']:
        ident = lane['identity']
        result.append({'lane': lane['lane'], 'source': ident[0] if ident else None,
                       'channel': ident[1] if ident else None,
                       'note': ident[2] if ident else None,
                       'generation': lane['generation']})
    return result


def validate_common(document, schema, origin, manifest, where):
    fields(document, ('schema', 'origin', 'producer', 'capture_id', 'scene',
                      'declared_count', 'rows'), where)
    if document['schema'] != schema or document['origin'] != origin:
        fail('SCHEMA_OR_ORIGIN_MISMATCH', where)
    producer = 'M3' if manifest['mode'] == 'REAL' and where == 'calendar' else (
        'DUT_PUBLIC_CAPTURE' if manifest['mode'] == 'REAL' else 'B0_SYNTHETIC_FIXTURE')
    if document['producer'] != producer:
        fail('PRODUCER_MISMATCH', where)
    for key in ('capture_id', 'scene'):
        if document[key] != manifest[key]:
            fail('CAPTURE_OR_SCENE_MISMATCH', where + '.' + key)
    sequence(document['rows'], where + '.rows')
    number(document['declared_count'], 0, MAX_ID, where + '.declared_count')
    if document['declared_count'] != len(document['rows']):
        fail('DECLARED_COUNT_MISMATCH', where)


def validate_calendar(document, manifest):
    origin = 'M3_INDEPENDENT_APPLIED_CALENDAR' if manifest['mode'] == 'REAL' else 'SYNTHETIC_FIXTURE'
    validate_common(document, 'M1_PRO_INDEPENDENT_CALENDAR_V1', origin, manifest, 'calendar')
    counts = Counter(calendar_rows=len(document['rows']))
    tick_map, effect_map, cancel_map = {}, {}, {}
    last_cycle, epoch = -1, -1
    for seq, row in enumerate(document['rows']):
        fields(row, ('seq', 'cycle', 'epoch', 'kind', 'payload'), 'calendar.row')
        number(row['seq'], 0, MAX_ID, 'calendar.seq')
        if row['seq'] != seq:
            fail('ROW_SEQUENCE_GAP_OR_DUPLICATE', 'calendar')
        cycle = number(row['cycle'], 0, MAX_CYCLE, 'calendar.cycle')
        number(row['epoch'], 0, MAX_ID, 'calendar.epoch')
        if cycle <= last_cycle:
            fail('SETTLED_PROFILE_REJECTS_SAME_EDGE_OR_REORDER', 'calendar')
        last_cycle = cycle
        kind, payload = row['kind'], row['payload']
        if kind == 'reset':
            fields(payload, (), 'reset.payload')
            epoch += 1
            if row['epoch'] != epoch or (seq == 0 and cycle != 0):
                fail('RESET_EPOCH_OR_INITIAL_CYCLE', 'calendar')
            counts['resets'] += 1
        elif epoch < 0 or row['epoch'] != epoch:
            fail('MISSING_RESET_OR_WRONG_EPOCH', 'calendar')
        elif kind == 'event':
            fields(payload, ('event', 'source', 'channel', 'note', 'velocity10',
                             'program', 'decision', 'lane', 'generation'), 'event.payload')
            if payload['event'] not in ('note_on', 'note_off', 'program'):
                fail('UNSUPPORTED_EVENT', str(payload['event']))
            for name, high in [('source', 15), ('channel', 15), ('note', 127),
                               ('velocity10', 1023), ('program', 4095)]:
                number(payload[name], 0, high, 'event.' + name)
            label(payload['decision'], 'event.decision')
            for name, high in [('lane', 3), ('generation', MAX_ID)]:
                if payload[name] is not None:
                    number(payload[name], 0, high, 'event.' + name)
            counts['events'] += 1
        elif kind == 'config_accept':
            fields(payload, ('enable', 'length', 'dry', 'wet', 'feedback'), 'config.payload')
            flag(payload['enable'], 'config.enable')
            number(payload['length'], 0, 1023, 'config.length')
            for name in ('dry', 'wet', 'feedback'):
                number(payload[name], 0, 32767, 'config.' + name)
            counts['config_accepts'] += 1
        elif kind in ('lane_tick', 'effect_accept', 'cancel'):
            required = {'lane_tick': ('request_id', 'lane_cycles', 'identities'),
                        'effect_accept': ('request_id', 'publish', 'publish_cycle'),
                        'cancel': ('request_id', 'reason')}[kind]
            fields(payload, required, kind + '.payload')
            rid = number(payload['request_id'], 0, MAX_ID, kind + '.request_id')
            key = (epoch, rid)
            target = {'lane_tick': tick_map, 'effect_accept': effect_map, 'cancel': cancel_map}[kind]
            if key in target:
                fail('DUPLICATE_REQUEST_ACTION', kind + ':' + str(key))
            target[key] = row
            if kind == 'lane_tick':
                lanes = sequence(payload['lane_cycles'], 'lane_tick.lane_cycles')
                if len(lanes) != 4:
                    fail('EVERY_LANE_TICK_REQUIRED', str(key))
                for lane, tick in enumerate(lanes):
                    fields(tick, ('lane', 'cycle'), 'lane_tick.lane_cycles')
                    number(tick['lane'], 0, 3, 'lane_tick.lane')
                    number(tick['cycle'], 0, MAX_CYCLE, 'lane_tick.cycle')
                    if tick['lane'] != lane or tick['cycle'] != cycle:
                        fail('UNSUPPORTED_STAGGER_OR_WRONG_LANE', str(key))
                identities(payload['identities'], 'lane_tick.identities')
                counts['lane_ticks'] += 1
            elif kind == 'effect_accept':
                flag(payload['publish'], 'effect_accept.publish')
                if payload['publish']:
                    number(payload['publish_cycle'], cycle, MAX_CYCLE, 'effect_accept.publish_cycle')
                elif payload['publish_cycle'] is not None:
                    fail('UNPUBLISHED_HAS_PUBLISH_CYCLE', str(key))
                counts['effect_accepts'] += 1
            else:
                label(payload['reason'], 'cancel.reason')
                counts['cancels'] += 1
        else:
            fail('UNSUPPORTED_CALENDAR_ACTION', str(kind))
    if not document['rows'] or document['rows'][0]['kind'] != 'reset':
        fail('INITIAL_RESET_REQUIRED', 'calendar')
    if not tick_map:
        fail('NO_LANE_TICKS', 'calendar')
    for key in effect_map.keys() | cancel_map.keys():
        if key not in tick_map:
            fail('ACTION_WITHOUT_LANE_TICK', str(key))
    reset_cycles = {r['epoch']: r['cycle'] for r in document['rows'] if r['kind'] == 'reset'}
    for key, tick in tick_map.items():
        effect, cancel = effect_map.get(key), cancel_map.get(key)
        if effect and effect['cycle'] < tick['cycle'] + 7:
            fail('EFFECT_ACCEPT_BEFORE_SIGNED_PIPELINE', str(key))
        if cancel and cancel['cycle'] < tick['cycle'] + 5:
            fail('UNSUPPORTED_EARLY_CANCEL', str(key))
        published = effect and effect['payload']['publish']
        if bool(cancel) == bool(published):
            fail('CANCEL_AND_PUBLICATION_INCONSISTENT', str(key))
        # No action after the following reset may name a previous epoch.
        next_reset = reset_cycles.get(key[0] + 1, MAX_CYCLE + 1)
        if effect and effect['payload']['publish'] and effect['payload']['publish_cycle'] >= next_reset:
            fail('PUBLICATION_CROSSES_RESET', str(key))
    return counts, tick_map, effect_map, cancel_map


def validate_diagnostics(value):
    fields(value, (), 'diagnostics', ('lanes', 'mixed_left', 'mixed_right', 'fx_left', 'fx_right'))
    for name in ('mixed_left', 'mixed_right', 'fx_left', 'fx_right'):
        if name in value:
            number(value[name], -8388608, 8388607, 'diagnostics.' + name)
    if 'lanes' in value:
        lanes = sequence(value['lanes'], 'diagnostics.lanes')
        seen = set()
        for lane in lanes:
            fields(lane, ('lane',), 'diagnostics.lane',
                   ('timbre', 'wave16', 'env_q15', 'voice_pcm24', 'fcw', 'phase_before', 'phase_after'))
            index = number(lane['lane'], 0, 3, 'diagnostics.lane')
            if index in seen:
                fail('DUPLICATE_DIAGNOSTIC_LANE', str(index))
            seen.add(index)
            ranges = {'timbre': (0, 1), 'wave16': (-32768, 32767), 'env_q15': (0, 32767),
                      'voice_pcm24': (-8388608, 8388607), 'fcw': (0, MAX_ID),
                      'phase_before': (0, MAX_ID), 'phase_after': (0, MAX_ID)}
            for name, item in lane.items():
                if name != 'lane':
                    number(item, *ranges[name], 'diagnostics.' + name)


def validate_public(document, manifest, effects=None):
    origin = 'REAL_DUT_PUBLIC_CAPTURE' if manifest['mode'] == 'REAL' else 'SYNTHETIC_FIXTURE'
    validate_common(document, 'M1_PRO_PUBLIC_PCM_V1', origin, manifest, 'public_pcm')
    rows = {}
    last_cycle = -1
    for seq, row in enumerate(document['rows']):
        fields(row, ('seq', 'cycle', 'epoch', 'request_id', 'identities', 'left', 'right', 'clip'),
               'public_pcm.row', ('diagnostics',))
        number(row['seq'], 0, MAX_ID, 'public_pcm.seq')
        if row['seq'] != seq:
            fail('ROW_SEQUENCE_GAP_OR_DUPLICATE', 'public_pcm')
        cycle = number(row['cycle'], 0, MAX_CYCLE, 'public_pcm.cycle')
        if cycle <= last_cycle:
            fail('PUBLICATION_REORDER_OR_SAME_EDGE', 'public_pcm')
        last_cycle = cycle
        key = (number(row['epoch'], 0, MAX_ID, 'public_pcm.epoch'),
               number(row['request_id'], 0, MAX_ID, 'public_pcm.request_id'))
        if key in rows:
            fail('DUPLICATE_PUBLIC_ID', str(key))
        if effects is not None:
            effect = effects.get(key)
            if not effect or not effect['payload']['publish'] or cycle != effect['payload']['publish_cycle']:
                fail('PUBLIC_ID_EPOCH_OR_CYCLE_NOT_IN_INDEPENDENT_CALENDAR', str(key))
        identities(row['identities'], 'public_pcm.identities')
        for name in ('left', 'right'):
            number(row[name], -8388608, 8388607, 'public_pcm.' + name)
        clips = sequence(row['clip'], 'public_pcm.clip')
        if len(clips) != 2:
            fail('STEREO_CLIP_REQUIRED', str(key))
        for value in clips:
            flag(value, 'public_pcm.clip')
        if 'diagnostics' in row:
            validate_diagnostics(row['diagnostics'])
        rows[key] = row
    if effects is not None:
        wanted = {key for key, effect in effects.items() if effect['payload']['publish']}
        if rows.keys() != wanted:
            fail('PUBLICATION_COUNT_OR_ID_SET_MISMATCH', 'public_pcm')
    if not rows:
        fail('NO_PUBLIC_PCM_SAMPLES', 'public_pcm')
    return rows


def reconstruct(calendar, ticks, effects):
    reference = reference_class()()
    expected = {}
    for row in calendar['rows']:
        cycle, kind, payload = row['cycle'], row['kind'], row['payload']
        try:
            if kind == 'reset':
                if row['epoch'] > 0:
                    if cycle <= reference.last_action:
                        fail('RESET_OVERLAPS_IN_FLIGHT_REFERENCE', str(cycle))
                    reference.reset(cycle)
            elif kind == 'event':
                applied = reference.event(cycle, payload['event'], payload['source'],
                                          payload['channel'], payload['note'],
                                          payload['velocity10'], payload['program'])
                for name in ('decision', 'lane', 'generation'):
                    if payload[name] != applied.get(name):
                        fail('EVENT_SLOT_OR_GENERATION_IDENTITY_MISMATCH', str(row['seq']) + ':' + name)
            elif kind == 'config_accept':
                reference.config_accept(cycle, payload['enable'], payload['length'],
                                        payload['dry'], payload['wet'], payload['feedback'])
            elif kind == 'lane_tick':
                key = (row['epoch'], payload['request_id'])
                effect = effects.get(key)
                sample = reference.sample(cycle, payload['request_id'], bool(effect),
                                          bool(effect and effect['payload']['publish']),
                                          effect['cycle'] if effect else None)
                if payload['identities'] != expected_identities(sample):
                    fail('LANE_TICK_SOURCE_NOTE_GENERATION_IDENTITY_MISMATCH', str(key))
                expected[key] = sample
        except ValueError as error:
            if isinstance(error, ContractError):
                raise
            raise ContractError('SIGNED_SETTLED_PROFILE_REJECTED:' + str(row['seq']) + ':' + str(error)) from error
    return expected


def pro_binding(desc, base, missing):
    if desc is None:
        missing.extend(['PRO_TOP_SOURCE_SHA_MISSING', 'PRO_ROM_SHA_MAPPING_MISSING',
                        'PRO_PORT_RESET_MAPPING_MISSING'])
        return None
    fields(desc, ('top_sources', 'rom_files', 'port_reset_map'), 'pro_binding')
    for group in ('top_sources', 'rom_files'):
        items = sequence(desc[group], 'pro_binding.' + group)
        if not items:
            missing.append('pro_binding.' + group + ':EMPTY')
        seen = set()
        for item in items:
            path = artifact(item, base, 'pro_binding.' + group, missing)
            if item['path'] in seen:
                fail('DUPLICATE_PRO_BINDING_FILE', item['path'])
            seen.add(item['path'])
            if path is None:
                continue
    if desc['port_reset_map'] is None:
        missing.append('PRO_PORT_RESET_MAPPING_MISSING')
        return None
    path = artifact(desc['port_reset_map'], base, 'pro_binding.port_reset_map', missing)
    if path is not None and desc['port_reset_map']['sha256'] not in APPROVED_PRO_MAP_SHA256:
        missing.append('PRO_PORT_RESET_ROM_MAPPING_NOT_IN_M2_SIGNED_ALLOWLIST')
    return desc['port_reset_map']['sha256']


def mismatch_report(manifest, sample, actual):
    sources = [lane['identity'][0] if lane['identity'] else None for lane in sample['lanes']]
    observed_layer, observed_lane, observed_source = 'public_pcm_or_clip', None, sources
    diagnostics = actual.get('diagnostics', {})
    for lane in sorted(diagnostics.get('lanes', []), key=lambda row: row['lane']):
        expected = sample['lanes'][lane['lane']]
        for field in ('timbre', 'fcw', 'phase_before', 'phase_after', 'wave16', 'env_q15', 'voice_pcm24'):
            if field in lane and lane[field] != expected[field]:
                observed_layer = field
                observed_lane = lane['lane']
                observed_source = expected['identity'][0] if expected['identity'] else None
                break
        if observed_lane is not None:
            break
    if observed_lane is None:
        for field in ('mixed_left', 'mixed_right', 'fx_left', 'fx_right'):
            expected = sample[field] if field.startswith('mixed_') else sample[field[3:]]
            if field in diagnostics and diagnostics[field] != expected:
                observed_layer = field
                break
    return {
        'scene': manifest['scene'], 'epoch': sample['epoch'], 'request_id': sample['request_id'],
        'source': observed_source, 'contributing_sources': sources,
        'lane': observed_lane, 'observed_layer': observed_layer,
        'expected_layers': {
            'lanes': [{key: lane[key] for key in ('lane', 'identity', 'generation', 'timbre',
                       'fcw', 'phase_before', 'phase_after', 'wave16', 'env_q15', 'voice_pcm24')}
                      for lane in sample['lanes']],
            'mix': {'left': sample['mixed_left'], 'right': sample['mixed_right'],
                    'upstream_clip': sample['upstream_clip']},
            'fx': {'left': sample['left'], 'right': sample['right'],
                   'effect_clip': sample['effect_clip'], 'feedback_clip': sample['feedback_clip'],
                   'clip': sample['clipped']},
        },
        'actual_public': {key: actual[key] for key in ('cycle', 'left', 'right', 'clip')},
        'actual_internal_diagnostics': actual.get('diagnostics'),
        'attribution': ('Public PCM/ID/clip alone cannot uniquely attribute a lane, timbre, envelope, '
                        'mix or effect cause. Optional internal observations are actual-only '
                        'diagnostic evidence; observed_layer identifies the first differing '
                        'supplied observation, not a unique root cause. Observations never supply '
                        'the expected result.'),
    }


def compare_bundle(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    manifest = read_json(manifest_path)
    fields(manifest, ('schema', 'mode', 'capture_id', 'scene', 'profile', 'reference',
                      'calendar', 'public_pcm', 'pro_binding', 'counts'), 'manifest')
    if manifest['schema'] != 'M1_PRO_CAPTURE_BUNDLE_V1' or manifest['mode'] not in ('SYNTHETIC', 'REAL'):
        fail('BUNDLE_SCHEMA_OR_MODE', 'manifest')
    for name in ('capture_id', 'scene'):
        label(manifest[name], 'manifest.' + name)
    if manifest['profile'] != PROFILE:
        fail('UNSUPPORTED_PROFILE', 'manifest.profile')
    verified = signed_reference_bindings()
    fields(manifest['reference'], ('signed_files', 'frozen_files'), 'manifest.reference')
    if manifest['reference'] != verified:
        fail('SIGNED_REFERENCE_BINDING_MISMATCH', 'manifest.reference')
    base, missing = manifest_path.parent, []
    counts = manifest['counts']
    if counts is not None:
        fields(counts, COUNTS, 'manifest.counts')
        for name, value in counts.items():
            number(value, 0, MAX_ID, 'manifest.counts.' + name)
    elif manifest['mode'] == 'SYNTHETIC':
        fail('SYNTHETIC_COUNTS_REQUIRED', 'manifest.counts')
    paths = {}
    for name in ('calendar', 'public_pcm'):
        if manifest[name] is None:
            missing.append(name + ':ORIGINAL_INPUT_MISSING')
            paths[name] = None
        else:
            paths[name] = artifact(manifest[name], base, name, missing)
    map_sha = pro_binding(manifest['pro_binding'], base, missing)
    missing.extend(['PRO_ASYNC_RESET_EDGES_NOT_COVERED_BY_SETTLED_PROFILE',
                    'M3_RAW_DRIVER_FULL_TRACE_OBSERVER_AND_SOURCE_BINDINGS_REQUIRED',
                    'M3_EXECUTION_TOOLS_ARGV_DUAL_STREAMS_EXIT_AND_QUOTA_RECEIPT_REQUIRED',
                    'M3_ORIGINAL_TRACE_CONTINUITY_AND_SAME_RUN_AUTHENTICATION_REQUIRED'])
    if manifest['mode'] == 'SYNTHETIC' and (paths['calendar'] is None or paths['public_pcm'] is None):
        fail('SYNTHETIC_ORIGINAL_INPUT_REQUIRED', 'manifest')
    result = {'schema': 'M1_PRO_CAPTURE_COMPARISON_V1', 'status': 'PENDING_REAL_CAPTURE',
              'mode': manifest['mode'], 'capture_id': manifest['capture_id'], 'scene': manifest['scene'],
              'profile': PROFILE, 'tolerance_pcm_lsb': 0, 'manifest_sha256': digest(manifest_path),
              'original_inputs': {name: manifest[name] for name in ('calendar', 'public_pcm')},
              'reference_bindings': verified, 'pro_map_sha256': map_sha,
              'missing_real_requirements': missing, 'identity_check': 'NOT_RUN',
              'zero_lsb_check': 'NOT_RUN', 'compared_public_samples': 0,
              'rtl_or_board_pass': False, 'board_release_allowed': False}
    # Validate every supplied input even when another real requirement is absent.
    calendar = read_json(paths['calendar']) if paths['calendar'] else None
    public = read_json(paths['public_pcm']) if paths['public_pcm'] else None
    if calendar is not None:
        actual_counts, ticks, effects, _ = validate_calendar(calendar, manifest)
    if public is not None and calendar is None:
        validate_public(public, manifest)
    if calendar is None or public is None:
        return result
    public_rows = validate_public(public, manifest, effects)
    actual_counts['public_pcm_rows'] = len(public_rows)
    if counts is None or any(counts[name] != actual_counts[name] for name in COUNTS):
        fail('BUNDLE_COUNTS_MISMATCH', 'manifest.counts')
    expected = reconstruct(calendar, ticks, effects)
    # Identity validation for ALL public rows precedes ANY public PCM comparison.
    for key, row in public_rows.items():
        if row['identities'] != expected_identities(expected[key]):
            fail('PUBLIC_SOURCE_CHANNEL_NOTE_GENERATION_IDENTITY_MISMATCH',
                 manifest['scene'] + ':' + str(key) + ':expected=' +
                 json.dumps(expected_identities(expected[key]), sort_keys=True) + ':actual=' +
                 json.dumps(row['identities'], sort_keys=True))
    result['identity_check'] = 'PASS'
    result['calendar_counts'] = dict(actual_counts)
    for key, row in public_rows.items():
        sample = expected[key]
        result['compared_public_samples'] += 1
        if (row['left'], row['right'], row['clip']) != (sample['left'], sample['right'], sample['clipped']):
            result['status'] = 'PCM_MISMATCH'
            result['zero_lsb_check'] = 'FAIL'
            result['first_difference'] = mismatch_report(manifest, sample, row)
            return result
    result['zero_lsb_check'] = 'PASS'
    result['status'] = ('SYNTHETIC_FIXTURE_PASS' if manifest['mode'] == 'SYNTHETIC' else
                        'PENDING_REAL_CAPTURE' if missing else 'REAL_CAPTURE_PCM_PASS')
    # Even an eventual admitted mapping signs only this arithmetic/profile, not
    # deadline, serial, synthesis, physical, license, or board acceptance.
    result['rtl_or_board_pass'] = False
    return result


def write_new_json(path, value):
    path = Path(path)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path, help='New report file; existing files are refused.')
    args = parser.parse_args(argv)
    if args.out.exists():
        print('REFUSE_OVERWRITE:' + str(args.out), file=sys.stderr)
        return 2
    try:
        result = compare_bundle(args.manifest)
    except (ContractError, OSError) as error:
        result = {'schema': 'M1_PRO_CAPTURE_COMPARISON_V1', 'status': 'CONTRACT_REJECTED',
                  'error': str(error), 'rtl_or_board_pass': False, 'board_release_allowed': False}
    try:
        write_new_json(args.out, result)
    except OSError as error:
        print('REPORT_WRITE_REFUSED:' + str(error), file=sys.stderr)
        return 2
    print(result['status'])
    return {'SYNTHETIC_FIXTURE_PASS': 0, 'REAL_CAPTURE_PCM_PASS': 0,
            'PENDING_REAL_CAPTURE': 3, 'PCM_MISMATCH': 1, 'CONTRACT_REJECTED': 2}[result['status']]


if __name__ == '__main__':
    sys.exit(main())
