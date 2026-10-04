"""Single fair audio-control boundary trial, original parser/constraints frozen."""
from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET,argparse
ROOT=Path(__file__).resolve().parents[2]
SCOPE=ROOT/'code/tb/board/audio_control_boundary_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 cli=argparse.ArgumentParser();cli.add_argument('--baseline-project',type=Path,required=True);cli.add_argument('--output',type=Path,required=True);cli.add_argument('--functional',type=Path,required=True);a=cli.parse_args();base=a.baseline_project.resolve();out=a.output.resolve();out.relative_to(ROOT/'code/output')
 if out.exists():raise ValueError('one trial only; existing output preserved')
 functional=json.loads(a.functional.read_text(encoding='utf-8'));assert functional['passed']
 manifest=json.loads((SCOPE/'manifest.json').read_text(encoding='utf-8'))
 for p,h in functional['source_hashes'].items():
  if Path(p).name in ['polyphonic_event_router.sv','polyphonic_envelope_bank.sv'] and str(SCOPE) in p:assert sha(Path(p))==h
 tree=ET.parse(base);nodes=list(tree.getroot().find('FileList'));assert len(nodes)==47
 provenance=json.loads((base.parent/'input_manifest.json').read_text(encoding='utf-8'))
 for e in provenance['source_builds']:assert sha(Path(e['actual_source']))==e['actual_sha']
 for p,h in provenance['roms'].items():assert sha(Path(p))==h
 out.mkdir(parents=True);changes={};old_paths={}
 for name in ['polyphonic_event_router.sv','polyphonic_envelope_bank.sv']:
  selected=[n for n in nodes if Path(n.attrib['path']).name==name];assert len(selected)==1
  old=Path(selected[0].attrib['path'])
  source=SCOPE/name;original=ROOT/'code/tb/board/pitch_mod_bank_integration_candidate'/name
  assert sha(original)==manifest['original_sources'][name]
  template=original.read_text(encoding='utf-8');staged=source.read_text(encoding='utf-8')
  if name=='polyphonic_envelope_bank.sv':
   # Reproduce ONLY the three frozen physical ROM-address substitutions.
   import re
   for key in ['OCT_FILE','SUB_FILE','LFO_FILE']:
    pattern=r'parameter '+key+r'="[^"]+"'
    current=re.findall(pattern,old.read_text(encoding='utf-8'));assert len(current)==1
    assert len(re.findall(pattern,template))==1 and len(re.findall(pattern,staged))==1
    template=re.sub(pattern,lambda _:current[0],template,count=1)
    staged=re.sub(pattern,lambda _:current[0],staged,count=1)
  assert template.encode('utf-8')==old.read_bytes(), 'unapproved physical source difference '+name
  new=out/name;new.write_text(staged,encoding='utf-8',newline='\n');selected[0].attrib['path']=new.as_posix()
  changes[str(old)]={'new':str(new),'old_sha':sha(old),'new_sha':sha(new)};old_paths[name]=str(old)
 for e in provenance['source_builds']:
  if e['actual_source'] in changes:
   name=Path(e['actual_source']).name;e.update(actual_source=str(out/name),actual_sha=sha(out/name),input_source=str(SCOPE/name),input_sha=sha(SCOPE/name))
 provenance['scope']='isolated audio control lease + registered authorization, original parser, no T027/T028 integration'
 project=out/'audio_visual_coexistence_top.gprj';tree.write(project,encoding='utf-8',xml_declaration=True)
 newnodes=list(ET.parse(project).getroot().find('FileList'));oldnodes=list(ET.parse(base).getroot().find('FileList'));assert sum(x.attrib!=y.attrib for x,y in zip(oldnodes,newnodes))==2
 (out/'input_manifest.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
 (out/'run.tcl').write_text('open_project {'+project.as_posix()+'}\nset_option -top_module audio_visual_coexistence_top\nset_option -verilog_std sysv2017\nrun all\n',encoding='ascii')
 fairness={'baseline_project':str(base),'candidate_project':str(project),'changed_sources':changes,'unchanged_sources':{n.attrib['path']:sha(Path(n.attrib['path'])) for n in oldnodes if n.attrib['path'] not in changes},'roms':provenance['roms'],'functional_sha':sha(a.functional),'baseline_sta_sha':sha(base.parent/'impl/pnr/audio_visual_coexistence_top_tr_content.html'),'candidate_manifest_sha':sha(SCOPE/'manifest.json'),'parser_preserved':'de68038','new_clock_or_constraints':False,'actual_build_limit':1,'seconds_limit':1800}
 (out/'fairness.json').write_text(json.dumps(fairness,indent=2)+'\n',encoding='utf-8')
 print('Prepared fair original V0171 trial: 47 sources, exactly bank/router changed, original parser/ROM/constraints frozen.')
if __name__=='__main__':main()