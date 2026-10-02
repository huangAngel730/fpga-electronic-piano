"""Prepare an isolated frozen-ADSR + exact-contact flash combination.

No production audio/top/constraint source is edited. The original immutable
Git audio is prepared first, then exactly three reviewed source files override
output copies: ADSR pipeline, private bank waits, parallel saturation counter.
New physical STA and hardware checks are required; preparing is NOT acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from prepare_audio_visual_probe import prepare

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--vendor", required=True, type=Path)
    cfg = parser.parse_args()
    out = cfg.output.resolve()
    out.relative_to(ROOT / "code/output")
    if out.exists():
        parser.error("output already exists; preserve prior report and candidate bytes")
    out.mkdir(parents=True)
    subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "code/scripts/run_adsr_pipeline_isolated.py"),
                    "--output", str(out / "reviewed_pipeline_sources"), "--generate-only"],
                   cwd=ROOT, check=True, timeout=60)
    subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "code/scripts/run_control_chain_isolation.py"),
                    "--output", str(out / "reviewed_counter_sources"), "--generate-only"],
                   cwd=ROOT, check=True, timeout=60)
    stage = out / "prepared"
    info = prepare(stage, cfg.vendor)
    # Preserve original proof. The snapshot and all original dependency hashes
    # are immutable; only staged sources change and are separately identified.
    (stage / "original_preparation_inputs.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    snapshot = Path(info["snapshot"])
    sources = {
        "adsr_piano_envelope.sv": out / "reviewed_pipeline_sources/adsr_piano_envelope.sv",
        "polyphonic_envelope_bank.sv": out / "reviewed_pipeline_sources/polyphonic_envelope_bank.sv",
        "button_event_converter.sv": out / "reviewed_counter_sources/button_parallel_counter_formal_name.sv",
    }
    changes = {}
    for name, source in sources.items():
        target = stage / "staged_sources" / name
        before = digest(target)
        text = source.read_text(encoding="utf-8")
        for rom in ("velocity_gain_rom.mem", "sine_1024_32767.mem", "sine_1024_8192.mem", "piano_band_4x256_8191.mem"):
            text = text.replace("model/generated/wavetables/" + rom,
                                (snapshot / ("code/model/generated/wavetables/" + rom)).as_posix())
        target.write_text(text, encoding="utf-8", newline="\n")
        changes[name] = {"original_staged_sha256": before, "reviewed_patch_source_sha256": digest(source),
                         "actual_build_sha256": digest(target), "source_path": str(source)}
    final_inputs = {path: digest(Path(path)) for path in info["input_sha256"]}
    # Do not relabel replacement inputs as original Git audio.
    info["input_sha256"] = final_inputs
    info["staged_audio_sha256"] = {path: digest(stage / path) for path in info["staged_audio_sha256"]}
    info["scope"] = "M2 three-source output override + current visual candidate; not production/hardware approval"
    info["reviewed_audio_source_overrides"] = changes
    (stage / "inputs.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    protection = ("code/rtl/audio/adsr_piano_envelope.sv", "code/rtl/board/polyphonic_envelope_bank.sv",
                  "code/rtl/input/button_event_converter/button_event_converter.sv",
                  "code/rtl/common/performance_event_fifo.sv", "code/rtl/board/electronic_piano_top.sv",
                  "code/rtl/common/audio_defs_pkg.sv", "code/constraints/electronic_piano.cst",
                  "code/constraints/audio_timing.sdc", "code/docs/模块接口规范.md")
    record = {"date": "2026-10-02", "formal_files_unchanged": True,
              "protected_formal_sha256": {name: digest(ROOT / name) for name in protection},
              "changes": changes, "actual_input_sha256": final_inputs,
              "constraints_sha256": {name: digest(stage / name) for name in ("audio_visual.cst", "audio_visual.sdc")},
              "physical_STA_completed": False, "board_programmed": False,
              "private_role_scope_handoff_required_before_formal_adoption": True,
              "source_label": "Frozen V0153 ADSR/bank + V0151 counter + current scoped visual source"}
    (stage / "combo_override.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("Prepared isolated combo at", stage)
    print("Run real regression/STA before judging any margin; no board or formal source changes.")


if __name__ == "__main__":
    main()
