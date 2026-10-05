"""Self-contained 60K route0/route1 AB freeze. No production writes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/"code/output/M3_parser_de68038_review_20261003/physical_parser_only"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical(text,folder):return text.replace(folder.as_posix(),"<FROZEN_ARM>").replace(str(folder),"<FROZEN_ARM>")
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",type=Path,required=True);a=ap.parse_args();out=a.output.resolve();out.relative_to(ROOT/"code/output");assert not out.exists(),"new once-only AB directory required"
    original=BASE/"audio_visual_coexistence_top.gprj";m=json.loads((BASE/"input_manifest.json").read_text(encoding="utf-8"));original_tree=ET.parse(original);nodes=list(original_tree.getroot().find("FileList"));assert len(nodes)==47
    for e in m["source_builds"]:assert sha(Path(e["actual_source"]))==e["actual_sha"],e["actual_source"]
    for name,h in m["roms"].items():assert sha(Path(name))==h,name
    headers={}
    for n in nodes:
        p=Path(n.attrib["path"])
        if p.suffix in (".sv",".v"):
            for inc in re.findall(r'`include\s+"([^"]+)"',p.read_text(encoding="utf-8")):
                hp=Path(inc);hp=hp if hp.is_absolute() else p.parent/hp;assert hp.is_file();headers[hp.resolve()]=sha(hp)
    assert len(headers)==2
    out.mkdir(parents=True)
    revision=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,capture_output=True,check=True).stdout.decode().strip()
    original_payloads={str(Path(n.attrib["path"])):sha(Path(n.attrib["path"])) for n in nodes}
    original_payloads.update({str(Path(k)):v for k,v in m["roms"].items()});original_payloads.update({str(k):v for k,v in headers.items()})
    assert len(original_payloads)==56
    # All three sources have actual recently passed behavior evidence; no new
    # rejected parser/audio candidate is used in this physical-only AB.
    pcm=ROOT/"code/output/deep_present_integration_20261005/pcm1/joint_functional_review.json"
    evidence=json.loads(pcm.read_text(encoding="utf-8"));assert evidence["passed"]
    # Recent PCM run used new parser, so only reuse its SAME frozen audio inputs,
    # not claim baseline-parser UART rerun. Exact baseline parser source was
    # already independently decoded/matched in that module test.
    audio_used={str(Path(k)):v for k,v in evidence["compiled_inputs"].items()}
    reused_audio={k:h for k,h in original_payloads.items() if k in audio_used}
    for k,h in reused_audio.items():assert audio_used[k]==h
    arms={};canonical_inputs=[]
    for arm,option in [("A_route0",0),("B_route1",1)]:
        folder=out/arm;folder.mkdir();mapping={}
        for n in nodes:
            old=Path(n.attrib["path"]).resolve();kind="constraints" if old.suffix in (".cst",".sdc") else "sources";dest=folder/kind/old.name;assert old not in mapping and dest not in mapping.values();mapping[old]=dest
        for name in m["roms"]:
            old=Path(name).resolve();mapping[old]=folder/"rom"/old.name
        for old in headers:mapping[old]=folder/"headers"/old.name
        replacements={}
        for old,new in mapping.items():
            replacements[old.as_posix()]=new.as_posix();replacements[str(old)]=new.as_posix()
        normalized={};inputs=[]
        for old,dest in mapping.items():
            dest.parent.mkdir(parents=True,exist_ok=True);raw=old.read_bytes();changed=False
            if old.suffix in (".sv",".v",".svh",".cst",".sdc"):
                text=raw.decode("utf-8")
                for before,after in sorted(replacements.items(),key=lambda x:len(x[0]),reverse=True):text=text.replace(before,after)
                payload=text.encode("utf-8");changed=payload!=raw
                # Prove every changed byte is an approved exact path rebinding.
                inverse=text
                for oldq,newq in mapping.items():
                    if oldq.as_posix() in raw.decode("utf-8"):inverse=inverse.replace(newq.as_posix(),oldq.as_posix())
                    elif str(oldq) in raw.decode("utf-8"):inverse=inverse.replace(newq.as_posix(),str(oldq))
                assert inverse.encode("utf-8")==raw,"non-path source change "+str(old)
                normalized[str(dest.relative_to(folder))]=hashlib.sha256(canonical(text,folder).encode()).hexdigest()
                for inc in re.findall(r'`include\s+"([^"]+)"',text):assert Path(inc).is_relative_to(folder),"external include"
            else:payload=raw;normalized[str(dest.relative_to(folder))]=hashlib.sha256(payload).hexdigest()
            dest.write_bytes(payload)
            inputs.append({"original":str(old),"original_sha256":sha(old),"actual_source":str(dest),"actual_sha":sha(dest),"size_bytes":len(payload),"only_path_rebound":changed})
        tree=ET.parse(original)
        for n in tree.getroot().find("FileList"):n.attrib["path"]=mapping[Path(n.attrib["path"]).resolve()].as_posix()
        project=folder/original.name;tree.write(project,encoding="utf-8",xml_declaration=True)
        # USER has only UI/old flow state, no implementation options. Preserve
        # UI metadata but reset flow/result state for a fresh source run.
        user=ET.parse(BASE/(original.name+".user"));flow=user.getroot().find("FlowState")
        for n in flow:n.attrib["State"]="0"
        old_results=user.getroot().find("ResultFileList");old_results.clear();user.write(folder/(original.name+".user"),encoding="utf-8",xml_declaration=True)
        tcl="open_project {"+project.as_posix()+"}\nset_option -top_module audio_visual_coexistence_top\nset_option -verilog_std sysv2017\nset_option -route_option "+str(option)+"\nrun all\n"
        (folder/"run.tcl").write_text(tcl,encoding="ascii")
        manifest={"scope":"fresh source run of frozen V0171 audio/PitchMod/CC64/strict visual, route only; not latest panel/T027/effect integration","git_context":revision,"source_builds":inputs[:47],"roms":{str(mapping[Path(k).resolve()]):h for k,h in m["roms"].items()},"headers":{str(mapping[k]):h for k,h in headers.items()},"all_input_files":inputs,"normalized_source_hashes":normalized,"actual_route_option_expected":option,"fresh_impl_copied":False,"physical_file_count":56,"phase_limit_seconds":1800,"max_effective_runs":1}
        (folder/"input_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8");canonical_inputs.append(normalized);arms[arm]={"folder":str(folder),"manifest_sha256":sha(folder/"input_manifest.json"),"project_sha256":sha(project),"tcl_sha256":sha(folder/"run.tcl"),"route_option":option}
    assert canonical_inputs[0]==canonical_inputs[1],"A/B inputs differ beyond directory relocation"
    diff={"date":"2026-10-05","base_project":str(original),"base_manifest_sha256":sha(BASE/"input_manifest.json"),"base_actual_cmd_sha256":sha(BASE/"impl/pnr/cmd.do"),"original_input_files":original_payloads,"arms":arms,"normalized_AB_input_identity":True,"sole_effective_option_change":"route_option0 ->1","phase_order":["A_route0","B_route1"],"wall_limit_per_arm_seconds":1800,"run_count_per_arm":1,"same_part":"GW5AT-LV60PG484AC1/I0 B","same_clocks_MHz":[50,25,125],"same_uncertainty_ns":{"setup":1.0,"hold":0.55},"serial_reset_locations":["R49C101[1][A]","R49C101[1][B]"],"goals":{"min_setup_ns":.5,"min_setup_gain_ns":.1,"all_domain_no_violations":True,"Hold_Recovery_Removal_not_worse":True,"resources_same":True},"production_changed":False,"download_allowed":False,"functional_reuse":{"existing_parser_previous_proof":"de68038/V0171 and unchanged accepted parser","recent_same_audio_joint_result_sha256":sha(pcm),"audio_inputs_exact_matches":reused_audio,"not_new_AB_behavior_run":True},"old_138K_result_not_applied":True}
    (out/"AB_freeze.json").write_text(json.dumps(diff,indent=2)+"\n",encoding="utf-8")
    print("Frozen AB 56 private input files each:47 sources/constraints +7 ROM+2 headers; only route_option differs")
if __name__=="__main__":main()
