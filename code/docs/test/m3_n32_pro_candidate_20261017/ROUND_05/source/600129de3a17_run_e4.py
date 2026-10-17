"""One frozen E4 composition round; fixed ModelSim, Job tree, raw dual streams."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sys
import time

from e4_common import ROOT, DOC, SOFT, identity, write_new
HELPERS = ROOT/"code/software/m3_r05_functional_integration_20261015"
sys.path.insert(0,str(HELPERS))
from supervised_process import invoke
from runner import tools_identity

TOOLS=Path("E:/FPGA/Bpan/modelsim/modelsim1/win64")
FROZEN=ROOT/"code/rtl/138K_try/hold_trials_20261005/L_locations_guard065"
RTL=ROOT/"code/rtl/common/m3_n32_pro_candidate_20261017"
TB=ROOT/"code/tb/audio/m3_n32_pro_candidate_20261017"
BUILD=ROOT/"code/build/138k_polyphony_resource/m3_n32_pro_candidate_20261017"
BAD=re.compile(r"\*\*\s*(?:fatal|error|failure)\b|\berrors\s*:\s*0*[1-9][0-9]*\b",re.I)


def sources():
    contract=ROOT/"code/rtl/common/m3_n32_allocator_candidate_20261013/B/b_n32_c_interface.json"
    old=json.loads(contract.read_text(encoding="utf-8"))
    paths=[]
    for name in old["compile_order"]:
        if name.startswith("<") or name.endswith("b_n32_r1_wrapper.sv"):
            continue
        paths.append(RTL/"b_n32_event_router_e4.sv" if name.endswith("b_n32_event_router.sv") else (Path(name) if ":/" in name else ROOT/name))
    paths += [ROOT/x for x in (
        "code/rtl/common/reset_sync.sv",
        "code/rtl/common/pcm_clip_counter.sv",
        "code/rtl/audio_out/pcm_result_hold.sv",
        "code/rtl/audio_out/pcm_frame_buffer.sv",
        "code/rtl/audio_out/i2s_tx.sv",
        "code/rtl/audio_out/m2_polyphony_frame_candidate_20261012/premixed_frame_adapter.sv",
        "code/rtl/common/visual_mailbox_cdc.sv",
        "code/rtl/common/pcm_waveform_observer_candidate/pcm_frame_observer.sv",
        "code/rtl/common/pcm_waveform_observer_candidate/pcm_waveform_observer_bridge.sv",
        "code/rtl/audio_out/m2_n32_output_candidate_20261013/m2_n32_output_transport.sv")]
    paths += [RTL/"e4_n32_candidate.sv",TB/"tb_e4_n32.sv"]
    assert len({x.name for x in paths})==len(paths)
    return paths


def support():
    files=list(SOFT.glob("*.py"))
    for folder in (ROOT/"code/software/polyphony_scaling_candidate",ROOT/"code/software/audio_math_acceptance_candidate"):
        files += list(folder.glob("*.py"))
    files += list((FROZEN/"rom").glob("*"))+list((FROZEN/"include").glob("*"))
    files += [HELPERS/x for x in ("common.py","supervised_process.py","windows_job.py","runner.py")]
    return [x for x in files if x.is_file()]


def label(path):
    p=Path(path)
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else "vendor/"+p.name


def run(number):
    if not 1<=number<=6 or len(list(DOC.glob("ROUND_*_CONSUMED.json")))>=6:
        raise ValueError("SIX_ROUND_LIMIT")
    # Every later round requires a concrete earlier failure, never a blind rerun.
    if number>1:
        previous=json.loads((DOC/f"ROUND_{number-1:02d}/RUN_RECEIPT.json").read_text(encoding="utf-8"))
        assert previous["status"]!="E4_SCOPED_COMPOSITION_AND_NEGATIVES_PASS"
        assert (DOC/f"REPAIR_{number:02d}.json").is_file()
    out=DOC/f"ROUND_{number:02d}"
    out.mkdir(exist_ok=False)
    start=time.monotonic()
    deadline=start+890  # reserve ten seconds for immutable identity/receipt cleanup
    probe=json.loads((DOC/"PREFLIGHT_01/PREFLIGHT_RECEIPT.json").read_text(encoding="utf-8"))
    assert probe["status"]=="FIXED_MODELSIM_SE64_2020_4_AVAILABLE"
    before=tools_identity(TOOLS)
    assert before==probe["tool_before"]
    source_paths=sources()
    allpaths=sorted(set(source_paths+support()))
    initial={label(x):identity(x) for x in allpaths}
    r={"schema":"M3_E4_FROZEN_COMPOSITION_ROUND_V1","status":"PREPARING","baseline_head":"ad2de2169230dc8fd9f4b6f8157d384306c2479a","round":number,"machine":platform.node(),"started_utc":datetime.now(timezone.utc).isoformat(),"python":identity(sys.executable),"python_version":sys.version,"source_before":initial,"tool_before":before,"tool_probe":identity(DOC/"PREFLIGHT_01/PREFLIGHT_RECEIPT.json"),"functional_attempt_consumed":False,"single_tool_budget_s":300,"group_budget_s":900,"python_group_budget_s":90,"calls":[],"cases":[],"source_snapshots":{},"physical_calls":0,"board_release_allowed":False}
    snapshot=out/"source"
    snapshot.mkdir()
    for key,info in initial.items():
        tag=info["sha256"][:12]+"_"+Path(info["path"]).name
        target=snapshot/tag
        if not target.exists():
            shutil.copyfile(info["path"],target)
        assert identity(target)["sha256"]==info["sha256"]
        r["source_snapshots"][key]=identity(target)
    stage=out/"stage"
    stage.mkdir()
    # Preserve source bytes; pROM contents are constant INIT_RAM words.
    # No absolute-path replacements and no ROM regeneration.
    for p in source_paths:
        shutil.copyfile(p,stage/p.name)
    for name in ("rom","include"):
        (stage/name).mkdir()
        for p in (FROZEN/name).glob("*"):
            if p.is_file():
                shutil.copyfile(p,stage/name/p.name)
    (stage/"compile.f").write_text("\n".join((stage/p.name).as_posix() for p in source_paths)+"\n",encoding="utf-8",newline="\n")
    r["stage_before"]={p.relative_to(stage).as_posix():identity(p) for p in stage.rglob("*") if p.is_file()}
    plan_path=DOC/f"CASE_PLAN_R{number:02d}.json"
    if not plan_path.is_file():
        plan_path=DOC/"CASE_PLAN.json"
    plan=json.loads(plan_path.read_text(encoding="utf-8"))
    r["case_plan"]=identity(plan_path)
    r["case_plan_body"]=plan
    r["authorization"]=identity(ROOT/"code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/task2_coordinator/NIGHT_PLAN_20261017_TASK2.md")
    r["budget_revision"]=identity(ROOT/"code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/task2_coordinator/BUDGET_REVISION_E4.json")
    r["stage"]=str(stage)
    write_new(out/"PREFLIGHT.json",r)
    env=dict(os.environ)
    key=next((x for x in env if x.upper()=="PATH"),"PATH")
    env[key]=str(TOOLS)+os.pathsep+env.get(key,"")
    python_deadline=None
    code=1
    def created(pid):
        if not r["functional_attempt_consumed"]:
            write_new(DOC/f"ROUND_{number:02d}_CONSUMED.json",{"round":number,"pid":pid,"preflight":identity(out/"PREFLIGHT.json"),"authorization":r["authorization"],"new_batch":True})
            r["functional_attempt_consumed"]=True
    def command(argv,cwd,logs,tag,cap=300):
        c=invoke(argv,cwd,logs,tag,deadline,step_budget=cap,environment=env,on_created=created)
        r["calls"].append(c)
        if c["timeout"] or c["error"] or c["log_limit_exceeded"]:
            raise ValueError("PROCESS_FAILURE:"+tag+":"+str(c["error"]))
        return c
    def text_of(call):
        return (Path(call["stdout"]["path"]).read_bytes()+b"\n"+Path(call["stderr"]["path"]).read_bytes()).decode("utf-8",errors="replace")
    try:
        for case in plan["cases"]:
            case_out=out/case["name"]
            case_out.mkdir()
            work=case_out/"work"
            logs=case_out/"logs"
            logs.mkdir()
            reused=case.get("reuse_simulation")
            reuse_binding=None
            if reused:
                origin_receipt=DOC/reused["receipt_relative"]
                assert identity(origin_receipt)["sha256"]==reused["receipt_sha256"]
                old=json.loads(origin_receipt.read_text(encoding="utf-8"))
                assert old["tool_before"]==old["tool_after"]==before
                for p in source_paths:
                    assert old["source_before"][label(p)]==identity(p)
                for p in support():
                    if not p.is_relative_to(SOFT):
                        assert old["source_before"][label(p)]==identity(p)
                sim=old["calls"][reused["simulation_call_index"]]
                assert sim["exit_code"]==0 and not sim["timeout"] and not sim["error"]
                for stream in ("stdout","stderr"):
                    assert identity(sim[stream]["path"])==sim[stream]
                reuse_binding={"receipt":identity(origin_receipt),"sim_call":sim,"source_policy":"ALL_COMPILED_HDL_ROM_INCLUDE_AND_REFERENCE_MODEL_BYTES_MATCH_CURRENT; checker-only repair","new_compile_calls":0,"new_simulation_calls":0}
            else:
                vlib=command([str(TOOLS/"vlib.exe"),"work"],case_out,logs,"vlib")
                if vlib["exit_code"]!=0 or BAD.search(text_of(vlib)):
                    raise ValueError("VLIB_NOT_PASS")
                args=[str(TOOLS/"vlog.exe"),"-sv","+incdir+"+(stage/"include").as_posix(),f"+define+B2C_N={case['n']}"]
                args += ["+define+"+x for x in case.get("defines",[])]
                args += ["-f",str(stage/"compile.f")]
                compile_call=command(args,case_out,logs,"vlog")
                if compile_call["exit_code"]!=0 or BAD.search(text_of(compile_call)):
                    raise ValueError("VLOG_NOT_PASS:"+case["name"])
                args=[str(TOOLS/"vsim.exe"),"-c","work.tb_e4_n32",*case.get("plusargs",[]),"-do","run -all; quit -f"]
                sim=command(args,case_out,logs,"vsim")
            raw=text_of(sim)
            expected=case.get("rtl_rejection")
            result={"case":case,"compile":None if reused else len(r["calls"])-2,"simulate":None if reused else len(r["calls"])-1,"sim_stdout":sim["stdout"],"reuse_binding":reuse_binding}
            if expected:
                failures=[]
                for line_number,line in enumerate(raw.splitlines(),1):
                    m=re.match(r"\s*(?:#\s*)?\*\*\s*(Fatal|Error|Failure):\s*(.*)",line,re.I)
                    if m:
                        failures.append({"line":line_number,"severity":m.group(1).upper(),"message":m.group(2),"raw":line})
                # Fixed ModelSim run-all/quit-f policy: handled $fatal yields
                # process exit0. A crash/nonzero/other tool error is not a test.
                if sim["exit_code"]!=0 or len(failures)!=1 or failures[0]["severity"]!="FATAL" or not re.match(re.escape(expected)+r"(?:\b|$)",failures[0]["message"]):
                    raise ValueError("TARGET_RTL_REFUSAL_MISSING:"+case["name"])
                if re.search(r"access violation|segmentation fault|license checkout failed|internal error|WinError",raw,re.I):
                    raise ValueError("ABNORMAL_TOOL_FAILURE_NOT_NEGATIVE_PASS:"+case["name"])
                result.update(status="ACTUAL_RTL_TARGET_REJECTED",diagnostic=expected,first_failure=failures[0],required_modelsim_exit_code=0)
            else:
                if sim["exit_code"]!=0 or BAD.search(raw) or not re.search(rf"(?m)^(?:#\s*)?PASS E4_N{case['n']}_ISOLATED_FROZEN_PIANO_NOT_PRO_DUT\s*$",raw):
                    raise ValueError("SIM_NOT_PASS:"+case["name"])
                # At most 90s cumulative Python check time, including this call.
                used=sum(x["elapsed_s"] for x in r["calls"] if Path(x["argv"][0]).name.lower().startswith("python"))
                if used>=90:
                    raise ValueError("PYTHON_GROUP_BUDGET")
                report=case_out/"CHECK_RESULT.json"
                check=command([sys.executable,"-X","utf8",str(SOFT/"check_e4.py"),"--input",sim["stdout"]["path"],"--output",str(report),"--n",str(case["n"])],ROOT,logs,"check",cap=90-used)
                result["check_result"]=identity(report) if report.is_file() else None
                result["check_call"]=len(r["calls"])-1
                expected_check=case.get("checker_rejection")
                if expected_check:
                    checked=json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
                    if check["exit_code"]!=1 or checked.get("reason")!=expected_check:
                        result["status"]="TARGET_CHECKER_REFUSAL_MISSING"
                        r["cases"].append(result)
                        raise ValueError("TARGET_CHECKER_REFUSAL_MISSING:"+case["name"])
                    result.update(status="ACTUAL_RTL_MUTANT_INDEPENDENTLY_REJECTED",diagnostic=expected_check)
                elif check["exit_code"]!=0:
                    result["status"]="INDEPENDENT_CHECK_FAILED"
                    r["cases"].append(result)
                    raise ValueError("CHECK_NOT_PASS:"+case["name"])
                else:
                    result["status"]="REAL_RTL_AND_INDEPENDENT_CHECK_PASS"
            r["cases"].append(result)
        r["status"]="E4_SCOPED_COMPOSITION_AND_NEGATIVES_PASS"
        code=0
    except Exception as exc:
        r.update(status="FAILED_STOP_ORIGINALS_PRESERVED",error=repr(exc))
    r["source_after"]={key:identity(v["path"]) for key,v in initial.items()}
    r["tool_after"]=tools_identity(TOOLS)
    r["stage_after"]={key:identity(stage/key) for key in r["stage_before"]}
    if r["source_before"]!=r["source_after"] or r["tool_before"]!=r["tool_after"] or r["stage_before"]!=r["stage_after"]:
        r.update(status="IDENTITY_DRIFT",preceding_error=r.get("error"))
        code=1
    r["elapsed_s"]=time.monotonic()-start
    r["ended_utc"]=datetime.now(timezone.utc).isoformat()
    r["exit_code"]=code
    write_new(out/"RUN_RECEIPT.json",r)
    print(json.dumps({"status":r["status"],"round":number,"elapsed_s":r["elapsed_s"],"cases":len(r["cases"]),"error":r.get("error"),"receipt":identity(out/"RUN_RECEIPT.json")}))
    return code


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--round",type=int,required=True)
    sys.exit(run(p.parse_args().round))
