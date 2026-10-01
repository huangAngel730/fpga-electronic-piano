#!/usr/bin/env python3
"""M2 four-lane bank to PCM commit test; PCM is explicit test stimulus; lowers unchanged allocator for Icarus."""
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parents[2];stage=root/'code/output/t024_audio_core';stage.mkdir(parents=True,exist_ok=True)
source=root/'code/rtl/audio/voice_allocator_4.sv';net=stage/'allocator.v';ys=stage/'lower.ys'
ys.write_text('read_slang --top voice_allocator_4 '+source.as_posix()+'\nproc\nopt\ntechmap\nopt\nwrite_verilog -noattr '+net.as_posix()+'\n',encoding='ascii')
cad=Path('D:/Gowin/oss-cad-suite');q=lambda p:'"'+str(p)+'"'
commands=[q(cad/'bin/yosys.exe')+' -Q -T -s '+q(ys),q(cad/'bin/iverilog.exe')+' -g2012 -I '+q(root/'code/rtl/board')+' -s tb_polyphonic_audio_core -o '+q(stage/'tb.vvp')+' '+' '.join(map(q,[root/'code/rtl/common/audio_defs_pkg.sv',net,root/'code/rtl/common/note_pitch.sv',root/'code/rtl/board/sustain_control_contract_pkg.sv',root/'code/rtl/input/sustain_control/sustain_controller.sv',root/'code/rtl/board/polyphonic_event_router.sv',root/'code/rtl/board/polyphonic_envelope_bank.sv',root/'code/rtl/audio/dds_oscillator.sv',root/'code/rtl/audio/adsr_piano_envelope.sv',root/'code/rtl/board/polyphonic_pcm_commit.sv',root/'code/rtl/mixer/pcm_mixer_4voice.sv',root/'code/rtl/audio_out/pcm_result_hold.sv',root/'code/rtl/audio_out/pcm_frame_buffer.sv',root/'code/rtl/common/pcm_clip_counter.sv',root/'code/rtl/common/system_status_counters.sv',root/'code/rtl/board/voice_gain_q15_candidate.sv',root/'code/rtl/board/polyphonic_audio_core.sv',root/'code/tb/board/tb_polyphonic_audio_core.sv'])),q(cad/'bin/vvp.exe')+' '+q(stage/'tb.vvp')+' '+q('+VELOCITY_ROM_PATH='+str(root/'code/model/generated/wavetables/velocity_gain_rom.mem'))+' '+q('+WAVETABLE_PATH='+str(root/'code/model/generated/wavetables/sine_1024_8192.mem'))+' '+q('+TRACE='+str(stage/'audio.trace'))]
bat=stage/'run.bat';bat.write_text('@echo off\r\ncall '+q(cad/'environment.bat')+' >nul\r\n'+'\r\nif errorlevel 1 exit /b 1\r\n'.join(commands)+'\r\nexit /b %errorlevel%\r\n',encoding='ascii')
p=subprocess.run(['cmd.exe','/c',str(bat)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120,cwd=stage)
(stage/'run.log').write_text(p.stdout+p.stderr,encoding='utf-8');
for line in (p.stdout+p.stderr).splitlines():
    if 'PASS polyphonic_audio_core' in line or 'FATAL' in line or 'error:' in line:print(line)
print('Full log:',stage/'run.log')
if p.returncode or 'PASS polyphonic_audio_core' not in p.stdout:raise SystemExit(p.returncode or 1)
raise SystemExit(subprocess.call([sys.executable,'-X','utf8',str(root/'code/tb/board/check_polyphonic_audio_trace.py'),str(stage/'audio.trace')]))