"""H real-bank/gain/mixer -> G mono effect -> original PCM transport, TB only."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys

from run_m3_delay_transaction_candidate import (
    ROOT, Simulator, load_module, output_dir, sha, source_identity,
)

sys.dont_write_bytecode = True
BENCH = ROOT / "code/tb/board/m3_delay_pcm_acceptance"
BANK = ROOT / "code/tb/board/pitch_mod_bank_integration_candidate"
ADAPTER = ROOT / "code/tb/board/m3_delay_transaction_candidate/m3_delay_transaction_adapter.sv"


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path)
    cli.add_argument("--positive-only", action="store_true", help="development only, not full acceptance")
    cli.add_argument("--modelsim-bin", type=Path, default=Path(os.environ.get(
        "MODELSIM_BIN", "E:/FPGA/Bpan/modelsim/modelsim1/win64")))
    cli.add_argument("--check-capture", type=Path)
    args = cli.parse_args()
    checker = load_module("h_checker", BENCH / "scoreboard.py")
    if args.check_capture:
        try:
            print(json.dumps(checker.check_capture(args.check_capture), indent=2))
            return 0
        except (OSError, AssertionError, ValueError) as error:
            print("FAIL H capture:", error)
            return 1
    out = output_dir(args.output, "m3_delay_pcm_")
    evidence = dict(scope="H mono TB-only candidate L2/L3; no production/STA/board/no-pop claim",
                    passed=False, full_acceptance=not args.positive_only, cases=[])
    simulator = None
    try:
        evidence["readonly_sources"] = source_identity()
        simulator = Simulator(out, args.modelsim_bin)
        simulator.run("tool_version", [args.modelsim_bin / "vsim.exe", "-version"], out, 30)
        adsr = out / "adsr_generated"
        adsr.mkdir()
        patcher = load_module("existing_adsr_patch", ROOT / "code/scripts/run_adsr_pipeline_isolated.py")
        metadata, _ = patcher.patch_copies(adsr)
        evidence["generated_adsr"] = metadata
        relative = [
            "code/rtl/common/audio_defs_pkg.sv", "code/rtl/audio/voice_allocator_4.sv",
            "code/rtl/common/note_pitch.sv", "code/rtl/board/sustain_control_contract_pkg.sv",
            "code/rtl/input/sustain_control/sustain_controller.sv",
            "code/rtl/board/performance_control_snapshot.sv",
            "code/tb/board/pitch_mod_pipeline_candidate/pitch_mod_fcw_pipeline.sv",
            "code/tb/board/pitch_mod_pipeline_candidate/pitch_mod_snapshot_pipeline.sv",
            "code/rtl/audio/dds_oscillator.sv", "code/rtl/audio/piano_dds_oscillator.sv",
            "code/rtl/board/voice_gain_q15_candidate.sv", "code/rtl/mixer/pcm_mixer_4voice.sv",
            "code/rtl/audio_out/pcm_result_hold.sv", "code/rtl/audio_out/pcm_frame_buffer.sv",
            "code/rtl/audio/delay_effect.sv"]
        # Same F source/ROM validator, without repeating F simulation.
        f_runner = load_module("readonly_f_helpers", ROOT / "code/scripts/run_m3_midi_pcm_acceptance.py")
        evidence["F_dependency_identity"] = f_runner.validate_sources()
        sources = [ROOT / p for p in relative] + [
            BANK / "polyphonic_event_router.sv", BANK / "polyphonic_envelope_bank.sv",
            adsr / "adsr_piano_envelope.sv", ADAPTER, BENCH / "tb_delay_pcm.sv"]
        evidence["compiled_sources"] = {str(p): sha(p) for p in sources}
        evidence["helper_sources"] = {str(p): sha(p) for p in [
            BENCH / "scoreboard.py", Path(__file__), ROOT / "code/scripts/run_m3_delay_transaction_candidate.py"]}
        effect = ROOT / "code/rtl/audio/delay_effect.sv"
        cases = [("depth16", 16, None, None, None, None), ("depth1024", 1024, None, None, None, None)]
        if not args.positive_only:
            cases += [
                ("wrong_id", 16, ROOT / "code/rtl/audio_out/pcm_result_hold.sv", "pcm_req_id <= result_req_id;", "pcm_req_id <= result_req_id ^ 32'd1;", "PCM frame id"),
                ("wrong_address", 16, effect, "wr_ptr - delay_samples[ADDR_BITS-1:0]", "wr_ptr - delay_samples[ADDR_BITS-1:0] - 1'b1", "feedback history/address mismatch"),
                ("missing_wet", 16, effect, "$signed(dry_contrib) + $signed(wet_contrib)", "$signed(dry_contrib) + 25'sd0", "wet/tail PCM mismatch")]
        roms = {"wave.mem": "code/model/generated/wavetables/piano_band_4x256_8191.mem",
                "velocity.mem": "code/model/generated/wavetables/velocity_gain_rom.mem",
                "oct_ratio_q16.mem": "code/model/generated/pitch_mod/oct_ratio_q16.mem",
                "sub_ratio_q16.mem": "code/model/generated/pitch_mod/sub_ratio_q16.mem",
                "lfo_sine_q15.mem": "code/model/generated/pitch_mod/lfo_sine_q15.mem"}
        evidence["roms"] = {rel: sha(ROOT / rel) for rel in roms.values()}
        for name, depth, target, before, after, reason in cases:
            folder = out / name
            folder.mkdir()
            for rom, rel in roms.items():
                destination = folder / rom if rom in ("wave.mem", "velocity.mem") else folder / "model/generated/pitch_mod" / rom
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / rel, destination)
            selected = sources.copy()
            verdict = dict(name=name, passed=False)
            if target:
                text = target.read_text(encoding="utf-8")
                if text.count(before) != 1:
                    raise ValueError("mutation anchor " + name)
                mutant = folder / target.name
                mutant.write_text(text.replace(before, after, 1), encoding="utf-8", newline="\n")
                selected[selected.index(target)] = mutant
                verdict["mutant_sha256"] = sha(mutant)
            try:
                verdict["exit_codes"] = simulator.simulate(name, folder, selected, "tb_delay_pcm", [
                    f"-gDEPTH={depth}", "+VELOCITY_ROM_PATH=" + str(folder / "velocity.mem")])
                capture = folder / "delay_pcm.capture"
                verdict["capture_sha256"] = sha(capture)
                verdict["counts"] = checker.check_capture(capture)
                verdict["passed"] = reason is None
            except AssertionError as error:
                verdict["rejection"] = str(error)
                verdict["passed"] = reason is not None and reason in str(error)
            except RuntimeError:
                codes = [simulator.runs.get(name + "_" + phase, {}).get("exit_code") for phase in ("library", "compile", "run")]
                transcript = (out / (name + "_run.log")).read_text(encoding="utf-8", errors="replace") if codes[2] is not None else ""
                verdict["exit_codes"] = codes
                verdict["rejection"] = transcript[-1500:]
                verdict["passed"] = reason is not None and codes[:2] == [0, 0] and codes[2] not in (None, 0, 124) and reason in transcript
            evidence["cases"].append(verdict)
            if not verdict["passed"]:
                raise AssertionError("case failed: " + str(verdict))
        # Actual CLI must fail closed for malformed evidence, not just helper.
        original = (out / "depth16/delay_pcm.capture").read_text(encoding="ascii")
        evidence["capture_negatives"] = []
        for name, data in [("empty", ""), ("truncated", original.rsplit("END", 1)[0]),
                           ("unknown", original.replace("B ", "BAD ", 1))]:
            path = out / (name + ".capture")
            path.write_text(data, encoding="ascii")
            code, _ = simulator.run(name, [sys.executable, "-X", "utf8", __file__, "--check-capture", path], ROOT)
            if code != 1:
                raise ValueError("bad capture not rejected: " + name)
            evidence["capture_negatives"].append(dict(name=name, exit_code=code))
        if source_identity() != evidence["readonly_sources"]:
            raise ValueError("source changed during H")
        for group in ("compiled_sources", "helper_sources", "roms"):
            for name, digest in evidence[group].items():
                if sha(ROOT / name) != digest:
                    raise ValueError("dependency changed during H: " + name)
        evidence["passed"] = True
    except (OSError, ValueError, RuntimeError, AssertionError) as error:
        evidence["error"] = str(error)
        print("FAIL H:", error, flush=True)
    evidence["runs"] = simulator.runs if simulator else {}
    (out / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print("Evidence:", out / "evidence.json", flush=True)
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
