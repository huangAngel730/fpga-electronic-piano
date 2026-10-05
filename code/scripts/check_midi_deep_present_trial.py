"""Fail-closed once-only deep parser physical screen; never interpret timeout PASS."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from check_pitch_mod_bank_combo import assess
from check_midi_pending_mask_trial import options
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument("folder",type=Path);a=ap.parse_args();out=a.folder.resolve();out.relative_to(ROOT/"code/output")
    bfile=out/"bounded_build_result.json"
    if not bfile.is_file():print("RUNNING: no terminal physical result");return 2
    bound=json.loads(bfile.read_text(encoding="utf-8"))
    if not bound["complete"]:
        result={"complete":False,"adopt":False,"reason":"bounded once-only physical run incomplete; retain baseline","bounded":bound,"newSTA":None}
    else:
        fair=json.loads((out/"fairness.json").read_text(encoding="utf-8"));base=Path(fair["baseline_project"]).parent
        for key in ["all_baseline_source_sha","unchanged_headers","ROM_sha","new_sources"]:
            for p,h in fair[key].items():assert sha(Path(p))==h,p
        for key in ["functional_result","pcm_result"]:
            assert sha(Path(fair[key]))==fair[key+"_sha"] and json.loads(Path(fair[key]).read_text(encoding="utf-8"))["passed"]
        assert sha(base/"impl/pnr/audio_visual_coexistence_top_tr_content.html")==fair["baseline_STA_sha"]
        old=list(ET.parse(fair["baseline_project"]).getroot().find("FileList"));new=list(ET.parse(fair["candidate_project"]).getroot().find("FileList"))
        assert len(old)==47 and len(new)==48 and sum(x.attrib!=y.attrib for x,y in zip(old,new))==1
        assert options(base)==options(out),"changed effective constraints/PNR options"
        before=assess(base);after=assess(out);bs=before["facts"]["exported_min_slack_ns"];cs=after["facts"]["exported_min_slack_ns"]
        delta={k:after["facts"]["resources"][k]-before["facts"]["resources"][k] for k in before["facts"]["resources"]}
        gate=out.parent/"repository_gate_exit.txt"
        criteria={"functional_and_realPCM":True,"baseline_timing_pass":before["timing_pass"],"candidate_all_domain_timing_pass":after["timing_pass"],"setup_target0_5":cs["Setup"] is not None and cs["Setup"]>=.5,"setup_improvement0_1":cs["Setup"] is not None and cs["Setup"]-bs["Setup"]>=.1,"logic_budget256":delta["Logic"]<=256,"register_budget512":delta["Register"]<=512,"DSP_BSRAM_no_increase":all(delta[k]<=0 for k in ["DSP","BSRAM"]),"hold_recovery_removal_not_worse":all(cs[k] is not None and cs[k]>=bs[k] for k in ["Hold","Recovery","Removal"]),"repository_gate":gate.exists() and gate.read_text().strip()=="0"}
        result={"complete":True,"adopt_screen_pass":all(criteria.values()),"criteria":criteria,"baseline":before,"candidate":after,"resource_delta":delta,"bounded":bound,"production_applied":False,"latest_panel_T027_T028_included":False,"board_release":False}
    (out/"physical_assessment.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ["baseline","candidate"]},indent=2));return 0
if __name__=="__main__":main()
