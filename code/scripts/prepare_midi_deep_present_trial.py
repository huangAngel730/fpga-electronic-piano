"""Freeze parser-only deep presentation trial; no production source writes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
SCOPE=ROOT/"code/tb/common/midi_deep_present_candidate"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--functional",type=Path,required=True);ap.add_argument("--pcm",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
    out=a.output.resolve();out.relative_to(ROOT/"code/output")
    assert not out.exists(),"single bounded trial, new output required"
    f=json.loads(a.functional.read_text(encoding="utf-8"));p=json.loads(a.pcm.read_text(encoding="utf-8"));assert f["passed"] and p["passed"]
    for name,h in f["inputs"].items():assert sha(ROOT/name)==h,name
    for name,h in p["compiled_inputs"].items():assert sha(Path(name))==h,name
    base=ROOT/"code/output/M3_parser_de68038_review_20261003/physical_parser_only"
    provenance=json.loads((base/"input_manifest.json").read_text(encoding="utf-8"))
    for e in provenance["source_builds"]:assert sha(Path(e["actual_source"]))==e["actual_sha"]
    for name,h in provenance["roms"].items():assert sha(Path(name))==h
    project=base/"audio_visual_coexistence_top.gprj";tree=ET.parse(project);files=tree.getroot().find("FileList");assert len(files)==47
    frozen={e.attrib["path"]:sha(Path(e.attrib["path"])) for e in files}
    old_parser=[e for e in files if Path(e.attrib["path"]).name=="midi_event_parser.sv"];assert len(old_parser)==1
    old_parser=old_parser[0];old=Path(old_parser.attrib["path"])
    assert old.read_bytes()==(ROOT/"code/rtl/input/midi_input/midi_event_parser.sv").read_bytes()
    headers={}
    for e in files:
        q=Path(e.attrib["path"])
        if q.suffix in (".sv",".v"):
            for name in re.findall(r'`include\s+"([^"]+)"',q.read_text(encoding="utf-8",errors="replace")):
                h=Path(name);h=h if h.is_absolute() else q.parent/h;assert h.is_file();headers[str(h)]=sha(h)
    out.mkdir(parents=True)
    new_parser=out/"midi_event_parser.sv";new_parser.write_bytes((SCOPE/new_parser.name).read_bytes())
    sel=out/"control_snapshot_top4.sv";sel.write_bytes((SCOPE/sel.name).read_bytes())
    old_parser.attrib["path"]=new_parser.as_posix();ET.SubElement(files,"File",path=sel.as_posix(),type="file.verilog",enable="1")
    assert len(files)==48
    trial=out/"audio_visual_coexistence_top.gprj";tree.write(trial,encoding="utf-8",xml_declaration=True)
    for mode in ["syn","pnr"]:
        (out/("run_"+mode+".tcl")).write_text("open_project {"+trial.as_posix()+"}\nset_option -top_module audio_visual_coexistence_top\nset_option -verilog_std sysv2017\nrun "+mode+"\n",encoding="ascii")
    fair={"date":"2026-10-05","baseline_project":str(project),"candidate_project":str(trial),"old_parser":str(old),"old_parser_sha":sha(old),"new_sources":{str(q):sha(q) for q in [new_parser,sel]},"all_baseline_source_sha":frozen,"unchanged_headers":headers,"ROM_sha":provenance["roms"],"old_entries":47,"new_entries":48,"changed_existing_entries":1,"new_module_entries":1,"functional_result":str(a.functional.resolve()),"functional_result_sha":sha(a.functional),"pcm_result":str(a.pcm.resolve()),"pcm_result_sha":sha(a.pcm),"baseline_STA_sha":sha(base/"impl/pnr/audio_visual_coexistence_top_tr_content.html"),"scope":"V0171 audio/strict-visual frozen, deep parser only; NOT latest panel/T027/T028","formal_source_modified":False,"effective_PnR_run_limit":1,"wall_timeout_seconds":1800,"before_PnR_synthesis_budget_required":True}
    for e in provenance["source_builds"]:
        if Path(e["actual_source"])==old:
            e.update(actual_source=str(new_parser),actual_sha=sha(new_parser),input_source=str(SCOPE/new_parser.name),input_sha=sha(SCOPE/new_parser.name))
    provenance["source_builds"].append({"actual_source":str(sel),"actual_sha":sha(sel),"input_source":str(SCOPE/sel.name),"input_sha":sha(SCOPE/sel.name)})
    provenance["scope"]="V0171 frozen audio + strict visual, deep presentation parser only"
    (out/"input_manifest.json").write_text(json.dumps(provenance,indent=2)+"\n",encoding="utf-8")
    (out/"fairness.json").write_text(json.dumps(fair,indent=2)+"\n",encoding="utf-8")
    print("Prepared 47 frozen sources: exactly1 replacement +1 selector; ROM/header/CST/SDC unchanged")
if __name__=="__main__":main()
