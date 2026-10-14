"""One bounded isolated score-readout/priority simulation, no hardware access."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]
CAD=Path('D:/Gowin/oss-cad-suite')
JOB=ROOT/'code/software/t052_runner_acceptance_candidate_20261012/windows_job.py'
PKG=ROOT/'code/rtl/common/audio_defs_pkg.sv'
RAM=ROOT/'code/rtl/input/score_transfer_bram_candidate/score_transfer_bram_candidate.sv'
RTL=ROOT/'code/rtl/board/m2_score_playback_candidate_20261015/m2_score_playback_candidate.sv'
TB=ROOT/'code/tb/board/m2_score_playback_candidate_20261015/tb_m2_score_playback_candidate.sv'
PROTO=ROOT/'code/docs/hardware/score_transfer_v1/PROTOCOL.md'


def identity(p):
    raw=Path(p).read_bytes()
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mutant',action='store_true')
    args=parser.parse_args()
    out=args.output.resolve()
    base=(ROOT/'code/output').resolve()
    if out.exists() or out==base or not out.is_relative_to(base):
        raise ValueError('NEW_OUTPUT_SCOPE_REQUIRED')
    out.mkdir(parents=True,exist_ok=False)
    begin=time.monotonic()
    result={'status':'FAIL_PARTIAL','error':None,'scope':'SYNCHRONOUS_RAM_PORT_STUB_L2_NOT_FULL_UART',
            'mutant':args.mutant,'new_EDA':0,'production_modified':False,'steps':[],
            'sources_before':{},'sources_after':{}}
    sources=[PKG,RAM,RTL,TB,PROTO,JOB,Path(__file__),CAD/'bin/iverilog.exe',CAD/'bin/vvp.exe']
    try:
        if identity(JOB)['sha256']!='5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b':
            raise ValueError('JOB_IDENTITY')
        before={str(p):identity(p) for p in sources}
        result['sources_before']=before
        spec=importlib.util.spec_from_file_location('m2_score_job',JOB)
        helper=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        env=os.environ.copy()
        env['YOSYSHQ_ROOT']=str(CAD)+os.sep
        env['PATH']=os.pathsep.join([str(CAD/'bin'),str(CAD/'lib'),env.get('PATH','')])
        image=out/'score.vvp'
        command=[str(CAD/'bin/iverilog.exe'),'-g2012','-s','tb_m2_score_playback_candidate',
                 '-o',str(image)]
        if args.mutant:command.append('-DMUTANT_STALE_BANK')
        command.extend(map(str,[PKG,RTL,TB]))
        def step(name,argv,exit_code,marker=None):
            remaining=300-(time.monotonic()-begin)
            if remaining<=0:raise TimeoutError('TOTAL300_PRE_'+name)
            job=helper.WindowsJob();t=time.monotonic();timeout=False
            try:
                with (out/(name+'.stdout.log')).open('xb') as stdout,(out/(name+'.stderr.log')).open('xb') as stderr:
                    proc=subprocess.Popen(argv,cwd=out,env=env,stdout=stdout,stderr=stderr,creationflags=4)
                    job.attach_and_resume(proc)
                    try:proc.wait(timeout=min(90,remaining))
                    except subprocess.TimeoutExpired:timeout=True;job.terminate();proc.wait(timeout=5)
            finally:job.close()
            raw=(out/(name+'.stdout.log')).read_bytes()+(out/(name+'.stderr.log')).read_bytes()
            result['steps'].append({'name':name,'argv':argv,'exit_code':proc.returncode,'timeout':timeout,
                                    'seconds':round(time.monotonic()-t,3),
                                    'stdout':identity(out/(name+'.stdout.log')),
                                    'stderr':identity(out/(name+'.stderr.log'))})
            if timeout or proc.returncode!=exit_code or (marker and marker.encode() not in raw):
                raise ValueError('STEP_FAILED:'+name)
        step('compile',command,0)
        step('simulate',[str(CAD/'bin/vvp.exe'),str(image)],1 if args.mutant else 0,
             'SCORE_STALE_BANK_OR_ID' if args.mutant else 'PASS M2_SCORE_RAM_EVENT_PRIORITY_ISOLATED')
        result['sources_after']={str(p):identity(p) for p in sources}
        if result['sources_after']!=before:raise ValueError('INPUT_DRIFT')
        if time.monotonic()-begin>=300:raise TimeoutError('TOTAL300_POST')
        result['status']='MUTANT_REJECTED' if args.mutant else 'SCORE_PLAYBACK_ISOLATED_PASS'
    except Exception as exc:
        result['error']=type(exc).__name__+': '+str(exc)
        result['sources_after']={str(p):identity(p) for p in sources if p.is_file()}
    result['seconds']=round(time.monotonic()-begin,3)
    result['exit_code']=0 if result['error'] is None else 1
    (out/'RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status','error','seconds','exit_code')}))
    return result['exit_code']

if __name__=='__main__':raise SystemExit(main())