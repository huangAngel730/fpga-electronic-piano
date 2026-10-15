"""Read-only historical audit and ZIP sealing. No RTL subprocess is reachable.

Added after R04: this file has NOT been validated by any historical RTL run.
It cannot grant, replenish or consume a simulation allowance.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
DOC=ROOT/"code/docs/test/m3_40mhz_pcm_i2s_latency_20261015"
TB=ROOT/"code/tb/audio_out/m3_40mhz_pcm_i2s_latency_20261015"
R05=ROOT/"code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_R05_XSAFE_ModelSim输入_20261015.zip"
AUTH_NAMES=("M3_四项并行主责授权_2026-10-15.md","M3_夜间M2候选权限预授权_2026-10-15.md","M3_夜间八小时任务单_2026-10-15.md")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(); out=args.output.resolve()
    if out.parent!=DOC.resolve():
        raise SystemExit("OUTPUT_OUTSIDE_WRITESET")
    out.mkdir(parents=False,exist_ok=False)
    git_calls=[]
    def git(name,arguments):
        p=subprocess.run(["git"]+arguments,cwd=ROOT,capture_output=True,timeout=30)
        (out/(name+".stdout")).write_bytes(p.stdout)
        (out/(name+".stderr")).write_bytes(p.stderr)
        git_calls.append({"argv":["git"]+arguments,"cwd":str(ROOT),"exit_code":p.returncode,"timeout":False,"stdout_sha256":digest(p.stdout),"stderr_sha256":digest(p.stderr)})
        if p.returncode:
            raise RuntimeError("READ_ONLY_GIT_FAILED:"+name)
        return p.stdout
    head=git("current_head",["rev-parse","HEAD"]).decode().strip()
    original_auth=git("initial_authority",["show","874c097d34140b120d52eaadd9748dd6ae8d5894:code/docs/M3_四项并行主责授权_2026-10-15.md"])
    git("night_authority_history",["log","--format=%H %cI %s","--","code/docs/M3_夜间M2候选权限预授权_2026-10-15.md"])
    authority=[]
    for name in AUTH_NAMES:
        p=ROOT/"code/docs"/name
        raw=p.read_bytes(); (out/name).write_bytes(raw)
        authority.append({"path":str(p.relative_to(ROOT)),"bytes":len(raw),"sha256":digest(raw)})
    (out/"INITIAL_AUTHORITY_874c097.md").write_bytes(original_auth)
    rounds=[]; categories=Counter(); all_calls=[]
    for name in ("R01","R02","R03","R04"):
        run=DOC/name
        raw=(run/"RUN_RECEIPT.json").read_bytes(); receipt=json.loads(raw)
        assert receipt["inputs_stable"] and receipt["before"]==receipt["after"]
        assert not any(call["timeout"] for call in receipt["calls"])
        assert receipt["elapsed_seconds"]<=300
        for call in receipt["calls"]:
            assert digest((run/(call["name"]+".stdout")).read_bytes())==call["stdout_sha256"]
            assert digest((run/(call["name"]+".stderr")).read_bytes())==call["stderr_sha256"]
            assert call["elapsed_seconds"]<=90
            kind=("VERSION" if call["name"].endswith("version") else
                  "RTL_COMPILE" if call["name"].endswith("compile") else
                  "RTL_SIMULATE" if call["name"].endswith("simulate") else "SOFTWARE")
            categories[kind]+=1
            all_calls.append({"run":name,"category":kind,**call})
        stage=receipt["stage_sha"]
        assert all(digest((run/"stage"/n).read_bytes())==s for n,s in stage.items())
        rounds.append({"run":name,"receipt_sha256":digest(raw),"filesystem_last_write_local":__import__('datetime').datetime.fromtimestamp((run/"RUN_RECEIPT.json").stat().st_mtime).isoformat(),"elapsed_seconds":receipt["elapsed_seconds"],"passed":receipt["passed"],"exit_code":receipt["exit_code"],"failure":receipt.get("failure"),"actual_child_invocations":receipt["actual_child_invocations"],"source_sha256":{Path(p).name:row["sha256"] for p,row in receipt["before"].items() if "latency_20261015" in p},"stage_sha256":stage})
    # Preserve earliest checker bytes reconstructed by reversing the one known
    # local diff, but label it DERIVED, not an original contemporaneous file.
    latest=(HERE/"check_capture.py").read_text(encoding="utf-8")
    new='''                    # The first complete WS-high half precedes the first full
                    # frame_tick. It is reset silence, not a manufactured PCM.
                    adoption=choices[pos] if pos>=0 else {"cycle":0,"pcm":(0,0),"id":None,"clip":0,"frame":0}
'''
    old='''                    require(pos>=0,"SERIAL_WITHOUT_ADOPTION")
                    adoption=choices[pos]
'''
    assert latest.count(new)==1
    reconstructed=latest.replace(new,old).encode("utf-8")
    assert digest(reconstructed)==rounds[0]["source_sha256"]["check_capture.py"]
    (out/"DERIVED_R01_R03_check_capture.py.txt").write_bytes(reconstructed)
    # Current tested files must still match R04. New audit/docs are separately
    # static and cannot acquire the old run's validation by inclusion in ZIP.
    r04=json.loads((DOC/"R04/RUN_RECEIPT.json").read_text(encoding="utf-8"))
    for p in (HERE/"check_capture.py",HERE/"run.py",HERE/"test_capture.py",TB/"tb_public_serial.sv"):
        assert digest(p.read_bytes())==r04["before"][str(p)]["sha256"]
    good=json.loads((DOC/"R04/normal/CHECK.json").read_text(encoding="utf-8"))
    bad=json.loads((DOC/"R04/wrong_stereo/CHECK.json").read_text(encoding="utf-8"))
    tests=json.loads((DOC/"R04/software_cases/RESULTS.json").read_text(encoding="utf-8"))
    assert good["passed"] and bad["diagnostic"]=="SERIAL_PCM_LSBJ_OR_STEREO"
    assert len(tests)==20 and all(x["passed"] for x in tests)
    assert digest((DOC/"R04/normal/capture.csv").read_bytes())==good["capture_sha256"]
    ledger_status=dict(Counter(row["status"] for row in good["request_ledger"]))
    audit={"schema":"C_HISTORICAL_AUDIT_V1","head_at_audit":head,"initial_runtime_head":"874c097d34140b120d52eaadd9748dd6ae8d5894","current_authority_inputs":authority,"historical_initial_authority_sha256":digest(original_auth),"rounds":rounds,"all_calls":all_calls,"call_categories":dict(categories),"historical_child_invocations":len(all_calls),"historical_iverilog_compilations":categories["RTL_COMPILE"],"historical_vvp_simulations":categories["RTL_SIMULATE"],"historical_simulation_seconds":sum(c["elapsed_seconds"] for c in all_calls if c["category"]=="RTL_SIMULATE"),"historical_simulation_timeouts":0,"read_only_git_calls_during_audit":git_calls,"new_rtl_invocations_this_audit":0,"real_r05_modelsim_invocations":0,"gowin_invocations":0,"device_operations":0,"authority_accounting":{"initial_four_pack_C":"Original 874c097 C authorization permits bounded new isolated software/module runs; no two-group quota appears in that version.","night_two_group_rule":"First published by 6d6c726 at local Git commit time 2026-10-15T23:52:02+08:00. Historical R01-R04 receipt filesystem times are 22:21:04 through 22:24:22, under initial delegation. Times are historical evidence, not a cryptographically trusted execution timestamp.","no_replenishment":"Do not reset, erase or recast the four historical rounds as two. Parent instructed no new RTL after recovery. New RTL groups run under night rule by this C window: 0. This audit grants no remaining allowance.","accounting_owner":"Primary coordinator; all C windows share one history. Any interpretation of historical limit changes belongs to M2/user, not the checker."},"result":{"new_module_fixture":"PASS_R04_ONLY","earliest_history":"R01_ACCESS_VIOLATION_R02_INITIAL_RESET_X_R03_STARTUP_HALF_ORACLE_FAILURE_RETAINED","software_cases_passed":20,"decoded_stereo_frames":good["decoded_stereo_frames"],"normal_capture_sha256":good["capture_sha256"],"request_statuses":ledger_status,"digital_latency_max_cycles":good["max_digital_request_to_serial_cycles"],"digital_latency_scope":"136 serial-observed requests only; four adopted tail requests lack complete serial observation; two intentionally expired requests are not new publications.","analog_latency":"UNKNOWN","r05_true_chain":"UNKNOWN_NO_PUBLIC_TRACE","physical_sta":"NOT_EXECUTED","clip":"Observer source metadata only; frozen pcm_frame_buffer/i2s_tx have no clip output port, so no physical clip propagation claim.","board_release_allowed":False},"selfreview":{"tested_sources_unchanged_from_R04":True,"added_audit_script":"STATIC_PLUS_SOFTWARE_SEAL_INTEGRITY_ONLY_NOT_RTL_TESTED","prior_checker_reconstruction":"Derived byte-identical reversal SHA verified; contemporaneous original software file was not separately frozen before R01-R03; receipt SHA and raw logs are original."}}
    audit["inventory_probe_outside_runner"]={"argv":["E:/FPGA/GAOYUNFPGA/138K/tools/icarus_oss_copy/bin/iverilog.exe","-V"],"known_invocations":1,"exit_code_from_shell":0,"local_separate_stdout_stderr":"NOT_FROZEN; tool conversation has combined original output. Not counted in the 22 runner children, not an RTL compile/run."}
    audit["known_iverilog_vvp_invocations_including_inventory"]=categories["VERSION"]+categories["RTL_COMPILE"]+categories["RTL_SIMULATE"]+1
    write_json(out/"NIGHT_RUN_RECEIPT.json",audit)
    candidates=[]
    for base in (HERE,TB,DOC):
        for p in base.rglob("*"):
            prior_seal=base==DOC and p.relative_to(DOC).parts[0].startswith("SEAL_")
            if p.is_file() and not p.is_relative_to(out) and not prior_seal and "__pycache__" not in p.parts:
                candidates.append(p)
    candidates += [p for p in out.rglob("*") if p.is_file()]
    manifest={str(p.relative_to(ROOT)).replace("\\","/"):{"bytes":p.stat().st_size,"sha256":digest(p.read_bytes())} for p in sorted(candidates)}
    write_json(out/"MANIFEST.json",manifest)
    package=out/"M3_C_PCM_SERIAL_MODULE_HISTORY_20261016.zip"
    with zipfile.ZipFile(package,"x",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(candidates): z.write(p,str(p.relative_to(ROOT)).replace("\\","/"))
        z.write(out/"MANIFEST.json","MANIFEST.json")
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        for name,row in manifest.items():
            data=z.read(name)
            assert len(data)==row["bytes"] and digest(data)==row["sha256"]
    result={"passed":True,"package":str(package),"bytes":package.stat().st_size,"sha256":digest(package.read_bytes()),"payload_files":len(manifest),"historical_processes":len(all_calls),"new_rtl_invocations":0,"board_release_allowed":False}
    write_json(out/"SEAL_RECEIPT.json",result)
    print(json.dumps(result))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
