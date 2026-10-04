"""Assess the single prepared-selector trial; timeout never implies timing FAIL."""
from pathlib import Path
import argparse,hashlib,json,xml.etree.ElementTree as ET
from check_pitch_mod_bank_combo import assess
from check_midi_pending_mask_trial import options
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    cli=argparse.ArgumentParser();cli.add_argument('output',type=Path);args=cli.parse_args();out=args.output.resolve();out.relative_to(ROOT/'code/output')
    stage=out/'physical1';bounded=stage/'bounded_build_result.json'
    if not bounded.is_file():print('RUNNING: no completed bounded build result, no timing verdict');return 2
    status=json.loads(bounded.read_text())
    if status.get('timeout'):
        result={'physical_complete':False,'adopt':False,'reason':'30min timeout; retain de68038/V0171; no timing verdict','status':status}
    else:
        fair=json.loads((stage/'fairness.json').read_text());base=Path(fair['baseline_project']).parent
        functional=json.loads((out/'functional1/functional_review.json').read_text());m=functional['manifest']
        for p,h in {**fair['unchanged_sources'],**fair['unchanged_ROMs']}.items():
            if sha(Path(p))!=h:raise ValueError('frozen input changed '+p)
        if sha(base/'impl/pnr/audio_visual_coexistence_top_tr_content.html')!=fair['baseline_STA_SHA']:raise ValueError('baseline report changed')
        if sha(stage/'midi_event_parser.sv')!=m['candidate_SHA']:raise ValueError('candidate changed')
        old=list(ET.parse(fair['baseline_project']).getroot().find('FileList'));new=list(ET.parse(fair['trial_project']).getroot().find('FileList'))
        if len(old)!=47 or len(new)!=47 or sum(a.attrib!=b.attrib for a,b in zip(old,new))!=1:raise ValueError('not exact one-file trial')
        if options(base)!=options(stage):raise ValueError('physical tool settings changed')
        before=assess(base);after=assess(stage)
        b=before['facts']['exported_min_slack_ns'];a=after['facts']['exported_min_slack_ns']
        delta={k:after['facts']['resources'][k]-before['facts']['resources'][k] for k in before['facts']['resources']}
        gate=out/'repository_gate_exit.txt'
        criteria={'repository_gate_pass':gate.is_file() and gate.read_text().strip()=='0','functional_pass':functional['passed'],'all_timing_CDC_pin_gates':after['timing_pass'],'setup_target':a['Setup'] is not None and a['Setup']>=m['goal_setup_ns'],'setup_improvement':a['Setup'] is not None and a['Setup']-b['Setup']>=m['minimum_setup_improvement_ns'],'Logic_cost':delta['Logic']<=m['max_additional_logic'],'register_cost':delta['Register']<=m['max_additional_registers'],'DSP_BSRAM_same_or_less':all(delta[k]<=0 for k in ['DSP','BSRAM']),'hold_recovery_removal_not_worse':all(a[k] is not None and a[k]>=b[k] for k in ['Hold','Recovery','Removal']),'formal_unchanged':sha(ROOT/'code/rtl/input/midi_input/midi_event_parser.sv')==m['frozen_parser_SHA']}
        result={'physical_complete':True,'adopt':all(criteria.values()),'criteria':criteria,'baseline':before,'candidate':after,'resources_delta':delta,'slack_delta':{k:None if a[k] is None else round(a[k]-b[k],6) for k in b},'actual_trials':1,'programmed':False,'production_changed':False,'new_register_state_bits':40}
    (out/'physical_assessment.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k not in ['baseline','candidate']},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())