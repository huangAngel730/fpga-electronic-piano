from pathlib import Path
import argparse
import json
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from hashlib import sha256
from zipfile import ZipFile

parser = argparse.ArgumentParser()
parser.add_argument("modelsim", type=Path)
parser.add_argument("evidence", type=Path)
parser.add_argument("--kind", choices=("fx", "top", "controls", "extra", "visual", "transport", "control_snapshot", "repeat_gap"), default="top")
parser.add_argument("--reference-r04", type=Path, help="R04 handoff ZIP for bit-exact comparison")
parser.add_argument("--reference-r05", type=Path)
args = parser.parse_args()
if args.kind=="extra" and not args.reference_r05:
    parser.error("--kind extra requires --reference-r05")
if args.reference_r04 and args.kind!="fx":
    parser.error("--reference-r04 requires --kind fx")
root = Path(__file__).resolve().parent
project = root / "project"
tool = args.modelsim.resolve()
out = args.evidence.resolve()
out.mkdir(parents=True, exist_ok=False)
steps = []

def run(name, argv, timeout):
    start = time.monotonic()
    with (out / (name+".log")).open("wb") as log:
        try:
            result = subprocess.run([str(tool / (argv[0]+".exe")), *map(str, argv[1:])],
                                    cwd=out, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
            rc = result.returncode
        except subprocess.TimeoutExpired:
            rc = 124
    steps.append({"tool": name, "exit": rc, "seconds": round(time.monotonic()-start, 3)})
    if rc:
        raise SystemExit(rc)

try:
    run("vlib", ["vlib", "work"], 15)
    if args.kind in {"top","visual","transport","control_snapshot"}:
        shutil.copytree(project / "rom", out / "rom")
        files = [project / entry.attrib["path"]
                 for entry in ET.parse(project / "pro_audio.gprj").findall("./FileList/File")
                 if entry.attrib.get("enable") == "1" and entry.attrib["path"].startswith("src/")]
        fixtures = ["extension_integration/clock_model.sv",
                    "extension_integration/gw5a_lut1_model.sv",
                    "extension_visual/display/dvi_sim_boundary.sv"]
        files += [project/"tb"/p for p in fixtures]
        defines, plusargs = [], []
        if args.kind=="top":
            files += [root/"visual_evidence/c1_pcm_checker.sv", project/"tb/tb_c1_top.sv"]
            plusargs = ["+C1_PCM_CHECK", "+C1_PCM_REQUIRE_STEREO"]
            top, markers = "tb_c1_top", ("PASS C1_TOP", "PASS C1_PCM_TAPS", "PASS C1_RENDER")
        elif args.kind=="visual":
            top, markers = "tb_visual_gap_hit200", ("VISUAL_GAP_HIT200_PASS",)
            files.append(project/f"tb/{top}.sv")
        elif args.kind=="control_snapshot":
            top, markers = "tb_r08_control_forwarding", ("PASS R08_CONTROL_FORWARDING",)
            files.append(project/f"tb/{top}.sv")
        else:
            top, markers = "tb_n32_bright_frame_transport", ("N32_BRIGHT_FRAME_TRANSPORT_PASS N=32",)
            files.append(project/f"tb/{top}.sv")
    elif args.kind == "extra":
        shutil.copytree(project/"rom",out/"rom")
        assert sha256(args.reference_r05.read_bytes()).hexdigest()=="e14f6326009fbdf611ceb426c7dbc34106d301e19c4ce9ffc86e5000a00482df"
        names=("c1_extra_voices","snare_voice","sax_voice_r05","guitar_voice")
        files=[project/"src/audio_defs_pkg.sv",project/"src/note_pitch.sv"]
        with ZipFile(args.reference_r05) as z:
            for name in names:
                rel=f"project/src/c1_extra/{name}.sv"
                body=z.read(rel).decode("utf-8")
                for module in names:
                    body=re.sub(r"\b"+module+r"\b","r05_"+module,body)
                dest=out/f"r05_{name}.sv"
                dest.write_text(body,encoding="utf-8",newline="\n")
                files += [root/rel,dest]
        files.append(root/"extra_evidence/tb_c1_extra_voices.sv")
        defines, plusargs = [], []
        top, markers = "tb_c1_extra_voices", ("PASS C1_EXTRA_VOICES",)
    elif args.kind == "repeat_gap":
        top, markers = "tb_r12_falling_repeat_gap", ("PASS R12_FALLING_REPEAT_GAP",)
        files = [project/"src/audio_defs_pkg.sv",
                 project/"src/extension_visual/display/pro_visual_score_tracker.sv",
                 project/f"tb/{top}.sv"]
        defines, plusargs = [], []
    elif args.kind == "controls":
        files = [
            project/"src/audio_defs_pkg.sv",
            project/"tb/extension_integration/gw5a_lut1_model.sv",
            project/"src/midi_event_parser.sv",
            project/"src/extension_controls/pro_midi_page_controls.sv",
            root/"controls_evidence/tb_c1_fx_controls.sv",
        ]
        defines, plusargs = [], []
        top, markers = "tb_c1_fx_controls", ("PASS C1_FX_CONTROLS",)
    else:
        files = sorted((project/"src/c1_fx").glob("*.sv")) + [project/"tb/tb_c1_fx.sv"]
        defines, plusargs = [], []
        top, markers = "tb_c1_fx", ("PASS C1_FX", "PASS C1_FX_STEMS", "PASS C1_DELAY_CHORUS_SOLO")
        if args.reference_r04:
            archive=args.reference_r04.read_bytes()
            expected="f582eb04c1896073a347bf509cc56dc415aa39a92421dcbd691469964887f425"
            if sha256(archive).hexdigest()!=expected:
                raise SystemExit("R04 archive SHA mismatch")
            names=("c1_pcm_effects","fx_chorus","fx_reverb")
            with ZipFile(args.reference_r04) as z:
                for name in names:
                    src=z.read(f"project/src/c1_fx/{name}.sv").decode("utf-8")
                    for module in names:
                        src=re.sub(r"\b"+module+r"\b","r04_"+module,src)
                    dest=out/f"r04_{name}.sv"
                    dest.write_text(src,encoding="utf-8",newline="\n")
                    files.insert(0,dest)
            defines=["+define+C1_R04_COMPARE"]
            markers+=("PASS C1_R04_BIT_EXACT",)

    run("vlog", ["vlog", "-sv", *defines, "+incdir+"+str(project/"include"), *files], 60)
    (out/"sim.do").write_text("onerror {quit -code 2}\nrun -all\nquit -code 0\n", encoding="utf-8")
    run("vsim", ["vsim", "-c", "-onfinish", "exit", top, *plusargs, "-do", "sim.do"], 180)
    log = (out/"vsim.log").read_text(encoding="utf-8", errors="replace")
    if any(mark not in log for mark in markers) or re.search(r"\*\* (?:Error|Fatal)", log):
        raise SystemExit(3)
    print("\n".join(line for line in log.splitlines() if "# PASS " in line))
finally:
    (out/"steps.json").write_text(json.dumps(steps, indent=2)+"\n",encoding="utf-8")
