"""Read-only frozen-source mapping audit; no synthesis or old replay."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "code/build/138k_polyphony_resource/prepared/N32_R1_20261011_01"
PINS = {
    "b2_audio_backend.sv": "90d8a09ffef56b873dfe495b9abbc987a0d37a405b4292a26c1327d5ea304452",
    "pitch_mod_fcw_pipeline.sv": "046c01b7f02f7c3a9ea32f58e21c0833a969e825a06b4a175232005594263588",
    "adsr_piano_envelope.sv": "1f4f6b0a53f403192d5089ee18e37717e6a927ffd2434cc2cf59435ea385eaab",
    "b1_statebank.sv": "9ab598affbd317dedb5bdd7e099335ad1f60e3c84ed115f6669d52b3966521ed",
    "b2d_control_snapshot.sv": "9cb23b971d243e1dcf43d2acf0445239f1f26b2f0edc51476ce6a0d5c5d450fd"
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    texts = {}
    identities = {}
    for name, pin in PINS.items():
        path = BASE / "sources" / name
        actual = digest(path)
        if actual != pin:
            raise ValueError("EXACT_FROZEN_SOURCE_SHA:" + name)
        texts[name] = path.read_text(encoding="utf-8")
        identities[name] = actual
    checks = {
        "private_lanes": "for(genvar i=0;i<N;i=i+1) begin:g_continuous" in texts["b2_audio_backend.sv"],
        "shared_wave": "logic signed [15:0] wave_rom [0:1023];" in texts["b2_audio_backend.sv"],
        "private_gain": "logic [15:0] gain_rom [0:1023];" in texts["adsr_piano_envelope.sv"],
        "private_pitch": "logic[19:0]oct_lut[0:49],sub_lut[0:1023];" in texts["pitch_mod_fcw_pipeline.sv"],
        "private_lfo": "logic signed[15:0]lfo_lut[0:1023];" in texts["pitch_mod_fcw_pipeline.sv"],
        "source_initial_scratch": "logic[19:0]sub_source[0:1023];" in texts["pitch_mod_fcw_pipeline.sv"],
        "async_control_read": "wire [28:0] raw_word=control_mem[read_identity];" in texts["b2d_control_snapshot.sv"],
        "lane_product": "step_product_q <= step_delta_q * reciprocal_q;" in texts["adsr_piano_envelope.sv"],
    }
    if not all(checks.values()):
        raise ValueError("SOURCE_STRUCTURE_ANCHOR_CHANGED")
    # These are source-declared logical bits, NOT actual BSRAM/DSP/FF mapping.
    roms = [dict(name="ADSR gain", bits_per_lane=1024 * 16),
            dict(name="Pitch octave", bits_per_lane=50 * 20),
            dict(name="Pitch fraction", bits_per_lane=1024 * 20),
            dict(name="LFO sine", bits_per_lane=1024 * 16)]
    for row in roms:
        row["declared_copies"] = 32
        row["declared_total_bits"] = row["bits_per_lane"] * 32
    return dict(schema=1, status="SOURCE_MAPPING_AUDIT_ONLY", N=32, response=1,
                identities=identities, structural_checks=checks,
                declared_private_ROMs=roms,
                private_read_ROM_bits=sum(x["declared_total_bits"] for x in roms),
                shared_wave_ROM_bits=1024 * 16,
                combined_read_ROM_bits=sum(x["declared_total_bits"] for x in roms) + 1024 * 16,
                excluded_initialization_scratch_bits=32 * 1024 * 20,
                scratch_reason="sub_source only used to permute initialized sub_lut; physical elimination UNKNOWN",
                multiply_source_sites_per_lane=8,
                multiply_reason="ADSR3 products and Pitch5 products; constant optimization/widths prevent direct DSP count",
                controls=dict(B1_table_bits=256 * 29, frontend_snapshot_table_bits=256 * 29,
                              B1_double_context_bits=2 * 32 * 74,
                              asynchronous_read_mapping="UNKNOWN; variable-index mux/dedicated RAM not proven"),
                timeout_evidence=dict(stage="technical mapping", actual_attempts=1, limit_seconds=900,
                                      causal_claim="NOT_PROVEN", resources="UNKNOWN", fresh_netlist=False),
                safest_next_candidate="explicit synchronous ROM mapping preserving private lanes/latencies and exact numeric bytes",
                algorithm_change=False, actual_FF_BSRAM_DSP="UNKNOWN", actual_STA="NOT_RUN",
                old_specialty_replay=False, real_tool_calls=0, production_admission=False)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    out = args.output.resolve()
    root = (ROOT / "code/output").resolve()
    if out == root or not out.is_relative_to(root) or out.exists():
        raise ValueError("REFUSE_OUTPUT_SCOPE_OR_EXISTS")
    report = audit()
    out.mkdir(parents=True, exist_ok=False)
    (out / "source_mapping_audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("status", "private_read_ROM_bits", "combined_read_ROM_bits", "real_tool_calls")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
