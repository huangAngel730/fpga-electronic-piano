"""Bounded offline T059 checks; never open devices, flash, install or scan BLE."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
CORE=ROOT/"code/software/score_ble_bridge_candidate"
APP=ROOT/"code/software/score_ble_android_candidate"
TEST=ROOT/"code/software/score_ble_test_candidate/acceptance.py"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--gcc",type=Path,default=Path("D:/program/OSsystem/MinGW/bin/gcc.exe"))
    parser.add_argument("--jdk",type=Path,default=Path("E:/FPGA/Bpan/Vivado/Vivado2020_2/2020.2/tps/win64/jre11.0.2"))
    parser.add_argument("--idf-root",type=Path,help="existing exported ESP-IDF v5.4.2 environment; build only")
    parser.add_argument("--gradle",type=Path,help="existing Gradle 8.9 executable; offline build only")
    parser.add_argument("--android-sdk",type=Path)
    parser.add_argument("--java17",type=Path)
    args=parser.parse_args(); out=args.output.resolve()
    if out.exists() or not out.is_relative_to((ROOT/"code/output").resolve()) or not out.name.startswith("m3_score_ble_"):
        parser.error("require new code/output/m3_score_ble_* directory")
    out.mkdir(parents=True); steps=[]; started=time.monotonic(); env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1")
    # Child-only deterministic locale; no change to the user's Java environment.
    env.pop("JAVA_TOOL_OPTIONS",None)
    env["PATH"]=str(args.gcc.parent)+os.pathsep+env.get("PATH","")
    def run(label,command):
        folder=out/label; folder.mkdir(); timeout=min(300,max(1,1800-int(time.monotonic()-started)))
        process=subprocess.Popen([str(x) for x in command],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        timed=False
        try: stdout,stderr=process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed=True
            if os.name=="nt": subprocess.run(["taskkill","/PID",str(process.pid),"/T","/F"],capture_output=True,timeout=15,check=False)
            else: process.kill()
            stdout,stderr=process.communicate(timeout=15)
        (folder/"stdout.log").write_bytes(stdout); (folder/"stderr.log").write_bytes(stderr)
        item=dict(label=label,command=[str(x) for x in command],exit=process.returncode,timed_out=timed,
                  stdout_sha256=hashlib.sha256(stdout).hexdigest(),stderr_sha256=hashlib.sha256(stderr).hexdigest())
        steps.append(item); print(label,item["exit"],stdout.decode("utf-8",errors="replace")[-600:],flush=True)
        return item,stdout+stderr
    def require(label,command):
        result,_=run(label,command)
        if result["exit"] or result["timed_out"]: raise ValueError(label+" failed")
    sources=[p for path in (CORE,APP,TEST.parent) for p in path.rglob("*") if p.is_file()]
    sources.append(Path(__file__).resolve())
    frozen=ROOT/"code/docs/hardware/score_transfer_v1/evidence/run_j_v22g6p"
    sources.extend([ROOT/"code/software/score_transfer_v1/score_transfer.py",frozen/"raw_manifest.json",frozen/"expected.json.b64",frozen/"normal__capture.txt.b64"])
    identity={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    failure=None
    firmware="NOT_RUN_MISSING_ESP_IDF"; apk="NOT_RUN_MISSING_ANDROID_SDK_GRADLE_JDK17"
    try:
        require("gcc_version",[args.gcc,"--version"])
        require("java_version",[args.jdk/"bin/java.exe","-version"])
        require("javac_version",[args.jdk/"bin/javac.exe","-version"])
        executable=out/"bridge.exe"
        gcc=[args.gcc,"-std=c99","-Wall","-Wextra","-Werror","-pedantic","-O2","-I",CORE/"core","-I",CORE]
        require("bridge_compile",gcc+[CORE/"core/bridge.c",CORE/"host.c","-o",executable])
        classes=out/"classes"; classes.mkdir()
        require("java_compile",[args.jdk/"bin/javac.exe","-encoding","UTF-8","-Xlint:all","-Werror","--release","8","-d",classes,
                 APP/"app/src/main/java/org/m3/score/Protocol.java",APP/"desktop/Harness.java"])
        capture=out/"positive.jsonl"
        require("bridge_capture",[sys.executable,"-B",TEST,"capture","--exe",executable,"--capture",capture])
        require("bridge_check",[sys.executable,"-B",TEST,"check","--capture",capture])
        require("java_client",[sys.executable,"-B",TEST,"java","--exe",executable,"--java",args.jdk/"bin/java.exe","--classes",classes,"--trace-dir",out/"joint_trace"])
        # Two behavioral mutants compile and run to completion, not compile errors.
        for name in ("crc_accept","partial_uart"):
            folder=out/name; folder.mkdir(); source=(CORE/"core/bridge.c").read_text(encoding="utf-8"); host=(CORE/"host.c").read_text(encoding="utf-8")
            if name=="crc_accept":
                anchor="if(got!=br_crc(s->data+2,s->used-4))"
                if source.count(anchor)!=1: raise ValueError("mutant anchor")
                source=source.replace(anchor,"if(got!=br_crc(s->data+2,s->used-4) && 0)")
            else:
                anchor="br_feed(&b,cmd=='G',data,n,ms);"
                if host.count(anchor)!=1: raise ValueError("mutant anchor")
                host=host.replace(anchor,"if(cmd=='G') { br_frame f; f.length=(uint16_t)n; if(n<=142) { memcpy(f.data,data,n); print_frame(\"UART\",&f); } } "+anchor)
            (folder/"bridge.c").write_text(source,encoding="utf-8",newline="\n"); (folder/"host.c").write_text(host,encoding="utf-8",newline="\n")
            exe=folder/"bridge.exe"; cap=folder/"capture.jsonl"
            require(name+"_compile",gcc+[folder/"bridge.c",folder/"host.c","-o",exe])
            require(name+"_full_run",[sys.executable,"-B",TEST,"capture","--exe",exe,"--capture",cap])
            result,output=run(name+"_reject",[sys.executable,"-B",TEST,"check","--capture",cap])
            token=b"CRC_REJECT" if name=="crc_accept" else b"NO_PARTIAL_UART"
            if result["exit"]!=1 or result["timed_out"] or token not in output: raise ValueError("not semantic rejection "+name)
        raw=capture.read_text(encoding="utf-8"); rows=raw.splitlines(); broken=out/"bad_capture"; broken.mkdir()
        bad_count=[json.loads(x) for x in rows]; bad_count[-1]["count"]-=1
        bad_expected=[json.loads(x) for x in rows]; bad_expected[2]["expected"]=["UART a5"]
        for name,value in (("empty",""),("truncated","\n".join(rows[:-1])+"\n"),("garbage","garbage\n"),
                           ("count","\n".join(json.dumps(x) for x in bad_count)+"\n"),
                           ("reference","\n".join(json.dumps(x) for x in bad_expected)+"\n")):
            path=broken/(name+".jsonl"); path.write_text(value,encoding="utf-8")
            result,_=run("bad_"+name,[sys.executable,"-B",TEST,"check","--capture",path])
            if result["exit"]!=1 or result["timed_out"]: raise ValueError("bad capture not rejected")
        if args.idf_root:
            env["IDF_PATH"]=str(args.idf_root.resolve())
            item,version=run("idf_version",["git","-C",args.idf_root,"describe","--tags","--exact-match"])
            if item["exit"] or version.strip()!=b"v5.4.2": raise ValueError("require exact IDF v5.4.2 tag")
            require("idf_commit",["git","-C",args.idf_root,"rev-parse","HEAD"])
            require("firmware_build",[sys.executable,args.idf_root/"tools/idf.py","-C",CORE,"-B",out/"firmware","-D","IDF_TARGET=esp32c3","-D","SDKCONFIG="+str(out/"sdkconfig"),"build"])
            firmware="COMPILED_NO_FLASH"
        if args.gradle:
            if not args.android_sdk or not args.java17: raise ValueError("APK requires explicit existing SDK/JDK17")
            env["JAVA_HOME"]=str(args.java17.resolve()); env["ANDROID_HOME"]=str(args.android_sdk.resolve())
            require("jdk17_version",[args.java17/"bin/java.exe","-version"])
            item,version=run("gradle_version",[args.gradle,"--offline","--version"])
            if item["exit"] or b"Gradle 8.9" not in version: raise ValueError("require Gradle 8.9")
            require("apk_build",[args.gradle,"--offline","--no-daemon","--project-cache-dir",out/"gradle_cache","-p",APP,"-PcandidateBuildDir="+str(out/"android"),"assembleDebug"])
            apk="COMPILED_NO_INSTALL"
    except Exception as exc: failure=str(exc)
    artifact_sha={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob("*") if p.is_file()}
    receipt=dict(schema=1,desktop_passed=failure is None,complete_t059_passed=failure is None and firmware=="COMPILED_NO_FLASH" and apk=="COMPILED_NO_INSTALL",error=failure,steps=steps,
                 source_sha256=identity,artifact_sha256=artifact_sha,firmware_build=firmware,
                 apk_build=apk,device_operations=False,
                 simulated_peers=True,sealed_old_rtl_replay=True)
    (out/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8",newline="\n")
    print("PASS desktop only" if failure is None else "FAIL "+failure,flush=True)
    return int(failure is not None)


if __name__=="__main__": raise SystemExit(main())
