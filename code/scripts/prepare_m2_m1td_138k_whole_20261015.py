"""Stage a reversible M1 four-voice timbre/delay successor of the exact T056 L board.

All inputs are read-only; the staged project is explicitly NOT a PnR/STA build.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'code/build/138k_l/runs/run_20261006_a0cb805_exact'
M1_ZIP = Path('D:/Cmove/CUsersAngel17move/Downloads/M1_双音色与立体声延迟完整链_20261014.zip')
M1_SHA = '5c18926ae307301e91ec0e44dcf4a48b2fb57adec71ad46c494b14df59913b06'
M1_PREFIX = 'code/rtl/audio/m1_timbre_delay_chain_candidate_20261014/'
CORE = ROOT / 'code/rtl/board/m2_fourvoice_timbre_delay_candidate_20261015/m2_fourvoice_timbre_delay_frame_core.sv'
ADAPTER = ROOT / 'code/rtl/audio_out/m2_polyphony_frame_candidate_20261012/premixed_frame_adapter.sv'
CAD = Path('D:/Gowin/oss-cad-suite')
JOB = ROOT / 'code/software/t052_runner_acceptance_candidate_20261012/windows_job.py'
VENDOR = Path('D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/simlib/gw5a/prim_sim.v')
STUB_PLL = ROOT / 'code/tb/board/t058_waveform_integration_20261008/clock_plan_sim.v'
STUB_DVI = ROOT / 'code/rtl/138K_try/hold_trials_20261005/dvi_sim_stub.v'
NEW_TOP = 'm2_fourvoice_timbre_delay_board_top'


def identity(path):
    raw = Path(path).read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--output', required=True, type=Path)
    args = cli.parse_args()
    out = args.output.resolve()
    allowed = (ROOT / 'code/output').resolve()
    if out.exists() or out == allowed or not out.is_relative_to(allowed):
        raise ValueError('NEW_OUTPUT_UNDER_CODE_OUTPUT_REQUIRED')
    out.mkdir(parents=True)
    start = time.monotonic()
    result = {'status': 'FAIL_PARTIAL', 'error': None, 'new_EDA_calls': 0,
              'production_modified': False, 'physical_STA': 'NOT_RUN',
              'board_release_allowed': False, 'compile_only': 'NOT_RUN',
              'stage': str(out), 'm1_zip_sha256': M1_SHA, 'source_before': {},
              'source_after': {}, 'path_adaptations': {}, 'disabled_old_constraints': []}
    before = {}
    try:
        frozen = BASE / 'project/receipt.json'
        source_receipt = json.loads(frozen.read_text(encoding='utf-8'))
        assert source_receipt['input_count'] == 56
        before[frozen] = identity(frozen)
        before[M1_ZIP] = identity(M1_ZIP)
        assert before[M1_ZIP]['sha256'] == M1_SHA
        for path in (CORE, ADAPTER, Path(__file__)):
            before[path] = identity(path)
        inputs = out / 'inputs'
        original = BASE / 'project/inputs'
        for name, item in source_receipt['inputs'].items():
            source = original / name
            assert identity(source)['sha256'] == item['adapted_sha256'], name
            before[source] = identity(source)
            dest = inputs / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(source.read_bytes())
        with zipfile.ZipFile(M1_ZIP) as bundle:
            assert bundle.testzip() is None
            manifest_path = 'code/docs/test/m1_timbre_delay_chain_candidate_20261014/FINAL_MANIFEST.json'
            manifest = json.loads(bundle.read(manifest_path))
            members = {x['path']: x for x in manifest['members']}
            for name in bundle.namelist():
                if not name.startswith(M1_PREFIX) or not name.endswith(('.sv', '.v', '.mem', '.svh', '.hex')):
                    continue
                relative = name.removeprefix(M1_PREFIX)
                if relative.startswith('dependencies/') or relative.endswith(('.sv', '.v')):
                    dest = inputs / 'sources' / Path(relative).name
                else:
                    dest = inputs / relative
                raw = bundle.read(name)
                item = members[name]
                assert len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256']
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    assert dest.read_bytes() == raw, 'SOURCE_ROM_OR_PACKAGE_COLLISION:' + relative
                else:
                    dest.write_bytes(raw)
        for source in (CORE, ADAPTER):
            dest = inputs / 'sources' / source.name
            assert not dest.exists(), 'M2_SOURCE_COLLISION'
            dest.write_bytes(source.read_bytes())
        top = inputs / 'sources' / 'audio_visual_coexistence_top.sv'
        original_top = top.read_text(encoding='utf-8')
        first = original_top.index('        polyphonic_audio_core u_audio_core(')
        last = original_top.index('      end\n    endgenerate', first)
        connection = '''        logic m1_config_pending;
        wire m1_config_ready, m1_request_accept, m1_commit;
        wire [31:0] m1_request_id;
        always_ff @(posedge core_clk or negedge rst_sync_n) begin
          if (!rst_sync_n) m1_config_pending <= 1'b1;
          else if (m1_config_pending && m1_config_ready) m1_config_pending <= 1'b0;
        end
        m2_fourvoice_timbre_delay_frame_core u_audio_core (
          .clk(core_clk), .rst_n(rst_sync_n), .event_valid(shared_event_valid),
          .event_ready(shared_event_ready), .event_data(shared_event_data),
          .frame_tick(i2s_frame_tick), .config_valid(m1_config_pending),
          .config_ready(m1_config_ready), .config_enable(1'b1),
          .config_delay_samples(16'd1), .config_dry_gain(15'd32767),
          .config_wet_gain(15'd16384), .config_feedback(15'd0),
          .play_left(buffered_left), .play_right(buffered_right),
          .pending_valid(pending_valid), .commit_pulse(m1_commit),
          .active_voice_count(status_active_voice_count),
          .clip_count(status_clip_count), .audio_underrun(audio_underrun),
          .audio_frame_count(audio_frame_count),
          .pcm_request_count(pcm_request_count),
          .pcm_commit_count(pcm_commit_count),
          .max_processing_cycles(core_max_processing_cycles),
          .request_accept(m1_request_accept), .request_id(m1_request_id),
          .committed_id(produced_req_id), .committed_left(produced_left),
          .committed_right(produced_right), .committed_clip()
        );
        assign voice_active = |status_active_voice_count;
        // Legacy debug alias is not consumed outside the fixed-tone branch.
        assign voice_note = 7'd0;
        assign frame_sample_req = m1_request_accept;
        assign sample_req_id = m1_request_id;
        assign pcm_valid_q = m1_commit;
        assign pcm_ready = 1'b1;
'''
        new_top = original_top[:first] + connection + original_top[last:]
        old_title = 'module audio_visual_coexistence_top #'
        assert new_top.count(old_title) == 1
        new_top = new_top.replace(old_title, 'module ' + NEW_TOP + ' #', 1)
        new_top = new_top.replace('AUDIO_VISUAL_COEXISTENCE_TOP_SV', 'M2_FOURVOICE_TIMBRE_DELAY_TOP_SV')
        old_header = original_top.split(') (', 1)[1].split(');', 1)[0]
        new_header = new_top.split(') (', 1)[1].split(');', 1)[0]
        assert old_header == new_header, 'BOARD_PUBLIC_PORT_CHANGED'
        assert not re.search(r'u_audio_core\.u_(bank|commit)', new_top), 'PRIVATE_SOURCE_ALIAS'
        top_new = inputs / 'sources' / (NEW_TOP + '.sv')
        top_new.write_text(new_top, encoding='utf-8', newline='\n')
        # Only ROM/include path literals change inside staged copies, with exact inverse.
        old_prefix = (BASE / 'project/inputs').as_posix() + '/'
        new_prefix = inputs.as_posix() + '/'
        for dest in (inputs / 'sources').glob('*'):
            if dest.suffix not in ('.sv', '.v') or dest == top:
                continue
            raw = dest.read_bytes()
            updates = raw.replace(old_prefix.encode(), new_prefix.encode())
            if dest.name.startswith('m1td_'):
                updates = re.sub(rb'"rom/([^"\r\n]+\.(?:mem|hex))"',
                                 lambda m: ('"' + (inputs / 'rom' / m[1].decode()).as_posix() + '"').encode(), updates)
                updates = updates.replace(b'"sustain_controller_ports.svh"',
                    ('"' + (inputs / 'include/sustain_controller_ports.svh').as_posix() + '"').encode())
            for header in ("sine_table.svh", "sustain_controller_ports.svh"):
                absolute = (chr(34) + (inputs / "include" / header).as_posix() + chr(34)).encode()
                updates = updates.replace(b'`include ' + absolute,
                                          b'`include ' + bytes([34]) + header.encode() + bytes([34]))
            if dest.name == 'm1td_note_pitch.sv':
                # This forked helper shares a guard name with the untouched
                # baseline note_pitch.sv, so isolate the guard in staged bytes.
                assert updates.count(b'`ifndef NOTE_PITCH_SV') == 1
                assert updates.count(b'`define NOTE_PITCH_SV') == 1
                updates = updates.replace(b'`ifndef NOTE_PITCH_SV', b'`ifndef M1TD_NOTE_PITCH_SV')
                updates = updates.replace(b'`define NOTE_PITCH_SV', b'`define M1TD_NOTE_PITCH_SV')
                updates = updates.replace(b'`endif // NOTE_PITCH_SV', b'`endif // M1TD_NOTE_PITCH_SV')
            if updates != raw:
                dest.write_bytes(updates)
                result['path_adaptations'][dest.name] = {'original_sha256': hashlib.sha256(raw).hexdigest(),
                    'staged_sha256': hashlib.sha256(updates).hexdigest()}
        # The new top is a copy, and the original frozen top remains byte-identical.
        assert top.read_text(encoding='utf-8') == original_top
        sdc = inputs / 'constraints/audio_visual_hold055.sdc'
        lines = []
        for line in sdc.read_text(encoding='utf-8').splitlines():
            if 'g_polyphonic.u_audio_core/u_bank' in line and not line.lstrip().startswith('#'):
                result['disabled_old_constraints'].append(line)
                lines.append('# M1TD NEW NETLIST ENDPOINT REQUIRED: ' + line)
            else:
                lines.append(line)
        assert len(result['disabled_old_constraints']) == 2, 'OLD_AUDIO_SDC_ENDPOINT_COUNT'
        sdc.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
        cst = inputs / 'constraints/audio_visual.cst'
        cst_lines = []
        old_loc_count = 0
        for line in cst.read_text(encoding='utf-8').splitlines():
            if line.startswith('INS_LOC ') and 'g_polyphonic.u_audio_core/u_bank' in line:
                old_loc_count += 1
                cst_lines.append('// M1TD NEW NETLIST ENDPOINT REQUIRED: ' + line)
            else:
                cst_lines.append(line)
        assert old_loc_count == 2, 'OLD_AUDIO_CST_ENDPOINT_COUNT'
        cst.write_text('\n'.join(cst_lines) + '\n', encoding='utf-8', newline='\n')
        result['disabled_old_cst_locs'] = old_loc_count
        tree = ET.parse(BASE / 'project/audio_visual_coexistence_top.gprj')
        filelist = tree.getroot().find('FileList')
        assert filelist is not None
        for entry in list(filelist.findall('File')):
            old_path = Path(entry.attrib['path'])
            relative = old_path.relative_to(BASE / 'project/inputs')
            if relative.name == 'dds_oscillator.sv':
                # Unused L audio core collides with M1's same-named ROM helper.
                filelist.remove(entry)
                result['excluded_unused_legacy_dds'] = relative.as_posix()
                continue
            path = inputs / relative
            if relative.name == 'audio_visual_coexistence_top.sv':
                path = top_new
            entry.set('path', path.as_posix())
        originals = {x.attrib['path'] for x in filelist.findall('File')}
        for source in sorted((inputs / 'sources').glob('*')):
            if source.suffix in ('.sv', '.v') and source != top and source.name != 'dds_oscillator.sv' and source.as_posix() not in originals:
                ET.SubElement(filelist, 'File', path=source.as_posix(), type='file.verilog', enable='1')
        project = out / (NEW_TOP + '.gprj')
        tree.write(project, encoding='utf-8', xml_declaration=True)
        result['project_sha256'] = identity(project)['sha256']
        result['input_files'] = {str(p.relative_to(out)): identity(p) for p in inputs.rglob('*') if p.is_file()}
        result['source_before'] = {str(p): identity(p) for p in before}
        result['source_after'] = {str(p): identity(p) for p in before}
        assert result['source_before'] == result['source_after'], 'PROTECTED_SOURCE_DRIFT'
        result['status'] = 'PREPARED_NOT_PHYSICALLY_ADMITTED'
    except Exception as exc:
        result['error'] = type(exc).__name__ + ': ' + str(exc)
    result['seconds'] = round(time.monotonic() - start, 3)
    result['exit_code'] = 0 if result['error'] is None else 1
    (out / 'PREPARATION_RECEIPT.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('status', 'error', 'seconds', 'exit_code')}, ensure_ascii=False))
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())