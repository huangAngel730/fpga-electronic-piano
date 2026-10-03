"""Reproduce actual four-voice V1/CC64 bank Pitch/Mod integration in isolation."""
from pathlib import Path
import argparse,json,hashlib,os,subprocess,sys,shutil,importlib.util
ROOT=Path(__file__).resolve().parents[2]
CAND=ROOT/'code/tb/board/pitch_mod_bank_integration_candidate'
CAD=Path('D:/Gowin/oss-cad-suite')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
 cfg=parser.parse_args();out=cfg.output.resolve();out.relative_to(ROOT/'code/output')
 if out.exists():raise ValueError('output exists: preserve prior evidence')
 out.mkdir(parents=True);env=os.environ.copy();env['PATH']=str(CAD/'lib')+';'+str(CAD/'bin')+';'+env['PATH'];env['PYTHONDONTWRITEBYTECODE']='1'
 runs={}
 def run(name,cmd,marker=None,success=True,timeout=120):
  with (out/(name+'.log')).open('w',encoding='utf-8') as stream:
   result=subprocess.run(list(map(str,cmd)),cwd=out,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
  text=(out/(name+'.log')).read_text(encoding='utf-8',errors='replace');runs[name]={'exit':result.returncode,'log_sha':sha(out/(name+'.log'))}
  print(name,'exit',result.returncode,flush=True)
  if (result.returncode==0)!=success or (marker and marker not in text):
   print(text[-3500:]);raise RuntimeError('unexpected verdict '+name)
  return text
 spec=importlib.util.spec_from_file_location('adsr_stage',ROOT/'code/scripts/run_adsr_pipeline_isolated.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 (out/'adsr').mkdir();metadata,_=mod.patch_copies(out/'adsr')
 ref=out/'bank_reference.sv';ref.write_text((out/'adsr/polyphonic_envelope_bank.sv').read_text().replace('module polyphonic_envelope_bank','module bank_reference',1),encoding='utf-8',newline='\n')
 for target,source in [('wave.mem','code/model/generated/wavetables/piano_band_4x256_8191.mem'),('velocity.mem','code/model/generated/wavetables/velocity_gain_rom.mem'),('oct.mem','code/model/generated/pitch_mod/oct_ratio_q16.mem'),('sub.mem','code/model/generated/pitch_mod/sub_ratio_q16.mem'),('lfo.mem','code/model/generated/pitch_mod/lfo_sine_q15.mem')]:shutil.copyfile(ROOT/source,out/target)
 (out/'model/generated/pitch_mod').mkdir(parents=True)
 for small,rom in [('oct.mem','oct_ratio_q16.mem'),('sub.mem','sub_ratio_q16.mem'),('lfo.mem','lfo_sine_q15.mem')]:shutil.copyfile(out/small,out/'model/generated/pitch_mod'/rom)
 allocator=ROOT/'code/rtl/audio/voice_allocator_4.sv';lower=out/'allocator.v';ys=out/'lower.ys';ys.write_text('read_slang --top voice_allocator_4 '+allocator.as_posix()+'\nproc\nopt\ntechmap\nopt\nwrite_verilog -noattr '+lower.as_posix()+'\n',encoding='ascii')
 run('allocator_lower',[CAD/'bin/yosys.exe','-Q','-T','-s',ys])
 sources=[ROOT/'code/rtl/common/audio_defs_pkg.sv',lower,ROOT/'code/rtl/common/note_pitch.sv',ROOT/'code/rtl/board/sustain_control_contract_pkg.sv',ROOT/'code/rtl/input/sustain_control/sustain_controller.sv',CAND/'polyphonic_event_router.sv',CAND/'polyphonic_envelope_bank.sv',ref,ROOT/'code/rtl/board/performance_control_snapshot.sv',ROOT/'code/tb/board/pitch_mod_pipeline_candidate/pitch_mod_fcw_pipeline.sv',ROOT/'code/tb/board/pitch_mod_pipeline_candidate/pitch_mod_snapshot_pipeline.sv',ROOT/'code/rtl/audio/dds_oscillator.sv',ROOT/'code/rtl/audio/piano_dds_oscillator.sv',out/'adsr/adsr_piano_envelope.sv']
 run('bank_compile',[CAD/'bin/iverilog.exe','-g2012','-I',ROOT/'code/rtl/board','-s','tb_pitch_mod_bank_integration','-o',out/'bank.vvp',*sources,CAND/'tb_pitch_mod_bank_integration.sv'])
 text=run('bank_run',[CAD/'bin/vvp.exe',out/'bank.vvp','+VELOCITY_ROM_PATH='+str(out/'velocity.mem')],marker='PASS actual bank PitchMod V1 CC64')
 print(text[-600:])
 # Actual accepted-event reference, not the RTL's selected controls.
 spec=importlib.util.spec_from_file_location('m1pitch',ROOT/'code/model/pitch_mod_model.py');model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
 state={};voices=[model.PitchModVoice() for _ in range(4)];requests={};computed={};summary={'captures':0,'math_results':0,'bank_results':0,'nonzero_controls':0,'dds_ticks':0,'cancelled_frames':0};lines=(out/'bank.capture').read_text().splitlines()
 for line in lines:
  f=line.split();tag=f[0]
  if tag=='R':
   state={};requests={};computed={}
   for v in voices:v.reset()
  elif tag=='E':
   ev=int(f[2],16);kind=(ev>>61)&7;identity=((ev>>57)&15)*16+((ev>>53)&15);ctrl=(ev>>18)&255;value=(ev>>6)&4095
   params=state.setdefault(identity,[0,0,2])
   if kind==3 and ctrl==0:params[0]=value-4096 if value&2048 else value
   if kind==4 and ctrl==1:params[1]=value
   if kind==4 and ctrl==4 and value<=24:params[2]=value
  elif tag=='N':
   mask=int(f[2],16)
   for i in range(4):
    if mask>>i&1:voices[i].reset()
  elif tag=='Q':
   rid=int(f[2]);mask=int(f[3],16);sources_id=int(f[4],16);channels=int(f[5],16);gen=int(f[6],16);base=int(f[7],16)
   params=[state.get(((sources_id>>(4*i))&15)*16+((channels>>(4*i))&15),[0,0,2]).copy() if mask>>i&1 else [0,0,2] for i in range(4)]
   requests[rid]=(mask,sources_id,channels,gen,base,params);summary['captures']+=1
  elif tag=='S':
   rid=int(f[2]);mask,src,ch,gen,base,params=requests[rid]
   assert int(f[3],16)==sum((p[0]&4095)<<(12*i) for i,p in enumerate(params)),('bend snapshot',line)
   assert int(f[4],16)==sum(p[1]<<(12*i) for i,p in enumerate(params)),('mod snapshot',line)
   assert int(f[5],16)==sum(p[2]<<(5*i) for i,p in enumerate(params)),('range snapshot',line)
   fcws=[]
   for i,p in enumerate(params):
    fcws.append(voices[i].step((base>>(32*i))&0xffffffff,p[0],p[2],p[1]) if mask>>i&1 else 0)
    if mask>>i&1 and (p[0] or p[1]):summary['nonzero_controls']+=1
   computed[rid]=sum(v<<(32*i) for i,v in enumerate(fcws))
  elif tag=='F':
   rid=int(f[2]);mask,src,ch,gen,base,params=requests[rid]
   assert (int(f[3],16),int(f[4],16),int(f[5],16),int(f[6],16))==(mask,src,ch,gen),('tag',line)
   assert int(f[7],16)==computed[rid],('independent FCW',line,hex(computed[rid]));summary['math_results']+=1
  elif tag=='D':
   rid=int(f[2]);mask,src,ch,gen,base,params=requests[rid]
   expected=sum((((computed[rid]>>(32*i))&0xffffffff) if mask>>i&1 else ((base>>(32*i))&0xffffffff))<<(32*i) for i in range(4))
   assert int(f[3],16)==expected,('DDS control',line);summary['dds_ticks']+=1
  elif tag=='B':
   rid=int(f[2]);assert rid in computed,('uncomputed output',line);summary['bank_results']+=1
  elif tag=='X':summary['cancelled_frames']+=1
  elif tag=='END':summary['RTL_summary']=list(map(int,f[1:]))
  else:raise AssertionError('unexpected record '+line)
 assert 'RTL_summary' in summary and summary['nonzero_controls']>2000 and summary['bank_results']>1800
 (out/'functional_review.json').write_text(json.dumps({'scope':'actual bank/router/DDS/ADSR integration candidate only','formal_modified':False,'source_hashes':{str(p):sha(p) for p in sources if p!=lower},'allocator_original_sha':sha(allocator),'generated_allocator_sha':sha(lower),'runs':runs,'independent_model':summary},indent=2)+'\n',encoding='utf-8')
 # Mandatory compile-then-reject behavioral negatives. No production edit.
 for label,anchor,replacement in [
  ('broken_tag','math_identity_matches=fcw_id==pending_req_id','math_identity_matches=fcw_id==(pending_req_id^32\'d1)'),
  ('live_fcw','computed_fcw[32*k+:32]<=frozen_occupied[k] ? fcw_values[32*k+:32] : frozen_base[32*k+:32];','computed_fcw[32*k+:32]<=frozen_base[32*k+:32];')]:
  text=(CAND/'polyphonic_envelope_bank.sv').read_text(encoding='utf-8')
  if text.count(anchor)!=1:raise ValueError('negative anchor not unique: '+label)
  mutant=out/(label+'.sv');mutant.write_text(text.replace(anchor,replacement,1),encoding='utf-8',newline='\n')
  src=sources.copy();src[src.index(CAND/'polyphonic_envelope_bank.sv')]=mutant
  run(label+'_compile',[CAD/'bin/iverilog.exe','-g2012','-I',ROOT/'code/rtl/board','-s','tb_pitch_mod_bank_integration','-o',out/(label+'.vvp'),*src,CAND/'tb_pitch_mod_bank_integration.sv'])
  if label=='broken_tag':
   run(label,[CAD/'bin/vvp.exe',out/(label+'.vvp'),'+VELOCITY_ROM_PATH='+str(out/'velocity.mem')],marker='finite accepted sample produces both results',success=False)
  else:
   # RTL phase checks alone would agree with a bypassed DDS. Capture gets
   # compared separately by the accepted-control oracle below in later run.
   run(label,[CAD/'bin/vvp.exe',out/(label+'.vvp'),'+VELOCITY_ROM_PATH='+str(out/'velocity.mem')],marker='computed adjusted FCW is not bypassed before DDS',success=False)
 pcm_sources=sources+[ROOT/'code/rtl/board/polyphonic_pcm_commit.sv',ROOT/'code/rtl/mixer/pcm_mixer_4voice.sv',ROOT/'code/rtl/audio_out/pcm_result_hold.sv',ROOT/'code/rtl/audio_out/pcm_frame_buffer.sv',ROOT/'code/rtl/common/pcm_clip_counter.sv',ROOT/'code/rtl/common/system_status_counters.sv',ROOT/'code/rtl/board/voice_gain_q15_candidate.sv',ROOT/'code/rtl/board/polyphonic_audio_core.sv']
 run('PCM_compile',[CAD/'bin/iverilog.exe','-g2012','-I',ROOT/'code/rtl/board','-s','tb_pitch_mod_audio_commit','-o',out/'pcm.vvp',*pcm_sources,CAND/'tb_pitch_mod_audio_commit.sv'])
 text=run('PCM_run',[CAD/'bin/vvp.exe',out/'pcm.vvp','+VELOCITY_ROM_PATH='+str(out/'velocity.mem')],marker='PASS actual V1 CC64 PitchMod PCM',timeout=180)
 print(text[-500:])
 (out/'functional_review.json').write_text(json.dumps({'scope':'actual bank/router/DDS/ADSR and PCM integration candidate only','formal_modified':False,'golden_model_sha':sha(ROOT/'code/model/pitch_mod_model.py'),'TB_sha256':{str(p):sha(p) for p in [CAND/'tb_pitch_mod_bank_integration.sv',CAND/'tb_pitch_mod_audio_commit.sv']},'ROM_sha256':{p.name:sha(p) for p in out.glob('*.mem')},'include_header_sha':sha(ROOT/'code/rtl/board/sustain_controller_ports.svh'),'source_hashes':{str(p):sha(p) for p in pcm_sources if p!=lower},'allocator_original_sha':sha(allocator),'generated_allocator_sha':sha(lower),'runs':runs,'independent_model':summary},indent=2)+'\n',encoding='utf-8')

 print('PASS independent accepted control->bank FCW/DDS/ADSR',summary,flush=True)
 return 0
if __name__=='__main__':raise SystemExit(main())
