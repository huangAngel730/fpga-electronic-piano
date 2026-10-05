"""Prepare one joint pipeline comparison against exact V0171; never build here."""
from pathlib import Path
import argparse,hashlib,json,re,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
SCOPE=ROOT/'code/tb/board/system_control_pipeline_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--baseline-project',type=Path,required=True);cli.add_argument('--functional',type=Path,required=True);cli.add_argument('--output',type=Path,required=True);a=cli.parse_args()
 base=a.baseline_project.resolve();out=a.output.resolve();out.relative_to(ROOT/'code/output')
 if out.exists():raise ValueError('One physical trial only, do not reuse output')
 f=json.loads(a.functional.read_text(encoding='utf-8'));assert f['passed'];m=json.loads((SCOPE/'manifest.json').read_text(encoding='utf-8'));pr=json.loads((base.parent/'input_manifest.json').read_text(encoding='utf-8'));tree=ET.parse(base);nodes=list(tree.getroot().find('FileList'));assert len(nodes)==47
 for e in pr['source_builds']:assert sha(Path(e['actual_source']))==e['actual_sha'],e['actual_source']
 for path,h in pr['roms'].items():assert sha(Path(path))==h,path
 prepared={};changes={}
 for name,info in m['candidate_sources'].items():
  candidate=SCOPE/name;assert sha(candidate)==info['sha256']
  old=[Path(n.attrib['path']) for n in nodes if Path(n.attrib['path']).name==name];assert len(old)==1
  old=old[0];candidate_text=candidate.read_text(encoding='utf-8')
  if name=='midi_event_parser.sv':assert sha(old)=='834887a990a4866d54669c5f18588a0b799aa4c08ccb27c91a2f9e5609f331c6'
  else:
   origin=ROOT/'code/tb/board/pitch_mod_bank_integration_candidate'/name;original_text=origin.read_text(encoding='utf-8')
   if name=='polyphonic_envelope_bank.sv':
    for key in ['OCT_FILE','SUB_FILE','LFO_FILE']:
     pattern=r'parameter '+key+r'="[^"]+"';occ=re.findall(pattern,old.read_text(encoding='utf-8'));assert len(occ)==1
     assert len(re.findall(pattern,original_text))==1 and len(re.findall(pattern,candidate_text))==1
     original_text=re.sub(pattern,lambda _:occ[0],original_text,count=1);candidate_text=re.sub(pattern,lambda _:occ[0],candidate_text,count=1)
   assert original_text.encode('utf-8')==old.read_bytes(),'extra frozen source transform '+name
  prepared[name]=(old,candidate,candidate_text)
 # Freeze implicit headers used by unchanged source absolute paths as well.
 includes={}
 for n in nodes:
  path=Path(n.attrib['path'])
  if path.suffix not in ['.sv','.v','.svh']:continue
  text=path.read_text(encoding='utf-8',errors='replace')
  for header in re.findall(r'`include\s+"([^"]+)"',text):
   hp=Path(header)
   if not hp.is_absolute():hp=path.parent/hp
   assert hp.is_file(),'missing immutable include '+str(hp);includes[str(hp)]=sha(hp)
 out.mkdir(parents=True)
 for name,(old,candidate,text) in prepared.items():
  staged=out/name;staged.write_text(text,encoding='utf-8',newline='\n')
  for n in nodes:
   if Path(n.attrib['path'])==old:n.attrib['path']=staged.as_posix()
  changes[str(old)]={'new':str(staged),'old_sha':sha(old),'new_sha':sha(staged),'candidate_raw_sha':sha(candidate),'physical_ROM_address_rebinding_only':name=='polyphonic_envelope_bank.sv'}
  for e in pr['source_builds']:
   if Path(e['actual_source'])==old:e.update(actual_source=str(staged),actual_sha=sha(staged),input_source=str(candidate),input_sha=sha(candidate))
 project=out/'audio_visual_coexistence_top.gprj';tree.write(project,encoding='utf-8',xml_declaration=True)
 original=list(ET.parse(base).getroot().find('FileList'));actual=list(ET.parse(project).getroot().find('FileList'));assert sum(x.attrib!=y.attrib for x,y in zip(original,actual))==3
 pr.update(scope='new joint3-source registered control pipeline screen; no latest panel/T027/T028 STA claim',user_authorized_scope='parser+audio together per2026-10-05 instruction',planned_effective_PnR_runs=1)
 (out/'input_manifest.json').write_text(json.dumps(pr,indent=2)+'\n',encoding='utf-8')
 (out/'run.tcl').write_text('open_project {'+project.as_posix()+'}\nset_option -top_module audio_visual_coexistence_top\nset_option -verilog_std sysv2017\nrun all\n',encoding='ascii')
 fair={'baseline_project':str(base),'trial_project':str(project),'changed_sources':changes,'unchanged_sources':{n.attrib['path']:sha(Path(n.attrib['path'])) for n in original if str(Path(n.attrib['path'])) not in changes},'unchanged_ROMs':pr['roms'],'implicit_headers':includes,'joint_functional_result':str(a.functional.resolve()),'joint_functional_sha':sha(a.functional),'candidate_manifest_sha':sha(SCOPE/'manifest.json'),'baseline_STA_SHA':sha(base.parent/'impl/pnr/audio_visual_coexistence_top_tr_content.html'),'same_settings_and_constraints':True,'effective_PnR_run_limit':1,'wall_timeout_seconds':1800,'formal_RTL_modified':False}
 (out/'fairness.json').write_text(json.dumps(fair,indent=2)+'\n',encoding='utf-8')
 print('Prepared exactly3 source changes,47entries, allROM/implicitheaders/constraints frozen; NOT a timing pass.')
if __name__=='__main__':main()