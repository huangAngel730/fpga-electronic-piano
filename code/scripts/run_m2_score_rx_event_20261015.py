"""One bounded real T062 UART→M2 score-event test, without any audio core."""
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
ENCODER=ROOT/'code/software/score_transfer_v1/score_transfer.py'
PKG=ROOT/'code/rtl/common/audio_defs_pkg.sv'
RX=ROOT/'code/rtl/common/uart_rx.sv'
TX=ROOT/'code/rtl/common/uart_tx.sv'
LANES=ROOT/'code/rtl/input/score_transfer_bram_candidate/score_byte_lane.sv'
RAM=ROOT/'code/rtl/input/score_transfer_bram_candidate/score_transfer_bram_candidate.sv'
PLAYER=ROOT/'code/rtl/board/m2_score_playback_candidate_20261015/m2_score_playback_candidate.sv'
TB=ROOT/'code/tb/board/m2_score_rx_event_candidate_20261015/tb_m2_score_rx_event.sv'


def identity(path):
    raw=Path(path).read_bytes()
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--mutant',action='store_true')
    args=ap.parse_args()
    out=args.output.resolve();scope=(ROOT/'code/output').resolve()
    if out.exists() or out==scope or not out.is_relative_to(scope):raise ValueError('NEW_OUTPUT_REQUIRED')
    out.mkdir(parents=True)
    begin=time.monotonic()
    receipt={'status':'FAIL_PARTIAL','error':None,'scope':'ACTUAL_T062_UART_RAM_TO_EVENT_NO_AUDIO',
             'mutant':args.mutant,'new_EDA':0,'production_modified':False,'steps':[],
             'sources_before':{},'sources_after':{}}
    sources=[PKG,RX,TX,LANES,RAM,PLAYER,TB,ENCODER,JOB,Path(__file__),CAD/'bin/iverilog.exe',CAD/'bin/vvp.exe']
    try:
        if identity(RAM)['sha256']!='ef57f7f98559a9f9dd262dacc77313cf720b4ff3df63ee962f75c41d1669bc1f':
            raise ValueError('T062_RAM_SOURCE_DRIFT')
        if identity(JOB)['sha256']!='5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b':
            raise ValueError('JOB_SOURCE_DRIFT')
        before={str(p):identity(p) for p in sources};receipt['sources_before']=before
        spec=importlib.util.spec_from_file_location('score_encode',ENCODER)
        score=importlib.util.module_from_spec(spec);spec.loader.exec_module(score)
        doc={'schema':1,'sample_hz':48000,'score_id':7,'events':[
            {'tick':0,'type':'note_on','channel':0,'note':69,'velocity':100},
            {'tick':16,'type':'note_off','channel':0,'note':69,'velocity':0}]}
        sid,records=score.encode_score(doc);frames=list(score.upload_frames(sid,records,session=1))
        if len(frames)!=3 or [len(f) for f in frames]!=[28,30,14]:raise ValueError('T057_FIXTURE_SIZE')
        bytesfile=out/'tx.hex';bytesfile.write_text('\n'.join(f'{b:02x}' for b in b''.join(frames))+'\n',encoding='ascii',newline='\n')
        receipt['score_fixture']={'record_sha256':hashlib.sha256(records).hexdigest(),
                                   'packet_sha256':[hashlib.sha256(f).hexdigest() for f in frames],
                                   'tx_hex':identity(bytesfile),'packet_lengths':[len(f) for f in frames]}
        spec=importlib.util.spec_from_file_location('m2_rx_winjob',JOB)
        helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
        env=os.environ.copy();env['YOSYSHQ_ROOT']=str(CAD)+os.sep
        env['PATH']=os.pathsep.join([str(CAD/'bin'),str(CAD/'lib'),env.get('PATH','')])
        cmd=[str(CAD/'bin/iverilog.exe'),'-g2012','-s','tb_m2_score_rx_event','-o',str(out/'rx.vvp')]
        if args.mutant:cmd.append('-DMUTANT_RAM_READ')
        cmd+=list(map(str,[PKG,RX,TX,LANES,RAM,PLAYER,TB]))
        def step(label,argv,expected,marker=None):
            left=300-(time.monotonic()-begin)
            if left<=0:raise TimeoutError('TOTAL300_PRE_'+label)
            job=helper.WindowsJob();start=time.monotonic();timeout=False
            try:
                with (out/(label+'.stdout.log')).open('xb') as stdout,(out/(label+'.stderr.log')).open('xb') as stderr:
                    proc=subprocess.Popen(argv,cwd=out,env=env,stdout=stdout,stderr=stderr,creationflags=4)
                    job.attach_and_resume(proc)
                    try:proc.wait(timeout=min(90,left))
                    except subprocess.TimeoutExpired:timeout=True;job.terminate();proc.wait(timeout=5)
            finally:job.close()
            output=(out/(label+'.stdout.log')).read_bytes()+(out/(label+'.stderr.log')).read_bytes()
            receipt['steps'].append({'label':label,'argv':argv,'exit_code':proc.returncode,
                                     'timeout':timeout,'seconds':round(time.monotonic()-start,3),
                                     'stdout':identity(out/(label+'.stdout.log')),
                                     'stderr':identity(out/(label+'.stderr.log'))})
            if timeout or proc.returncode!=expected or (marker and marker.encode() not in output):
                raise ValueError('STEP_FAILED:'+label)
        step('compile',cmd,0)
        run=[str(CAD/'bin/vvp.exe'),str(out/'rx.vvp'),'+BYTES='+str(bytesfile),
             '+P1=28','+P2=30','+P3=14']
        step('simulate',run,1 if args.mutant else 0,
             'REAL_RAM_SCORE_RX_EVENT_BAD' if args.mutant else 'PASS REAL_T062_UART_TO_SCORE_EVENTS_NO_AUDIO')
        after={str(p):identity(p) for p in sources};receipt['sources_after']=after
        if after!=before:raise ValueError('PROTECTED_SOURCE_DRIFT')
        if time.monotonic()-begin>=300:raise TimeoutError('TOTAL300_POST')
        receipt['status']='MUTANT_REJECTED' if args.mutant else 'REAL_RAM_UART_TO_EVENT_L2_PASS'
    except Exception as exc:
        receipt['error']=type(exc).__name__+': '+str(exc)
        receipt['sources_after']={str(p):identity(p) for p in sources if p.is_file()}
    receipt['elapsed_seconds']=round(time.monotonic()-begin,3)
    receipt['exit_code']=0 if receipt['error'] is None else 1
    (out/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:receipt.get(k) for k in ('status','error','elapsed_seconds','exit_code')}))
    return receipt['exit_code']

if __name__=='__main__':raise SystemExit(main())