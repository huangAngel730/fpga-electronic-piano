"""Bound static software suite and production prepare/verify; no HDL/EDA."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
ABCD=ROOT/'code/output/n32_publication_20261014_r01/transfer/M3_N32_ABCD_20261014_COMPLETE.zip'
CFULL=ROOT/'code/output/n32_c_full_publication_20261014_r01/transfer/M3_N32_C_FULL_20261014.zip'
RECEIPT=Path('E:/FPGA/GAOYUNFPGA/Callback3/chat6/M2_REVIEW_RECEIPT.json')
JOB=ROOT/'code/software/t052_runner_acceptance_candidate_20261012/windows_job.py'
JOB_SHA='5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b'


def info(path):
    digest=hashlib.sha256();length=0
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            digest.update(block);length+=len(block)
    return dict(bytes=length,sha256=digest.hexdigest())


def execute(argv,cwd,directory,seconds,environment):
    directory.mkdir(exist_ok=False)
    record=dict(argv=list(map(str,argv)),cwd=str(cwd),environment=environment,
                bound_seconds=seconds,exit_code=None,timed_out=False,started=False,
                shell=False,automatic_retries=0,EDA_calls=0,RTL_calls=0)
    start=time.monotonic();job=None
    try:
        if os.name!='nt':raise ValueError('WINDOWS_PRIVATE_JOB_REQUIRED')
        if info(JOB)['sha256']!=JOB_SHA:raise ValueError('PRIVATE_JOB_IDENTITY_CHANGED')
        spec=importlib.util.spec_from_file_location('binding_owned_job',JOB)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        job=module.WindowsJob()
        with (directory/'stdout.log').open('xb') as out,(directory/'stderr.log').open('xb') as err:
            child=subprocess.Popen(argv,cwd=cwd,env=environment,stdout=out,stderr=err,creationflags=0x00000004)
            record['started']=True;job.attach_and_resume(child)
            try:child.wait(timeout=seconds)
            except subprocess.TimeoutExpired:
                record['timed_out']=True;record['termination']=job.terminate();child.wait(timeout=5)
            record['exit_code']=child.returncode
    except Exception as error:record['error']=type(error).__name__+': '+str(error)
    finally:
        if job is not None:job.close()
        record['seconds']=time.monotonic()-start
        record['logs']={p.name:info(p) for p in directory.glob('*.log')}
        (directory/'receipt.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();output=args.output.resolve()
    if output.parent!=ROOT/'code/output' or not output.name.startswith('n32_d_cfull_binding_'):
        parser.error('fresh direct task output under code/output required')
    output.mkdir(exist_ok=False);start=time.monotonic()
    result=dict(schema=1,passed=False,stages=[],total_bound_seconds=300,step_bound_seconds=90,
                EDA_calls=0,RTL_calls=0,device_calls=0,scope='STATIC_BINDING_ONLY',resources='UNKNOWN',STA='NOT_RUN',T061_complete=False)
    paths=[];before={}
    try:
        for path in HERE.iterdir():
            if path.is_file() and path.suffix in ('.py','.json','.txt'):
                destination=output/'source_before'/path.name;destination.parent.mkdir(exist_ok=True);shutil.copyfile(path,destination)
        paths=list(HERE.glob('*.py'))+list(HERE.glob('*.json'))+list(HERE.glob('*.txt'))
        paths += [ABCD,CFULL,RECEIPT,RECEIPT.with_name('M2_REVIEW.md'),JOB,
                  ROOT/'code/build/138k_polyphony_resource/m3_n32_allocator_candidate_20261013/D_N32_R1_EXACT_HANDOFF_20261015.md',Path(sys.executable).resolve()]
        runtime=Path(sys.executable).resolve().parent
        paths += [p for p in runtime.rglob('*') if p.is_file() and p.suffix.lower() in ('.exe','.dll','.pyd','.zip')]
        paths=sorted(set(paths));before={str(p):info(p) for p in paths}
        fixed={ABCD:'ba9e4f42d9aa5bb60c6d5122ae271fc58b3b9e7d27cca4caa48fd9740d85aa36',CFULL:'eac6e9371a96e91447a75d869d7e7a6dc76252fd89d6c8b621953a396a42c726',RECEIPT:'e0447a093fc6d2cc593d9012f8ac2be0585aeed33cee447bc02ffbe84d795fbe'}
        for path,expected in fixed.items():
            if before[str(path)]['sha256']!=expected:raise ValueError('INDEPENDENT_ANCHOR_MISMATCH: '+str(path))
        environment={key:value for key,value in os.environ.items() if key.upper() in ('SYSTEMROOT','WINDIR','COMSPEC','PATH','TEMP','TMP')}
        environment.update(PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',PYTHONIOENCODING='utf-8')
        bootstrap=("import os,sys,unittest;sys.path.insert(0,sys.argv[1]);os.environ['N32_BINDING_TEST_OUTPUT']=sys.argv[2];"
                   "s=unittest.defaultTestLoader.discover(sys.argv[1],pattern='test_binding.py');"
                   "r=unittest.TextTestRunner(verbosity=2).run(s);raise SystemExit(not r.wasSuccessful())")
        base=[sys.executable,'-I','-S','-B','-X','utf8']
        commands=[('software_tests',base+['-c',bootstrap,str(HERE),str(output/'cases')]),
                  ('prepare',base+[str(HERE/'binding_check.py'),'prepare','--abcd',str(ABCD),'--cfull',str(CFULL),'--receipt',str(RECEIPT),'--output',str(output/'prepared')]),
                  ('verify',base+[str(HERE/'binding_check.py'),'verify','--prepared',str(output/'prepared'),'--output',str(output/'verified')])]
        for name,argv in commands:
            remaining=300-(time.monotonic()-start)-10
            if remaining<=0:raise TimeoutError('OUTER_BUDGET_BEFORE_LAUNCH')
            execution=execute(argv,ROOT,output/(name+'_logs'),min(90,remaining),environment)
            result['stages'].append(dict(name=name,execution=execution))
            if execution['exit_code']!=0 or execution['timed_out'] or execution.get('error'):
                raise ValueError('STAGE_FAILED: '+name)
        result['passed']=True
    except Exception as error:result['error']=type(error).__name__+': '+str(error)
    finally:
        after={};errors=[]
        for path in paths:
            try:after[str(path)]=info(path)
            except Exception as error:after[str(path)]=None;errors.append(str(path)+': '+str(error))
        result.update(before=before,after=after,identity_errors=errors,seconds=time.monotonic()-start)
        if errors or before!=after or result['seconds']>300:result['passed']=False
        result['runner_exit']=0 if result['passed'] else 1
        (output/'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result.get(k) for k in ('passed','runner_exit','error','seconds')}))
    print('Receipt:',output/'receipt.json')
    return result['runner_exit']


if __name__=='__main__':raise SystemExit(main())
