"""Run PC codec -> original UART -> T057 candidate RTL, independently adjudicate."""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
TB = ROOT/"code/tb/input/score_transfer_candidate"
RTL = ROOT/"code/rtl/input/score_transfer_candidate/score_transfer_candidate.sv"
SOFTWARE = ROOT/"code/software/score_transfer_v1"
DOCS = ROOT/"code/docs/hardware/score_transfer_v1"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+"\n", encoding="utf-8", newline="\n")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def io_path(path):
    value=str(path.absolute())
    return Path("\\\\?\\"+value) if os.name=="nt" and len(value)>=248 else path


def gate_snapshot(out, run):
    """Run unmodified repository gate without writes outside task's output tree."""
    mirror=out/"repo_gate_snapshot"
    mirror.mkdir()
    tracked=subprocess.check_output(["git","-c","core.quotepath=false","ls-files","-z"],cwd=ROOT)
    paths=[Path(p) for p in tracked.decode("utf-8").split("\0") if p]
    for task_root in (SOFTWARE,TB,RTL.parent,DOCS):
        paths.extend(p.relative_to(ROOT) for p in task_root.rglob("*")
                     if p.is_file() and "runs" not in p.parts and "__pycache__" not in p.parts)
    paths.append(Path(__file__).relative_to(ROOT))
    hashes={}
    for relative in sorted(set(paths)):
        source=io_path(ROOT/relative)
        if not source.is_file():
            raise ValueError(f"missing gate input {relative}")
        target=io_path(mirror/relative); target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        if target.read_bytes()!=source.read_bytes():
            raise ValueError("gate snapshot mismatch")
        hashes[relative.as_posix()]=sha(source.read_bytes())
    if run("gate_init",["git","init","--quiet"],mirror,30)[0]:
        raise ValueError("gate init failed")
    if run("gate_stage",["git","-c","core.longpaths=true","add","-A"],mirror,60)[0]:
        raise ValueError("gate stage failed (see original stderr)")
    dump(out/"gate_sources.json",hashes)
    code,log=run("check_repo",["powershell","-NoProfile","-ExecutionPolicy","Bypass","-File",
                              mirror/"code/scripts/check_repo.ps1"],mirror,timeout=1200)
    for relative,digest in hashes.items():
        if sha(io_path(ROOT/relative).read_bytes())!=digest or sha(io_path(mirror/relative).read_bytes())!=digest:
            raise ValueError("gate source changed: "+relative)
    return code,log


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelsim-bin",type=Path,default=Path("E:/FPGA/Bpan/modelsim/modelsim1/win64"))
    parser.add_argument("--repo-gate",action="store_true")
    parser.add_argument("--repo-gate-only",action="store_true",help="supplemental snapshot gate only; no T057 functional PASS")
    parser.add_argument("--publish",action="store_true",help="save original raw bytes as Base64 in authorized evidence")
    parser.add_argument("--check-capture",type=Path)
    parser.add_argument("--expected",type=Path)
    args=parser.parse_args()
    checker=load(TB/"check_capture.py","t057_checker")
    if args.check_capture:
        if not args.expected:
            parser.error("--expected required")
        print(json.dumps(checker.check(args.check_capture,args.expected))); return 0
    vectors=load(TB/"vectors.py","t057_vectors")
    output_root=TB/"runs"; output_root.mkdir(exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix="run_",dir=output_root))
    print(f"T057 OUTPUT {out}",flush=True)
    records=[]

    def run(label, command, cwd=out, timeout=900):
        command=[str(x) for x in command]
        start=time.monotonic()
        environment=os.environ.copy()
        runtime=Path(sys.executable).parent
        environment["PATH"]=str(runtime)+os.pathsep+environment.get("PATH","")
        result=subprocess.run(command,cwd=cwd,env=environment,capture_output=True,timeout=timeout)
        (out/(label+".stdout.bin")).write_bytes(result.stdout)
        (out/(label+".stderr.bin")).write_bytes(result.stderr)
        records.append(dict(label=label,command=command,exit_code=result.returncode,
                            seconds=round(time.monotonic()-start,3)))
        print(f"{label}: exit={result.returncode} {records[-1]['seconds']}s",flush=True)
        return result.returncode,result.stdout.decode("utf-8",errors="replace")

    result=dict(schema=1,base_commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT).decode().strip(),
                actual_level="L2/limited L3 PC codec and serial RTL simulation",
                programmed=False,hardware_verified=False,repo_gate=False,output=out.name)
    if args.repo_gate_only:
        result["actual_level"]="repository gate only; no new T057 functional acceptance"
        try:
            code,log=gate_snapshot(out,run)
            result["repo_gate"]=code==0 and "All repository checks passed." in log
            result["status"]="PASS" if result["repo_gate"] else "FAIL"
            result["gate_files"]=len(json.loads((out/"gate_sources.json").read_text()))
        except Exception as exc:
            result["status"]="FAIL"; result["error"]=str(exc)
        result["commands"]=records; dump(out/"receipt.json",result)
        print(json.dumps(result,ensure_ascii=False)); return 0 if result["status"]=="PASS" else 1
    try:
        tools={name:args.modelsim_bin/(name+".exe") for name in ("vlib","vlog","vsim")}
        if not all(p.is_file() for p in tools.values()):
            raise FileNotFoundError("ModelSim not found; no simulated PASS")
        if run("version",[tools["vsim"],"-version"],timeout=30)[0]:
            raise ValueError("version command failed")
        expectation=vectors.build(out)
        sources=[ROOT/"code/rtl/common/uart_rx.sv",ROOT/"code/rtl/common/uart_tx.sv",RTL,TB/"tb_score_transfer.sv"]
        source_files=sources+[SOFTWARE/"score_transfer.py",TB/"vectors.py",TB/"check_capture.py",
                              TB/"test_software.py",TB/"test_capture.py",TB/"test_cli_failures.py",
                              Path(__file__),DOCS/"PROTOCOL.md"]
        dump(out/"source_manifest.json",{p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in source_files})
        unit=run("software_tests",[sys.executable,"-B","-X","utf8",TB/"test_software.py"])
        if unit[0]:
            raise ValueError("software tests failed")
        if run("pc_cli_rejection",[sys.executable,"-B","-X","utf8",TB/"test_cli_failures.py",out/"cli_negative"])[0]:
            raise ValueError("actual PC CLI negative failed")
        if run("pc_encode",[sys.executable,"-B","-X","utf8",SOFTWARE/"score_transfer.py","encode",
                             "--score",out/"score16.json","--output",out/"pc_encoded"])[0]:
            raise ValueError("real PC CLI failed")
        if len((out/"pc_encoded/records.bin").read_bytes())!=4096:
            raise ValueError("PC capacity encoding missing")
        for label, define in (("normal",None),("offset_mutant","MUTANT_OFFSET"),
                               ("crc_mutant","MUTANT_SKIP_SCORE_CRC")):
            folder=out/label; folder.mkdir()
            if run(label+"_vlib",[tools["vlib"],"work"],folder)[0]:
                raise ValueError("vlib failed")
            cmd=[tools["vlog"],"-sv"]
            if define:
                cmd.append("+define+"+define)
            cmd.extend(sources)
            if run(label+"_compile",cmd,folder)[0]:
                raise ValueError(f"{label}: compiler failure is NOT mutant success")
            capture=folder/"capture.txt"
            do="onerror {quit -code 2}; onbreak {quit -code 3}; run -all; quit -code 0"
            code,log=run(label+"_simulate",[tools["vsim"],"-c","-wlf","simulation.wlf","work.tb_score_transfer",
                         "+PLAN="+(out/"plan.txt").as_posix(),"+CAPTURE="+capture.as_posix(),"-do",do],folder)
            if code or "HARNESS COMPLETE" not in log or not capture.is_file():
                raise ValueError(f"{label}: incomplete/timeout is NOT negative PASS")
            code,log=run(label+"_check",[sys.executable,"-B","-X","utf8",TB/"check_capture.py",
                                        capture,out/"expected.json"])
            if label=="normal":
                if code:
                    raise ValueError(log)
                result["coverage"]=checker.check(capture,out/"expected.json")
            elif code!=1 or "FAIL " not in log:
                raise ValueError(f"{label}: mutant was not behaviorally rejected")
            else:
                result[label]=dict(compiled=True,simulation_complete=True,checker_exit=code,reason=log.strip())
        # Replay uses real recorded RTL ACKs and asserts exact PC writes; not a model
        # server or hardware claim. Deliberate dropped ACK exercises retry state.
        if run("pc_rtl_ack_replay",[sys.executable,"-B","-X","utf8",TB/"test_software.py",
                                    "--rtl-capture",out/"normal/capture.txt","--expected",out/"expected.json"])[0]:
            raise ValueError("PC real-RTL ACK replay failed")
        if run("capture_rejection",[sys.executable,"-B","-X","utf8",TB/"test_capture.py",
                                     out/"normal/capture.txt",out/"expected.json",out/"checker_mutations"])[0]:
            raise ValueError("damaged capture accepted")
        result["damaged_capture_rejections"]=len(json.loads((out/"checker_mutations/receipt.json").read_text()))
        if args.repo_gate:
            code,log=gate_snapshot(out,run)
            if code or "All repository checks passed." not in log:
                raise ValueError("repository gate failed")
            result["repo_gate"]=True
            result["gate_files"]=len(json.loads((out/"gate_sources.json").read_text()))
        result["status"]="PASS"
        for p in source_files:
            initial=json.loads((out/"source_manifest.json").read_text(encoding="utf-8"))
            if sha(p.read_bytes())!=initial[p.relative_to(ROOT).as_posix()]:
                raise ValueError("executed source changed during run")
    except Exception as exc:
        result["status"]="FAIL"; result["error"]=str(exc)
    result["commands"]=records
    hashes={p.relative_to(out).as_posix():sha(p.read_bytes()) for p in out.rglob("*")
            if p.is_file() and "repo_gate_snapshot" not in p.parts and p.suffix not in (".wlf",)
            and "work" not in p.parts and p.name!="receipt.json"}
    result["raw_sha256"]=hashes
    dump(out/"receipt.json",result)
    if args.publish and result["status"]=="PASS":
        evidence=DOCS/"evidence"/out.name
        evidence.mkdir(parents=True,exist_ok=False)
        selected=[out/"receipt.json",out/"source_manifest.json",out/"expected.json",out/"plan.txt"]
        selected.extend(out.glob("*.stdout.bin")); selected.extend(out.glob("*.stderr.bin"))
        selected.extend(out/"checker_mutations"/name for name in ("receipt.json",))
        selected.extend((out/"checker_mutations").glob("*.stdout.bin"))
        selected.extend((out/"checker_mutations").glob("*.stderr.bin"))
        selected.extend((out/"cli_negative").glob("*"))
        selected.extend((out/"pc_encoded").glob("*"))
        selected.extend(out.glob("score*.json"))
        if args.repo_gate:
            selected.append(out/"gate_sources.json")
        selected.extend(out/label/"capture.txt" for label in ("normal","offset_mutant","crc_mutant"))
        index={}
        for p in selected:
            name=p.relative_to(out).as_posix().replace("/","__")+".b64"
            raw=p.read_bytes(); encoded=base64.b64encode(raw)
            (evidence/name).write_bytes(encoded+b"\n")
            if base64.b64decode((evidence/name).read_bytes())!=raw:
                raise ValueError("Base64 roundtrip")
            index[name]=dict(original=p.relative_to(out).as_posix(),sha256=sha(raw),bytes=len(raw))
        dump(evidence/"raw_manifest.json",index)
        result["published_evidence"]=evidence.relative_to(ROOT).as_posix()
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    return 0 if result["status"]=="PASS" else 1


if __name__=="__main__":
    sys.exit(main())
