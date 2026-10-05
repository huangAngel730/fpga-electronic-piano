"""Run one sequential source-built pair with 1800s bound per arm, no retry."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import time
ROOT=Path(__file__).resolve().parents[2]
GW=Path(r"D:\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64\IDE\bin\gw_sh.exe")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def freeze_check(out,freeze):
    for name,h in freeze["original_input_files"].items():assert sha(Path(name))==h,name
    for arm,v in freeze["arms"].items():
        folder=Path(v["folder"]);mf=folder/"input_manifest.json";assert sha(mf)==v["manifest_sha256"]
        m=json.loads(mf.read_text(encoding="utf-8"))
        for i in m["all_input_files"]:assert sha(Path(i["actual_source"]))==i["actual_sha"],i["actual_source"]
        assert sha(folder/"run.tcl")==v["tcl_sha256"]
def stop_tree(pid,folder):
    command="$items=Get-CimInstance Win32_Process; $ids=@("+str(pid)+"); for($r=0;$r -lt 8;$r++){ $children=@($items | Where-Object { $_.ParentProcessId -in $ids } | Select-Object -ExpandProperty ProcessId); $ids=@($ids+$children | Select-Object -Unique) }; foreach($taskId in ($ids | Sort-Object -Descending)){ Stop-Process -Id $taskId -Force -ErrorAction Continue }"
    p=subprocess.run(["powershell","-NoProfile","-Command",command],capture_output=True,timeout=30)
    (folder/"process_stop.log").write_bytes(p.stdout+p.stderr)
    return p.returncode

def main():
    ap=argparse.ArgumentParser();ap.add_argument("folder",type=Path);a=ap.parse_args();out=a.folder.resolve();out.relative_to(ROOT/"code/output")
    assert not (out/"pair_started.json").exists(),"exactly once; no automatic retry"
    freeze=json.loads((out/"AB_freeze.json").read_text(encoding="utf-8"));freeze_check(out,freeze)
    now=datetime.now().astimezone().isoformat()
    (out/"pair_started.json").write_text(json.dumps({"started":now,"phase_order":freeze["phase_order"],"arm_limit_seconds":1800,"no_auto_retry":True})+"\n")
    results={}
    for arm in freeze["phase_order"]:
        folder=out/arm;assert not (folder/"impl").exists(),"not a fresh build"
        freeze_check(out,freeze)
        started=time.monotonic();stamp=datetime.now().astimezone().isoformat();timed_out=False
        with (folder/"build.log").open("wb") as f:
            p=subprocess.Popen([str(GW),str(folder/"run.tcl")],cwd=folder,stdout=f,stderr=subprocess.STDOUT)
            process={"pid":p.pid,"started":stamp,"command":[str(GW),str(folder/"run.tcl")],"arm":arm,"route_option":freeze["arms"][arm]["route_option"]}
            (folder/"process.json").write_text(json.dumps(process,indent=2)+"\n");print("START",arm,"PID",p.pid,"route",process["route_option"],flush=True)
            try:code=p.wait(timeout=1800)
            except subprocess.TimeoutExpired:
                timed_out=True
                cleanup=stop_tree(p.pid,folder)
                if cleanup!=0:
                    # This only stops the same owned process; never retries build.
                    p.kill()
                try:code=p.wait(timeout=10)
                except subprocess.TimeoutExpired:code=-1
        ended=datetime.now().astimezone().isoformat();elapsed=time.monotonic()-started
        complete=not timed_out and code==0 and (folder/"impl/pnr/audio_visual_coexistence_top_tr_content.html").exists()
        result={"started":stamp,"ended":ended,"elapsed_seconds":elapsed,"exit":code,"timed_out":timed_out,"complete":complete,"source_run_count":1,"STA_pass_not_assumed":True,"route_option":process["route_option"],"build_log_sha256":sha(folder/"build.log"),"programmed":False}
        (folder/"build_exit.txt").write_text(str(code));(folder/"bounded_build_result.json").write_text(json.dumps(result,indent=2)+"\n");results[arm]=result
        (out/"pair_progress.json").write_text(json.dumps({"results":results,"active":None,"not_adopted":True},indent=2)+"\n")
        print("END",arm,json.dumps(result),flush=True)
        freeze_check(out,freeze)
    (out/"pair_complete.json").write_text(json.dumps({"results":results,"both_complete":all(r["complete"] for r in results.values()),"no_auto_adoption":True,"no_retry":True},indent=2)+"\n")
    print("PAIR ENDED. Independent full STA/physical comparison still required.",flush=True)
if __name__=="__main__":main()
