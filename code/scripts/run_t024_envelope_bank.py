#!/usr/bin/env python3
"""M2 four-envelope sample/lifecycle test; lowers unchanged allocator for Icarus."""
from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[2];stage=root/'code/output/t024_envelope_bank';stage.mkdir(parents=True,exist_ok=True)
source=root/'code/rtl/audio/voice_allocator_4.sv';net=stage/'allocator.v';ys=stage/'lower.ys'
ys.write_text('read_slang --top voice_allocator_4 '+source.as_posix()+'\nproc\nopt\ntechmap\nopt\nwrite_verilog -noattr '+net.as_posix()+'\n',encoding='ascii')
cad=Path('D:/Gowin/oss-cad-suite');q=lambda p:'"'+str(p)+'"'
commands=[q(cad/'bin/yosys.exe')+' -Q -T -s '+q(ys),q(cad/'bin/iverilog.exe')+' -g2012 -I '+q(root/'code/rtl/board')+' -s tb_polyphonic_envelope_bank -o '+q(stage/'tb.vvp')+' '+' '.join(map(q,[root/'code/rtl/common/audio_defs_pkg.sv',net,root/'code/rtl/common/note_pitch.sv',root/'code/rtl/board/sustain_control_contract_pkg.sv',root/'code/rtl/input/sustain_control/sustain_controller.sv',root/'code/rtl/board/polyphonic_event_router.sv',root/'code/rtl/board/polyphonic_envelope_bank.sv',root/'code/rtl/audio/dds_oscillator.sv',root/'code/rtl/audio/piano_dds_oscillator.sv',root/'code/rtl/audio/adsr_piano_envelope.sv',root/'code/tb/board/tb_polyphonic_envelope_bank.sv'])),q(cad/'bin/vvp.exe')+' '+q(stage/'tb.vvp')+' '+q('+VELOCITY_ROM_PATH='+str(root/'code/model/generated/wavetables/velocity_gain_rom.mem'))+' '+q('+WAVETABLE_PATH='+str(root/'code/model/generated/wavetables/sine_1024_32767.mem'))]
bat=stage/'run.bat';bat.write_text('@echo off\r\ncall '+q(cad/'environment.bat')+' >nul\r\n'+'\r\nif errorlevel 1 exit /b 1\r\n'.join(commands)+'\r\nexit /b %errorlevel%\r\n',encoding='ascii')
p=subprocess.run(['cmd.exe','/c',str(bat)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120,cwd=stage)
(stage/'run.log').write_text(p.stdout+p.stderr,encoding='utf-8');
for line in (p.stdout+p.stderr).splitlines():
    if 'PASS polyphonic_envelope_bank' in line or 'FATAL' in line or 'error:' in line:print(line)
print('Full log:',stage/'run.log')
raise SystemExit(p.returncode if p.returncode else (0 if 'PASS polyphonic_envelope_bank' in p.stdout else 1))