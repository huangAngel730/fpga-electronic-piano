"""Bounded file/port checks only. This does not compile or certify RTL behavior."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parent.parents[3]
REL = 'code/rtl/board/m2_138k_pro_fourvoice_candidate_20261016/r06_observer_20261017'
DOC = 'code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/r06_observer_20261017'
NAMES = ['m2_fourvoice_timbre_delay_frame_core_r06.sv',
         'm2_fourvoice_timbre_delay_board_top_r06.sv',
         'm2_138k_pro_fourvoice_observer_top_r06.sv', 'm2_r06_tx_identity_sidecar.sv']

def clean(text):
    return re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)

def compact(text):
    return re.sub(r'\s+', '', clean(text))

def require(condition, code):
    if not condition:
        raise ValueError(code)

def body(text, name):
    text = clean(text)
    matches = list(re.finditer(r'\b' + re.escape(name) + r'\s*\(', text))
    require(len(matches) == 1, 'INSTANCE_NOT_UNIQUE:' + name)
    begin = matches[0].end()
    depth = 1
    for end in range(begin, len(text)):
        depth += (text[end] == '(') - (text[end] == ')')
        if depth == 0:
            return text[begin:end]
    raise ValueError('UNBALANCED_INSTANCE:' + name)

def connections(text, name):
    value = body(text, name)
    rows = {}
    for match in re.finditer(r'\.(\w+)\s*\(', value):
        key = match[1]
        require(key not in rows, 'DUPLICATE_PIN:' + key)
        start = match.end()
        depth = 1
        for end in range(start, len(value)):
            depth += (value[end] == '(') - (value[end] == ')')
            if depth == 0:
                rows[key] = compact(value[start:end])
                break
        else:
            raise ValueError('UNBALANCED_PIN:' + key)
    return rows

def observation_ports(text):
    pattern = r'\boutput\s+(?:wire|logic)\s+(signed\s+)?(?:\[(\d+):(\d+)\]\s*)?(obs_\w+)\b'
    rows = {}
    for match in re.finditer(pattern, clean(text)):
        require(match[4] not in rows, 'DUPLICATE_OBSERVATION_PORT')
        width = abs(int(match[2]) - int(match[3])) + 1 if match[2] else 1
        rows[match[4]] = {'width': width, 'signed': bool(match[1])}
    return rows

def check(root, binding_path):
    root = Path(root).resolve()
    binding = json.loads(Path(binding_path).read_text(encoding='utf-8'))
    require(binding['schema'] == 'M2_R06_OBSERVER_EXPORTS_V1', 'BINDING_SCHEMA')
    require(binding['sampling_phase'] == 'POSEDGE_PRE_NBA', 'SAMPLING_PHASE')
    require(binding['HDL_executed'] is False and binding['board_release_allowed'] is False,
            'FALSE_VERIFICATION_LEVEL')
    texts = {}
    for name in NAMES:
        raw = (root / REL / name).read_bytes()
        require(len(raw) < 200000 and b'\r\n' not in raw, 'SOURCE_SIZE_OR_EOL')
        require(hashlib.sha256(raw).hexdigest() == binding['source_sha256'][name], 'SOURCE_SHA:' + name)
        texts[name] = raw.decode('utf-8')
    core, board, top, sidecar = [texts[n] for n in NAMES]
    expected = binding['expected_observation_ports']
    require(len(expected) == 38, 'EXPECTED_PORT_COUNT')
    require(observation_ports(top) == expected and observation_ports(board) == expected,
            'PUBLIC_PORT_WIDTH_OR_SIGN')
    outer = connections(top, 'u_legacy')
    require(all(outer.get(n) == n for n in expected), 'WRAPPER_ROUTE')
    require('m2_fourvoice_timbre_delay_board_top_r06#(.SOURCE_MODE(0))u_legacy(' in compact(top),
            'FOURVOICE_MODE_NOT_FIXED')
    archive = root / binding['source_archive']
    require(hashlib.sha256(archive.read_bytes()).hexdigest() == binding['source_archive_sha256'],
            'BASELINE_ARCHIVE_SHA')
    with zipfile.ZipFile(archive) as z:
        original_core = z.read('source_closure/inputs/sources/m2_fourvoice_timbre_delay_frame_core.sv').decode('utf-8')
        original_board = z.read('source_closure/inputs/sources/m2_fourvoice_timbre_delay_board_top.sv').decode('utf-8')
    # Preserve actual frozen producer/control connections, not a self-made oracle.
    for instance in ('u_chain', 'u_frame_adapter', 'u_latency'):
        require(connections(core, instance) == connections(original_core, instance),
                'PRODUCTION_CONNECTION_DRIFT:' + instance)
    require(connections(board, 'u_i2s_tx') == connections(original_board, 'u_i2s_tx'), 'TX_CONNECTION_DRIFT')
    old_audio, new_audio = connections(original_board, 'u_audio_core'), connections(board, 'u_audio_core')
    require(all(new_audio.get(k) == v for k, v in old_audio.items() if k != 'committed_clip'),
            'BOARD_AUDIO_CONNECTION_DRIFT')
    require('assignobs_result_clip_mask={clip_right,clip_left};' in compact(core), 'CLIP_PACKING')
    pins = connections(core, 'u_tx_identity_sidecar')
    inputs = re.findall(r'\binput\s+logic\s+(?:signed\s+)?(?:\[[^]]+\]\s*)?(\w+)', clean(sidecar))
    outputs = re.findall(r'\boutput\s+wire\s+(?:signed\s+)?(?:\[[^]]+\]\s*)?(\w+)', clean(sidecar))
    require(len(inputs) + len(outputs) == 28 and set(pins) == set(inputs + outputs), 'SIDECAR_PIN_SET')
    require(all(pins[n] == '' or pins[n].startswith('obs_') for n in outputs), 'DIAGNOSTIC_FEEDBACK')
    critical = {'result_valid': 'result_valid', 'result_ready': 'result_ready', 'result_id': 'result_id',
                'result_clip_mask': '{clip_right,clip_left}', 'commit_pulse': 'commit_pulse',
                'commit_id': 'committed_id', 'buffer_pending_valid': 'pending_valid',
                'play_left': 'play_left', 'play_right': 'play_right', 'tx_valid': "1'b1"}
    require(all(pins.get(k) == v for k, v in critical.items()), 'SIDECAR_SOURCE_BINDING')
    s = compact(sidecar)
    require('assigntx_sample_valid=rst_n&&frame_tick&&tx_valid;' in s, 'TX_ADOPTION_PREDICATE')
    require('pending_clip_mask<=result_hold_clip_mask;' in s and
            'result_hold_clip_mask<=result_clip_mask;' in s, 'CLIP_HOLD_TO_COMMIT')
    require('assigntx_req_id_valid=tx_metadata_valid&&!selected_startup;' in s, 'STARTUP_ID_VALIDITY')
    require('frame_id_overflow_sticky' in s and '!frame_id_overflow' in s, 'ORDINAL_GUARD')
    require(not re.search(r'\b(?:force|release)\b', clean(sidecar)), 'HIERARCHICAL_OVERRIDE')
    return {'status': 'PASS_STATIC_FILE_PORT_CHECKS_ONLY', 'level': 'L0', 'ports': 38,
            'HDL_executed': False, 'authority_verified': False, 'board_release_allowed': False}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--bindings', type=Path)
    args = parser.parse_args()
    try:
        result = check(args.root, args.bindings or args.root / DOC / 'OBSERVER_EXPORTS_R06C3.json')
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as error:
        print(json.dumps({'status': 'REJECT', 'error': str(error), 'HDL_executed': False}))
        return 2
    print(json.dumps(result))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
