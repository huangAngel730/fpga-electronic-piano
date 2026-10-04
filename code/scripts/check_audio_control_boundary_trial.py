"""Compare one two-file audio boundary trial without altering official sources."""
from pathlib import Path
import argparse,json,hashlib,xml.etree.ElementTree as ET
from check_pitch_mod_bank_combo import assess
from check_midi_pending_mask_trial import options
ROOT=Path(__file__).resolve().parents[2]
SCOPE=ROOT/'code/tb/board/audio_control_boundary_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 cli=argparse.ArgumentParser();cli.add_argument('output',type=Path);a=cli.parse_args();out=a.output.resolve();out.relative_to(ROOT/'code/output');stage=out/'physical_valid1';bound=stage/'bounded_build_result.json'
 if not bound.is_file():print('RUNNING: no final STA verdict');return 2
 status=json.loads(bound.read_text(encoding='utf-8'))
 if not status['complete']:
  result={'complete':False,'adopt':False,'reason':'30min physical limit; preserve baseline, no timing PASS/FAIL verdict','bounded_status':status,'actual_PnR_trials':1}
 else:
  fair=json.loads((stage/'fairness.json').read_text(encoding='utf-8'));base=Path(fair['baseline_project']).parent;functional=json.loads((out/'functional1/functional_complete.json').read_text(encoding='utf-8'));m=json.loads((SCOPE/'manifest.json').read_text(encoding='utf-8'))
  assert sha(out/'functional1/functional_complete.json')==fair['functional_sha']
  for path,h in {**fair['unchanged_sources'],**fair['roms']}.items():assert sha(Path(path))==h,'input changed '+path
  for old,v in fair['changed_sources'].items():assert sha(Path(old))==v['old_sha'] and sha(Path(v['new']))==v['new_sha']
  assert sha(base/'impl/pnr/audio_visual_coexistence_top_tr_content.html')==fair['baseline_sta_sha']
  assert options(base)==options(stage),'PnR options differ'
  old=list(ET.parse(fair['baseline_project']).getroot().find('FileList'));new=list(ET.parse(fair['candidate_project']).getroot().find('FileList'));assert len(old)==len(new)==47 and sum(x.attrib!=y.attrib for x,y in zip(old,new))==2
  before=assess(base);after=assess(stage);bs=before['facts']['exported_min_slack_ns'];cs=after['facts']['exported_min_slack_ns'];delta={k:after['facts']['resources'][k]-before['facts']['resources'][k] for k in before['facts']['resources']};goal=m['adoption']
  gate=out/'repository_gate_exit.txt'
  criteria={'functional_complete':functional['passed'],'repository_gate_pass':gate.is_file() and gate.read_text().strip()=='0','actual_all_domain_timing_CDC_pins':after['timing_pass'],'setup_target':cs['Setup'] is not None and cs['Setup']>=goal['setup_target_ns'],'setup_improvement':cs['Setup'] is not None and cs['Setup']-bs['Setup']>=goal['minimum_global_setup_improvement_ns'],'logic_cost':delta['Logic']<=goal['max_additional_logic'],'register_cost':delta['Register']<=goal['max_additional_register'],'DSP_BSRAM_not_increased':all(delta[k]<=0 for k in ['DSP','BSRAM']),'hold_recovery_removal_not_worse':all(cs[k] is not None and cs[k]>=bs[k] for k in ['Hold','Recovery','Removal']),'old_private_base_preserved':all(sha(ROOT/'code/tb/board/pitch_mod_bank_integration_candidate'/n)==h for n,h in m['original_sources'].items())}
  result={'complete':True,'adopt':all(criteria.values()),'criteria':criteria,'baseline':before,'candidate':after,'resource_delta':delta,'slack_delta':{k:None if cs[k] is None else round(cs[k]-bs[k],6) for k in bs},'actual_PnR_trials':1,'early_tool_start_failure_not_PnR':1,'elapsed_seconds':status['elapsed_seconds'],'declared_extra_internal_cycle':1,'retirement_deferred_under_result_backpressure':True,'applied':False,'programmed':False}
 (out/'physical_assessment.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in result.items() if k not in ['baseline','candidate']},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())