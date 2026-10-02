"""Compile and execute real RTL in owned V3 build snapshots only."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

V3=Path(__file__).resolve().parents[1]
CAD=Path("D:/Gowin/oss-cad-suite")
FILES=[
"rtl/common/audio_defs_pkg.sv","ALLOCATOR","rtl/common/note_pitch.sv",
"rtl/board/sustain_control_contract_pkg.sv","rtl/input/sustain_control/sustain_controller.sv",
"rtl/board/polyphonic_event_router.sv","rtl/board/polyphonic_envelope_bank.sv",
"rtl/audio/dds_oscillator.sv","rtl/audio/piano_dds_oscillator.sv",
"rtl/audio/adsr_piano_envelope.sv","rtl/board/polyphonic_pcm_commit.sv",
"rtl/mixer/pcm_mixer_4voice.sv","rtl/audio_out/pcm_result_hold.sv",
"rtl/audio_out/pcm_frame_buffer.sv","rtl/common/pcm_clip_counter.sv",
"rtl/common/system_status_counters.sv","rtl/board/voice_gain_q15_candidate.sv",
"rtl/board/polyphonic_audio_core.sv"]
def run(command,work,name):
    result=subprocess.run(command,cwd=work,capture_output=True,text=True,encoding="utf-8",
                          errors="replace",timeout=300,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"})
    text=result.stdout+result.stderr
    (work/(name+".log")).write_text(text,encoding="utf-8")
    for line in text.splitlines():
        if any(term in line for term in ("PASS","FAIL","FATAL","error:")):
            print(line)
    if result.returncode:
        raise RuntimeError(str(command)+": failed "+str(result.returncode))
    return text
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",type=Path,required=True)
    p.add_argument("--suite",choices=["lifecycle","existing_trace","existing_capabilities","existing_sustain"],required=True)
    p.add_argument("--cc64",action="store_true")
    args=p.parse_args();snapshot=args.snapshot.resolve()
    if not snapshot.is_relative_to(V3/"build"):
        p.error("Only owned V3 build snapshots permitted")
    code=snapshot/"code";work=snapshot/("tests_"+args.suite)
    if work.exists():
        p.error("Preserve existing results: select a fresh build snapshot")
    work.mkdir(parents=True)
    net=work/"allocator.v";ys=work/"lower.ys"
    ys.write_text("read_slang --top voice_allocator_4 "+(code/"rtl/audio/voice_allocator_4.sv").as_posix()+
                  "\nproc\nopt\ntechmap\nopt\nwrite_verilog -noattr "+net.as_posix()+"\n",encoding="ascii")
    if args.suite=="lifecycle":
        top="tb_v3_lifecycle";tb=V3/"verification/tb_v3_lifecycle.sv";params=["-P",top+".HAS_CC64="+str(int(args.cc64))]
    elif args.suite=="existing_trace":
        top="tb_polyphonic_audio_core";tb=code/"tb/board"/(top+".sv");params=["-P",top+".PIANO_TIMBRE_ENABLE=1"]
    elif args.suite=="existing_capabilities":
        top="tb_t024_audio_capabilities";tb=code/"tb/board"/(top+".sv");params=["-P",top+".PIANO_TIMBRE_ENABLE=1"]
    else:
        top="tb_sustain_audio_integration";tb=code/"tb/board"/(top+".sv");params=[]
    filepaths=[net if name=="ALLOCATOR" else code/name for name in FILES]
    # Frozen V3 may add explicitly declared oscillator implementation files.
    extra_manifest=snapshot/"extra_rtl.json"
    if extra_manifest.exists():
        filepaths.extend(snapshot/name for name in json.loads(extra_manifest.read_text()))
    commands=[
        [str(CAD/"bin/yosys.exe"),"-Q","-T","-s",str(ys)],
        [str(CAD/"bin/iverilog.exe"),"-g2012","-I",str(code/"rtl/board"),"-I",str(snapshot/"source/rtl"),"-s",top,*params,
         "-o",str(work/"tb.vvp"),*map(str,filepaths),str(tb)],
        [str(CAD/"bin/vvp.exe"),str(work/"tb.vvp"),
         "+VELOCITY_ROM_PATH="+str(code/"model/generated/wavetables/velocity_gain_rom.mem"),
         "+WAVETABLE_PATH="+str(code/"model/generated/wavetables/piano_band_4x256_8191.mem"),
         "+TRACE="+str(work/"audio.trace"),"+CAPTURE="+str(work/"audio.capture")]]
    # Execute native programs with the installed CAD environment, never old scripts.
    quote=lambda text:'"'+str(text)+'"'
    for i,command in enumerate(commands):
        bat=work/("step"+str(i)+".bat")
        bat.write_text("@echo off\r\ncall "+quote(CAD/"environment.bat")+" >nul\r\n"+
                       " ".join(map(quote,command))+"\r\nexit /b %errorlevel%\r\n",encoding="ascii")
        output=run(["cmd.exe","/c",str(bat)],work,"step"+str(i))
    if "PASS" not in output:
        raise RuntimeError("RTL did not report PASS")
    if args.suite=="lifecycle" and extra_manifest.exists():
        run([sys.executable,"-B",str(V3/"verification/check_v3_core_trace.py"),
             str(work/"audio.trace"),"--snapshot",str(snapshot)],work,"golden")
    elif args.suite=="existing_trace":
        run([sys.executable,"-B",str(code/"tb/board/check_polyphonic_audio_trace.py"),
             str(work/"audio.trace"),"--piano-v1"],work,"golden")
    elif args.suite=="existing_capabilities":
        run([sys.executable,"-B",str(code/"tb/board/check_t024_audio_capabilities.py"),
             str(work/"audio.capture"),"--json",str(work/"analysis.json"),"--negative-tests"],work,"golden")
    print("PASS executed",args.suite,"in",snapshot)
if __name__=="__main__":
    main()
