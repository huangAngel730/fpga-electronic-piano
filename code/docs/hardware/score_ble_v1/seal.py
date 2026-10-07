"""Seal small necessary raw evidence, or verify existing evidence/source identity."""
from __future__ import annotations
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent


def digest(data): return hashlib.sha256(data).hexdigest()


def main():
    cli=argparse.ArgumentParser(); cli.add_argument("--output",type=Path); cli.add_argument("--gate",type=Path); cli.add_argument("--verify",action="store_true"); cli.add_argument("--run-gate",type=Path); cli.add_argument("--file-list",action="store_true"); cli.add_argument("--bundle",type=Path); args=cli.parse_args()
    if args.bundle:
        out=args.bundle.resolve()
        if out.exists() or not out.is_relative_to((ROOT/"code/output").resolve()) or not out.name.startswith("m3_score_ble_"): cli.error("require new m3_score_ble_* bundle directory")
        folders=[ROOT/"code/rtl/input/pcm_waveform_candidate",ROOT/"code/tb/input/pcm_waveform_candidate",ROOT/"code/docs/hardware/pcm_waveform_v1",
                 ROOT/"code/software/score_ble_bridge_candidate",ROOT/"code/software/score_ble_android_candidate",ROOT/"code/software/score_ble_test_candidate",HERE]
        files=[p for folder in folders for p in folder.rglob("*") if p.is_file()]
        files.extend([ROOT/"code/scripts/run_m3_pcm_waveform_acceptance.py",ROOT/"code/scripts/run_m3_score_ble_acceptance.py"])
        out.mkdir(parents=True); package=out/"M3_T058_waveform_T059_desktop_PARTIAL_20261007.zip"
        with zipfile.ZipFile(package,"w",compression=zipfile.ZIP_DEFLATED) as z:
            for p in sorted(files): z.write(p,p.relative_to(ROOT).as_posix())
        print(package); print("SHA256",digest(package.read_bytes()))
        return
    if args.run_gate:
        out=args.run_gate.resolve()
        if out.exists() or not out.is_relative_to((ROOT/"code/output").resolve()) or not out.name.startswith("m3_score_ble_"): cli.error("require new m3_score_ble_* output")
        out.mkdir(parents=True); env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1")
        env["PATH"]=str(Path(sys.executable).parent)+os.pathsep+"D:/Gowin/oss-cad-suite/bin;D:/Gowin/oss-cad-suite/lib;"+env.get("PATH","")
        command=["powershell","-NoProfile","-ExecutionPolicy","Bypass","-File",str(ROOT/"code/scripts/check_repo.ps1")]
        timed=False
        with (out/"stdout.log").open("wb") as stdout,(out/"stderr.log").open("wb") as stderr:
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr)
            try: process.wait(timeout=600)
            except subprocess.TimeoutExpired:
                timed=True
                if os.name=="nt": subprocess.run(["taskkill","/PID",str(process.pid),"/T","/F"],capture_output=True,timeout=15,check=False)
                else: process.kill()
                process.wait(timeout=15)
        raw_out=(out/"stdout.log").read_bytes(); raw_err=(out/"stderr.log").read_bytes()
        passed=not timed and process.returncode==0 and b"All repository checks passed." in raw_out
        (out/"receipt.json").write_text(json.dumps(dict(passed=passed,exit=process.returncode,timed_out=timed,command=command,stdout_sha256=digest(raw_out),stderr_sha256=digest(raw_err)),indent=2)+"\n",encoding="utf-8")
        print(raw_out.decode("utf-8",errors="replace")); print(raw_err.decode("utf-8",errors="replace"))
        if not passed: raise SystemExit(1)
        return
    if args.file_list:
        file=HERE/"FILE_LIST.json"
        if file.exists(): cli.error("refuse file-list overwrite")
        files=[p for folder in (ROOT/"code/software/score_ble_bridge_candidate",ROOT/"code/software/score_ble_android_candidate",ROOT/"code/software/score_ble_test_candidate",HERE) for p in folder.rglob("*") if p.is_file()]
        files.append(ROOT/"code/scripts/run_m3_score_ble_acceptance.py")
        file.write_text(json.dumps({p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p.read_bytes())) for p in sorted(files)},indent=2)+"\n",encoding="utf-8",newline="\n")
        return
    sealed=HERE/"evidence.zip.b64"; manifest=HERE/"raw_manifest.json"
    if args.verify:
        raw=base64.b64decode(sealed.read_bytes()); meta=json.loads(manifest.read_text(encoding="utf-8"))
        if digest(raw)!=meta["archive_sha256"]: raise ValueError("ARCHIVE_SHA")
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if set(z.namelist())!=set(meta["files"]): raise ValueError("ARCHIVE_MEMBERS")
            for name,item in meta["files"].items():
                data=z.read(name)
                if len(data)!=item["bytes"] or digest(data)!=item["sha256"]: raise ValueError("RAW_SHA "+name)
            receipt=json.loads(z.read("receipt.json"))
            if not receipt["desktop_passed"] or receipt["complete_t059_passed"]: raise ValueError("PARTIAL_RECEIPT")
            for file,expected in receipt["source_sha256"].items():
                if digest((ROOT/file).read_bytes())!=expected: raise ValueError("EXECUTED_SOURCE_CHANGED "+file)
            for step in receipt["steps"]:
                for stream in ("stdout","stderr"):
                    if digest(z.read(step["label"]+"/"+stream+".log"))!=step[stream+"_sha256"]: raise ValueError("LOG_IDENTITY")
            gate=json.loads(z.read("gate/receipt.json"))
            if not gate["passed"] or gate["exit"]!=0: raise ValueError("GATE_FAIL")
        print("PASS",len(meta["files"]),"sealed raw files; executed source SHA; desktop-only receipt")
        return
    if not args.output or not args.gate or sealed.exists() or manifest.exists(): cli.error("require fresh seal and output/gate")
    selected=[p for p in args.output.rglob("*") if p.is_file() and p.suffix in (".log",".json",".jsonl",".c")]
    buffer=io.BytesIO(); members={}
    with zipfile.ZipFile(buffer,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for prefix,files,base in (("",selected,args.output),("gate/",[args.gate/n for n in ("stdout.log","stderr.log","receipt.json")],args.gate)):
            for p in files:
                name=prefix+p.relative_to(base).as_posix(); data=p.read_bytes()
                z.writestr(name,data); members[name]={"bytes":len(data),"sha256":digest(data)}
    data=buffer.getvalue(); sealed.write_bytes(base64.encodebytes(data))
    manifest.write_text(json.dumps(dict(archive_sha256=digest(data),files=members),indent=2)+"\n",encoding="utf-8",newline="\n")
    print("SEALED",len(members),"files",len(data),"compressed bytes")


if __name__=="__main__": main()
