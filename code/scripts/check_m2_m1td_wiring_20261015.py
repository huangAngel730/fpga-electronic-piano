"""Static identity and wiring audit for an isolated 138K M1 timbre/delay project.

No simulator or EDA calls. Proves source bindings, not temporal behavior.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
TOP = 'm2_fourvoice_timbre_delay_board_top'


def ident(path):
    data = path.read_bytes()
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def board_check(top, core, adapter, sdc, cst):
    checks = {
        'm1_chain_only_once': len(re.findall(r'\bm1td_timbre_delay_chain\s+u_chain\s*\(', core)) == 1,
        'frame_adapter_only_once': len(re.findall(r'\bpremixed_frame_adapter\s+u_frame_adapter\s*\(', core)) == 1,
        'req_identity': '.sample_req(request_accept)' in core and
                        '.sample_req_id(request_id)' in core and
                        '.candidate_sample_id(request_id)' in core,
        'result_identity': '.candidate_result_id(result_id)' in core and
                           '.result_id(result_id)' in core and
                           '.committed_id(committed_id)' in core,
        'signed_stereo': '.candidate_left(result_left)' in core and
                         '.candidate_right(result_right)' in core and
                         '.play_left(play_left)' in core and '.play_right(play_right)' in core,
        'clip_success_only': '.candidate_clipped(clip_left | clip_right)' in core and
                             '.commit_pulse(commit_pulse)' in core and
                             '.pcm_commit(commit_pulse)' in core,
        'reset_frame': '.rst_n(rst_n)' in core and '.frame_tick(frame_tick)' in core,
        'config_bound': '.config_valid(m1_config_pending)' in top and
                        'm1_config_pending && m1_config_ready' in top and
                        '.config_delay_samples(16\'d1)' in top,
        'one_sender': len(re.findall(r'\bi2s_tx\s*#', top)) == 1,
        'board_midi': '.event_valid(shared_event_valid)' in top and
                      '.event_data(shared_event_data)' in top,
        'board_pcm_to_sender': '.pcm_left  (buffered_left)' in top and
                               '.pcm_right (buffered_right)' in top,
        'board_frame': '.frame_tick(i2s_frame_tick)' in top,
        'no_private_old_voices': 'u_audio_core.u_bank' not in top and
                                 'u_audio_core.u_commit' not in top,
        'sdc_no_stale_active_endpoints': not any('g_polyphonic.u_audio_core/u_bank' in line and
            not line.lstrip().startswith('#') for line in sdc.splitlines()),
        'cst_no_stale_active_locations': not any('g_polyphonic.u_audio_core/u_bank' in line and
            line.startswith('INS_LOC') for line in cst.splitlines()),
    }
    for key, ok in checks.items():
        require(ok, 'WIRING:' + key)
    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prepared', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    out = args.output.resolve()
    allowed = (ROOT / 'code/output').resolve()
    require(not out.exists() and out != allowed and out.is_relative_to(allowed), 'OUTPUT_SCOPE_OR_EXISTS')
    out.mkdir(parents=True)
    result = {'status': 'FAIL_PARTIAL', 'error': None, 'scope': 'STATIC_WIRING_L0',
              'new_simulation': 0, 'new_EDA': 0, 'physical_STA': 'NOT_RUN'}
    try:
        prepared = args.prepared.resolve()
        require(prepared.is_relative_to(allowed), 'PREPARED_SCOPE')
        receipt = json.loads((prepared / 'PREPARATION_RECEIPT.json').read_text(encoding='utf-8'))
        require(receipt['status'] == 'PREPARED_NOT_PHYSICALLY_ADMITTED', 'PREPARED_FAILED')
        project = prepared / (TOP + '.gprj')
        require(ident(project)['sha256'] == receipt['project_sha256'], 'PROJECT_DRIFT')
        files = [Path(x.attrib['path']) for x in ET.parse(project).getroot().iter('File')]
        baseline_project = ROOT / 'code/build/138k_l/runs/run_20261006_a0cb805_exact/project/audio_visual_coexistence_top.gprj'
        old_files = list(ET.parse(baseline_project).getroot().iter('File'))
        require(receipt.get('excluded_unused_legacy_dds') == 'sources/dds_oscillator.sv', 'LEGACY_DDS_EXCLUSION')
        require(len(files) == len(old_files) - 1 + 23 and
                all(p.is_file() and p.is_relative_to(prepared) for p in files), 'PROJECT_FILES')
        for file in files:
            relative = file.relative_to(prepared).as_posix()
            bound = {k.replace('\\', '/'):v for k,v in receipt['input_files'].items()}
            require(ident(file) == bound[relative], 'FILE_DRIFT:' + relative)
        base = prepared / 'inputs'
        top_file = base / 'sources' / (TOP + '.sv')
        core_file = base / 'sources/m2_fourvoice_timbre_delay_frame_core.sv'
        adapter_file = base / 'sources/premixed_frame_adapter.sv'
        sdc_file = base / 'constraints/audio_visual_hold055.sdc'
        cst_file = base / 'constraints/audio_visual.cst'
        texts = [p.read_text(encoding='utf-8') for p in (top_file, core_file, adapter_file, sdc_file, cst_file)]
        checks = board_check(*texts)
        # Ensure both target miswirings are actually rejected by the same audit.
        left_wrong = texts[1].replace('.candidate_left(result_left)', '.candidate_left(result_right)', 1)
        clip_wrong = texts[1].replace('.candidate_clipped(clip_left | clip_right)', '.candidate_clipped(1\'b0)', 1)
        for mutant, reason in ((left_wrong, 'WIRING:signed_stereo'),(clip_wrong,'WIRING:clip_success_only')):
            try:
                board_check(texts[0], mutant, texts[2], texts[3], texts[4])
            except ValueError as exc:
                require(str(exc) == reason, 'WRONG_MUTATION_DIAGNOSTIC')
            else:
                raise ValueError('MUTATION_ACCEPTED')
        result.update(status='STATIC_WIRING_PASS_NOT_RTL', files_bound=len(files), checks=checks,
                      negative_checks=2, project_sha256=ident(project)['sha256'],
                      module_sha256=ident(core_file)['sha256'])
    except Exception as exc:
        result['error'] = type(exc).__name__ + ': ' + str(exc)
    result['exit_code'] = 0 if result['error'] is None else 1
    (out / 'STATIC_RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result.get(k) for k in ('status','error','files_bound','negative_checks','exit_code')}))
    return result['exit_code']

if __name__ == '__main__':
    raise SystemExit(main())