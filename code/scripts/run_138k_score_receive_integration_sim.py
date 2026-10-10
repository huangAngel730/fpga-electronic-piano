"""Bounded new score-port integration against frozen audio/wave reference."""
from __future__ import annotations
import argparse,hashlib,json,os,re,subprocess,sys,time,xml.etree.ElementTree as ET,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'code/scripts'))
import prepare_138k_score_receive_integration as prepare
TB=ROOT/'code/tb/board/score_receive_integration_20261009';sys.path.insert(0,str(TB))
import vectors,check_capture
CAD=Path('D:/Gowin/oss-cad-suite')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--project',type=Path,required=True);cli.add_argument('--output',type=Path,required=True);cli.add_argument('--negative',choices=['audio_isolation','response_command']);args=cli.parse_args();prepare.validate(args.project);O=args.output.resolve();O.relative_to((ROOT/'code/output').resolve());O.mkdir(parents=True,exist_ok=False);S=O/'sources';S.mkdir();start=time.monotonic();env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1');env['PATH']=str(CAD/'bin')+os.pathsep+str(CAD/'lib')+os.pathsep+env.get('PATH','');record={'passed':False,'date':'2026-10-09','scope':'shortscore/fulltop logicaleq only; not hardware or TMDS','steps':{},'source_SHA256':{},'adaptations':{},'negative':args.negative,'programmed':False};oracle=vectors.build(O/'vectors');record['oracle_SHA256']=sha(O/'vectors/oracle.json');compiled={}
    def run(label,cmd,limit):
        t=time.monotonic();remain=1800-(t-start)
        if remain<=0:raise ValueError('global_timeout')
        p=subprocess.run(list(map(str,cmd)),cwd=O,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=min(limit,remain));(O/(label+'.stdout.log')).write_bytes(p.stdout);(O/(label+'.stderr.log')).write_bytes(p.stderr);record['steps'][label]={'command':list(map(str,cmd)),'exit_code':p.returncode,'seconds':round(time.monotonic()-t,3),'stdout_SHA256':hashlib.sha256(p.stdout).hexdigest(),'stderr_SHA256':hashlib.sha256(p.stderr).hexdigest()};print(label,p.returncode,flush=True);return p
    def adapt(name,raw):
        s=raw.decode('utf-8');new=re.sub(r'\bint unsigned\b','integer',s);new=re.sub(r'`include "[^"]*/(sine_table\.svh|sustain_controller_ports\.svh)"',r'`include "\1"',new)
        if name=='voice_allocator_4.sv':
            fields={'note_active':1,'in_release':1,'source':4,'channel':4,'note':8,'age':2};anchor='    voice_slot_t slots [0:3];';assert new.count(anchor)==1;decl='\n'.join('    logic '+('['+str(w-1)+':0] ' if w>1 else '')+'sim_slot_'+f+' [0:3];' for f,w in fields.items());new=new.replace(anchor,decl).replace("                slots[i] <= '0;",'\n'.join("                sim_slot_"+f+"[i] <= '0;" for f in fields),1)
            for field in fields:new=re.sub(r'slots\[([^\]]+)\]\.'+field+r'\b',r'sim_slot_'+field+r'[\1]',new)
        q=S/name;q.write_text(new,encoding='utf-8',newline='\n');record['adaptations'][name]={'original_SHA256':hashlib.sha256(raw).hexdigest(),'adapted_SHA256':sha(q),'scope':'onlyIcarusintqualifier/structfield/includeSyntax'};return q
    code=1
    try:
        manifest=prepare.validate(args.project);record['frozen_receipt_SHA256']=sha(args.project/'frozen_receipt.json');units=[]
        for q in (args.project/'inputs/sources').iterdir():
            record['source_SHA256'][str(q.resolve())]=sha(q)
            if q.name not in ['DVI_TX_Top.v','TMDS_PLL_800_600_60.v']:adapt(q.name,q.read_bytes())
        for q in (args.project/'inputs/include').glob('*'):adapt(q.name,q.read_bytes());record['source_SHA256'][str(q.resolve())]=sha(q)
        parent_inputs=prepare.parent.inputs(args.project)[0];raw=parent_inputs['sources/audio_visual_coexistence_top.sv'].decode();raw=raw.replace('module audio_visual_coexistence_top','module reference_audio_visual_top').replace('AUDIO_VISUAL_COEXISTENCE_TOP_SV','REFERENCE_AUDIO_VISUAL_TOP_SV');adapt('reference_audio_visual_top.sv',raw.encode());record['reference_current_v3_top_SHA256']=hashlib.sha256(parent_inputs['sources/audio_visual_coexistence_top.sv']).hexdigest()
        tree=ET.parse(args.project/prepare.PROJECT).getroot();names=[Path(x.attrib['path']).name for x in tree.find('FileList') if x.attrib['type']=='file.verilog' and Path(x.attrib['path']).name not in ['DVI_TX_Top.v','TMDS_PLL_800_600_60.v']];units=[S/n for n in names]+[S/'reference_audio_visual_top.sv']
        if args.negative=='audio_isolation':
            q=S/'audio_visual_coexistence_top.sv';before='.pcm_left  (buffered_left)';s=q.read_text(encoding='utf-8');assert s.count(before)==1;q.write_text(s.replace(before,'.pcm_left  (buffered_left ^ 24\'sh000100)'),encoding='utf-8',newline='\n')
        if args.negative=='response_command':
            q=S/'score_transfer_candidate.sv';before='buffer[12]=command;';s=q.read_text(encoding='utf-8');assert s.count(before)==1;q.write_text(s.replace(before,"buffer[12]=command ^ 8'h01;"),encoding='utf-8',newline='\n')
        bench=TB/'tb_score_receive_integration.sv';clock=ROOT/'code/tb/board/t058_waveform_integration_20261008/clock_plan_sim.v';stub=ROOT/'code/rtl/138K_try/clock_trials_20261005/dvi_sim_stub.v';tools=[CAD/'bin/iverilog.exe',CAD/'bin/vvp.exe']
        for q in [bench,clock,stub,TB/'vectors.py',TB/'check_capture.py',Path(__file__),*tools]:record['source_SHA256'][str(q.resolve())]=sha(q)
        cmd=[tools[0],'-B',CAD/'lib/ivl','-g2012','-I',S,'-s','tb_score_receive_integration','-o',O/'sim.vvp']
        if args.negative=='response_command':cmd+=['-Ptb_score_receive_integration.NEGATIVE_STOP=1']
        cmd +=units+[clock,stub,bench];p=run('compile',cmd,90)
        if p.returncode:raise ValueError('compile_failed')
        compiled={str(q.resolve()):sha(q) for q in [*units,clock,stub,bench]};record['compiled_sources_SHA256']=compiled;p=run('simulate',[tools[1],O/'sim.vvp','+PLAN='+str(O/'vectors/plan.txt'),'+CAPTURE='+str(O/'capture.txt')],1200)
        if args.negative=='audio_isolation':
            if p.returncode!=1 or b'UPLOAD_AUDIO_OR_STAT_CHANGED' not in p.stdout+p.stderr:raise ValueError('audio_negative_not_designassert')
            record['specified_negative']={'compile_exit':0,'run_exit':1,'reason':'UPLOAD_AUDIO_OR_STAT_CHANGED'}
        else:
            if p.returncode:raise ValueError('simulate_failed')
            try:record['result']=check_capture.check(O/'capture.txt',oracle,args.negative=='response_command')
            except ValueError as exc:
                if args.negative!='response_command' or 'RESPONSE_BYTES_COMMAND_METADATA_OR_EVENT' not in str(exc):raise
                record['specified_negative']={'compile_exit':0,'run_exit':0,'checker_exit':1,'reason':str(exc)}
            if args.negative=='response_command' and 'specified_negative' not in record:raise ValueError('negative_falsegreen')
        if any(sha(Path(n))!=h for n,h in record['source_SHA256'].items()):raise ValueError('source_changed')
        if any(sha(Path(n))!=h for n,h in compiled.items()):raise ValueError('compiled_changed')
        record['passed']=True;code=0
    except Exception as exc:record['error']=type(exc).__name__+': '+str(exc);print(record['error'],flush=True)
    record['elapsed_seconds']=round(time.monotonic()-start,3);record['capture_SHA256']=sha(O/'capture.txt') if (O/'capture.txt').exists() else None
    if record['elapsed_seconds']>1800:record['passed']=False;code=1;record['error']='elapsed_global_timeout'
    (O/'receipt.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');print('SCORE_INTEGRATION',record['passed'],record['elapsed_seconds'],flush=True);return code
if __name__=='__main__':raise SystemExit(main())
