#!/usr/bin/env python3
"""Build two T005 stereo diagnostics without editing the formal top or CST."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'code/output/t005_channel_probe'

def run(command, cwd, log):
    result = subprocess.run(command, cwd=cwd, capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=600)
    log.write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(f'Command exit={result.returncode}; see {log}')
    return result.stdout + result.stderr

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--simulate-only', action='store_true')
    args = cli.parse_args()
    original = ROOT / 'code/rtl/board/electronic_piano_top.sv'
    diagnostic_base = 'e6f6638'
    text = subprocess.check_output(['git','show',diagnostic_base+':code/rtl/board/electronic_piano_top.sv'],cwd=ROOT).decode('utf-8')
    # Fail closed if fixed-tone source structure changes.
    edits = [('module electronic_piano_top #(', 'module t005_channel_probe #('),
             ('parameter int unsigned SOURCE_MODE = 0,', 'parameter int unsigned SOURCE_MODE = 1,')]
    project = ET.ElementTree(ET.fromstring(subprocess.check_output(['git','show',diagnostic_base+':code/build/electronic_piano.gprj'],cwd=ROOT)))
    source_files=[]; entries=[]
    for elem in project.findall('.//File'):
        file=(ROOT/'code/build'/elem.attrib['path']).resolve()
        entries.append((file, elem.attrib['type']))
        if elem.attrib['type']=='file.verilog' and file != original:
            source_files.append(file)
    # Prove this reuses the repaired T005 serializer.
    fixed = subprocess.check_output(['git','show','0898da0:code/rtl/audio_out/i2s_tx.sv'],cwd=ROOT)
    if fixed != (ROOT/'code/rtl/audio_out/i2s_tx.sv').read_bytes():
        raise RuntimeError('Serializer differs from 0898da0; review before diagnostic build')
    cad=Path(os.environ.get('YOSYSHQ_ROOT','D:/Gowin/oss-cad-suite'))
    gowin=Path(os.environ.get('GOWIN_HOME','D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64'))/'IDE/bin/gw_sh.exe'
    manifest={'baseline':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'diagnostic_top_commit':diagnostic_base,'diagnostic_top_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),'serializer_commit':'0898da0','sys_clk_hz':50000000,'sample_rate_hz':48000,
              'tone_hz_nominal':440,'peak_pcm16':8192,'download':'SRAM only; not automatically programmed',
              'source_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in source_files+[original,ROOT/'code/tb/board/tb_t005_channel_probe.sv']},'channels':{}}
    for side in ['left','right']:
        stage=OUT/side;stage.mkdir(parents=True,exist_ok=True)
        generated=text
        for before,after in edits:
            if generated.count(before)!=1: raise RuntimeError(f'Unexpected source: {before}')
            generated=generated.replace(before,after)
        table = (ROOT/'code/rtl/common/sine_table.svh').read_text(encoding='utf-8')
        table = '\n'.join(line for line in table.splitlines()
                          if not line.lstrip().startswith(('`ifndef','`define','`endif')))
        signature = '    function automatic logic signed [15:0] sine_sample('
        if generated.count(signature)!=1:raise RuntimeError('Unexpected sine function')
        generated=generated.replace(signature,table+'\n'+signature)
        generated=generated.replace('return u_simple_voice.sine_sample(index);',
                                    'return sine_lookup({{(32-SINE_IDX_BITS){1\'b0}}, index});')
        silent='right' if side=='left' else 'left'
        before=f'assign pcm_{silent}' + ('  ' if silent=='left' else ' ') + "= $signed({tone_sample, 8'b0});"
        if generated.count(before)!=1:raise RuntimeError('Unexpected fixed PCM assignment')
        generated=generated.replace(before,f"assign pcm_{silent} = '0;")
        top=stage/'t005_channel_probe.sv';top.write_text(generated,encoding='utf-8',newline='\n')
        binary=stage/'channel.vvp'
        compile_cmd=[str(cad/'bin/iverilog.exe'),'-g2012','-I',str(ROOT/'code/rtl/common'),'-s','tb_t005_channel_probe',
                     f'-Ptb_t005_channel_probe.ACTIVE_LEFT={1 if side=="left" else 0}','-o',str(binary),
                     *map(str,source_files),str(top),str(ROOT/'code/tb/board/tb_t005_channel_probe.sv')]
        # Native CAD tools require environment.bat on Windows.
        bat=stage/'simulate.bat'
        quote=lambda x:'"'+x+'"'
        bat.write_text('@echo off\r\ncall '+quote(str(cad/'environment.bat'))+' >nul\r\n'+
                       ' '.join(map(quote,compile_cmd))+'\r\nif errorlevel 1 exit /b 1\r\n'+
                       quote(str(cad/'bin/vvp.exe'))+' '+quote(str(binary))+'\r\nexit /b %errorlevel%\r\n',encoding='ascii')
        output=run(['cmd.exe','/c',str(bat)],stage,stage/'simulation.log')
        if 'PASS T005 channel probe' not in output:raise RuntimeError('Simulation PASS marker absent')
        print(side,output[output.index('PASS T005 channel probe'):].splitlines()[0],flush=True)
        info={'generated_top_sha256':sha(top),'simulation_log_sha256':sha(stage/'simulation.log'),'simulation':'PASS'}
        if not args.simulate_only:
            p=ET.Element('Project');ET.SubElement(p,'Template').text='FPGA';ET.SubElement(p,'Version').text='5'
            ET.SubElement(p,'Device',name='GW5AT-60B',pn='GW5AT-LV60PG484AC1/I0').text='gw5at60b-002'
            fl=ET.SubElement(p,'FileList')
            for file,kind in entries:
                ET.SubElement(fl,'File',path=(top if file==original else file).as_posix(),type=kind,enable='1')
            name=f't005_{side}_440hz';gprj=stage/(name+'.gprj');ET.ElementTree(p).write(gprj,encoding='utf-8',xml_declaration=True)
            tcl=stage/'build.tcl';tcl.write_text('cd {'+stage.as_posix()+'}\nopen_project {'+gprj.as_posix()+'}\nset_option -verilog_std sysv2017\nset_option -top_module t005_channel_probe\nrun all\n',encoding='ascii')
            print('Building',side,flush=True)
            run([str(gowin),str(tcl)],stage,stage/'build.log')
            fs=stage/'impl/pnr'/(name+'.fs')
            if not fs.exists():raise RuntimeError('Missing bitstream')
            info.update({'fs_path':str(fs),'fs_sha256':sha(fs),'build_log_sha256':sha(stage/'build.log'),
                         'timing_report':str(stage/'impl/pnr'/(name+'_tr_content.html')),
                         'resource_report':str(stage/'impl/pnr'/(name+'.rpt.txt'))})
        manifest['channels'][side]=info
        (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Manifest:',OUT/'manifest.json')
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,RuntimeError,subprocess.SubprocessError) as exc:
        print('FAIL T005 diagnostic:',exc,file=sys.stderr);sys.exit(1)