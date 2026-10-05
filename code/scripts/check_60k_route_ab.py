"""Independent report gate for 60K route0/route1 AB; no automatic application."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from check_pitch_mod_bank_combo import assess
from check_visual_serial_reset_report import check as reset_gate
from check_hdmi_link_report import ReportParser
from run_60k_route_ab import freeze_check
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def option_lines(folder,drop_route=False):
    result=[]
    for line in (folder/"impl/pnr/cmd.do").read_text(encoding="utf-8").splitlines():
        if drop_route and line.startswith("-route_option "):continue
        if line.startswith(("-d ","-cst ","-sdc ","-cfg ")):line=line.split(" ",1)[0]+" <private-path>"
        result.append(line)
    return result

def one_arm(folder,expected):
    bound=folder/"bounded_build_result.json"
    if not bound.exists():return {"complete":False,"status":"running or not started","gate_pass":False}
    b=json.loads(bound.read_text(encoding="utf-8"))
    if not b["complete"]:return {"complete":False,"status":"physical not completed; no STA verdict","gate_pass":False,"bounded":b}
    check=assess(folder);errors=check["errors"].copy()
    actual=option_lines(folder);route=[x for x in actual if x.startswith("-route_option ")]
    if route!=["-route_option "+str(expected)]:errors.append("actual route option differs from frozen arm")
    if "-timing" not in actual or "-correct_hold 1" not in actual:errors.append("timing driven or automatic Hold repair not retained")
    cst=folder/"constraints/audio_visual.cst";timing=folder/"impl/pnr/audio_visual_coexistence_top_tr_content.html"
    errors+=reset_gate(timing.read_text(encoding="utf-8").replace("u_visual/",""),cst.read_text(encoding="utf-8").replace("u_visual/",""))
    cfg=folder/"impl/pnr/device.cfg"
    parser=ReportParser();parser.feed(timing.read_text(encoding="utf-8"))
    active=sorted({r[2] for section,r in parser.rows if section=="SDC_Report" and len(r)==3 and r[1]=="Actived"})
    # Read both fixed FFs in actual detailed analysis, not just CST text.
    reset_loc={}
    for stage,loc in [(0,"R49C101[1][A]"),(1,"R49C101[1][B]")]:
        needle=f"u_visual/u_serial_reset/sync_chain_{stage}_s0/"
        found=[r for section,r in parser.rows if "Analysis" in section and any(needle in cell for cell in r) and loc in r]
        reset_loc[str(stage)]={"expected":loc,"actual_detailed_rows":found}
        if not found:errors.append("reset stage"+str(stage)+" actual fixed location absent")
    return {"complete":True,"gate_pass":not errors,"errors":errors,"bounded":b,"full_report":check,"effective_options":actual,"cfg_sha256":sha(cfg),"active_sdc":active,"reset_location_evidence":reset_loc}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("folder",type=Path);ap.add_argument("--partial",action="store_true");a=ap.parse_args();out=a.folder.resolve();out.relative_to(ROOT/"code/output")
    frozen=json.loads((out/"AB_freeze.json").read_text(encoding="utf-8"));freeze_check(out,frozen)
    for name,v in frozen["arms"].items():
        assert sha(out/name/"audio_visual_coexistence_top.gprj")==v["project_sha256"],"project file/source ordering changed"
    arms={name:one_arm(out/name,frozen["arms"][name]["route_option"]) for name in frozen["phase_order"]}
    A=arms["A_route0"];B=arms["B_route1"]
    result={"date":"2026-10-05","arms":arms,"both_complete":A["complete"] and B["complete"],"adopt":False,"download_allowed":False,"formal_modified":False,"AB_freeze_sha256":sha(out/"AB_freeze.json"),"same_RTL_ROM_constraints_verified":True,"latest_panel_T027_T028_not_included":True}
    if result["both_complete"]:
        ar=A["full_report"]["facts"];br=B["full_report"]["facts"];old=ar["exported_min_slack_ns"];new=br["exported_min_slack_ns"]
        delta={k:br["resources"][k]-ar["resources"][k] for k in ar["resources"]}
        base=Path(frozen["base_project"]).parent
        sameoptions=option_lines(out/"A_route0",True)==option_lines(out/"B_route1",True)==option_lines(base,True)
        # cfg must match between AB and old device image settings as well.
        cfgsame=A["cfg_sha256"]==B["cfg_sha256"]==sha(base/"impl/pnr/device.cfg")
        criteria={"both_independent_full_gates":A["gate_pass"] and B["gate_pass"],"actual_options_only_route_changed":sameoptions,"device_config_identical":cfgsame,"active_SDC_identical":A["active_sdc"]==B["active_sdc"],"resources_identical":all(v==0 for v in delta.values()),"setup_goal0_5":new["Setup"] is not None and new["Setup"]>=.5,"setup_gain0_1":new["Setup"] is not None and old["Setup"] is not None and new["Setup"]-old["Setup"]>=.1,"Hold_Recovery_Removal_not_worse":all(new[k] is not None and old[k] is not None and new[k]>=old[k] for k in ["Hold","Recovery","Removal"])}
        result.update(criteria=criteria,physical_screen_pass=all(criteria.values()),resource_delta=delta,slack_delta={k:None if new[k] is None or old[k] is None else round(new[k]-old[k],6) for k in old},standalone_board_validation_required=True)
        # Passing screen is still not permission to replace formal production.
        result["adopt"]=False
    else:result["reason"]="Incomplete arm cannot be replaced by historical STA or tool estimates"
    name="partial_report.json" if a.partial else "AB_assessment.json"
    (out/name).write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    brief={"both_complete":result["both_complete"],"arm_status":{n:{"complete":v["complete"],"gate_pass":v["gate_pass"],"errors":v.get("errors",[]),"slacks":v.get("full_report",{}).get("facts",{}).get("exported_min_slack_ns")} for n,v in arms.items()},"criteria":result.get("criteria"),"slack_delta":result.get("slack_delta"),"physical_screen_pass":result.get("physical_screen_pass"),"adopted":False,"download_allowed":False}
    print(json.dumps(brief,indent=2));return 0
if __name__=="__main__":main()
