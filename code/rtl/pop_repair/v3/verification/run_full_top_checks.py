"""Read-only formal TB copied to V3: real UART, V3 top and PT8211 decode."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPO = Path("E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano")
CAD = Path("D:/Gowin/oss-cad-suite")


def execute(command, work, name):
    bat = work / (name+".bat")
    bat.write_text('@echo off\r\ncall "'+str(CAD / "environment.bat")+'" >nul\r\n'+
                   " ".join('"'+str(part)+'"' for part in command)+"\r\nexit /b %errorlevel%\r\n",encoding="ascii")
    with (work / (name+".log")).open("w",encoding="utf-8") as stream:
        result = subprocess.run(["cmd.exe","/c",str(bat)],cwd=work,stdout=stream,
                                stderr=subprocess.STDOUT,timeout=300)
    text = (work / (name+".log")).read_text(encoding="utf-8")
    print(text[-1800:],flush=True)
    return result.returncode,text


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",type=Path,required=True)
    p.add_argument("--mode",choices=["note_fast","note_real","sustain_fast"],required=True)
    args=p.parse_args();snap=args.snapshot.resolve()
    if not snap.is_relative_to(ROOT / "build"):
        p.error("owned snapshot only")
    manifest=json.loads((snap / "frozen_input_manifest.json").read_text(encoding="utf-8"))
    for item in manifest["staged_files"]:
        if hashlib.sha256((snap / item["path"]).read_bytes()).hexdigest()!=item["sha256"]:
            raise ValueError("changed input "+item["path"])
    work=snap / ("tests_top_"+args.mode)
    if work.exists():p.error("refuse overwrites")
    work.mkdir()
    top="tb_sustain_midi_top" if args.mode=="sustain_fast" else "tb_t024_midi_polyphonic_path"
    original=REPO / "code/tb/board" / (top+".sv")
    tb=work / original.name;shutil.copy2(original,tb)
    filelist=[Path(n.attrib["path"]) for n in ET.parse(manifest["project"]).findall(".//File")
              if n.attrib["type"]=="file.verilog"]
    filelist=[snap / "tests_lifecycle/allocator.v" if f.name=="voice_allocator_4.sv" else f for f in filelist]
    command=[CAD / "bin/iverilog.exe","-g2012","-I",snap / "code/rtl/common",
             "-I",snap / "code/rtl/board","-I",snap / "source/rtl","-s",top,
             "-P",top+".FAST_AUDIO="+str(int(args.mode!="note_real")),"-o",work / "tb.vvp",*filelist,tb]
    code,text=execute(command,work,"compile")
    if code:raise RuntimeError("compile failed")
    command=[CAD / "bin/vvp.exe",work / "tb.vvp",
             "+WAVETABLE_PATH="+str(snap / "code/model/generated/wavetables/piano_band_4x256_8191.mem"),
             "+VELOCITY_ROM_PATH="+str(snap / "code/model/generated/wavetables/velocity_gain_rom.mem")]
    code,text=execute(command,work,"run")
    if code or "PASS "+top not in text or "FATAL" in text:raise RuntimeError("RTL failed")
    negative=None
    if args.mode=="note_fast":
        code,bad=execute([*command,"+NEGATIVE_DATA"],work,"negative_lsb")
        negative=code!=0 and "PT8211 PCM mismatch" in bad
        if not negative:raise RuntimeError("corrupted serial LSB not rejected")
    report={"status":"PASS","mode":args.mode,"original_tb":str(original),
            "original_tb_sha256":hashlib.sha256(original.read_bytes()).hexdigest(),
            "copied_tb_sha256":hashlib.sha256(tb.read_bytes()).hexdigest(),
            "actual_PASS":[line for line in text.splitlines() if line.startswith("PASS")],
            "negative_serial_LSB_rejected":negative,
            "scope":"V3 full MIDI/top/PT8211; fast modes accelerate audio only, MIDI remains50MHz/31250; no STAT/board claim"}
    (work / "result.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("PASS V3 full-top",args.mode,flush=True)


if __name__=="__main__":main()
