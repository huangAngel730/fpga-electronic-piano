"""Run already-installed Icarus; never installs or changes system environment.

All artifacts/logs under design/model_results; exact cwd V3 root for ROM paths.
Prerequisite: diagnose_v3.py --selftest; no generation of source files here.
"""
import json
from pathlib import Path
import subprocess
from v3_parameters import note_fcw

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "design" / "model_results"
ENV = Path("D:/Gowin/oss-cad-suite/environment.bat")
IVL = Path("D:/Gowin/oss-cad-suite/bin/iverilog.exe")
VVP = Path("D:/Gowin/oss-cad-suite/bin/vvp.exe")

def run(command, label):
    # Raw Windows command line avoids list2cmdline escaping quotes into cmd's
    # /c string. All fixed tool paths are verified ASCII/no-space here.
    result = subprocess.run(f'cmd /d /c call {ENV} && {command}',
                            cwd=ROOT, capture_output=True, text=True, timeout=90)
    output = result.stdout+result.stderr
    (DEST/f"{label}.log").write_text(output, encoding="utf-8", newline="\n")
    print(label, "exit", result.returncode, output[-150:].strip())
    if result.returncode:
        raise RuntimeError(f"{label} failed; read preserved log")
    return output

if __name__=="__main__":
    for p in (ENV,IVL,VVP):
        if not p.is_file():
            raise FileNotFoundError(p)
    DEST.mkdir(parents=True,exist_ok=True)
    run(f'"{IVL}" -g2012 -I source/rtl -s tb_piano_dds_oscillator_v3 '
        '-o design/model_results/tb_osc.vvp source/baseline/piano_dds_oscillator.sv '
        'source/rtl/piano_dds_oscillator_v3.sv source/rtl/tb_piano_dds_oscillator_v3.sv', "iverilog_compile")
    checks=[]
    for n in (21,24,36,48,57):
        text=run(f'"{VVP}" design/model_results/tb_osc.vvp '
                 f'+VECTOR=design/model_results/osc_note{n}.mem +FCW={note_fcw(n)}',f"rtl_note{n}")
        assert "PASS V3 oscillator 2048 exact samples" in text
        checks.append({"note":n,"samples":2048,"fcw":note_fcw(n),"status":"PASS"})
    (DEST/"oscillator_rtl_results.json").write_text(json.dumps(checks,indent=2)+"\n",encoding="utf-8",newline="\n")
    run(f'"{IVL}" -g2012 -I source/rtl -s tb_v3_bank_latency '
        '-o design/model_results/tb_bank.vvp source/baseline/piano_dds_oscillator.sv '
        'source/baseline/adsr_piano_envelope.sv source/rtl/piano_dds_oscillator_v3.sv '
        'source/rtl/polyphonic_envelope_bank.sv source/rtl/tb_v3_bank_latency.sv',"bank_compile")
    text=run(f'"{VVP}" design/model_results/tb_bank.vvp '
             '+VELOCITY_ROM_PATH=source/baseline/velocity_gain_rom.mem',"bank_latency")
    assert "PASS V3 bank latency" in text
