"""Compare one physically implemented parser candidate with frozen V0171.

This only reads hashes, reports and exact source identities. It does not edit
reports, synthesize designs, relax constraints or apply the production patch.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from check_pitch_mod_bank_combo import assess

ROOT=Path(__file__).resolve().parents[2]
SCOPE=ROOT/'code/tb/common/midi_pending_mask_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def options(folder):
    return [line.split(' ',1)[0]+' <path>' if line.startswith(('-d ','-cst ','-sdc ','-cfg ')) else line
            for line in (folder/'impl/pnr/cmd.do').read_text(encoding='utf-8').splitlines()]

def review(output):
    output=output.resolve()
    trial=output/'physical1'
    fair=json.loads((trial/'fairness.json').read_text(encoding='utf-8'))
    baseline=Path(fair['baseline_project']).parent
    manifest=json.loads((SCOPE/'manifest.json').read_text(encoding='utf-8'))
    functional=json.loads((output/'functional1/functional_review.json').read_text(encoding='utf-8'))
    if functional['manifest']['candidate_SHA']!=manifest['candidate_SHA']:
        raise ValueError('different functional candidate')
    if sha(SCOPE/'midi_event_parser.sv')!=manifest['candidate_SHA']:
        raise ValueError('candidate changed after verification')
    if sha(ROOT/'code/rtl/input/midi_input/midi_event_parser.sv')!=manifest['frozen_parser_SHA']:
        raise ValueError('production parser changed; do not mix baselines')
    for name,h in fair['unchanged_sources'].items():
        if sha(Path(name))!=h:raise ValueError('baseline input changed: '+name)
    for name,h in fair['unchanged_ROMs'].items():
        if sha(Path(name))!=h:raise ValueError('ROM changed: '+name)
    old=list(ET.parse(baseline/'audio_visual_coexistence_top.gprj').getroot().find('FileList'))
    new=list(ET.parse(trial/'audio_visual_coexistence_top.gprj').getroot().find('FileList'))
    if len(old)!=47 or len(new)!=47:raise ValueError('unexpected project file count')
    changed=[(a.attrib,b.attrib) for a,b in zip(old,new) if a.attrib!=b.attrib]
    if len(changed)!=1 or any(Path(x['path']).name!='midi_event_parser.sv' for x in changed[0]):
        raise ValueError('not a parser-only physical trial')
    if options(baseline)!=options(trial):raise ValueError('physical settings differ')
    if sha(baseline/'impl/pnr/audio_visual_coexistence_top_tr_content.html')!=fair['baseline_STA_SHA']:
        raise ValueError('baseline report changed')
    if int((trial/'build_exit.txt').read_text())!=0:raise ValueError('physical tool failed')
    before=assess(baseline);after=assess(trial)
    if not before['timing_pass']:raise ValueError('baseline is not the accepted marginal gate')
    resources={k:after['facts']['resources'][k]-before['facts']['resources'][k]
               for k in before['facts']['resources']}
    old_slack=before['facts']['exported_min_slack_ns']
    new_slack=after['facts']['exported_min_slack_ns']
    criteria={
        'functional_and_negative_expected_outcomes':all((r['exit']==0)==r['expected_success'] for r in functional['runs'].values()),
        'all_clock_CDC_pin_timing_gates_pass':after['timing_pass'],
        'Setup_at_least0_500ns':new_slack['Setup'] is not None and new_slack['Setup']>=manifest['predeclared_physical_goal_ns'],
        'additionalLogic_at_most128':resources['Logic']<=128,
        'no_register_DSP_BSRAM_increase':all(resources[k]<=0 for k in ('Register','DSP','BSRAM')),
        'Hold_Recovery_Removal_not_worse':all(new_slack[k] is not None and new_slack[k]>=old_slack[k]
                                              for k in ('Hold','Recovery','Removal')),
        'same_frozen_inputs_and_settings':True,
        'no_production_source_write':True,
    }
    decision=all(criteria.values())
    artifact={str(p.relative_to(trial)):sha(p) for p in [trial/'build.log',trial/'impl/pnr/cmd.do',
       trial/'impl/pnr/audio_visual_coexistence_top_tr_content.html',trial/'impl/pnr/audio_visual_coexistence_top.rpt.txt',
       trial/'impl/pnr/audio_visual_coexistence_top.pin.html',trial/'audio_visual_coexistence_top.gprj']}
    fs=trial/'impl/pnr/audio_visual_coexistence_top.fs'
    if fs.exists():artifact['research_only_fs_SHA']=sha(fs)
    return {'date':'2026-10-03','scope':'one frozen V0171 parser-only experiment, not latest production or board release',
      'functional':functional,'baseline':before,'candidate':after,'resources_delta':resources,
      'slack_delta_ns':{k:round(new_slack[k]-old_slack[k],6) for k in old_slack},
      'criteria':criteria,'recommend_adoption':decision,
      'decision':'candidate meets screen; user-forwarded M3 formal landing remains required' if decision else 'reject candidate; retain de68038 and V0171 baseline',
      'actual_PnR_trials':1,'no_seed_search':True,'formal_parser_modified':False,'programmed':False,
      'artifact_SHA':artifact,'fairness_SHA':sha(trial/'fairness.json'),
      'functional_result_before_trial_SHA':fair['functional_result_SHA'],
      'final_functional_result_SHA':sha(output/'functional1/functional_review.json'),
      'functional_guard_refinement':'Additional empty/truncated count and rotation mutant tested after physical staging; candidate HDL unchanged',
      'mapping_register_changes_not_RTL_added_pipeline':True}

def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('output',type=Path)
    args=cli.parse_args();result=review(args.output)
    (args.output/'physical_assessment.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'decision':result['decision'],'criteria':result['criteria'],
      'resource_delta':result['resources_delta'],'slack_delta_ns':result['slack_delta_ns'],
      'actual_candidate_slack':result['candidate']['facts']['exported_min_slack_ns']},indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
