"""M2 pipeline/visual candidate versus immutable original audio reference.

Physical audio pins are compared every sys_clk; adopted PCM and voice count at
frame boundaries and committed same-request PCM are checked. Internal pending
PCM arrival, STAT byte timing and processing-cycle counters may change, and are
NOT claimed cycle-equivalent. Writes prepared-folder simulation artifacts only.
"""
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
    # Compare against independent ORIGINAL envelope/bank/core/button definitions.
    reference_sources = []
    for name, original, refname in [
        ("adsr_piano_envelope.sv", "audio", "adsr_reference"),
        ("polyphonic_envelope_bank.sv", "board", "bank_reference"),
        ("polyphonic_audio_core.sv", "board", "core_reference"),
        ("button_event_converter.sv", "input/button_event_converter", "button_reference")]:
        original_name = name[:-3]
        content = (snapshot / ("code/rtl/" + original + "/" + name)).read_text(encoding="utf-8")
        content = content.replace("module " + original_name, "module " + refname, 1)
        if refname == "bank_reference": content = content.replace("adsr_piano_envelope u_envelope", "adsr_reference u_envelope")
        if refname == "core_reference": content = content.replace("polyphonic_envelope_bank #", "bank_reference #")
        for wave in ["sine_1024_8192.mem", "sine_1024_32767.mem", "velocity_gain_rom.mem", "piano_band_4x256_8191.mem"]:
            content = content.replace("model/generated/wavetables/" + wave, (snapshot / ("code/model/generated/wavetables/" + wave)).as_posix())
        ref = sim / (refname + ".sv"); ref.write_text(content, encoding="utf-8")
        reference_sources.append(ref)
    top = sim / "reference_top.sv"
    top.write_text(Path(info["formal_reference_top"]).read_text(encoding="utf-8").replace("polyphonic_audio_core u_audio_core", "core_reference u_audio_core").replace("button_event_converter #", "button_reference #"), encoding="utf-8")
    # Buffered PCM and physical audio pins remain identical; computation/counters
    # and event-ready may settle a few sys cycles later inside the same frame.
    tb = sim / "tb_pipeline_coexistence.sv"
    test = (ROOT / "code/tb/board/tb_audio_visual_coexistence.sv").read_text(encoding="utf-8")
    test = test.replace("i2s_din,pa_en,uart_tx,dut.buffered_left", "i2s_din,pa_en,dut.buffered_left")
    test = test.replace("r_i2s_din,r_pa_en,r_uart_tx,reference_top.buffered_left", "r_i2s_din,r_pa_en,reference_top.buffered_left")
    test = test.replace("dut.audio_underrun,dut.status_active_voice_count,dut.pcm_commit_count,\n              dut.core_max_processing_cycles", "dut.audio_underrun")
    test = test.replace("reference_top.audio_underrun,\n              reference_top.status_active_voice_count,reference_top.pcm_commit_count,\n              reference_top.core_max_processing_cycles", "reference_top.audio_underrun")
    test = test.replace("if(dut.rst_sync_n && dut.i2s_frame_tick)begin", "if(dut.rst_sync_n && dut.i2s_frame_tick)begin\n            if(dut.status_active_voice_count !== reference_top.status_active_voice_count) $fatal(1,\"frame-aligned voice count changed\");")
    test = test.replace("i2s_din,pa_en,dut.buffered_left,dut.buffered_right,\n              dut.audio_underrun", "i2s_din,pa_en,dut.audio_underrun")
    test = test.replace("r_i2s_din,r_pa_en,reference_top.buffered_left,\n              reference_top.buffered_right,reference_top.audio_underrun", "r_i2s_din,r_pa_en,reference_top.audio_underrun")
    test = test.replace("pcm_frames++;", """if(dut.pcm_commit_count !== reference_top.pcm_commit_count ||
               dut.pcm_request_count !== reference_top.pcm_request_count ||
               dut.buffered_left !== reference_top.buffered_left ||
               dut.buffered_right !== reference_top.buffered_right)
                $fatal(1, "frame-adopted PCM/counts changed");
            pcm_frames++;""")
    # Compare data only after both candidates have committed the same request;
    # earlier combinational play_left exposes newly completed pending PCM.
    test = test.replace("if(dut.rst_sync_n && dut.i2s_frame_tick)begin", """if(dut.pending_valid && reference_top.pending_valid &&
           dut.g_polyphonic.u_audio_core.sample_req_id==reference_top.g_polyphonic.u_audio_core.sample_req_id &&
           {dut.buffered_left,dut.buffered_right} !== {reference_top.buffered_left,reference_top.buffered_right})
            $fatal(1,"same-request committed PCM changed");
        if(dut.rst_sync_n && dut.i2s_frame_tick)begin""")
    test = test.replace("$finish;", """$display("PIPELINE processing_peak candidate=%0d reference=%0d",dut.core_max_processing_cycles,reference_top.core_max_processing_cycles);
        $finish;""")
    tb.write_text(test, encoding="utf-8")
    sources += reference_sources + [top, ROOT / "code/tb/board/audio_visual_phy_model.sv", tb]
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
