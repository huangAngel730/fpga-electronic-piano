"""Run official top source list with real UART STAT and allocator ports."""
from pathlib import Path
import subprocess
import argparse
import re
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser();parser.add_argument('--top',default='tb_t025_top_stat');parser.add_argument('--tb',default='code/tb/board/tb_t025_top_stat.sv');args=parser.parse_args()
stage=ROOT/'code/output'/args.top;stage.mkdir(parents=True,exist_ok=True)
cad=Path('D:/Gowin/oss-cad-suite');q=lambda p:'"'+str(p)+'"'
ys=stage/'lower.ys';ys.write_text('read_slang --top voice_allocator_4 '+(ROOT/'code/rtl/audio/voice_allocator_4.sv').as_posix()+'\nproc\nopt\ntechmap\nopt\nwrite_verilog -noattr '+(stage/'allocator.v').as_posix()+'\n',encoding='ascii')
sources=[]
for e in ET.parse(ROOT/'code/build/electronic_piano.gprj').findall('.//File'):
 if e.attrib['type']=='file.verilog':
  p=(ROOT/'code/build'/e.attrib['path']).resolve()
  sources.append(stage/'allocator.v' if p.name=='voice_allocator_4.sv' else p)
sources.sort(key=lambda p:0 if p.name=='audio_defs_pkg.sv' else (1 if p.name=='sustain_control_contract_pkg.sv' else 2))
sources.append(ROOT/args.tb)
commands=[q(cad/'bin/yosys.exe')+' -Q -T -s '+q(ys),q(cad/'bin/iverilog.exe')+' -g2012 -s '+args.top+' -I '+q(ROOT/'code/rtl/board')+' -I '+q(ROOT/'code/rtl/common')+' -o '+q(stage/'tb.vvp')+' '+' '.join(map(q,sources)),q(cad/'bin/vvp.exe')+' '+q(stage/'tb.vvp')+' '+q('+VELOCITY_ROM_PATH='+str(ROOT/'code/model/generated/wavetables/velocity_gain_rom.mem'))+' '+q('+WAVETABLE_PATH='+str(ROOT/'code/model/generated/wavetables/piano_band_4x256_8191.mem'))]
bat=stage/'run.bat';bat.write_text('@echo off\r\ncall '+q(cad/'environment.bat')+' >nul\r\n'+'\r\nif errorlevel 1 exit /b 1\r\n'.join(commands)+'\r\nexit /b %errorlevel%\r\n',encoding='ascii')
p=subprocess.run(['cmd.exe','/c',str(bat)],cwd=stage,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=300)
(stage/'run.log').write_text(p.stdout+p.stderr,encoding='utf-8')
for line in p.stdout.splitlines():
 if 'PASS' in line or 'FATAL' in line or '[FAIL]' in line or 'DEBUG' in line:print(line)
if p.returncode:print((p.stdout+p.stderr)[-2000:])
passed=(('PASS '+args.top) in p.stdout or re.search(r'>>>.*PASS',p.stdout)) and not re.search(r'FATAL|\[FAIL\]|>>>.*FAIL',p.stdout)
print('Log:',stage/'run.log')
raise SystemExit(p.returncode if p.returncode else (0 if passed else 1))
