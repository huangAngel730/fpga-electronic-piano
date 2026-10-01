"""V1+CC64 audio cycle-equivalence with a full independent display consumer."""
import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CAD = Path("D:/Gowin/oss-cad-suite")


def run(command, cwd, log):
    with log.open("w", encoding="utf-8", newline="\n") as stream:
        result = subprocess.run(command, cwd=cwd, stdout=stream,
                                stderr=subprocess.STDOUT, timeout=900)
    text = log.read_text(encoding="utf-8", errors="replace")
    if result.returncode:
        print(text[-4000:])
        raise RuntimeError("simulation step failed: " + log.name)
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--small-raster", action="store_true")
    args = parser.parse_args()
    stage = args.prepared.resolve()
    info = json.loads((stage / "inputs.json").read_text(encoding="utf-8"))
    snapshot = Path(info["snapshot"])
    sim = stage / "simulation"
    sim.mkdir(exist_ok=True)
    os.environ["PATH"] = str(CAD / "lib") + os.pathsep + str(CAD / "bin") + os.pathsep + os.environ["PATH"]
    allocator = snapshot / "code/rtl/audio/voice_allocator_4.sv"
    net = sim / "allocator.v"
    script = sim / "lower.ys"
    script.write_text("read_slang --top voice_allocator_4 " + allocator.as_posix() +
                      "\nproc\nopt\ntechmap\nopt\nwrite_verilog -noattr " + net.as_posix() + "\n", encoding="ascii")
    run([str(CAD / "bin/yosys.exe"), "-Q", "-T", "-s", str(script)], sim, sim / "lower.log")
    sources = []
    for name in info["sources"]:
        path = Path(name)
        if path.name in ("TMDS_PLL_800_600_60.v", "DVI_TX_Top.v"):
            continue
        sources.append(net if path.name == allocator.name else path)
    sources += [Path(info["formal_reference_top"]), ROOT / "code/tb/board/audio_visual_phy_model.sv",
                ROOT / "code/tb/board/tb_audio_visual_coexistence.sv"]
    for header, location in [("sine_table.svh", "common"), ("sustain_controller_ports.svh", "board")]:
        (sim / header).write_bytes((snapshot / ("code/rtl/" + location + "/" + header)).read_bytes())
    staged = []
    for index, source in enumerate(sources):
        text = source.read_text(encoding="utf-8")
        for header, location in [("sine_table.svh", "common"), ("sustain_controller_ports.svh", "board")]:
            path = snapshot / ("code/rtl/" + location + "/" + header)
            text = text.replace(path.as_posix(), header)
        dest = sim / ("source_" + str(index) + ".sv")
        dest.write_text(text, encoding="utf-8", newline="\n")
        staged.append(dest)
    sources = staged
    exe = sim / "coexistence.vvp"
    command = [str(CAD / "bin/iverilog.exe"), "-g2012", "-I", str(sim), "-I", str(snapshot / "code/rtl/common"),
               "-I", str(snapshot / "code/rtl/board"), "-s", "tb_audio_visual_coexistence", "-o", str(exe)]
    if args.small_raster:
        command += ["-P", "tb_audio_visual_coexistence.SMALL_RASTER=1"]
    run(command + list(map(str, sources)), sim, sim / "compile.log")
    text = run([str(CAD / "bin/vvp.exe"), str(exe)], sim, sim / "run.log")
    results = [line for line in text.splitlines() if line.startswith("PASS coexistence")]
    if len(results) != 1:
        raise RuntimeError("missing coexistence verdict")
    print(results[0])
    print("PHY is a behavioral wiring model; no physical HDMI claim")


if __name__ == "__main__":
    main()
