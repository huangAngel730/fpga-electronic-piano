"""User-authorized joint parser/audio pipeline candidate; no production writes."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys,importlib.util,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
SCOPE=ROOT/'code/tb/board/system_control_pipeline_candidate'
CAD=Path('D:/Gowin/oss-cad-suite')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main():
 cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--output',type=Path);cli.add_argument('--check-capture',type=Path);a=cli.parse_args()
 if a.check_capture:
  checker=load('existing_joint_accepted_reference',ROOT/'code/tb/board/m3_midi_pcm_acceptance/scoreboard.py');checker.SCENARIOS=checker.SCENARIOS|{'reset_verify'}
  try:
   counts=checker.check_capture(a.check_capture,ROOT);print(json.dumps(counts,ensure_ascii=False,indent=2));return 0
  except (OSError,AssertionError,ValueError,IndexError,KeyError) as error:
   print('FAIL joint capture:',error);return 1
 if a.output is None:cli.error('--output is required unless --check-capture')
 out=a.output.resolve();out.relative_to(ROOT/'code/output');out.mkdir(parents=True,exist_ok=False)
 env=os.environ.copy();env['PATH']=str(CAD/'lib')+';'+str(CAD/'bin')+';'+env['PATH'];env['PYTHONDONTWRITEBYTECODE']='1'
 manifest=json.loads((SCOPE/'manifest.json').read_text(encoding='utf-8'));runs={};record={'passed':False,'scope':'real UART32FIFO real bank+FCW/DDS+PCM joint model checks; isolated, not officiallatest allfeatures','candidate_manifest':manifest}
 for name,identity in manifest['candidate_sources'].items():assert sha(SCOPE/name)==identity['sha256']
 # Exact proven component results are reused only after verifying measured source and logs.
 parser_evidence=ROOT/'code/output/midi_prepared_candidate_20261004/functional_entry_verified/functional_review.json'
 parser=json.loads(parser_evidence.read_text(encoding='utf-8'));assert parser['passed'] and parser['manifest']['candidate_SHA']==sha(SCOPE/'midi_event_parser.sv')
 for name,data in parser['runs'].items():
  if data.get('log_SHA'):assert sha(parser_evidence.parent/(name+'.log'))==data['log_SHA']
 audio_evidence=ROOT/'code/output/audio_control_boundary_20261004/functional1/functional_complete.json';audio=json.loads(audio_evidence.read_text(encoding='utf-8'));assert audio['passed']
 for name in ['polyphonic_event_router.sv','polyphonic_envelope_bank.sv']:
  original=ROOT/'code/tb/board/audio_control_boundary_candidate'/name;assert original.read_bytes()==(SCOPE/name).read_bytes()
 for name,data in audio['runs'].items():assert sha(audio_evidence.parent/(name+'.log'))==data['log_sha']
 record['component_evidence_reused']={'parser_result_sha':sha(parser_evidence),'audio_result_sha':sha(audio_evidence),'component_sources_and_logs_checked':True,'not_new_reexecution_claim':True}
 base=ROOT/'code/output/M3_parser_de68038_review_20261003/physical_parser_only'
 provenance=json.loads((base/'input_manifest.json').read_text(encoding='utf-8'));physical={Path(e['actual_source']).name:Path(e['actual_source']) for e in provenance['source_builds']}
 for e in provenance['source_builds']:assert sha(Path(e['actual_source']))==e['actual_sha']
 for p,h in provenance['roms'].items():assert sha(Path(p))==h
 def run(name,cmd,good=True,marker=None,timeout=240):
  log=out/(name+'.log')
  with log.open('wb')as stream:
   try:q=subprocess.run(list(map(str,cmd)),cwd=out,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
   except subprocess.TimeoutExpired:
    runs[name]={'timeout':True,'expected_success':good,'timeout_seconds':timeout,'log_sha':sha(log)}
    raise
  text=log.read_text(encoding='utf-8',errors='replace');runs[name]={'exit':q.returncode,'expected_success':good,'log_sha':sha(log),'command':list(map(str,cmd))};print(name,'EXIT',q.returncode,text[-900:],flush=True)
  if (q.returncode==0)!=good or marker and marker not in text:raise RuntimeError('unexpected '+name)
  return text
 try:
  original=physical['voice_allocator_4.sv'];lower=out/'allocator.v';ys=out/'lower.ys';ys.write_text('read_slang --top voice_allocator_4 '+original.as_posix()+'\nproc\nopt\ntechmap\nopt\nwrite_verilog -noattr '+lower.as_posix()+'\n',encoding='ascii');run('lower_allocator',[CAD/'bin/yosys.exe','-Q','-T','-s',ys],timeout=60)
  # Historical unadjusted center bank gets its own unchanged router.
  reference=out/'bank_reference.sv';reference.write_bytes((ROOT/'code/output/audio_control_boundary_20261004/functional1/bank_reference.sv').read_bytes())
  names=['audio_defs_pkg.sv','uart_rx.sv','performance_event_fifo.sv','midi_input.sv','note_pitch.sv','sustain_control_contract_pkg.sv','sustain_controller.sv','performance_control_snapshot.sv','pitch_mod_fcw_pipeline.sv','pitch_mod_snapshot_pipeline.sv','dds_oscillator.sv','piano_dds_oscillator.sv','adsr_piano_envelope.sv','polyphonic_pcm_commit.sv','pcm_mixer_4voice.sv','pcm_result_hold.sv','pcm_frame_buffer.sv','pcm_clip_counter.sv','system_status_counters.sv','voice_gain_q15_candidate.sv','polyphonic_audio_core.sv']
  sources=[physical['audio_defs_pkg.sv'],lower]+[physical[n] for n in names if n!='audio_defs_pkg.sv']+[SCOPE/'midi_event_parser.sv',SCOPE/'polyphonic_event_router.sv',SCOPE/'polyphonic_envelope_bank.sv',SCOPE/'polyphonic_event_router_reference.sv',reference]
  roms={'wave.mem':ROOT/'code/model/generated/wavetables/piano_band_4x256_8191.mem','velocity.mem':ROOT/'code/model/generated/wavetables/velocity_gain_rom.mem'}
  for name,p in roms.items():(out/name).write_bytes(p.read_bytes())
  small=out/'model/generated/pitch_mod';small.mkdir(parents=True)
  for name in ['oct_ratio_q16.mem','sub_ratio_q16.mem','lfo_sine_q15.mem']:(small/name).write_bytes((ROOT/'code/model/generated/pitch_mod'/name).read_bytes())
  # Icarus cannot resolve the frozen long absolute include. The read-only
  # original header SHA is known; only transport path changes in a copy.
  sustain_original=physical['sustain_controller.sv']
  import re
  code=sustain_original.read_text(encoding='utf-8')
  header_path=re.search(r'`include "([^"]+)"',code).group(1)
  header=Path(header_path)
  assert header.is_file() and sha(header)=='8c51459cd47a7e21609cc02780a93af7d6be0fd5bf2d2278edda92e8a7ef486d'
  (out/'sustain_controller_ports.svh').write_bytes(header.read_bytes())
  short_sustain=out/'sustain_controller.sv'
  short_sustain.write_text(code.replace(header_path,'sustain_controller_ports.svh',1),encoding='utf-8',newline='\n')
  sources[sources.index(sustain_original)]=short_sustain
  record['simulator_include_binding_only']={'original_SHA':sha(sustain_original),'copied_SHA':sha(short_sustain),'header_SHA':sha(header),'header_code_unchanged':True}
  tb=SCOPE/'tb_system_control_pipeline.sv';top='tb_system_control_pipeline'
  run('joint_compile',[CAD/'bin/iverilog.exe','-g2012','-I',out,'-I',ROOT/'code/rtl/board','-s',top,'-o',out/'joint.vvp',*sources,tb],timeout=40)
  run('joint_run',[CAD/'bin/vvp.exe',out/'joint.vvp','+VELOCITY_ROM_PATH='+str(out/'velocity.mem')],marker='PASS F real UART FIFO allocator V1 CC64 PitchMod PCM',timeout=900)
  print('CAPTURE_FILES',list(out.glob('*.capture')),flush=True)
  positive_capture=out/'positive_completed.capture';positive_capture.write_bytes((out/'midi_pcm.capture').read_bytes())
  checker=load('existing_accepted_joint_reference',ROOT/'code/tb/board/m3_midi_pcm_acceptance/scoreboard.py');checker.SCENARIOS=checker.SCENARIOS|{'reset_verify'};capture=positive_capture
  if not capture.is_file():capture=next(out.glob('*.capture'))
  counts=checker.check_capture(capture,ROOT);print('MODEL COUNTS',json.dumps(counts),flush=True);record['independent_joint_reference']=counts;record['joint_capture_sha']=sha(capture)
  # Broken result identity rejection proves computation cannot be discarded/corrupted invisibly.
  text=(SCOPE/'polyphonic_envelope_bank.sv').read_text(encoding='utf-8');needle='result_req_id<=pending_req_id;';assert text.count(needle)==1
  bad=out/'wrong_result_tag.sv';bad.write_text(text.replace(needle,"result_req_id<=pending_req_id^32'd1;",1),encoding='utf-8',newline='\n');bad_sources=sources.copy();bad_sources[bad_sources.index(SCOPE/'polyphonic_envelope_bank.sv')]=bad
  # Negative-only observer never drives DUT. A stale offered result must
  # be rejected explicitly, not just eventually by an input-drain timeout.
  negative_text=tb.read_text(encoding='utf-8')
  observer='''    always @(posedge clk)begin
        if(rst_n && !frame_tick && dut.bank_valid && dut.bank_id!=dut.sample_req_id)
            $fatal(1,"F wrong result tag offered: expected=%0d actual=%0d",dut.sample_req_id,dut.bank_id);
    end
'''
  negative_tb=out/'tb_negative_tag_observer.sv'
  assert negative_text.count('endmodule')==1
  negative_tb.write_text(negative_text.replace('endmodule',observer+'endmodule'),encoding='utf-8',newline='\n')
  record['positive_compiled_inputs']={str(p):sha(p) for p in sources}
  record['negative_only_observer_tb_sha']=sha(negative_tb)
  run('wrong_guard_compile',[CAD/'bin/iverilog.exe','-g2012','-I',out,'-I',ROOT/'code/rtl/board','-s',top,'-o',out/'bad.vvp',*bad_sources,negative_tb],timeout=40)
  # Original joint scenario must reject by normal valid-result/underrun behavior.
  run('wrong_guard_run',[CAD/'bin/vvp.exe',out/'bad.vvp','+VELOCITY_ROM_PATH='+str(out/'velocity.mem')],good=False,marker='F wrong result tag offered',timeout=60)
  record.update(passed=True,joint_capture_sha=sha(positive_capture),compiled_inputs={str(p):sha(p) for p in sources},normal_logic_frames_only=True,physical_build_not_executed=True)
  return 0
 finally:
  record['runs']=runs;record['source_candidate_sha']={n:sha(SCOPE/n) for n in manifest['candidate_sources']};(out/'joint_functional_review.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':raise SystemExit(main())