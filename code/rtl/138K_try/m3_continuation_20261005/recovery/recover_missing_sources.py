"""Reconstruct documented generated inputs, accepting only historical SHA matches.

Inputs are already copied into the isolated tree. No repository writes, builds,
IP decryption, semantic guessing, or source replacement on a mismatch.
"""
import hashlib
import json
from pathlib import Path, PureWindowsPath

HERE = Path(__file__).resolve().parent
if HERE != Path('E:/FPGA/GAOYUNFPGA/138K_try/m3_continuation_20261005/recovery'):
    raise ValueError('Unexpected recovery location')
BASE = HERE / 'audio_e5eb025'
AUDIT = HERE.parent / 'audit_snapshot'
manifest = json.loads((AUDIT / 'V0165_manifest_original.json').read_text(encoding='utf-8'))
expected = {PureWindowsPath(x['actual_source']).name: x['actual_sha']
            for x in manifest['source_builds']}
roms = {PureWindowsPath(p).name: p.replace('\\', '/') for p in manifest['roms']}
historical_base = ('D:/17/project_17/fpga_gowin/code/output/renderer_timing_20260930/'
                   'code/output/audio_visual_v1_external_reset_20261001/audio_snapshot')
OUT = HERE / 'hash_proven_inputs'
OUT.mkdir(exist_ok=True)
attempts = []


def sha(data):
    return hashlib.sha256(data).hexdigest()


def accept(name, content, method, input_files):
    data = content.encode('utf-8') if isinstance(content, str) else content
    matched = sha(data) == expected[name]
    attempts.append({'name': name, 'method': method, 'sha256': sha(data),
                     'expected_sha256': expected[name], 'matched': matched,
                     'input_files': input_files})
    if matched:
        target = OUT / name
        if target.exists() and target.read_bytes() != data:
            raise ValueError('Conflicting proof')
        target.write_bytes(data)
    return matched


def audio_stage(relative):
    text = (BASE / relative).read_text(encoding='utf-8')
    for header, location in [('sustain_controller_ports.svh', 'board'),
                             ('sine_table.svh', 'common')]:
        text = text.replace('`include "' + header + '"',
                            '`include "' + historical_base + '/code/rtl/'
                            + location + '/' + header + '"')
    for name in ['sine_1024_8192.mem', 'sine_1024_32767.mem',
                 'velocity_gain_rom.mem', 'piano_band_4x256_8191.mem']:
        text = text.replace('model/generated/wavetables/' + name,
                            historical_base + '/code/model/generated/wavetables/' + name)
    return text


for relative in ['code/rtl/common/simple_voice.sv',
                 'code/rtl/input/sustain_control/sustain_controller.sv']:
    accept(Path(relative).name, audio_stage(relative),
           'exact prepare_audio_visual_probe documented historical include paths', [relative])
    combo_base = ('D:/17/project_17/fpga_gowin/code/output/t009_zip2_review_20260930/'
                  'code/output/adsr_strict_flash_combo_20261002/prepared/audio_snapshot')
    accept(Path(relative).name, audio_stage(relative).replace(historical_base, combo_base),
           'prepare_adsr_visual_combo documented snapshot relocation; SHA-gated',
           [relative, 'prepare_adsr_visual_combo.py',
            'repository evidence/adsr_strict_flash_combo_M2_20261002.json'])

relative = 'code/rtl/audio/dds_oscillator.sv'
text = audio_stage(relative)
accept('dds_oscillator.sv', text, 'historical pre-physical audio stage', [relative])
for name, old_path in roms.items():
    text = text.replace(historical_base + '/code/model/generated/wavetables/' + name, old_path)
accept('dds_oscillator.sv', text, 'documented subsequent physical ROM path relocation', [relative])

text = audio_stage('code/rtl/board/electronic_piano_top.sv')
text = text.replace('ELECTRONIC_PIANO_TOP_SV', 'AUDIO_VISUAL_COEXISTENCE_TOP_SV')
text = text.replace('module electronic_piano_top #(', 'module audio_visual_coexistence_top #(', 1)
anchor = 'output logic uart_tx      // U15  -> BL616'
if text.count(anchor) != 1:
    raise ValueError('Original top anchor differs')
text = text.replace(anchor, 'output logic uart_tx,     // U15  -> BL616', 1)
endport = text.index('\n);', text.index('module audio_visual'))
text = (text[:endport] + '\n    output wire tmds_clk_p,tmds_clk_n,\n'
        '    output wire [2:0] tmds_data_p,tmds_data_n' + text[endport:])
addition = '''
    // Display-only copy of events already accepted by the current audio core.
    // PLL/video resets never enter the audio reset or ready path.
    wire visual_pll_locked;
    audio_visual_display_probe u_visual (
        .sys_clk(sys_clk),.sys_rst_n(sys_rst_n),
        .accepted_valid(shared_event_valid && shared_event_ready),
        .accepted_data(shared_event_data),
        .tmds_clk_p(tmds_clk_p),.tmds_clk_n(tmds_clk_n),
        .tmds_data_p(tmds_data_p),.tmds_data_n(tmds_data_n),
        .visual_pll_locked(visual_pll_locked)
    );
'''
text = text.replace('endmodule', addition + '\nendmodule', 1)
accept('audio_visual_coexistence_top.sv', text,
       'replayed exact original prepare_audio_visual_probe top generation',
       ['code/rtl/board/electronic_piano_top.sv', 'prepare_audio_visual_probe.py'])

text = (HERE / 'bank_input.sv').read_text(encoding='utf-8')
for name in ['oct_ratio_q16.mem', 'sub_ratio_q16.mem', 'lfo_sine_q15.mem']:
    text = text.replace('model/generated/pitch_mod/' + name, roms[name])
accept('polyphonic_envelope_bank.sv', text,
       'exact prepare_pitch_mod_bank_combo pitch ROM path relocation', ['bank_input.sv'])

cst = (BASE / 'code/constraints/electronic_piano.cst').read_text(encoding='utf-8')
for line in (HERE / 'hdmi_link_probe.cst').read_text(encoding='utf-8').splitlines():
    if '"tmds_' in line or line.startswith('INS_LOC'):
        cst += '\n' + line.replace('u_video_pll/', 'u_visual/u_video_pll/')
cst += '\nINS_LOC "u_visual/u_serial_reset/sync_chain_0_s0" R49C101[1][A];\n'
cst += 'INS_LOC "u_visual/u_serial_reset/sync_chain_1_s0" R49C101[1][B];\n'
accept('audio_visual.cst', cst, 'exact original audio/video constraint assembly',
       ['code/constraints/electronic_piano.cst', 'hdmi_link_probe.cst'])

sdc = (BASE / 'code/constraints/audio_timing.sdc').read_text(encoding='utf-8')
lines = []
for line in (HERE / 'visual_full_path_probe.sdc').read_text(encoding='utf-8').splitlines():
    if line.startswith('create_clock'):
        continue
    lines.append(line.replace('u_video_pll/', 'u_visual/u_video_pll/')
                 .replace('u_event_bridge/', 'u_visual/u_event_bridge/')
                 .replace('u_control/', 'u_visual/u_control/'))
sdc += '\n# Independent audio+visual diagnostic: original audio constraints above.\n' + '\n'.join(lines) + '\n'
for clock in ['sys_clk', 'video_pixel', 'video_serial']:
    sdc += ('report_timing -setup -from_clock [get_clocks {' + clock
            + '}] -to_clock [get_clocks {' + clock + '}] -max_paths 80 -max_common_paths 1\n')
    sdc += ('report_timing -hold -from_clock [get_clocks {' + clock
            + '}] -to_clock [get_clocks {' + clock + '}] -max_paths 10 -max_common_paths 1\n')
sdc = sdc.replace('set_clock_uncertainty -hold  0.500', 'set_clock_uncertainty -hold  0.550')
accept('audio_visual_hold055.sdc', sdc, 'original assembly plus documented Hold 0.500 to 0.550',
       ['code/constraints/audio_timing.sdc', 'visual_full_path_probe.sdc'])

raw_pll = (HERE / 'vendor/TMDS_PLL_800_600_60.v').read_bytes()
if sha(raw_pll) != 'e43e57d7301929dcdeceabf5274fab46080697f82e3fa2d30479d69e87c0801a':
    raise ValueError('Official PLL source drift')
text = raw_pll.decode('utf-8')
for old, new in [('IDIV_SEL = 1;', 'IDIV_SEL = 1;'), ('MDIV_SEL = 16;', 'MDIV_SEL = 20;'),
                 ('ODIV0_SEL = 4;', 'ODIV0_SEL = 8;'), ('ODIV1_SEL = 20;', 'ODIV1_SEL = 40;')]:
    if 'PLLA_inst.' + old not in text:
        raise ValueError('PLL parameter anchor missing')
    text = text.replace('PLLA_inst.' + old, 'PLLA_inst.' + new)
text = '// M2 derived 125/25 MHz configuration; original copyright below.\n' + text
if sha(text.encode('utf-8')) != 'ededfd3e361c7e9b4523de6b3b50e00c98baed5b9900a361c606ab574376f9ba':
    raise ValueError('Derived PLL input SHA differs')
accept('TMDS_PLL_800_600_60.v', text.replace('\r\n', '\n'),
       'exact reviewed PLL parameter edits then original physical LF transport',
       ['vendor/TMDS_PLL_800_600_60.v', 'original build_hdmi_link_probe.ps1'])

report = {'scope': 'hash-gated deterministic recovery, not timing acceptance',
          'audio_commit': 'e5eb025ea37dfd7312b4a4e74e1a881c223dda1d',
          'official_vendor_commit': 'f0347d830305ef3efb921f47bb51701e569beefd',
          'attempts': attempts,
          'recovered_names': sorted({x['name'] for x in attempts if x['matched']}),
          'EDA_run': False}
(HERE / 'recovery_proof.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
for entry in attempts:
    print(('MATCH' if entry['matched'] else 'MISMATCH'), entry['name'], entry['sha256'])
print('Recovered unique inputs:', len(report['recovered_names']))
