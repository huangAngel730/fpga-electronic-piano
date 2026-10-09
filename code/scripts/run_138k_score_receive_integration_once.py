"""Exactly one full score-uart project build, requiring fulltop qualified proof."""
from pathlib import Path
import argparse,hashlib,json,subprocess,time,sys,os
from datetime import datetime
import prepare_138k_score_receive_integration as prepared
import check_138k_score_receive_integration as gate
ROOT=Path(__file__).resolve().parents[2]
TOOL=Path('D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def main():
    c=argparse.ArgumentParser(description=__doc__);c.add_argument('--output',type=Path,required=True);c.add_argument('--simulation-receipts',type=Path,nargs='+',required=True);c.add_argument('--preflight-receipt',type=Path,required=True);c.add_argument('--timeout-seconds',type=int,default=1800);args=c.parse_args();run=args.output.resolve();run.relative_to((prepared.BUILD_ROOT/'runs').resolve())
    if run.exists() or run==(prepared.BUILD_ROOT/'runs').resolve() or not 1<=args.timeout_seconds<=1800:c.error('unique bounded newrun required')
    proofs={}
    for path in args.simulation_receipts:
        r=json.loads(path.read_bytes())
        if not r.get('passed') or r.get('elapsed_seconds',999999)>1800:c.error('simulationnotqualified')
        name=r.get('negative') or 'positive'
        if name in proofs:c.error('duplicateproof')
        for rel,h in r['source_SHA256'].items():
            if sha(rel)!=h:c.error('simulatedsourcechanged '+rel)
        for rel,h in r['compiled_sources_SHA256'].items():
            if sha(rel)!=h:c.error('compiledstagingchanged '+rel)
        proofs[name]={'path':str(path.resolve()),'sha256':sha(path),'result':r.get('result'),'specified_negative':r.get('specified_negative')}
    if set(proofs)!={'positive','audio_isolation','response_command'}:c.error('needqualifiedpositiveand2behaviornegative')
    p=json.loads(args.preflight_receipt.read_bytes())
    if not p.get('passed'):c.error('preflightfailed')
    for rel,h in p['source_SHA256'].items():
        if sha(ROOT/rel)!=h:c.error('preflightsourcechanged')
    run.mkdir(parents=True);project=run/'project';prepared.prepare(project);r={'date':'2026-10-09','version':'score_receive_integration_1','attempt_count':1,'state':'running','programmed':False,'timeout_seconds':args.timeout_seconds,'timed_out':False,'started':datetime.now().astimezone().isoformat(),'simulation_proofs':proofs,'preflight_SHA256':sha(args.preflight_receipt),'frozen_sha256_before':sha(project/'frozen_receipt.json'),'command':[str(TOOL),'run.tcl'],'tools_and_sources_sha256':{str(q.resolve()):sha(q) for q in [TOOL,Path(__file__),Path(prepared.__file__),Path(gate.__file__),prepared.SCOPE/'integration_manifest.json',*list((prepared.SCOPE/'overlay').iterdir())]}};dump(run/'build_receipt.json',r);start=time.monotonic()
    with (run/'build.log').open('wb') as log:
        proc=subprocess.Popen(r['command'],cwd=project,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW);r['pid']=proc.pid;dump(run/'build_receipt.json',r)
        try:proc.wait(timeout=args.timeout_seconds)
        except subprocess.TimeoutExpired:r['timed_out']=True;subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True,timeout=20);proc.wait(timeout=20)
    r.update(exit_code=proc.returncode,state='finished' if not proc.returncode and not r['timed_out'] else 'failed',elapsed_seconds=round(time.monotonic()-start,3),finished=datetime.now().astimezone().isoformat(),frozen_sha256_after=sha(project/'frozen_receipt.json'),log_sha256=sha(run/'build.log'));dump(run/'build_receipt.json',r)
    if proc.returncode or r['timed_out']:print(json.dumps(r,indent=2));return 1
    result=gate.review(run);dump(run/'assessment.json',result);r['assessment_passed']=result['passed'];dump(run/'build_receipt.json',r);print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
