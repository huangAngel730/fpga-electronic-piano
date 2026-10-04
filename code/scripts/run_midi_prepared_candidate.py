"""Bounded isolated prepared-selector review; never alters production parser."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,time
ROOT=Path(__file__).resolve().parents[2]
SCOPE=ROOT/'code/tb/common/midi_prepared_candidate'
CAD=Path('D:/Gowin/oss-cad-suite')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    cli=argparse.ArgumentParser();cli.add_argument('--output',type=Path,required=True);cli.add_argument('--resume-tested-prefix',action='store_true');args=cli.parse_args()
    out=args.output.resolve();out.relative_to(ROOT/'code/output')
    if out.exists() and not args.resume_tested_prefix:raise ValueError('preserve existing run')
    if not out.exists():out.mkdir(parents=True)
    manifest=json.loads((SCOPE/'manifest.json').read_text())
    formal=ROOT/'code/rtl/input/midi_input/midi_event_parser.sv'
    if sha(formal)!=manifest['frozen_parser_SHA']:raise ValueError('baseline changed')
    original=formal.read_bytes();candidate=SCOPE/'midi_event_parser.sv'
    if sha(candidate)!=manifest['candidate_SHA']:raise ValueError('candidate changed')
    ref=out/'reference.sv';ref.write_bytes(original.replace(b'module midi_event_parser #(',b'module midi_event_parser_frozen #(',1))
    defs=ROOT/'code/rtl/common/audio_defs_pkg.sv'
    bench=(ROOT/'code/tb/common/midi_scheduler_setup_review/tb_m2_parser_miter.sv').read_text()
    assert bench.count('i==3?3:8')==1
    bench=bench.replace('i==3?3:8','i==3?16:8')
    tb=out/'tb_prepared_miter.sv';tb.write_text(bench,encoding='utf-8',newline='\n')
    env=os.environ.copy();env['PATH']=str(CAD/'lib')+';'+str(CAD/'bin')+';'+env['PATH']
    previous=json.loads((out/'run_status.json').read_text(encoding='utf-8')) if args.resume_tested_prefix else {}
    results={}
    def run(name,cmd,good=True,marker=None,timeout=240):
        start=time.monotonic();log=out/(name+'.log')
        if args.resume_tested_prefix and name!='directed_checker':
            old=previous.get('runs',{}).get(name)
            if not old or sha(log)!=old.get('log_SHA') or (old['exit']==0)!=good:raise ValueError('cannot reuse unverifiable failed prefix '+name)
            text=log.read_text(encoding='utf-8',errors='replace')
            if marker and marker not in text:raise ValueError('prefix marker missing '+name)
            results[name]={**old,'reused_measured_prefix':True};print('REUSE actual tested prefix',name,flush=True);return
        with log.open('w',encoding='utf-8') as f:
            try:p=subprocess.run([str(x) for x in cmd],cwd=out,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
            except subprocess.TimeoutExpired:
                results[name]={'timeout':True,'expected_success':good};raise
        text=log.read_text(encoding='utf-8',errors='replace');results[name]={'exit':p.returncode,'expected_success':good,'log_SHA':sha(log),'elapsed_seconds':round(time.monotonic()-start,2)}
        print(name,'exit',p.returncode,text[-650:],flush=True)
        if (p.returncode==0)!=good or (marker and marker not in text):raise ValueError('Unexpected result '+name)
    try:
        run('positive_compile',[CAD/'bin/iverilog.exe','-g2012','-s','tb_m2_parser_miter','-o',out/'positive.vvp',defs,candidate,ref,tb],timeout=40)
        run('positive',[CAD/'bin/vvp.exe',out/'positive.vvp'],marker='PASS M2 full original parser miter lane=3')
        text=candidate.read_text()
        mutants=[('stale_latest','parsed_control_rank <= first_prepared_rank','parsed_control_rank < first_prepared_rank'),('missing_previous_repair','previous_update<=parsed_control;','previous_update<=1\'b0;')]
        for name,before,after in mutants:
            if before not in text:raise ValueError('missing mutant anchor '+name)
            bad=out/(name+'.sv');bad.write_text(text.replace(before,after,1),encoding='utf-8',newline='\n')
            run(name+'_compile',[CAD/'bin/iverilog.exe','-g2012','-s','tb_m2_parser_miter','-o',out/(name+'.vvp'),defs,bad,ref,tb],timeout=40)
            run(name,[CAD/'bin/vvp.exe',out/(name+'.vvp')],good=False,marker='full parser')
        run('directed_checker',[os.sys.executable,'-X','utf8',SCOPE/'run_directed.py','--output',out/('directed_repaired' if args.resume_tested_prefix else 'directed')],marker='third_fallback_wrong compile 0 run 1',timeout=50)
        record={'manifest':manifest,'passed':True,'runs':results,'formal_SHA_after':sha(formal),'TB_SHA':sha(tb),'raw_source_comparison':'all public outputs and original registered scheduler state every cycle, four configurations incl burst1/8/16'}
        (out/'functional_review.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        print('PASS actual full-parser cycle equivalence and 2 full-parser + 1 directed compiled behavior mutants; NOT physical STA.',flush=True)
        return 0
    finally:
        (out/'run_status.json').write_text(json.dumps({'runs':results,'formal_SHA_after':sha(formal)},indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':raise SystemExit(main())