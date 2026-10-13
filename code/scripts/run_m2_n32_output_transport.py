"""New isolated transport selftests only; no Gowin or production mutation."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
CAD=Path('D:/Gowin/oss-cad-suite')
BASE=ROOT/'code/build/138k_night_cache_combo/staged_20261010_01'
RESOURCE=ROOT/'code/build/138k_polyphony_resource/prom_candidate_20261013_01'
TB=ROOT/'code/tb/audio_out/m2_n32_output_candidate_20261013'
RTL=ROOT/'code/rtl/audio_out/m2_n32_output_candidate_20261013/m2_n32_output_transport.sv'
VENDOR=Path('D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/simlib/gw5a/prim_sim.v')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',choices=['base','full32','subsystem','subsystem_wait'],default='base');args=parser.parse_args()
    out=args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'code/output') or out==ROOT/'code/output':raise ValueError('OUTPUT_SCOPE_OR_EXISTS')
    out.mkdir(parents=True,exist_ok=False);start=time.monotonic();steps=[];error=None;before={};after={}
    spec=importlib.util.spec_from_file_location('jobhelper',ROOT/'code/software/t052_runner_acceptance_candidate_20261012/windows_job.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    env=os.environ.copy();env['YOSYSHQ_ROOT']=str(CAD)+os.sep;env['PATH']=os.pathsep.join([str(CAD/'bin'),str(CAD/'lib'),env.get('PATH','')])
    transport=[BASE/'inputs/sources'/name for name in ['reset_sync.sv','visual_mailbox_cdc.sv','pcm_frame_observer.sv','pcm_waveform_observer_bridge.sv','i2s_tx.sv']]
    transport += [ROOT/'code/rtl/audio_out/pcm_result_hold.sv',ROOT/'code/rtl/audio_out/pcm_frame_buffer.sv',ROOT/'code/rtl/common/pcm_clip_counter.sv',ROOT/'code/rtl/audio_out/m2_polyphony_frame_candidate_20261012/premixed_frame_adapter.sv',RTL]
    if args.case.startswith('subsystem'):transport += [RTL.with_name('m2_n32_audio_subsystem.sv'),BASE/'inputs/sources/system_status_counters.sv']
    sources=[Path(n.attrib['path']) for n in ET.parse(RESOURCE/'n32_prom_resource.gprj').iter('File') if n.attrib['type']=='file.verilog']
    protected=transport+sources+list(TB.glob('*.sv'))+[VENDOR,Path(__file__),Path(spec.origin),RESOURCE/'resource_receipt.json',BASE/'frozen_receipt.json',CAD/'bin/iverilog.exe',CAD/'bin/vvp.exe']
    try:
        receipt=json.loads((BASE/'frozen_receipt.json').read_bytes())
        for p in transport:
            if p.is_relative_to(BASE/'inputs'):
                assert sha(p)==receipt['inputs'][p.relative_to(BASE/'inputs').as_posix()]['adapted_sha256']
        resource=json.loads((RESOURCE/'resource_receipt.json').read_bytes())
        assert sha(RESOURCE/'resource_receipt.json')=='f77a526318cd213b164e9bed5d0d1d0f2ca19aad89a61813f082d7d5971151bf'
        for name,item in resource['artifacts'].items():
            path=RESOURCE/name
            if path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:raise ValueError('RESOURCE_ARTIFACT_DRIFT:'+name)
            protected.append(path)
        for path,digest in resource['include_SHA'].items():
            header=Path(path)
            if sha(header)!=digest:raise ValueError('RESOURCE_INCLUDE_DRIFT:'+path)
            protected.append(header)
        for p,digest in resource['input_SHA'].items():assert sha(Path(p))==digest
        assert sha(VENDOR)=='202f65ccf77126d04e47db36c95e237e48522f3a105a3e64d9fcbf4e3b782f27'
        assert sha(Path(spec.origin))=='5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b'
        before={str(p):sha(p) for p in sorted(set(protected))}
        snapshots=[]
        for index,path in enumerate(sorted(set(protected))):
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=before[str(path)]:raise ValueError('SNAPSHOT_DRIFT:'+str(path))
            saved=out/'input_snapshot'/(str(index).zfill(3)+'_'+path.name)
            saved.parent.mkdir(exist_ok=True);saved.write_bytes(raw)
            snapshots.append(dict(original=str(path),snapshot=saved.relative_to(out).as_posix(),bytes=len(raw),sha256=before[str(path)]))
        (out/'snapshot_manifest.json').write_text(json.dumps(snapshots,indent=2)+'\n',encoding='utf-8',newline='\n')
        library=VENDOR.read_text(encoding='utf-8');parts=[]
        for module in ['GSR','pROM']:
            match=re.search(r'^module '+module+r' \([^\n]*\);[\s\S]*?^endmodule[^\n]*',library,re.M)
            if not match:raise ValueError('VENDOR_MODULE:'+module)
            parts.append(match.group(0))
        vendor=out/'vendor_GSR_pROM.v';vendor.write_text('`timescale 1ns/1ps\n'+'\n\n'.join(parts)+'\n',encoding='utf-8',newline='\n')
        def run(label,command,wanted,diagnostic=None):
            remaining=900-(time.monotonic()-start)
            if remaining<=0:raise TimeoutError('TOTAL900')
            directory=out/label;directory.mkdir();tick=time.monotonic();job=helper.WindowsJob();timeout=False
            try:
                with (directory/'stdout.log').open('wb') as stdout,(directory/'stderr.log').open('wb') as stderr:
                    process=subprocess.Popen(list(map(str,command)),cwd=out,env=env,stdout=stdout,stderr=stderr,creationflags=4)
                    job.attach_and_resume(process)
                    try:process.wait(timeout=min(300,remaining))
                    except subprocess.TimeoutExpired:timeout=True;job.terminate();process.wait(timeout=5)
            finally:job.close()
            text=(directory/'stdout.log').read_text(encoding='utf-8',errors='replace')+(directory/'stderr.log').read_text(encoding='utf-8',errors='replace')
            steps.append(dict(name=label,command=list(map(str,command)),cwd=str(out),exit=process.returncode,timeout=timeout,seconds=time.monotonic()-tick,diagnostic=diagnostic,stdout_SHA=sha(directory/'stdout.log'),stderr_SHA=sha(directory/'stderr.log')))
            if timeout or process.returncode!=wanted or (diagnostic and diagnostic not in text):raise ValueError('STEP_FAILED:'+label)
            print(label,process.returncode,flush=True)
        cases=[
            ('transport',None,'tb_output_transport',0,'PASS OUTPUT_TRANSPORT',False),
            ('bad_left','M2_OUTPUT_BAD_LEFT','tb_output_transport',1,'COMMIT_PCM_CLIP_LEDGER_MISMATCH',False),
            ('bad_clip','M2_OUTPUT_BAD_CLIP','tb_output_transport',1,'COMMIT_PCM_CLIP_LEDGER_MISMATCH',False),
            ('real_n32',None,'tb_n32_output_path',0,'PASS N32_PROM_OUTPUT_PATH',True)]
        if args.case=='full32':cases=[('real_n32_full32','M2_OUTPUT_FULL32','tb_n32_output_path',0,'PASS N32_PROM_OUTPUT_PATH',True)]
        if args.case=='subsystem':cases=[
            ('subsystem',None,'tb_n32_output_path',0,'STAT active=32',True),
            ('bad_count','M2_SUBSYSTEM_BAD_COUNT','tb_n32_output_path',1,'SUBSYSTEM_ACTIVE_COUNT_MISMATCH',True),
            ('bad_latency','M2_SUBSYSTEM_BAD_LATENCY','tb_n32_output_path',1,'SUBSYSTEM_FRAME_CREDIT_LATENCY_MISMATCH',True)]
        if args.case=='subsystem_wait':cases=[('subsystem_wait',None,'tb_n32_output_path',0,'STAT active=32',True)]
        for label,macro,top,wanted,diagnostic,real in cases:
            image=out/(label+'.vvp');files=transport+[TB/(top+'.sv')]
            if real:files=sources+[vendor]+files
            command=[CAD/'bin/iverilog.exe','-g2012','-I',ROOT/'code/build/138k_polyphony_resource/prepared/N32_R1_20261011_01/include','-s',top,'-o',image]
            if macro:command+=['-D'+macro]
            if args.case.startswith('subsystem'):command+=['-DM2_OUTPUT_FULL32','-DM2_OUTPUT_SUBSYSTEM']
            if args.case=='subsystem_wait':command+=['-DM2_OUTPUT_READ_SHORT']
            run(label+'_compile',command+files,0)
            run(label+'_simulate',[CAD/'bin/vvp.exe',image],wanted,diagnostic)
        after={p:sha(Path(p)) for p in before}
        if before!=after:raise ValueError('PROTECTED_SOURCE_DRIFT')
        if time.monotonic()-start>=900:raise TimeoutError('TOTAL900_POSTCHECK')
    except Exception as exc:
        error=type(exc).__name__+': '+str(exc)
        if before:after={p:sha(Path(p)) for p in before}
    final=dict(status='PASS' if error is None else 'FAIL_PARTIAL',case=args.case,exit_code=int(error is not None),error=error,total_bound=900,per_step=300,seconds=time.monotonic()-start,steps=steps,source_before=before,source_after=after,new_EDA_calls=0,physical_STA='NOT_RUN',production_connected=False,sound_math_replayed=False)
    (out/'receipt.json').write_text(json.dumps(final,indent=2)+'\n',encoding='utf-8',newline='\n')
    if time.monotonic()-start>=900:
        final.update(status='FAIL_PARTIAL',exit_code=1,error='TOTAL900_RECEIPT_TAIL',seconds=time.monotonic()-start)
        (out/'receipt.json').write_text(json.dumps(final,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:final[k] for k in ['status','exit_code','seconds','error']}));return final['exit_code']


if __name__=='__main__':raise SystemExit(main())
