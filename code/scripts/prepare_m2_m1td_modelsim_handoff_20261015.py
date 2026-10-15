"""Prepare a portable read-only ModelSim input bundle; this does not invoke ModelSim."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'code/output/m2_m1td_whole_prepare_20261015_06'
VENDOR=ROOT/'code/output/m2_m1td_whole_compile_20261015_05/vendor_GSR_pROM.v'
PLL=ROOT/'code/tb/board/t058_waveform_integration_20261008/clock_plan_sim.v'
DVI=ROOT/'code/rtl/138K_try/hold_trials_20261005/dvi_sim_stub.v'
TB=ROOT/'code/tb/board/m2_m1td_modelsim_handoff_20261015/tb_m2_m1td_real_chain.sv'
M1=Path('D:/Cmove/CUsersAngel17move/Downloads/M1_双音色与立体声延迟完整链_20261014.zip')
ABS_QUOTED=re.compile(rb'"([A-Za-z]:/[^"\r\n]+\.(?:mem|hex|svh))"')


def ident(path):
 raw=Path(path).read_bytes()
 return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def main():
 a=argparse.ArgumentParser()
 a.add_argument('--output',required=True,type=Path)
 args=a.parse_args()
 out=args.output.resolve()
 allowed=(ROOT/'code/output').resolve()
 if out.exists() or out==allowed or not out.is_relative_to(allowed):raise ValueError('NEW_OUTPUT_REQUIRED')
 out.mkdir(parents=True)
 result={'status':'FAIL_PARTIAL','error':None,'simulator_run':False,'physical_STA':'NOT_RUN',
         'production_modified':False,'path_adaptations':{},'source_identities':{},'output_identities':{}}
 try:
  original=json.loads((SOURCE/'PREPARATION_RECEIPT.json').read_text(encoding='utf-8'))
  if original['status']!='PREPARED_NOT_PHYSICALLY_ADMITTED':raise ValueError('PREPARED_INVALID')
  if ident(M1)['sha256']!='5c18926ae307301e91ec0e44dcf4a48b2fb57adec71ad46c494b14df59913b06':
   raise ValueError('M1_PACKAGE_DRIFT')
  stage=SOURCE/'inputs';dest=out/'inputs'
  for key,item in original['input_files'].items():
   relative=key.replace('\\','/')
   src=SOURCE/relative
   if ident(src)!=item:raise ValueError('STAGED_INPUT_DRIFT:'+relative)
   data=src.read_bytes()
   if src.suffix in ('.sv','.v'):
    adjustments=[]
    for match in reversed(list(ABS_QUOTED.finditer(data))):
     lit=match[1].decode('utf-8')
     if not lit.startswith(stage.as_posix()+'/'):
      raise ValueError('EXTERNAL_ABSOLUTE_MEDIA_LITERAL:'+lit)
     portable=lit[len(stage.as_posix())+1:]
     if not portable.startswith(('rom/','include/')) or not (stage/portable).is_file():
      raise ValueError('UNBOUND_PORTABLE_LITERAL:'+portable)
     replacement=('"'+portable+'"').encode('utf-8')
     oldbytes=match[0]
     data=data[:match.start()]+replacement+data[match.end():]
     adjustments.append({'old':oldbytes.decode('utf-8'),'new':replacement.decode('utf-8'),
                         'dependency_sha256':ident(stage/portable)['sha256']})
    if adjustments:
     result['path_adaptations'][relative]=list(reversed(adjustments))
   dst=out/relative
   dst.parent.mkdir(parents=True,exist_ok=True)
   dst.write_bytes(data)
   result['source_identities'][relative]=item
   result['output_identities'][relative]=ident(dst)
  assert len(result['source_identities'])==84
  for name,path in [('sources/vendor_GSR_pROM.v',VENDOR),('sources/clock_plan_sim.v',PLL),
                     ('sources/dvi_sim_stub.v',DVI),('tb_m2_m1td_real_chain.sv',TB)]:
   target=dest/name
   if target.exists():raise ValueError('EXTRA_COLLISION:'+name)
   target.parent.mkdir(parents=True,exist_ok=True)
   shutil.copyfile(path,target)
   result['source_identities']['extra/'+name]=ident(path)
   result['output_identities']['inputs/'+name]=ident(target)
  project=ET.parse(SOURCE/'m2_fourvoice_timbre_delay_board_top.gprj')
  units=[]
  for obj in project.getroot().iter('File'):
   src=Path(obj.attrib['path'])
   if not src.is_relative_to(stage):raise ValueError('GPRJ_SOURCE_SCOPE')
   relative=src.relative_to(stage).as_posix()
   if obj.attrib['type']=='file.verilog' and src.name not in ('TMDS_PLL_800_600_60.v','DVI_TX_Top.v'):
    units.append(relative)
  assert len(units)==65, len(units) # 69 total: two constraints, two vendor video IPs excluded from nominal sim.
  packages=['sources/audio_defs_pkg.sv','sources/sustain_control_contract_pkg.sv']
  assert all(p in units for p in packages)
  units=packages+[x for x in units if x not in packages]
  units+=["sources/vendor_GSR_pROM.v","sources/clock_plan_sim.v",
          "sources/dvi_sim_stub.v","tb_m2_m1td_real_chain.sv"]
  (dest/'compile.f').write_text('\n'.join(units)+'\n',encoding='utf-8',newline='\n')
  remaining=[]
  for file in (dest/'sources').iterdir():
   if file.suffix in ('.sv','.v'):
    remaining += [(file.name,x.decode()) for x in ABS_QUOTED.findall(file.read_bytes())]
  if remaining:raise ValueError('REMAINING_ABSOLUTE_REFERENCES:'+str(remaining[:2]))
  instructions='''# M1 independent execution handoff; nothing was run during this preparation.\n\nFrom this directory's `inputs` subfolder, on a host with a verified ModelSim 10.7:\n\n    vlib work\n    vlog -sv +incdir+include -f compile.f\n    vsim -c work.tb_m2_m1td_real_chain -do "run -all; quit -f"\n\nBefore execution seal the exact ModelSim binaries and dependency hashes,\ncommands, cwd, bounded deadlines (each tool <=300s, entire run <=900s),\nnew output folder and fail-on-FATAL/PASS-marker contract. A ModelSim process\nexit 0 alone is not PASS. Run once only after reviewer approves the exact\nsource/tool combination. No Gowin, PnR, STA or device calls.\n\nThe TB checks MIDI->shared FIFO->real M1 sound/score->PCM/frame/PT8211\nand reset, but it does not independently recompute M1 arithmetic or prove\nBSRAM resource inference. The old T056 .fs and STA never apply here.\n'''
  (out/'README.md').write_text(instructions,encoding='utf-8',newline='\n')
  result['status']='PORTABLE_MODELSIM_INPUT_PREPARED_NOT_EXECUTED'
  result['compile_units']=len(units)
  result['mapped_literal_count']=sum(len(v) for v in result['path_adaptations'].values())
  result['m1_archive_sha256']=ident(M1)['sha256']
 except Exception as exc:
  result['error']=type(exc).__name__+': '+str(exc)
 result['exit_code']=0 if result['error'] is None else 1
 raw=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
 (out/'PREPARATION_RECEIPT.json').write_bytes(raw)
 if result['error'] is None:
  files=[p for p in out.rglob('*') if p.is_file()]
  manifest={'status':result['status'],'members':{p.relative_to(out).as_posix():ident(p) for p in files}}
  encoded=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
  archive=out/'M2_138K_M1双音色延迟_ModelSim自包含输入_20261015.zip'
  with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
   z.writestr('MANIFEST.json',encoded)
   for p in files:z.write(p,p.relative_to(out).as_posix())
  with zipfile.ZipFile(archive) as z:
   if z.testzip() is not None:raise ValueError('ZIP_CRC')
   for name,item in manifest['members'].items():
    b=z.read(name)
    if hashlib.sha256(b).hexdigest()!=item['sha256'] or len(b)!=item['bytes']:
     raise ValueError('ZIP_IDENTITY:'+name)
  result['archive']={'path':str(archive),'bytes':archive.stat().st_size,'sha256':ident(archive)['sha256']}
 print(json.dumps({k:result.get(k) for k in ('status','error','compile_units','mapped_literal_count','archive','exit_code')},ensure_ascii=False))
 return result['exit_code']

if __name__=='__main__':raise SystemExit(main())
