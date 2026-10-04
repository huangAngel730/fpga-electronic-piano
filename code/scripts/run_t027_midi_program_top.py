#!/usr/bin/env python3
"""Run actual UART Program Change through the formal T027 top at 50MHz."""
from __future__ import annotations

from pathlib import Path
import subprocess
import os
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/'code/output/t027_midi_program_top'
STAGE.mkdir(parents=True,exist_ok=True)
# M1's timbre oscillator uses relative defaults in Icarus; stage both ROMs.
rom_dir=STAGE/'model/generated'
rom_dir.mkdir(parents=True,exist_ok=True)
for name in ('sine_wavetable.hex','triangle_wavetable.hex'):
    (rom_dir/name).write_bytes((ROOT/'code/model/generated'/name).read_bytes())
CAD=Path('D:/Gowin/oss-cad-suite')
os.environ['PATH']=str(CAD/'lib')+os.pathsep+str(CAD/'bin')+os.pathsep+os.environ['PATH']
allocator=ROOT/'code/rtl/audio/voice_allocator_4.sv'
net=STAGE/'allocator.v'
(STAGE/'lower.ys').write_text(
    'read_slang --top voice_allocator_4 '+allocator.as_posix()+'\n'
    'proc\nopt\ntechmap\nopt\nwrite_verilog -noattr '+net.as_posix()+'\n',
    encoding='ascii')

def execute(args: list[str], log_name: str) -> str:
    result=subprocess.run(args,cwd=STAGE,capture_output=True,text=True,
                          encoding='utf-8',errors='replace',timeout=180)
    text=result.stdout+result.stderr
    (STAGE/log_name).write_text(text,encoding='utf-8',newline='\n')
    if result.returncode:
        print(text[-2200:]);raise SystemExit(result.returncode)
    return text

execute([str(CAD/'bin/yosys.exe'),'-Q','-T','-s',str(STAGE/'lower.ys')],
        'lower.log')
project=ROOT/'code/build/electronic_piano.gprj'
sources=[(project.parent/entry.attrib['path']).resolve()
         for entry in ET.parse(project).findall('.//File')
         if entry.attrib['type']=='file.verilog' and entry.attrib.get('enable','1')=='1']
sources=[net if file.name==allocator.name else file for file in sources]
sources.sort(key=lambda file: 0 if file.name=='audio_defs_pkg.sv' else
             (1 if file.name=='sustain_control_contract_pkg.sv' else 2))
tb=ROOT/'code/tb/board/tb_t027_midi_program_top.sv'
binary=STAGE/'test.vvp'
execute([str(CAD/'bin/iverilog.exe'),'-g2012','-s','tb_t027_midi_program_top',
         '-I',str(ROOT/'code/rtl/common'),'-I',str(ROOT/'code/rtl/board'),
         '-o',str(binary)]+list(map(str,sources))+[str(tb)],'compile.log')
output=execute([str(CAD/'bin/vvp.exe'),str(binary),
    '+WAVETABLE_PATH='+str(ROOT/'code/model/generated/wavetables/piano_band_4x256_8191.mem'),
    '+VELOCITY_ROM_PATH='+str(ROOT/'code/model/generated/wavetables/velocity_gain_rom.mem')],
    'run.log')
for line in output.splitlines():
    if line.startswith(('PASS T027','FATAL','ERROR:')):print(line)
if ('readmemh: Unable to open' in output or 'ERROR:' in output or
        'PASS T027 real UART Program' not in output):
    raise SystemExit('T027 real UART test missing ROM or PASS marker')
print('PASS T027 end-to-end UART Program simulation, not hardware L6')
