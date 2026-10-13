"""Generate isolated GW5A pROM successor; never invokes synthesis or simulation."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "code/build/138k_polyphony_resource/prepared/N32_R1_20261011_01"
DEST = ROOT / "code/rtl/common/m2_n32_prom_candidate_20261013"
VENDOR = Path("D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/simlib/gw5a/prim_sim.v")
VENDOR_SHA = "202f65ccf77126d04e47db36c95e237e48522f3a105a3e64d9fcbf4e3b782f27"
PINS = {
    "adsr_piano_envelope.sv": "1f4f6b0a53f403192d5089ee18e37717e6a927ffd2434cc2cf59435ea385eaab",
    "pitch_mod_fcw_pipeline.sv": "046c01b7f02f7c3a9ea32f58e21c0833a969e825a06b4a175232005594263588",
    "b2_audio_backend.sv": "90d8a09ffef56b873dfe495b9abbc987a0d37a405b4292a26c1327d5ea304452",
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("EXACT_REPLACEMENT_COUNT:" + old[:55])
    return text.replace(old, new)


def encode_fraction(x):
    return x ^ (((x << 1) | (x >> 9)) & 1023) ^ (((x << 3) | (x >> 7)) & 1023)


def primitive(instance, values, width, address, bus):
    bitstream = sum(value << (i * width) for i, value in enumerate(values))
    if bitstream.bit_length() > 16384:
        raise ValueError("PRIMITIVE_CAPACITY")
    params = [".READ_MODE(1'b0)", ".BIT_WIDTH(" + str(width) + ")", '.RESET_MODE("SYNC")']
    params += [".INIT_RAM_%02X(256'h%064x)" % (i, (bitstream >> (256 * i)) & ((1 << 256) - 1)) for i in range(64)]
    return "    pROM #(\n        " + ",\n        ".join(params) + ") " + instance + " (\n        .DO(" + bus + "),.AD(" + address + "),.CLK(clk),.CE(ce),.OCE(1'b1),.RESET(1'b0));\n"


def wrapper(name, words, bits, addr_bits):
    header = "// Generated from frozen ROM numeric words. Single synchronous CE read; no local reset.\n"
    text = header + "module m2_prom_" + name + "(input wire clk,ce,input wire [" + str(addr_bits - 1) + ":0] addr,output wire [" + str(bits - 1) + ":0] data);\n"
    if bits == 16:
        text += "    wire [31:0] q;\n"
        text += primitive("storage", words, 16, "{addr,4'b0}", "q")
        text += "    assign data=q[15:0];\n"
        count = 1
    elif addr_bits == 6:
        text += "    wire [31:0] q;\n"
        text += primitive("storage", words, 32, "{3'b0,addr,5'b0}", "q")
        text += "    assign data=q[19:0];\n"
        count = 1
    else:
        text += "    wire [31:0] lo,hi;\n"
        text += primitive("storage_lo", [v & 65535 for v in words], 16, "{addr,4'b0}", "lo")
        text += primitive("storage_hi", [v >> 16 for v in words], 4, "{2'b0,addr,2'b0}", "hi")
        text += "    assign data={hi[3:0],lo[15:0]};\n"
        count = 2
    return (text + "endmodule\n").encode(), count


def expected():
    if sha(VENDOR.read_bytes()) != VENDOR_SHA:
        raise ValueError("EXACT_GW5A_VENDOR_MODEL_SHA")
    source = {}
    for name, pin in PINS.items():
        raw = (BASE / "sources" / name).read_bytes()
        if sha(raw) != pin:
            raise ValueError("EXACT_FROZEN_SOURCE:" + name)
        source[name] = raw.decode()
    rom_names = {"gain": ("velocity_gain_rom.mem", 16, 10, 1024),
                 "oct": ("oct_ratio_q16.mem", 20, 6, 50),
                 "sub": ("sub_ratio_q16.mem", 20, 10, 1024),
                 "lfo": ("lfo_sine_q15.mem", 16, 10, 1024),
                 "wave": ("piano_band_4x256_8191.mem", 16, 10, 1024)}
    payload, roms, maps = {}, {}, {}
    for name, (filename, width, addr, length) in rom_names.items():
        raw = (BASE / "rom" / filename).read_bytes()
        words = [int(w, 16) for w in raw.split()]
        if len(words) != length or any(w >= 1 << width for w in words):
            raise ValueError("EXACT_ROM_SHAPE:" + filename)
        words = words + [0] * ((1 << addr) - length)
        if name == "sub":
            permuted = [0] * 1024
            if len({encode_fraction(i) for i in range(1024)}) != 1024:
                raise ValueError("FRACTION_ENCODING_NOT_BIJECTIVE")
            for i, value in enumerate(words):
                permuted[encode_fraction(i)] = value
            words = permuted
        data, count = wrapper(name, words, width, addr)
        payload["m2_prom_" + name + ".sv"] = data
        roms[filename] = dict(bytes=len(raw), sha256=sha(raw))
        maps[name] = dict(bits=width, address_bits=addr, words=length, explicit_pROM_instances=count,
                          unused_addresses="zero padded; oct legal lookup stays0..49",
                          fraction_permutation=name == "sub")
    edits = {}
    old = source["adsr_piano_envelope.sv"]
    new = replace_once(old, "module adsr_piano_envelope (", "module m2_adsr_piano_prom (")
    start = new.index("    logic [15:0] gain_rom [0:1023];")
    end = new.index("    // Preserve M1's public debug encoding", start)
    new = new[:start] + "    m2_prom_gain gain_storage(.clk(sys_clk),.ce(1'b1),.addr(rom_addr),.data(rom_dout));\n\n" + new[end:]
    edits["m2_adsr_piano_prom.sv"] = (old, new)
    old = source["pitch_mod_fcw_pipeline.sv"]
    new = replace_once(old, "module pitch_mod_fcw_pipeline #(", "module m2_pitch_mod_prom #(")
    new = replace_once(new, " logic[19:0]oct_lut[0:49],sub_lut[0:1023];\n logic[19:0]sub_source[0:1023];\n", "")
    start = new.index(" logic signed[15:0]lfo_lut[0:1023];")
    end = new.index(" logic[31:0]lfo_phase;", start)
    new = new[:start] + new[end:]
    old_capture = " always_ff @(posedge sys_clk)begin\n  if(sample_enable)sine_s0<=lfo_lut[phase_now[31:22]];\n  if(valid_pipe[2])begin oct_s3<=oct_lut[oct_index];sub_s3<=sub_lut[encode_fraction(sub_index)];end\n end"
    new_capture = " m2_prom_lfo sine_storage(.clk(sys_clk),.ce(sample_enable),.addr(phase_now[31:22]),.data(sine_s0));\n m2_prom_oct oct_storage(.clk(sys_clk),.ce(valid_pipe[2]),.addr(oct_index),.data(oct_s3));\n m2_prom_sub sub_storage(.clk(sys_clk),.ce(valid_pipe[2]),.addr(encode_fraction(sub_index)),.data(sub_s3));"
    new = replace_once(new, old_capture, new_capture)
    edits["m2_pitch_mod_prom.sv"] = (old, new)
    old = source["b2_audio_backend.sv"]
    new = replace_once(old, "module b2_audio_backend #(", "module m2_b2_backend_prom #(")
    new = replace_once(new, "adsr_piano_envelope u_adsr(", "m2_adsr_piano_prom u_adsr(")
    new = replace_once(new, "pitch_mod_fcw_pipeline #(", "m2_pitch_mod_prom #(")
    new = replace_once(new, "    logic signed [15:0] wave_rom [0:1023];\n", "")
    new = replace_once(new, "    initial $readmemh(WAVE_FILE,wave_rom);\n    always_ff @(posedge clk) if(state==ROM_START && !cancel)\n        wave_q<=wave_rom[wave_addr];", "    m2_prom_wave wave_storage(.clk(clk),.ce(state==ROM_START && !cancel),.addr(wave_addr),.data(wave_q));")
    # Original simulation-only array check references the replaced array.
    new = replace_once(new, "        for(integer a=0;a<1024;a=a+1)\n            if(^wave_rom[a]===1'bx) $fatal(1,\"MISSING_PIANO_ROM_WORD\");\n", "")
    edits["m2_b2_backend_prom.sv"] = (old, new)
    clip = ROOT / "code/rtl/common/m2_n32_clipped_candidate_20261012/b2d_event_audio_clipped.sv"
    raw_clip = clip.read_bytes()
    if sha(raw_clip) != "3fd292ab7a3748f10054ec5eb26d44f20b83880073a220aa6b4ddc2f1a98427f":
        raise ValueError("EXACT_CLIPPED_SUCCESSOR_SHA")
    new_clip = replace_once(raw_clip.decode(), "module b2d_event_audio_clipped #(", "module m2_b2d_event_audio_prom #(")
    new_clip = replace_once(new_clip, "b2_audio_backend #(", "m2_b2_backend_prom #(")
    edits["m2_b2d_event_audio_prom.sv"] = (raw_clip.decode(), new_clip)
    diff = []
    for name, (old, new) in edits.items():
        payload[name] = new.encode()
        diff += difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile="readonly_original/" + name, tofile=name)
    payload["SOURCE_DIFF.patch"] = "".join(diff).encode()
    receipt = dict(schema=1, status="ISOLATED_PROM_CANDIDATE_NOT_SYNTHESIZED", generator_sha256=sha(Path(__file__).read_bytes()),
                   frozen_source_SHA=PINS, clipped_source_SHA=sha(raw_clip), original_ROMs=roms,
                   vendor_model=dict(path=str(VENDOR), sha256=VENDOR_SHA, model_version_header="1.9.10 within installed1.9.11.03"),
                   ROM_mapping=maps, primitive_configuration="pROM READ_MODE0 synchronous bypass, CE original, RESET0, OCE1",
                   expected_explicit_pROM_instance_count_N32=32 * (1 + 1 + 2 + 1) + 1,
                   instance_count_is_not_actual_BSRAM_report=True,
                   original_runtime_ROM_override_support="NOT_SUPPORTED; fixed frozen ROM identity only, parameter paths retained for mechanical compatibility not configurable numeric source",
                   change_scope="private read ROM replaces original read registers, arithmetic/reset/event/calendar preserved",
                   original_algorithm_ROM_changed=False, synthesized=False, physical_STA="NOT_RUN", production_connected=False,
                   artifacts={n: dict(bytes=len(b), sha256=sha(b)) for n, b in payload.items()})
    payload["candidate_receipt.json"] = canonical(receipt)
    return payload, receipt


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--check", action="store_true")
    args = cli.parse_args()
    payload, report = expected()
    if args.check:
        actual = {p.name: p.read_bytes() for p in DEST.iterdir() if p.is_file()}
        if actual != payload:
            raise ValueError("EXACT_GENERATED_CANDIDATE_SHA")
    else:
        if DEST.exists():
            raise ValueError("REFUSE_EXISTING_CANDIDATE")
        DEST.mkdir(parents=True, exist_ok=False)
        for name, raw in payload.items():
            with (DEST / name).open("xb") as stream:
                stream.write(raw)
    print(json.dumps(dict(status=report["status"], files=len(payload), planned_pROM_N32=161, new_synthesis_calls=0)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
