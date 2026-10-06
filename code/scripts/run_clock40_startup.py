"""Bounded L-source startup tests only; no synthesis, PnR or board download."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[2]
SCOPE=ROOT/'code/tb/board/clock40_startup_20261006'
CAD=Path('D:/Gowin/oss-cad-suite')
ARCHIVE=ROOT/'code/rtl/138K_try/hold_trials_20261005/M3_138K_Hold修复证据_20261005.zip'
PREFIX='E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/rtl/138K_try/hold_trials_20261005/L_locations_guard065'
DEADLINE=datetime.fromisoformat('2026-10-06T04:30:00+08:00')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument('--output',type=Path,required=True)
    cli.add_argument('--scenario',type=int,choices=(0,1,2))
    cli.add_argument('--mutants-only',action='store_true')
    args=cli.parse_args()
    output=args.output.resolve()
    output.relative_to(ROOT/'code/output')
    assert not output.exists(),'Never overwrite prior attempt'
    output.mkdir(parents=True)
    env=os.environ.copy()
    env['PATH']=str(CAD/'bin')+';'+str(CAD/'lib')+';'+env['PATH']
    env['PYTHONDONTWRITEBYTECODE']='1'
    result={'date':'2026-10-06','passed':False,'profile':'M3 L original source',
            'real_vendor_PLL_model':True,'encrypted_DVI_replaced_by_boundary_stub':True,
            'no_PnR_no_flash':True,'source_archive_sha256':sha(ARCHIVE),'runs':{},'adaptations':[]}
    def run(name,cmd,success=True,marker=None,limit=900):
        remaining=(DEADLINE-datetime.now().astimezone()).total_seconds()
        if remaining<=0:
            raise RuntimeError('Agreed04:30 stop boundary reached')
        timeout=min(limit,remaining)
        log=output/(name+'.log')
        start=time.monotonic()
        with log.open('wb') as f:
            process=subprocess.Popen(list(map(str,cmd)),cwd=output,env=env,stdout=f,stderr=subprocess.STDOUT)
            try:
                code=process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
                result['runs'][name]={'timed_out':True,'elapsed':time.monotonic()-start,'timeout':timeout,'log_sha':sha(log)}
                raise
        text=log.read_text(encoding='utf-8',errors='replace')
        result['runs'][name]={'exit':code,'expected_success':success,'elapsed':time.monotonic()-start,
                             'log_sha':sha(log),'command':list(map(str,cmd))}
        print(name,'EXIT',code,text[-1300:],flush=True)
        if (code==0)!=success or marker and marker not in text:
            raise RuntimeError('Unexpected test result '+name)
    try:
        with zipfile.ZipFile(ARCHIVE) as z:
            manifest=json.loads(z.read('L_locations_guard065/input_manifest.json'))
            for entry in manifest['inputs']:
                rel=entry['path'].replace('\\','/')
                raw=z.read('L_locations_guard065/'+rel)
                assert hashlib.sha256(raw).hexdigest()==entry['candidate_SHA256'],rel
                target=output/rel
                target.parent.mkdir(parents=True,exist_ok=True)
                data=raw.replace(PREFIX.encode(),output.as_posix().encode())
                if target.suffix in ('.sv','.v'):
                    body=data.decode('utf-8')
                    for inc in re.findall(r'`include\s+"([^\"]+)"',body):
                        before='`include "'+inc+'"'
                        body=body.replace(before,'`include "'+Path(inc).name+'"')
                        result['adaptations'].append({'file':rel,'include_basename_only':inc})
                    if target.name=='voice_allocator_4.sv':
                        fields={'note_active':1,'in_release':1,'source':4,'channel':4,'note':8,'age':2}
                        assert body.count('    voice_slot_t slots [0:3];')==1
                        declarations='\n'.join('    logic '+(f'[{width-1}:0] ' if width>1 else '')+f'sim_slot_{name} [0:3];' for name,width in fields.items())
                        body=body.replace('    voice_slot_t slots [0:3];',declarations,1)
                        assert body.count("                slots[i] <= '0;")==1
                        body=body.replace("                slots[i] <= '0;",'\n'.join(f"                sim_slot_{name}[i] <= '0;" for name in fields),1)
                        for name in fields:
                            body=re.sub(r'slots\[([^\]]+)\]\.'+name+r'\b',r'sim_slot_'+name+r'[\1]',body)
                        assert not re.search(r'\bslots\b',body)
                        result['adaptations'].append({'file':rel,'mechanical_fields_only_same_NBA_order':fields})
                    data=body.encode('utf-8')
                target.write_bytes(data)
            tree=ET.fromstring(z.read('L_locations_guard065/audio_visual_coexistence_top.gprj'))
            names=[Path(n.attrib['path']).name for n in tree.find('FileList') if n.attrib['type']=='file.verilog']
            assert len(names)==45
        dvi=ROOT/'code/rtl/138K_try/clock_trials_20261005/dvi_sim_stub.v'
        files=[dvi if n=='DVI_TX_Top.v' else output/'sources'/n for n in names]
        vendor=ROOT/'code/rtl/138K_try/tools/gowin_1_9_11_03/IDE/simlib/gw5a/prim_sim.v'
        assert vendor.is_file()
        bench=SCOPE/'tb_clock40_startup.sv'
        result['vendor_model_SHA']=sha(vendor)
        result['testbench_SHA']=sha(bench)
        result['compiled_input_SHA']={str(p):sha(p) for p in files+[vendor,bench]}
        compiler=[CAD/'bin/iverilog.exe','-B',CAD/'lib/ivl','-g2012','-I',output/'include','-s','tb_clock40_startup']
        scenarios=[args.scenario] if args.scenario is not None else [0,1,2]
        if not args.mutants_only:
            for scenario in scenarios:
                image=output/(f'scenario{scenario}.vvp')
                run(f'scenario{scenario}_compile',compiler+['-Ptb_clock40_startup.SCENARIO='+str(scenario),'-o',image,*files,vendor,bench],limit=90)
                run(f'scenario{scenario}',[CAD/'bin/vvp.exe',image],marker='PASS essential startup scenario='+str(scenario))
                capture=output/'startup.capture'
                saved=output/(f'scenario{scenario}.capture')
                assert b'END scenario=' in capture.read_bytes()
                saved.write_bytes(capture.read_bytes())
        if args.scenario is None:
            top=output/'sources/audio_visual_coexistence_top.sv'
            body=top.read_text(encoding='utf-8')
            faults=[('bypass_LOCK_reset','wire core_async_rst_n = sys_rst_n && visual_pll_locked;','wire core_async_rst_n = sys_rst_n;',0,'autopower initial-high external reset and mute'),
                    ('no_direct_mute','assign pa_en = ~rst_sync_n | ~core_async_rst_n;','assign pa_en = ~rst_sync_n;',2,'direct mute while no valid PLL/core clock')]
            for name,old,new,scenario,reason in faults:
                assert body.count(old)==1,name
                bad=output/(name+'.sv')
                bad.write_text(body.replace(old,new,1),encoding='utf-8',newline='\n')
                altered=[bad if p==top else p for p in files]
                image=output/(name+'.vvp')
                run(name+'_compile',compiler+['-Ptb_clock40_startup.SCENARIO='+str(scenario),'-o',image,*altered,vendor,bench],limit=90)
                run(name,[CAD/'bin/vvp.exe',image],success=False,marker=reason,limit=120)
        result['passed']=True
        return 0
    finally:
        (output/'review.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    raise SystemExit(main())
