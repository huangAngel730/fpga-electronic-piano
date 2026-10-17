"""R6-1 static contract checks; no HDL execution, arithmetic or capture parser.

Only the simple, explicit ANSI ports and named instance connections used by the
M1 observation candidates are recognized. Unsupported RTL syntax fails closed.
Static evidence proves a bound source/port mapping, not RTL behavior or a board.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


IDENTIFIER = r'[A-Za-z_][A-Za-z0-9_$]*'
RULES = {
    'apply_valid': (1, False, 'APPLY_ACTION_PRE_NBA', ['ACTUAL_ROUTER_ACTION_NOT_INGRESS_ACCEPT']),
    'apply_data': (64, False, 'APPLY_DATA_WHEN_KNOWN', ['NO_FABRICATED_EVENT_FOR_RETIRE_OR_DEFERRED_RELEASE']),
    'occupied_mask': (4, False, 'LIVE_ALLOCATOR_STATE', ['RELEASING_REMAINS_OCCUPIED']),
    'releasing_mask': (4, False, 'LIVE_ALLOCATOR_STATE', ['NOTE_OFF_NOT_RETIRE']),
    'note_on_mask': (4, False, 'CONSUMED_NOTE_ON_PULSE', ['RETRIGGER_AND_STEAL_NOT_SAME_GENERATION']),
    'note_off_mask': (4, False, 'CONSUMED_NOTE_OFF_PULSE', ['NOTE_OFF_NOT_RETIRE']),
    'retire_mask': (4, False, 'ACTUAL_RETIRE_ACTION', ['RELEASE_DONE_AND_NO_PENDING_NOTE_ON']),
    'slot_source': (16, False, 'LIVE_ALLOCATOR_STATE', ['LANE0_LEAST_SIGNIFICANT_4_BITS']),
    'slot_channel': (16, False, 'LIVE_ALLOCATOR_STATE', ['LANE0_LEAST_SIGNIFICANT_4_BITS']),
    'slot_note': (32, False, 'LIVE_ALLOCATOR_STATE', ['LANE0_LEAST_SIGNIFICANT_8_BITS_ZERO_EXTENDED_MIDI7']),
    'slot_generation': (128, False, 'LIVE_ALLOCATOR_STATE', ['PER_LANE_32_RESET_ZERO_INCREMENT_ON_ALLOCATION']),
    'advance_mask': (4, False, 'COMMON_LANE_TICK', ['ALL_FOUR_LANES_SAME_EDGE_INCLUDING_EMPTY', 'ONLY_0000_OR_1111']),
    'advance_frame_id': (32, False, 'ID_VALID_ONLY_WITH_ADVANCE', ['PENDING_ACCEPTED_REQUEST_ID_NOT_NEWEST_FRAME']),
    'effect_input_valid': (1, False, 'ACTUAL_EFFECT_INPUT_HANDSHAKE', ['ACCEPT_ONLY_VALID_AND_READY']),
    'effect_input_ready': (1, False, 'ACTUAL_EFFECT_INPUT_HANDSHAKE', ['ACCEPT_ONLY_VALID_AND_READY']),
    'effect_input_id': (32, False, 'PAYLOAD_ON_EFFECT_ACCEPT', ['ACCEPTED_THEN_CANCELLED_HISTORY_NOT_ROLLED_BACK']),
    'effect_input_left': (24, True, 'PAYLOAD_ON_EFFECT_ACCEPT', ['SIGNED_PCM24_NO_RECOMPUTED_MIX']),
    'effect_input_right': (24, True, 'PAYLOAD_ON_EFFECT_ACCEPT', ['SIGNED_PCM24_NO_RECOMPUTED_MIX']),
    'effect_input_clip': (2, False, 'PAYLOAD_ON_EFFECT_ACCEPT', ['BIT0_LEFT_BIT1_RIGHT_UPSTREAM_CLIP']),
}
PORTS = {
    'apply_valid': 'obs_apply_valid', 'apply_data': 'obs_apply_data',
    'occupied_mask': 'obs_slot_occupied', 'releasing_mask': 'obs_slot_releasing',
    'note_on_mask': 'obs_slot_note_on', 'note_off_mask': 'obs_slot_note_off',
    'retire_mask': 'obs_retire_mask', 'slot_source': 'obs_slot_sources',
    'slot_channel': 'obs_slot_channels', 'slot_note': 'obs_slot_notes',
    'slot_generation': 'obs_slot_generations', 'advance_mask': 'obs_advance_mask',
    'advance_frame_id': 'obs_advance_frame_id', 'effect_input_valid': 'obs_effect_input_valid',
    'effect_input_ready': 'obs_effect_input_ready', 'effect_input_id': 'obs_effect_input_id',
    'effect_input_left': 'obs_effect_input_left', 'effect_input_right': 'obs_effect_input_right',
    'effect_input_clip': 'obs_effect_input_clip',
}
ALIASES = {
    'apply_valid': '|obs_apply_kind',
    'apply_data': "obs_original_event_w ? held_event : 64'd0",
    'occupied_mask': 'slot_occupied', 'releasing_mask': 'slot_releasing',
    'note_on_mask': 'slot_note_on', 'note_off_mask': 'slot_note_off',
    'retire_mask': "obs_retire_w ? (4'b0001 << target_slot) : 4'd0",
    'slot_source': 'slot_sources', 'slot_channel': 'slot_channels',
    'slot_note': 'slot_notes', 'slot_generation': 'slot_generations',
    'advance_mask': '{4{lane_tick}}', 'advance_frame_id': 'pending_req_id',
    'effect_input_valid': 'audio_valid', 'effect_input_ready': 'audio_ready',
    'effect_input_id': 'audio_id', 'effect_input_left': 'audio_left',
    'effect_input_right': 'audio_right',
    'effect_input_clip': '{audio_clip_right,audio_clip_left}',
}
SAMPLE = {'clock': 'clk', 'edge': 'posedge', 'phase': 'pre_NBA',
          'reset': 'ASYNC_ASSERT_UPSTREAM_SYNC_RELEASE'}
MAX_BYTES = 8 * 1024 * 1024


class ContractError(ValueError):
    pass


def reject(code, where):
    raise ContractError(code + ':' + where)


def fields(value, required, where):
    if type(value) is not dict:
        reject('OBJECT_REQUIRED', where)
    if set(value) != set(required):
        reject('FIELDS', where + ':missing=' + ','.join(sorted(set(required) - set(value))) +
               ':extra=' + ','.join(sorted(set(value) - set(required))))


def integer(value, low, high, where):
    if type(value) is not int or not low <= value <= high:
        reject('INTEGER_RANGE', where)


def array(value, where):
    if type(value) is not list:
        reject('ARRAY_REQUIRED', where)
    return value


def word(value, where):
    if type(value) is not str or re.fullmatch(IDENTIFIER, value) is None:
        reject('PLAIN_IDENTIFIER_REQUIRED_NO_HIERARCHY', where)
    return value


def text(value, where):
    if type(value) is not str or not value.strip():
        reject('NONEMPTY_TEXT_REQUIRED', where)
    return value


def sha(value, where):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        reject('SHA256_REQUIRED', where)
    return value


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            reject('DUPLICATE_JSON_KEY', key)
        result[key] = value
    return result


def no_float(value):
    reject('NONINTEGER_JSON_NUMBER', value)


def read_json(path):
    raw = Path(path).read_bytes()
    if len(raw) > MAX_BYTES:
        reject('INPUT_TOO_LARGE', str(path))
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=no_duplicates,
                          parse_float=no_float, parse_constant=no_float)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ContractError('INVALID_JSON:' + str(error)) from error


def bound_path(root, name):
    text(name, 'path')
    relative = Path(name)
    if relative.is_absolute() or relative.drive or '..' in relative.parts:
        reject('PATH_ESCAPE', name)
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        reject('PATH_ESCAPE', name)
    return path


def strip_comments(source):
    """Retain line count while excluding commented fake ports and strings."""
    def blank(match):
        return ''.join('\n' if char == '\n' else ' ' for char in match.group(0))
    return re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"', blank, source)


def strip_observation_markers(source):
    """Delete only paired observer addition blocks; preserve all other bytes."""
    result, active = [], None
    for line in source.splitlines(keepends=True):
        marker = re.fullmatch(r'\s*//\s*(BEGIN|END) (M1_OBSERVER_R06[A-Z0-9_]*)\s*', line)
        if marker:
            action, name = marker.groups()
            if action == 'BEGIN':
                if active is not None:
                    reject('NESTED_OBSERVER_MARKER', name)
                active = name
            else:
                if active != name:
                    reject('UNPAIRED_OBSERVER_MARKER', name)
                active = None
        elif active is None:
            result.append(line)
    if active is not None:
        reject('UNCLOSED_OBSERVER_MARKER', active)
    return ''.join(result)


def closing(text_value, start):
    if text_value[start] != '(':
        reject('EXPECTED_PAREN', str(start))
    depth = 0
    for index in range(start, len(text_value)):
        if text_value[index] == '(':
            depth += 1
        elif text_value[index] == ')':
            depth -= 1
            if depth == 0:
                return index
    reject('UNBALANCED_RTL_PAREN', str(start))


def module_ports(header, module):
    result = {}
    inherited = None
    for fragment in header.split(','):
        fragment = fragment.strip()
        declaration = re.fullmatch(r'(input|output|inout)\s+(?:(?:wire|logic|reg)\s+)?'
                                   r'(signed\s+)?(?:\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*)?'
                                   r'(' + IDENTIFIER + r')', fragment)
        if declaration:
            direction, signed, high, low, name = declaration.groups()
            width = abs(int(high) - int(low)) + 1 if high is not None else 1
            inherited = (direction, width, bool(signed))
        elif re.fullmatch(IDENTIFIER, fragment) and inherited:
            name = fragment
        else:
            reject('UNSUPPORTED_ANSI_PORT_SYNTAX', module + ':' + fragment)
        if name in result:
            reject('DUPLICATE_PORT', module + ':' + name)
        result[name] = inherited
    return result


def parse_modules(raw):
    clean = strip_comments(raw)
    result = {}
    starts = list(re.finditer(r'\bmodule\s+(' + IDENTIFIER + r')\b', clean))
    for match in starts:
        name = match.group(1)
        start = match.end()
        while clean[start].isspace():
            start += 1
        if clean[start] == '#':
            start = clean.index('(', start)
            start = closing(clean, start) + 1
            while clean[start].isspace():
                start += 1
        if clean[start] != '(':
            reject('ONLY_ANSI_MODULES_SUPPORTED', name)
        end_header = closing(clean, start)
        end_match = re.search(r'\bendmodule\b', clean[end_header:])
        if end_match is None:
            reject('MISSING_ENDMODULE', name)
        if name in result:
            reject('DUPLICATE_MODULE_IN_FILE', name)
        body_end = end_header + end_match.start()
        result[name] = {'ports': module_ports(clean[start + 1:end_header], name),
                        'body': clean[end_header + 1:body_end], 'raw': raw}
    if not result:
        reject('NO_MODULE', 'source')
    return result


def instance_ports(module, child_type, instance_name):
    pattern = r'\b' + re.escape(child_type) + r'\b\s*'
    matches = []
    body = module['body']
    for match in re.finditer(pattern, body):
        offset = match.end()
        if offset < len(body) and body[offset] == '#':
            offset = body.index('(', offset)
            offset = closing(body, offset) + 1
        while offset < len(body) and body[offset].isspace():
            offset += 1
        found = re.match(IDENTIFIER, body[offset:])
        if not found or found.group(0) != instance_name:
            continue
        offset += found.end()
        while body[offset].isspace():
            offset += 1
        end = closing(body, offset)
        matches.append(body[offset + 1:end])
    if len(matches) != 1:
        reject('NAMED_INSTANCE_NOT_UNIQUE', child_type + ':' + instance_name)
    return matches[0]


def port(module, name, expected):
    word(name, 'port')
    found = module['ports'].get(name)
    if found != ('output', expected[0], expected[1]):
        reject('PUBLIC_OUTPUT_WIDTH_SIGNED_OR_EXISTENCE', name + ':' + str(found))


def evidence(items, source):
    if not array(items, 'evidence'):
        reject('SOURCE_EVIDENCE_REQUIRED', 'evidence')
    lines = source.splitlines()
    for item in items:
        fields(item, ('line', 'text'), 'evidence')
        integer(item['line'], 1, len(lines), 'evidence.line')
        exact = text(item['text'], 'evidence.text')
        if lines[item['line'] - 1] != exact or not strip_comments(exact).strip():
            reject('SOURCE_LINE_EVIDENCE_MISMATCH_OR_COMMENT_ONLY', str(item['line']))


def check_contract(contract, root):
    root = Path(root).resolve()
    fields(contract, ('schema', 'basis', 'observation_module', 'sample', 'sources',
                      'source_list', 'replacements', 'fields', 'limitations',
                      'm2_external_observer_mapping', 'pro_admission'), 'contract')
    if contract['schema'] != 'M1_R06_SOURCE_SEMANTICS_V1':
        reject('SCHEMA', 'contract')
    fields(contract['basis'], ('commit', 'evidence_origin'), 'basis')
    if re.fullmatch('[0-9a-f]{40}', text(contract['basis']['commit'], 'basis.commit')) is None:
        reject('COMMIT_REQUIRED', 'basis.commit')
    text(contract['basis']['evidence_origin'], 'basis.evidence_origin')
    if contract['m2_external_observer_mapping'] != 'UNRESOLVED_PENDING_M2_BLOB_AND_INTEGRATION':
        reject('M2_MAPPING_NOT_AUTHENTICATED_BY_THIS_CHECKER', 'm2_external_observer_mapping')
    if contract['pro_admission'] is not False:
        reject('PRO_ADMISSION_FORBIDDEN', 'pro_admission')
    word(contract['observation_module'], 'observation_module')
    if contract['sample'] != SAMPLE:
        reject('WRONG_SAMPLE_EDGE_OR_PHASE', 'sample')
    limitations = array(contract['limitations'], 'limitations')
    for required in ('NO_HDL_RUN', 'NO_GOLDEN_MATH_PROOF', 'NO_PRO_BOARD_PASS',
                     'M2_PUBLIC_ROUTE_AND_SOURCE_ADMISSION_REQUIRED', 'RESET_EDGES_REMAIN_REQUIRED'):
        if required not in limitations:
            reject('LIMITATION_REQUIRED', required)
    sources, modules = {}, {}
    for row in array(contract['sources'], 'sources'):
        fields(row, ('id', 'path', 'sha256', 'role'), 'source')
        key = word(row['id'], 'source.id')
        if key in sources or row['role'] not in ('BASELINE', 'CANDIDATE', 'DEPENDENCY'):
            reject('DUPLICATE_SOURCE_OR_ROLE', key)
        path = bound_path(root, row['path'])
        raw = path.read_bytes()
        if len(raw) > MAX_BYTES or digest(raw) != sha(row['sha256'], key):
            reject('SOURCE_SHA_MISMATCH', key)
        decoded = raw.decode('utf-8')
        sources[key] = dict(row, raw=decoded, path_object=path)
        modules[key] = parse_modules(decoded)
    selected = array(contract['source_list'], 'source_list')
    for item in selected:
        word(item, 'source_list')
    if not selected or len(set(selected)) != len(selected):
        reject('SOURCE_LIST_EMPTY_OR_DUPLICATE', 'source_list')
    compiled_modules = {}
    for key in selected:
        word(key, 'source_list')
        if key not in sources:
            reject('UNBOUND_SOURCE', key)
        for name in modules[key]:
            if name in compiled_modules:
                reject('DUPLICATE_COMPILED_MODULE', name)
            compiled_modules[name] = key
    replacements = array(contract['replacements'], 'replacements')
    replaced = set()
    for row in replacements:
        fields(row, ('baseline', 'candidate', 'module'), 'replacement')
        old, new, module = row['baseline'], row['candidate'], row['module']
        for item in (old, new, module):
            word(item, 'replacement')
        if old not in sources or new not in sources:
            reject('UNBOUND_REPLACEMENT', str(row))
        if (sources[old]['role'], sources[new]['role']) != ('BASELINE', 'CANDIDATE'):
            reject('REPLACEMENT_ROLE', module)
        if module not in modules[old] or module not in modules[new]:
            reject('REPLACEMENT_MODULE_MISMATCH', module)
        if old in selected or new not in selected or new in replaced:
            reject('REPLACEMENT_NOT_EXPLICIT_OR_DUPLICATE', module)
        if strip_observation_markers(sources[new]['raw']) != sources[old]['raw']:
            reject('SOURCE_CHANGED_OUTSIDE_OBSERVER_MARKERS', module)
        replaced.add(new)
    if {key for key in selected if sources[key]['role'] == 'CANDIDATE'} != replaced:
        reject('CANDIDATE_WITHOUT_EXPLICIT_REPLACEMENT', 'source_list')
    if contract['observation_module'] not in compiled_modules:
        reject('OBSERVATION_MODULE_NOT_COMPILED', contract['observation_module'])
    field_rows = array(contract['fields'], 'fields')
    if len(field_rows) != 19:
        reject('EXACTLY_19_FIELDS_REQUIRED', str(len(field_rows)))
    seen, unresolved, reports = set(), [], []
    for row in field_rows:
        fields(row, ('semantic_id', 'public_name', 'width', 'signed', 'sample', 'update_rule',
                     'semantic_rules', 'definition', 'derivation', 'source', 'export'), 'field')
        key = row['semantic_id']
        if type(key) is not str or key not in RULES or key in seen:
            reject('UNKNOWN_OR_DUPLICATE_SEMANTIC_ID', str(key))
        seen.add(key)
        expected = RULES[key]
        integer(row['width'], 1, 128, key + '.width')
        if type(row['signed']) is not bool or (row['width'], row['signed']) != expected[:2]:
            reject('FIELD_WIDTH_OR_SIGNED', key)
        if row['sample'] != SAMPLE or row['update_rule'] != expected[2]:
            reject('FIELD_SAMPLE_OR_UPDATE_RULE', key)
        if row['semantic_rules'] != expected[3]:
            reject('SEMANTIC_RULES_MISMATCH', key)
        if row['public_name'] != PORTS[key]:
            reject('PUBLIC_NAME_MISMATCH', key)
        text(row['definition'], key + '.definition')
        if row['derivation'] != 'DIRECT_SOURCE_OBSERVATION':
            reject('ALGEBRAIC_OR_INFERRED_ATTRIBUTION_FORBIDDEN', key)
        source = row['source']
        fields(source, ('file_id', 'sha256', 'module', 'signal', 'evidence'), key + '.source')
        sid = source['file_id']
        word(sid, key + '.source.file_id')
        if sid not in selected or sid not in sources:
            reject('FIELD_SOURCE_NOT_COMPILED_OR_BOUND', key)
        if source['sha256'] != sources[sid]['sha256']:
            reject('FIELD_SOURCE_SHA_MISMATCH', key)
        word(source['module'], key + '.source.module')
        if source['module'] not in modules[sid]:
            reject('SOURCE_MODULE_MISSING', key)
        port(modules[sid][source['module']], source['signal'], expected)
        evidence(source['evidence'], sources[sid]['raw'])
        body = modules[sid][source['module']]['body']
        assignments = re.findall(r'\bassign\s+' + re.escape(source['signal']) + r'\s*=([^;]+);', body)
        if len(assignments) != 1 or re.sub(r'\s+', '', assignments[0]) != re.sub(r'\s+', '', ALIASES[key]):
            reject('SOURCE_ALIAS_OR_COMMON_ADVANCE_MISMATCH', key)
        export = row['export']
        fields(export, ('status', 'reason', 'route'), key + '.export')
        route = array(export['route'], key + '.route')
        if export['status'] == 'UNRESOLVED':
            text(export['reason'], key + '.reason')
            if route:
                reject('UNRESOLVED_MUST_NOT_CLAIM_ROUTE', key)
            unresolved.append(key)
        elif export['status'] == 'PROVIDED':
            if export['reason'] is not None or not route:
                reject('PROVIDED_REASON_OR_ROUTE', key)
            previous = None
            for hop in route:
                fields(hop, ('file_id', 'module', 'port', 'instance'), key + '.hop')
                hid = hop['file_id']
                word(hid, key + '.hop.file_id')
                word(hop['module'], key + '.hop.module')
                if hid not in selected or hop['module'] not in modules.get(hid, {}):
                    reject('ROUTE_SOURCE_NOT_COMPILED_OR_BOUND', key)
                module = modules[hid][hop['module']]
                port(module, hop['port'], expected)
                if previous is None:
                    if (hid, hop['module'], hop['port'], hop['instance']) != (
                            sid, source['module'], source['signal'], None):
                        reject('ROUTE_DOES_NOT_START_AT_BOUND_SOURCE', key)
                else:
                    word(hop['instance'], key + '.instance')
                    pins = instance_ports(module, previous['module'], hop['instance'])
                    expression = r'\.' + re.escape(previous['port']) + r'\s*\(\s*' + re.escape(hop['port']) + r'\s*\)'
                    if len(re.findall(expression, pins)) != 1:
                        reject('PUBLIC_PORT_ROUTE_NOT_DIRECT', key)
                previous = hop
            if route[-1]['module'] != contract['observation_module'] or route[-1]['port'] != row['public_name']:
                reject('ROUTE_NOT_TO_PUBLIC_OBSERVATION_SURFACE', key)
        else:
            reject('EXPORT_STATUS', key)
        reports.append({'semantic_id': key, 'export_status': export['status'],
                        'source_sha256': source['sha256'], 'public_name': row['public_name']})
    return {'schema': 'M1_R06_SOURCE_SEMANTICS_RESULT_V1',
            'status': 'PENDING_PUBLIC_EXPORTS' if unresolved else 'STATIC_SOURCE_SEMANTICS_READY',
            'checked_fields': 19, 'unresolved': unresolved, 'fields': reports,
            'source_list': selected, 'source_sha256': {key: sources[key]['sha256'] for key in sources},
            'hdl_executed': False, 'golden_math_verified': False, 'board_release_allowed': False,
            'm2_external_observer_mapping': contract['m2_external_observer_mapping'],
            'pro_admission': False,
            'level': 'L0_STATIC_CONTRACT_ONLY'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out.exists():
        print('REFUSE_OVERWRITE:' + str(args.out), file=sys.stderr)
        return 2
    try:
        result = check_contract(read_json(args.contract), args.root)
        result['contract_sha256'] = digest(args.contract.read_bytes())
    except (ContractError, OSError, UnicodeError, IndexError) as error:
        result = {'schema': 'M1_R06_SOURCE_SEMANTICS_RESULT_V1', 'status': 'REJECTED',
                  'error': str(error), 'hdl_executed': False, 'board_release_allowed': False}
    try:
        with args.out.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write('\n')
    except OSError as error:
        print('OUTPUT_WRITE_REFUSED:' + str(error), file=sys.stderr)
        return 2
    print(result['status'])
    return {'STATIC_SOURCE_SEMANTICS_READY': 0, 'PENDING_PUBLIC_EXPORTS': 3, 'REJECTED': 2}[result['status']]


if __name__ == '__main__':
    sys.exit(main())
