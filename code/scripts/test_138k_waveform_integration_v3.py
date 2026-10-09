from pathlib import Path
import sys,json,copy,xml.etree.ElementTree as ET,hashlib,subprocess
R=Path.cwd();sys.path.insert(0,str(R/'code/scripts'));import prepare_138k_waveform_integration_v3 as p;import check_138k_waveform_integration_build_v3 as g
O=R/'code/output/t058_reset_hold_v3_20261009/preflight_qualified';O.mkdir(exist_ok=False);proj=R/'code/build/138k_waveform/v3_preflight_20261009';checks=[]
def check(name,b):checks.append({'check':name,'pass':bool(b)});assert b,name
def rejected(name,fn):
 try:fn()
 except (ValueError,OSError):check(name,True)
 else:check(name,False)
x=p.validate(proj);old=p.parent.inputs(proj)[0];new=p.inputs(proj)[0];sdckey='constraints/audio_visual_hold055.sdc';check('same58_andGSC_exceptexactSDC',{n:b for n,b in old.items() if n!=sdckey}=={n:b for n,b in new.items() if n!=sdckey});check('oldSDCprefixunchanged',new[sdckey].startswith(old[sdckey]));sdc=new[sdckey].decode();check('exact4CLEAR_andstrictmin_whitelist',not g.inspect_constraint_scope(sdc));m=json.loads((p.SCOPE/'revision_manifest.json').read_bytes());
for label,newtext in [('removeHolduncert',sdc.replace('set_clock_uncertainty -hold  0.650','set_clock_uncertainty -hold  0.600')),('cutALLclocks',sdc+'\nset_clock_groups -asynchronous -group [get_clocks {sys_clk}] -group [get_clocks {video_pixel}]\n'),('broadCLEAR',sdc.replace(m['additional_exact_falsepaths'][0],m['additional_exact_falsepaths'][0].replace('sync_chain_0_s0/CLEAR','*/CLEAR'))),('cutDpin',sdc.replace(m['additional_exact_falsepaths'][0],m['additional_exact_falsepaths'][0].replace('/CLEAR','/D'))),('missingmin',sdc.replace(m['additional_min_delay'],'')),('missingresetDreport',sdc.replace(m['additional_reports'][0],''))]:
 check('mutation_really_changed_'+label,newtext!=sdc)
 check('reject_'+label,bool(g.inspect_constraint_scope(newtext)))
rejected('reject_overwrite',lambda:p.prepare(proj))
for name in ['constraints/audio_visual_hold055.sdc','constraints/waveform_payload_preserve.gsc','sources/visual_mailbox_cdc.sv','rom/sine_1024_8192.mem']:
 path=proj/'inputs'/name;raw=path.read_bytes();path.write_bytes(raw+b'\n//changed\n');rejected('hidden_'+name,lambda:p.validate(proj));path.write_bytes(raw)
p.validate(proj)
parent=R/'code/build/138k_waveform/runs/run_20261008_payload_preserve_v2/project/impl/gwsynthesis/audio_visual_coexistence_top_syn_rsc.xml';facts,count,errors=g.inspect_ram_hierarchy(parent);check('physicalprevious23_BSRAM_89SSRAM_hierarchyexact',not errors and count==23 and facts['observer_SSRAM']==28);tree=ET.parse(parent).getroot();q=O/'rsc.xml'
for label,fn in [('changeTotalSS',lambda t:t.attrib.update(T_Ssram='90')),('observeraddRAM',lambda t:next(x for x in t.iter() if x.attrib.get('name')=='u_wave_bridge').attrib.update(T_Bsram='1')),('waveDSP',lambda t:next(x for x in t.iter() if x.attrib.get('name')=='u_waveform').attrib.update(T_MULT12X12='1')),('changeaudio',lambda t:next(x for x in t.iter() if x.attrib.get('name')=='g_polyphonic.u_audio_core').attrib.update(T_Bsram='19'))]:
 t=copy.deepcopy(tree);fn(t);ET.ElementTree(t).write(q);check('rejectresource_'+label,bool(g.inspect_ram_hierarchy(q)[2]))
# Added local reports must match real endpoint D paths; old reports must not be accepted as v3.
timing=R/'code/build/138k_waveform/runs/run_20261008_payload_preserve_v2/project/impl/pnr/audio_visual_coexistence_top_tr_content.html';usage=timing.parent/'audio_visual_coexistence_top.rpt.txt';errors,facts=g.inspect_directed_paths(timing.read_text(encoding='utf-8'),usage.read_text(encoding='utf-8'),sdc);check('oldv2STArefused_missingnewactiveandpaths',len(errors)>=3);check('approvedreportregexworks',not any('malformed' in e for e in errors));sourceids={n:hashlib.sha256((R/n).read_bytes()).hexdigest() for n in ['code/scripts/prepare_138k_waveform_integration_v3.py','code/scripts/check_138k_waveform_integration_build_v3.py','code/scripts/run_138k_waveform_integration_once_v3.py','code/scripts/run_138k_waveform_reset_contract_v3.py']};record={'passed':True,'checks':checks,'source_sha256':sourceids,'oldv2reportrejected_errors':errors,'no_new_toolrun_claim':True};(O/'receipt.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');print('V3_PREFLIGHT_PASS',len(checks));print('OLD_V2_REPORT_REFUSED',errors)
