"""Seal small necessary raw evidence, or verify existing evidence/source identity."""
from __future__ import annotations
import argparse
import base64
import gzip
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


def approved_adapter_history(file, expected):
    """D040 exception: verify old execution bytes separately from new adapters.

    Never replace the old receipt SHA. Only the two explicitly approved paths
    may use the source snapshots in the new versioned evidence. Other source
    changes continue to fail the original checks.
    """
    allowed=("code/software/score_ble_bridge_candidate/main/main.c",
             "code/software/score_ble_android_candidate/app/src/main/java/org/m3/score/MainActivity.kt")
    if file not in allowed: return False
    folder=HERE/"target_adapter_repair_20261008"
    baseline=json.loads((folder/"baseline.json").read_text(encoding="utf-8"))
    metadata=json.loads((folder/"evidence/raw_manifest.json").read_text(encoding="utf-8"))
    raw={}
    for name,item in metadata.items():
        carrier=(folder/"evidence"/name).read_bytes()
        data=gzip.decompress(base64.b64decode(carrier))
        if digest(carrier)!=item["carrier_sha256"] or digest(data)!=item["raw_sha256"] or len(data)!=item["raw_bytes"]:
            raise ValueError("ADAPTER_HISTORY_RAW_SHA")
        raw[item["original"]]=data
    receipt=json.loads(raw["run/receipt.json"])
    if not receipt["passed"] or digest(raw["run/receipt.json"])!=baseline["regression_receipt_raw_sha256"]:
        raise ValueError("ADAPTER_HISTORY_RECEIPT")
    if receipt["adapter_versions"]!=baseline["adapter_versions"] or receipt["eight_unchanged_sources"]!=baseline["eight_unchanged_sources"]:
        raise ValueError("ADAPTER_HISTORY_BASELINE")
    if set(baseline["adapter_versions"])!=set(allowed) or len(baseline["eight_unchanged_sources"])!=8:
        raise ValueError("ADAPTER_HISTORY_SCOPE")
    for path,item in baseline["adapter_versions"].items():
        if digest(raw["run/sources/old_"+Path(path).name])!=item["old_sha256"] or digest((ROOT/path).read_bytes())!=item["new_sha256"]:
            raise ValueError("ADAPTER_HISTORY_SOURCE")
    for path,value in baseline["eight_unchanged_sources"].items():
        if digest((ROOT/path).read_bytes())!=value: raise ValueError("ADAPTER_HISTORY_IMMUTABLE_EIGHT")
    if baseline["adapter_versions"][file]["old_sha256"]!=expected: raise ValueError("ADAPTER_HISTORY_OLD_EXECUTION_SHA")
    return True


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
                if digest((ROOT/file).read_bytes())!=expected:
                    if approved_adapter_history(file,expected): continue
                    if file!="code/software/score_ble_test_candidate/acceptance.py": raise ValueError("EXECUTED_SOURCE_CHANGED "+file)
                    revision=HERE/"review_repair_20261008/evidence"
                    metadata=json.loads((revision/"raw_manifest.json").read_text(encoding="utf-8")); revised_raw={}
                    for name,item in metadata.items():
                        data=gzip.decompress(base64.b64decode((revision/name).read_bytes()))
                        if digest(data)!=item["raw_sha256"] or len(data)!=item["raw_bytes"]: raise ValueError("REPAIR_RAW_SHA")
                        revised_raw[item["original"]]=data
                    audit=json.loads(revised_raw["run/fragment_audit/receipt.json"])
                    current=json.loads(revised_raw["run/receipt.json"])
                    if not audit["passed"] or not current["desktop_passed"] or current["complete_t059_passed"]: raise ValueError("REPAIR_RECEIPT")
                    if audit["original_source_sha256"]!=receipt["source_sha256"] or digest(revised_raw["run/fragment_audit/legacy_acceptance.py"])!=expected: raise ValueError("LEGACY_TEST_SNAPSHOT")
                    for path,value in current["source_sha256"].items():
                        if digest((ROOT/path).read_bytes())!=value and not approved_adapter_history(path,value): raise ValueError("REPAIR_EXECUTED_SOURCE_CHANGED "+path)
                    for path,value in audit["source_sha256"].items():
                        if digest((ROOT/path).read_bytes())!=value: raise ValueError("REPAIR_AUDIT_SOURCE_CHANGED "+path)
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
