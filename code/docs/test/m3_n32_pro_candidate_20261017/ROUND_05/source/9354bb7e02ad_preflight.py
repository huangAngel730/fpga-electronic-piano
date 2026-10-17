"""New E4 tool identity preflight; version-only, no compilation or simulation."""
from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import re
import sys
import time

from e4_common import ROOT, DOC, SOFT, identity, write_new

# Import the unchanged Job supervisor only. It writes exclusively caller paths.
HELPERS = ROOT / "code/software/m3_r05_functional_integration_20261015"
sys.path.insert(0,str(HELPERS))
from supervised_process import invoke
from runner import tools_identity, runtime_configuration
from tool_probe_policy import probe_arguments, probe_valid

TOOLS = Path("E:/FPGA/Bpan/modelsim/modelsim1/win64")


def main():
    out = DOC/"PREFLIGHT_01"
    out.mkdir(exist_ok=False,parents=True)
    logs = out/"logs"
    logs.mkdir()
    started = time.monotonic()
    r = {"status":"PREFLIGHT_RUNNING","machine":platform.node(),"python":identity(sys.executable),"python_version":sys.version,"started_utc":datetime.now(timezone.utc).isoformat(),"tool_before":tools_identity(TOOLS),"runtime":runtime_configuration(TOOLS),"helpers":{x:identity(HELPERS/x) for x in ("common.py","supervised_process.py","windows_job.py","runner.py","tool_probe_policy.py","receipt_check.py")},"calls":[],"functional_calls":0,"group_allowance_consumed":False,"board_release_allowed":False}
    env=dict(os.environ)
    pathkey=next((k for k in env if k.upper()=="PATH"),"PATH")
    env[pathkey]=str(TOOLS)+os.pathsep+env.get(pathkey,"")
    code=1
    try:
        for name in ("vlib","vlog","vsim"):
            c=invoke([str(TOOLS/(name+".exe")),*probe_arguments(name)],out,logs,name,started+90,step_budget=30,environment=env)
            r["calls"].append(c)
            raw=Path(c["stdout"]["path"]).read_bytes()+Path(c["stderr"]["path"]).read_bytes()
            if not probe_valid(name,c,raw):
                raise ValueError("BLOCKED_TOOL_PROBE:"+name)
        r["tool_after"]=tools_identity(TOOLS)
        assert r["tool_after"]==r["tool_before"]
        r["status"]="FIXED_MODELSIM_SE64_2020_4_AVAILABLE"
        code=0
    except Exception as exc:
        r.update(status="BLOCKED_TOOL",error=repr(exc))
    r["elapsed_s"]=time.monotonic()-started
    r["exit_code"]=code
    write_new(out/"PREFLIGHT_RECEIPT.json",r)
    print(r["status"],r.get("error",""))
    return code


if __name__=="__main__":
    sys.exit(main())
