"""One joint pipeline trial assessment; report missing/timeout never means pass."""
from pathlib import Path
import argparse,json,hashlib,xml.etree.ElementTree as ET
from check_pitch_mod_bank_combo import assess
from check_midi_pending_mask_trial import options
ROOT=Path(__file__).resolve().parents[2]
SCOPE=ROOT/'code/tb/board/system_control_pipeline_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 cli=argparse.ArgumentParser();cli.add_argument('output',type=Path);a=cli.parse_args();out=a.output.resolve();out.relative_to(ROOT/'code/output');stage=out/'physical1'
 if not (stage/'bounded_build_result.json').is_file():print('RUNNING/not built: no final timing verdict');return 2
 bound=json.loads((stage/'bounded_build_result.json').read_text(encoding='utf-8'))
 if not bound['complete']:
  result={'complete':False,'adopt':False,'reason':'single1800s physical bound reached; retain baseline, no new STA verdict','effective_PnR_runs':1,'bounded':bound}
 else:
  fair=json.loads((stage/'fairness.json').read_text(encoding='utf-8'));base=Path(fair['baseline_project']).parent;m=json.loads((SCOPE/'manifest.json').read_text(encoding='utf-8'));f=Path(fair['joint_functional_result'])
  assert sha(f)==fair['joint_functional_sha'] and json.loads(f.read_text(encoding='utf-8'))['passed']
  assert sha(SCOPE/'manifest.json')==fair['candidate_manifest_sha']
  for name,e in m['candidate_sources'].items():assert sha(SCOPE/name)==e['sha256']
  for p,h in {**fair['unchanged_sources'],**fair['unchanged_ROMs'],**fair['implicit_headers']}.items():assert sha(Path(p))==h,p
  for p,v in fair['changed_sources'].items():assert sha(Path(p))==v['old_sha'] and sha(Path(v['new']))==v['new_sha']
  assert sha(base/'impl/pnr/audio_visual_coexistence_top_tr_content.html')==fair['baseline_STA_SHA']
  assert options(base)==options(stage),'changed effective PnR options'
  old=list(ET.parse(fair['baseline_project']).getroot().find('FileList'));new=list(ET.parse(fair['trial_project']).getroot().find('FileList'));assert len(old)==len(new)==47 and sum(x.attrib!=y.attrib for x,y in zip(old,new))==3
  before=assess(base);after=assess(stage);b=before['facts']['exported_min_slack_ns'];c=after['facts']['exported_min_slack_ns'];delta={k:after['facts']['resources'][k]-before['facts']['resources'][k] for k in before['facts']['resources']}
  gate=out/'repository_gate_exit.txt'
  criteria={'real_joint_functional_pass':json.loads(f.read_text())['passed'],'final_repository_gate_pass':gate.is_file() and gate.read_text().strip()=='0','all_domains_CDC_pins_PASS':after['timing_pass'],'system_setup_at_least0_5':c['Setup'] is not None and c['Setup']>=m['minimum_global_setup_ns'],'system_setup_improvement_at_least0_1':c['Setup'] is not None and c['Setup']-b['Setup']>=m['minimum_setup_improvement_ns'],'logic_cost':delta['Logic']<=m['max_logic_delta'],'register_cost':delta['Register']<=m['max_register_delta'],'DSP_BSRAM_no_increase':all(delta[k]<=0 for k in ['DSP','BSRAM']),'Hold_Recovery_Removal_not_worse':all(c[k] is not None and c[k]>=b[k] for k in ['Hold','Recovery','Removal'])}
  result={'complete':True,'adopt_screen_pass':all(criteria.values()),'criteria':criteria,'baseline':before,'candidate':after,'resource_delta':delta,'slack_delta':{k:None if c[k] is None else round(c[k]-b[k],6) for k in b},'effective_PnR_runs':1,'elapsed_seconds':bound['elapsed_seconds'],'official_sources_modified':False,'board_programmed':False,'scope':'frozen V0171 features only; not latestT027/panel/effects release'}
 (out/'physical_assessment.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in result.items() if k not in ['baseline','candidate']},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())