"""Run one bounded board wiring simulation with a declared M1 port stub."""
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

ROOT=Path(__file__).resolve().parents[2]
CAD=Path('D:/Gowin/oss-cad-suite')
VENDOR=Path('D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/simlib/gw5a/prim_sim.v')
PLL=ROOT/'code/tb/board/t058_waveform_integration_20261008/clock_plan_sim.v'
DVI=ROOT/'code/rtl/138K_try/hold_trials_20261005/dvi_sim_stub.v'
JOB=ROOT/'code/software/t052_runner_acceptance_candidate_20261012/windows_job.py'
TB=ROOT/'code/tb/board/m2_m1td_board_contract_20261015/tb_m2_m1td_board_contract.sv'


def ident(p):
 b=Path(p).read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}


def main():
    a=argparse.ArgumentParser();a.add_argument('--prepared',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--mutant',action='store_true');args=a.parse_args()
    prepared=args.prepared.resolve();out=args.output.resolve();allowed=(ROOT/'code/output').resolve()
    if out.exists() or out==allowed or not out.is_relative_to(allowed):raise ValueError('NEW_OUTPUT_REQUIRED')
    out.mkdir()
    start=time.monotonic();result={'status':'FAIL_PARTIAL','error':None,'scope':'BOARD_WIRING_M1_PORT_STUB_ONLY',
     'new_EDA':0,'real_M1_chain_executed':False,'steps':[],'source_before':{},'source_after':{},'physical_STA':'NOT_RUN'}
    protected=[]
    try:
        r=json.loads((prepared/'PREPARATION_RECEIPT.json').read_text(encoding='utf-8'))
        if r['status']!='PREPARED_NOT_PHYSICALLY_ADMITTED':raise ValueError('PREPARED_IDENTITY')
        p=prepared/'m2_fourvoice_timbre_delay_board_top.gprj'
        if ident(p)['sha256']!=r['project_sha256']:raise ValueError('PROJECT_DRIFT')
        protected += [p,prepared/'PREPARATION_RECEIPT.json',TB,JOB,VENDOR,PLL,DVI,Path(__file__),CAD/'bin/iverilog.exe',CAD/'bin/vvp.exe']
        units=[];bound={k.replace('\\','/'):v for k,v in r['input_files'].items()}
        for x in ET.parse(p).getroot().iter('File'):
            f=Path(x.attrib['path']);key=f.relative_to(prepared).as_posix()
            if ident(f)!=bound[key]:raise ValueError('INPUT_DRIFT:'+key)
            protected.append(f)
            if x.attrib['type']=='file.verilog' and f.name not in ('TMDS_PLL_800_600_60.v','DVI_TX_Top.v') and not f.name.startswith('m1td_'):
                units.append(f)
        if ident(JOB)['sha256']!='5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b':raise ValueError('JOB_DRIFT')
        before={str(f):ident(f) for f in protected};result['source_before']=before
        lib=VENDOR.read_text(encoding='utf-8');parts=[]
        for n in ('GSR','pROM'):
            m=re.search(r'^module '+n+r' \([^\n]*\);[\s\S]*?^endmodule[^\n]*',lib,re.M)
            if not m:raise ValueError('MISSING_VENDOR:'+n)
            parts.append(m.group(0))
        vendor=out/'vendor_GSR_pROM.v';vendor.write_text('`timescale 1ns/1ps\n'+'\n'.join(parts),encoding='utf-8',newline='\n')
        if args.mutant:
            target=next(f for f in units if f.name=='m2_fourvoice_timbre_delay_board_top.sv')
            raw=target.read_text(encoding='utf-8')
            left='.committed_left(produced_left)'
            right='.committed_right(produced_right)'
            if raw.count(left)!=1 or raw.count(right)!=1:raise ValueError('MUTATION_ANCHOR')
            wrong=raw.replace(left,'.committed_left(produced_right)',1).replace(right,'.committed_right(produced_left)',1)
            mutant=out/target.name
            mutant.write_text(wrong,encoding='utf-8',newline='\n')
            units[units.index(target)]=mutant
            result['mutant']={'type':'SWAP_COMMITTED_STEREO','source_sha256':ident(target)['sha256'],'mutated_sha256':ident(mutant)['sha256']}
        units.sort(key=lambda f:0 if f.name=='audio_defs_pkg.sv' else 1 if f.name=='sustain_control_contract_pkg.sv' else 2)
        command=[str(CAD/'bin/iverilog.exe'),'-g2012','-I',str(prepared/'inputs/include'),'-s','tb_m2_m1td_board_contract','-o',str(out/'board.vvp')]
        command+=list(map(str,units+[vendor,PLL,DVI,TB]))
        spec=importlib.util.spec_from_file_location('m2_stub_job',JOB);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
        env=os.environ.copy();env['YOSYSHQ_ROOT']=str(CAD)+os.sep;env['PATH']=os.pathsep.join([str(CAD/'bin'),str(CAD/'lib'),env.get('PATH','')])
        def step(name,argv,marker=None):
            budget=300-(time.monotonic()-start)
            if budget<=0:raise TimeoutError('TOTAL300_PRE_'+name)
            job=helper.WindowsJob();tick=time.monotonic();timeout=False
            try:
                with (out/(name+'.stdout.log')).open('xb') as stdout,(out/(name+'.stderr.log')).open('xb') as stderr:
                    child=subprocess.Popen(argv,cwd=prepared/'inputs',env=env,stdout=stdout,stderr=stderr,creationflags=4)
                    job.attach_and_resume(child)
                    try:child.wait(timeout=min(90,budget))
                    except subprocess.TimeoutExpired:timeout=True;job.terminate();child.wait(timeout=5)
            finally:job.close()
            record={'name':name,'argv':argv,'exit_code':child.returncode,'timed_out':timeout,'seconds':round(time.monotonic()-tick,3),
                    'stdout':ident(out/(name+'.stdout.log')),'stderr':ident(out/(name+'.stderr.log'))}
            result['steps'].append(record)
            if timeout or child.returncode!=0:raise ValueError('STEP_FAILED:'+name)
            if marker and marker.encode() not in (out/(name+'.stdout.log')).read_bytes():raise ValueError('PASS_MARKER_MISSING:'+name)
        step('compile',command)
        if args.mutant:
            try:
                step('simulate',[str(CAD/'bin/vvp.exe'),str(out/'board.vvp')])
            except ValueError as exc:
                if str(exc)!='STEP_FAILED:simulate' or b'BOARD_STEREO_COMMIT_WIRING_MISMATCH' not in (out/'simulate.stdout.log').read_bytes():
                    raise
            else:
                raise ValueError('MUTANT_NOT_REJECTED')
        else:
            step('simulate',[str(CAD/'bin/vvp.exe'),str(out/'board.vvp')],'PASS M2_M1TD_BOARD_WIRING_WITH_M1_STUB_ONLY')
        result['source_after']={str(f):ident(f) for f in protected}
        if result['source_after']!=before:raise ValueError('SOURCE_DRIFT')
        if time.monotonic()-start>=300:raise TimeoutError('TOTAL300')
        result['status']='BOARD_WIRING_MUTANT_REJECTED' if args.mutant else 'BOARD_WIRING_STUB_PASS_NOT_M1_SOUND'
    except Exception as exc:
        result['error']=type(exc).__name__+': '+str(exc)
        result['source_after']={str(f):ident(f) for f in protected if f.is_file()}
    result['seconds']=round(time.monotonic()-start,3)
    result['exit_code']=0 if result['error'] is None else 1
    (out/'RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status','error','seconds','exit_code')}))
    return result['exit_code']

if __name__=='__main__':raise SystemExit(main())