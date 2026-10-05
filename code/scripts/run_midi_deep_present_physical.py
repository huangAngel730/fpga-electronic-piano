"""One PnR after synthesis budget screening. Original constraints/options frozen."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
ROOT=Path(__file__).resolve().parents[2]
GOWIN=Path(r"D:\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64\IDE\bin\gw_sh.exe")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def resources(p):
    s=p.read_text(encoding="utf-8")
    def number(pattern):
        match=re.search(pattern,s,re.S)
        if not match:raise ValueError("missing resource "+pattern)
        return int(match[1])
    result={"Logic":number(r'class="label">Logic</td>\s*<td>(\d+)'),"Register":number(r'class="label"><b>Register\s*</b></td>\s*<td>(\d+)'),"BSRAM":number(r'class="label"><b>BSRAM\s*</b></td>\s*<td>(\d+)')}
    section=re.search(r'<b>DSP\s*</b>(.*?)<b>BSRAM\s*</b>',s,re.S)
    if not section:raise ValueError("no DSP primitive section")
    result["DSP_primitives"]={name:int(value) for name,value in re.findall(r'<td class="label">(?:&nbsp)*([^<]+)</td>\s*<td>(\d+)</td>',section[1])}
    if not result["DSP_primitives"]:raise ValueError("unknown DSP primitive counts")
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument("folder",type=Path);a=ap.parse_args();folder=a.folder.resolve();folder.relative_to(ROOT/"code/output")
    assert (folder/"synthesis_exit.txt").read_text().strip()=="0","synthesis not completed successfully"
    assert not (folder/"pnr_started.json").exists(),"one effective PnR only"
    fair=json.loads((folder/"fairness.json").read_text(encoding="utf-8"));base=Path(fair["baseline_project"]).parent
    for key in ["all_baseline_source_sha","unchanged_headers","ROM_sha","new_sources"]:
        for name,h in fair[key].items():assert sha(Path(name))==h,name
    rpt=Path("impl/gwsynthesis/audio_visual_coexistence_top_syn.rpt.html")
    old=resources(base/rpt);new=resources(folder/rpt)
    delta={k:new[k]-old[k] for k in ["Logic","Register","BSRAM"]}
    checks={"logic_budget256":delta["Logic"]<=256,"register_budget512":delta["Register"]<=512,"BSRAM_no_increase":delta["BSRAM"]<=0,"DSP_primitives_identical":new["DSP_primitives"]==old["DSP_primitives"]}
    budget={"before":old,"after":new,"delta":delta,"checks":checks,"synthesis_only_not_STA":True}
    (folder/"synthesis_budget.json").write_text(json.dumps(budget,indent=2)+"\n",encoding="utf-8");print(json.dumps(budget,indent=2),flush=True)
    if not all(checks.values()):
        result={"complete":False,"reason":"synthesis cost exceeds approved screen; no PnR started","effective_PnR_runs":0,"budget":budget,"retain_baseline":True}
        (folder/"bounded_build_result.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8");return 0
    started=time.monotonic()
    with (folder/"build.log").open("wb") as stream:
        proc=subprocess.Popen([str(GOWIN),str(folder/"run_pnr.tcl")],cwd=folder,stdout=stream,stderr=subprocess.STDOUT)
        (folder/"pnr_started.json").write_text(json.dumps({"pid":proc.pid,"one_effective_PnR":True,"wall_limit_seconds":1800})+"\n")
        timed_out=False
        try:code=proc.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            timed_out=True
            # Native PowerShell only stops this recorded process and descendants.
            # No filesystem operations or computed deletion paths.
            command="$all=Get-CimInstance Win32_Process; $ids=@("+str(proc.pid)+"); for($round=0;$round -lt 6;$round++){ $more=@($all | Where-Object { $_.ParentProcessId -in $ids } | Select-Object -ExpandProperty ProcessId); $ids=@($ids+$more | Select-Object -Unique) }; foreach($taskId in ($ids | Sort-Object -Descending)){ Stop-Process -Id $taskId -Force -ErrorAction Continue }"
            stopped=subprocess.run(["powershell","-NoProfile","-Command",command],capture_output=True,timeout=30)
            (folder/"timeout_process_stop.log").write_bytes(stopped.stdout+stopped.stderr)
            try:code=proc.wait(timeout=10)
            except subprocess.TimeoutExpired:code=-1
        result={"complete":not timed_out and code==0 and (folder/"impl/pnr/audio_visual_coexistence_top_tr_content.html").exists(),"exit":code,"timed_out":timed_out,"elapsed_seconds":time.monotonic()-started,"effective_PnR_runs":1,"wall_limit_seconds":1800,"no_auto_retry":True,"latest_features_not_included":True,"programmed":False}
        (folder/"build_exit.txt").write_text(str(code))
        (folder/"bounded_build_result.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(result,indent=2),flush=True)
    return 0
if __name__=="__main__":raise SystemExit(main())
