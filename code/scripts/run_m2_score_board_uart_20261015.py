"""Run a bounded real T062 UART→score-event→audio frame private simulation."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]
CAD=Path('D:/Gowin/oss-cad-suite')
VENDOR=Path('D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/simlib/gw5a/prim_sim.v')
PLL=ROOT/'code/tb/board/t058_waveform_integration_20261008/clock_plan_sim.v'
DVI=ROOT/'code/rtl/138K_try/hold_trials_20261005/dvi_sim_stub.v'
JOB=ROOT/'code/software/t052_runner_acceptance_candidate_20261012/windows_job.py'
ENCODER=ROOT/'code/software/score_transfer_v1/score_transfer.py'
TB=ROOT/'code/tb/board/m2_score_board_uart_candidate_20261015/tb_m2_score_board_uart.sv'


def ident(path):
    raw=Path(path).read_bytes()
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--prepared',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--mutant',action='store_true')
    args=ap.parse_args()
    prepared=args.prepared.resolve();out=args.output.resolve();scope=(ROOT/'code/output').resolve()
    if out.exists() or out==scope or not out.is_relative_to(scope):raise ValueError('NEW_OUTPUT_REQUIRED')
    out.mkdir(parents=True)
    begin=time.monotonic()
    result={'status':'FAIL_PARTIAL','error':None,'scope':'ISOLATED_ACTUAL_T062_UART_AUDIO_L2',
            'mutant':args.mutant,'new_EDA':0,'production_modified':False,
            'steps':[],'sources_before':{},'sources_after':{}}
    protected=[]
    try:
        if not prepared.is_relative_to(scope):raise ValueError('PREPARED_SCOPE')
        receipt=json.loads((prepared/'PREPARATION_RECEIPT.json').read_text(encoding='utf-8'))
        if receipt['status']!='PREPARED_SCORE_BOARD_NOT_PHYSICALLY_ADMITTED':raise ValueError('PREPARED_IDENTITY')
        sources=[Path(p) for p in receipt['source_files']]
        top=prepared/'m2_score_playback_board_top.sv'
        if ident(top)!=receipt['top']:raise ValueError('TOP_DRIFT')
        protected=list(dict.fromkeys([*sources,prepared/'PREPARATION_RECEIPT.json',ENCODER,TB,JOB,VENDOR,PLL,DVI,Path(__file__),CAD/'bin/iverilog.exe',CAD/'bin/vvp.exe']))
        if ident(JOB)['sha256']!='5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b':raise ValueError('JOB_SHA')
        old=json.loads((ROOT/'code/build/138k_night_cache_combo/staged_20261010_01/frozen_receipt.json').read_text(encoding='utf-8'))
        for n,item in old['inputs'].items():
            file=ROOT/'code/build/138k_night_cache_combo/staged_20261010_01/inputs'/n
            if ident(file)['sha256']!=item['adapted_sha256']:raise ValueError('FROZEN_INPUT_DRIFT:'+n)
        before={str(p):ident(p) for p in protected};result['sources_before']=before
        spec=importlib.util.spec_from_file_location('m2_score_encoder',ENCODER)
        score=importlib.util.module_from_spec(spec);spec.loader.exec_module(score)
        doc={'schema':1,'sample_hz':48000,'score_id':7,'events':[
            {'tick':0,'type':'note_on','channel':0,'note':69,'velocity':100},
            {'tick':16,'type':'note_off','channel':0,'note':69,'velocity':0}]}
        sid,records=score.encode_score(doc)
        frames=list(score.upload_frames(sid,records,session=1))
        if len(frames)!=3:raise ValueError('PACKET_COUNT')
        raw=b''.join(frames)
        bytesfile=out/'tx.hex'
        bytesfile.write_text('\n'.join(format(b,'02x') for b in raw)+'\n',encoding='ascii',newline='\n')
        result['score_input']={'doc':doc,'records_sha256':hashlib.sha256(records).hexdigest(),
            'packets':[len(x) for x in frames],'packet_sha256':[hashlib.sha256(x).hexdigest() for x in frames],
            'bytes':ident(bytesfile)}
        lib=VENDOR.read_text(encoding='utf-8');models=[]
        for name in ('GSR','pROM'):
            m=re.search(r'^module '+name+r' \([^\n]*\);[\s\S]*?^endmodule[^\n]*',lib,re.M)
            if not m:raise ValueError('PRIMITIVE_MISSING:'+name)
            models.append(m.group(0))
        model=out/'vendor_GSR_pROM.v';model.write_text('`timescale 1ns/1ps\n'+'\n'.join(models),encoding='utf-8',newline='\n')
        hdls=[p for p in sources if p.suffix in ('.sv','.v') and p.name not in ('DVI_TX_Top.v','TMDS_PLL_800_600_60.v')]
        # Icarus does not resolve quoted C:/... `include paths. Relocate only
        # these two literal headers in new compile copies, with exact inverse.
        result['include_adaptations']={}
        include_root=ROOT/'code/build/138k_night_cache_combo/staged_20261010_01/inputs/include'
        for name,header in (('simple_voice.sv','sine_table.svh'),('sustain_controller.sv','sustain_controller_ports.svh')):
            source=next(p for p in hdls if p.name==name)
            original=source.read_bytes()
            exact=(chr(34)+(include_root/header).as_posix()+chr(34)).encode()
            replacement=bytes([34])+header.encode()+bytes([34])
            if original.count(exact)!=1:raise ValueError('HEADER_RELOCATION_ANCHOR:'+name)
            adapted=original.replace(exact,replacement,1)
            if adapted.replace(replacement,exact,1)!=original:raise ValueError('HEADER_RELOCATION_INVERSE:'+name)
            destination=out/name
            destination.write_bytes(adapted)
            hdls[hdls.index(source)]=destination
            result['include_adaptations'][name]={'source':ident(source),'adapted':ident(destination)}
        if args.mutant:
            orig=top.read_text(encoding='utf-8');old_wire='.event_data(score_mixed_data),.frame_tick(i2s_frame_tick),'
            if orig.count(old_wire)!=1:raise ValueError('MUTATION_ANCHOR')
            bad=out/'m2_score_playback_board_top.sv'
            bad.write_text(orig.replace(old_wire,'.event_data(shared_event_data),.frame_tick(i2s_frame_tick),',1),encoding='utf-8',newline='\n')
            hdls[hdls.index(top)]=bad
            result['mutation']={'kind':'DISCONNECT_SCORE_EVENT_FROM_AUDIO','original':ident(top),'mutated':ident(bad)}
        hdls.sort(key=lambda x:0 if x.name=='audio_defs_pkg.sv' else 1 if x.name=='sustain_control_contract_pkg.sv' else 2)
        command=[str(CAD/'bin/iverilog.exe'),'-g2012','-I',str(ROOT/'code/build/138k_night_cache_combo/staged_20261010_01/inputs/include'),'-s','tb_m2_score_board_uart','-o',str(out/'board.vvp')]
        command+=list(map(str,[*hdls,model,PLL,DVI,TB]))
        job_spec=importlib.util.spec_from_file_location('m2_winjob',JOB)
        helper=importlib.util.module_from_spec(job_spec);job_spec.loader.exec_module(helper)
        env=os.environ.copy();env['YOSYSHQ_ROOT']=str(CAD)+os.sep;env['PATH']=os.pathsep.join([str(CAD/'bin'),str(CAD/'lib'),env.get('PATH','')])
        def step(label,argv,expected,marker=None):
            left=300-(time.monotonic()-begin)
            if left<=0:raise TimeoutError('TOTAL300_PRE_'+label)
            job=helper.WindowsJob();start=time.monotonic();timed_out=False
            try:
                with (out/(label+'.stdout.log')).open('xb') as stdout,(out/(label+'.stderr.log')).open('xb') as stderr:
                    child=subprocess.Popen(argv,cwd=out,env=env,stdout=stdout,stderr=stderr,creationflags=4)
                    job.attach_and_resume(child)
                    try:child.wait(timeout=min(90,left))
                    except subprocess.TimeoutExpired:timed_out=True;job.terminate();child.wait(timeout=5)
            finally:job.close()
            raw=(out/(label+'.stdout.log')).read_bytes()+(out/(label+'.stderr.log')).read_bytes()
            result['steps'].append({'name':label,'argv':argv,'exit_code':child.returncode,'timeout':timed_out,
                'seconds':round(time.monotonic()-start,3),'stdout':ident(out/(label+'.stdout.log')),
                'stderr':ident(out/(label+'.stderr.log'))})
            if timed_out or child.returncode!=expected or (marker and marker.encode() not in raw):raise ValueError('STEP_FAILED:'+label)
        step('compile',command,0)
        args_run=[str(CAD/'bin/vvp.exe'),str(out/'board.vvp'),'+BYTES='+str(bytesfile),
                  '+P1='+str(len(frames[0])),'+P2='+str(len(frames[1])),'+P3='+str(len(frames[2]))]
        step('simulate',args_run,1 if args.mutant else 0,
             'SCORE_EVENT_NOT_REACHING_AUDIO' if args.mutant else 'PASS REAL_T062_UART_TO_SCORE_EVENT_TO_PCM_ISOLATED')
        after={str(p):ident(p) for p in protected};result['sources_after']=after
        if after!=before:raise ValueError('INPUT_DRIFT_AFTER')
        if time.monotonic()-begin>=300:raise TimeoutError('TOTAL300_POST')
        result['status']='MUTANT_REJECTED' if args.mutant else 'REAL_T062_UART_EVENT_AUDIO_SIM_PASS'
    except Exception as exc:
        result['error']=type(exc).__name__+': '+str(exc)
        result['sources_after']={str(p):ident(p) for p in protected if p.is_file()}
    result['seconds']=round(time.monotonic()-begin,3)
    result['exit_code']=0 if result['error'] is None else 1
    (out/'RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status','error','seconds','exit_code')}))
    return result['exit_code']

if __name__=='__main__':raise SystemExit(main())