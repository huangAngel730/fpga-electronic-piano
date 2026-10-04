"""Prepare the one allowed physical pending-mask candidate; no build/programming."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
SCOPE=ROOT/'code/tb/common/midi_pending_mask_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-project',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--functional-result',type=Path,required=True)
    args=parser.parse_args();base=args.baseline_project.resolve();out=args.output.resolve();out.relative_to(ROOT/'code/output')
    if out.exists():raise ValueError('output exists; only one trial is allowed')
    functional=json.loads(args.functional_result.read_text(encoding='utf-8'))
    if any((r['exit']==0)!=r['expected_success'] for r in functional['runs'].values()):raise ValueError('functional result not all correct')
    manifest=json.loads((SCOPE/'manifest.json').read_text())
    candidate=SCOPE/'midi_event_parser.sv'
    if sha(candidate)!=manifest['candidate_SHA']:raise ValueError('candidate changed after definition')
    if functional['manifest']['candidate_SHA']!=sha(candidate):raise ValueError('untested candidate')
    tree=ET.parse(base);nodes=list(tree.getroot().find('FileList'))
    for node in nodes:
        if not Path(node.attrib['path']).is_file():raise ValueError('missing input')
    changes=[node for node in nodes if Path(node.attrib['path']).name=='midi_event_parser.sv']
    if len(changes)!=1 or sha(Path(changes[0].attrib['path']))!=manifest['frozen_parser_SHA']:raise ValueError('wrong baseline parser')
    # Follow original independent STA input provenance exactly, including ROMs.
    provenance=json.loads((base.parent/'input_manifest.json').read_text())
    for entry in provenance['source_builds']:
        path=Path(entry['actual_source'])
        if sha(path)!=entry['actual_sha']:raise ValueError('baseline source changed '+str(path))
    for name,h in provenance['roms'].items():
        if sha(Path(name))!=h:raise ValueError('baseline ROM changed')
    out.mkdir(parents=True)
    staged=out/'midi_event_parser.sv';staged.write_bytes(candidate.read_bytes())
    old=Path(changes[0].attrib['path']);changes[0].attrib['path']=staged.as_posix()
    project=out/'audio_visual_coexistence_top.gprj';tree.write(project,encoding='utf-8',xml_declaration=True)
    x=list(ET.parse(base).getroot().find('FileList'));y=list(ET.parse(project).getroot().find('FileList'))
    if len(x)!=len(y) or sum(a.attrib!=b.attrib for a,b in zip(x,y))!=1:raise ValueError('unfair comparison')
    for entry in provenance['source_builds']:
        if Path(entry['actual_source'])==old:
            entry.update(actual_source=str(staged),actual_sha=sha(staged),input_source=str(candidate),input_sha=sha(candidate))
    provenance.update(scope='onehot mask trial, isolated fair one-parser change; no production release',
        baseline_project=str(base),experiment_manifest=manifest,planned_builds=1)
    (out/'input_manifest.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    (out/'run.tcl').write_text('open_project {'+project.as_posix()+'}\nset_option -top_module audio_visual_coexistence_top\nset_option -verilog_std sysv2017\nrun all\n',encoding='ascii')
    record={'baseline_project':str(base),'trial_project':str(project),
        'same_input_filelist_except_parser':True,'filelist_count':len(nodes),
        'source_delta':{'before':str(old),'before_SHA':sha(old),'after':str(staged),'after_SHA':sha(staged)},
        'unchanged_sources':{n.attrib['path']:sha(Path(n.attrib['path'])) for n in x if Path(n.attrib['path'])!=old},
        'unchanged_ROMs':provenance['roms'],'functional_result_SHA':sha(args.functional_result),
        'production_parser_SHA':sha(ROOT/'code/rtl/input/midi_input/midi_event_parser.sv'),
        'no_clock_constraint_change':True,'baseline_STA_SHA':sha(base.parent/'impl/pnr/audio_visual_coexistence_top_tr_content.html')}
    (out/'fairness.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print('Prepared exactly one source change, all clock/pin/ROM inputs frozen. Not a PnR PASS.')
    return 0
if __name__=='__main__':raise SystemExit(main())
