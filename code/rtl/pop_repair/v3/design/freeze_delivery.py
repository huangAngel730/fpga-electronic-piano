"""One-shot freeze gate; reads source/old code and writes ONLY design manifests.

Never overwrite an existing DESIGN_READY. No source generation or mutation.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
REPO = Path(r"E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano")
PARENT = Path(r"E:\FPGA\GAOYUNFPGA")
PYTHON = r"C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(name, payload):
    (ROOT/"design"/name).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")

if __name__=="__main__":
    ready = ROOT/"design"/"DESIGN_READY.json"
    if ready.exists():
        raise SystemExit("Refusing to replace frozen gate; source rework requires explicit authorization")
    mappings = {
        "piano_dds_oscillator.sv":REPO/"code/rtl/audio/piano_dds_oscillator.sv",
        "adsr_piano_envelope.sv":REPO/"code/rtl/audio/adsr_piano_envelope.sv",
        "polyphonic_envelope_bank.sv":REPO/"code/rtl/board/polyphonic_envelope_bank.sv",
        "polyphonic_audio_core.sv":REPO/"code/rtl/board/polyphonic_audio_core.sv",
        "piano_wavetable_gen.py":REPO/"code/model/piano_wavetable_gen.py",
        "adsr_piano.py":REPO/"code/model/adsr_piano.py",
        "audio_defs.py":REPO/"code/model/audio_defs.py",
        "piano_band_4x256_8191.mem":REPO/"code/model/generated/wavetables/piano_band_4x256_8191.mem",
        "velocity_gain_rom.mem":REPO/"code/model/generated/wavetables/velocity_gain_rom.mem",
        "note_pitch.sv":REPO/"code/rtl/common/note_pitch.sv",
        "generate_wavetable_v2.py":PARENT/"pop_repair/model/generate_wavetable_v2.py",
    }
    provenance=[]
    for name, original in mappings.items():
        copied=ROOT/"source/baseline"/name
        assert sha(original)==sha(copied), f"Original differs from copied baseline: {original}"
        provenance.append({"original":str(original),"copied":str(copied),
                           "sha256":sha(copied),"bytes":copied.stat().st_size,
                           "copy_check":"original SHA calculated before copy and compared; current original rechecked equal at freeze"})
    old_manifest=ROOT/"verification/old_versions_baseline.json"
    old=json.loads(old_manifest.read_text(encoding="utf-8"))["roots"]
    old_count=0
    for directory, entries in old.items():
        directory=Path(directory)
        current={p.relative_to(directory).as_posix() for p in directory.rglob("*")
                 if p.is_file() and p.relative_to(directory).parts[0]!="v3"
                 and not {"__pycache__",".pytest_cache",".git"}.intersection(p.relative_to(directory).parts)}
        assert current==set(entries), f"Old-file inventory changed: {directory}"
        for relative, record in entries.items():
            assert sha(directory/relative)==record["sha256"], f"Old-file content changed: {relative}"
            old_count+=1
    reference=ROOT/"verification/baseline_reference_manifest.json"
    reference_inputs=json.loads(reference.read_text(encoding="utf-8"))["files"]
    for path, record in reference_inputs.items():
        assert sha(Path(path))==record["sha256"], f"Formal input changed: {path}"
    protected = [PARENT/"AIRead/DOC_INDEX.md",PARENT/"AIRead/BOARD_CONTEXT.md",PARENT/"AGENTS.md",
                 REPO/"code/rtl/board/electronic_piano_top.sv",REPO/"code/rtl/common/audio_defs_pkg.sv",
                 REPO/"code/constraints/electronic_piano.cst",REPO/"code/constraints/audio_timing.sdc"]
    head=subprocess.check_output(["git","-C",str(REPO),"rev-parse","HEAD"],text=True).strip()
    status=subprocess.check_output(["git","-C",str(REPO),"status","--short"],text=True).strip()
    assert head=="427f3d33d6559e83b31e7e5347993db7dc4fa124", "Baseline HEAD changed; reconcile rather than mislabel"
    inputs={"utc":datetime.now(timezone.utc).isoformat(),"formal_baseline_head":head,
            "formal_git_status":status,"baseline_copies":provenance,
            "formal_dependencies_main2_snapshot_manifest":{"path":str(reference),"sha256":sha(reference),"files":reference_inputs},
            "protected_files":{str(p):sha(p) for p in protected},
            "old_versions_audit":{"manifest":str(old_manifest),"manifest_sha256":sha(old_manifest),
                                  "files_checked":old_count,"sha_inventory_unchanged":True}}
    save("input_manifest.json",inputs)
    source_files={p.relative_to(ROOT).as_posix():{"sha256":sha(p),"bytes":p.stat().st_size}
                  for p in sorted((ROOT/"source").rglob("*")) if p.is_file()}
    assert not any("__pycache__" in p for p in source_files)
    tests=json.loads((ROOT/"design/model_results/oscillator_rtl_results.json").read_text(encoding="utf-8"))
    assert sum(t["samples"] for t in tests)==10240 and all(t["status"]=="PASS" for t in tests)
    assert "PASS V3 bank latency" in (ROOT/"design/model_results/bank_latency.log").read_text(encoding="utf-8")
    dependencies={"python_exe":PYTHON,"numpy":"2.3.5","scipy_required":False,
                  "iverilog":"D:/Gowin/oss-cad-suite/bin/iverilog.exe",
                  "vvp":"D:/Gowin/oss-cad-suite/bin/vvp.exe",
                  "child_environment_bat":"D:/Gowin/oss-cad-suite/environment.bat",
                  "independent_metrics":{"path":str(ROOT/"verification/audio_metrics.py"),"sha256":sha(ROOT/"verification/audio_metrics.py")}}
    commands={"cwd":str(ROOT),
              "model_selftest_and_audio":f'& "{PYTHON}" -B "{ROOT / "source/model/diagnose_v3.py"}" --selftest --audio',
              "oscillator_and_stub_bank_rtl":f'& "{PYTHON}" -B "{ROOT / "source/model/run_oscillator_check.py"}"',
              "exploration":f'& "{PYTHON}" -B "{ROOT / "design/explore_spectrum.py"}" --variant conservative12',
              "asset_generator_provenance_only":"source/model/generate_v3_assets.py; DO NOT run against frozen source. Run on an authorized separate build copy if reproducing."}
    payload={"schema_version":1,"status":"DESIGN_READY_SOURCE_FROZEN_RESEARCH_CANDIDATE",
             "utc":datetime.now(timezone.utc).isoformat(),"source_root":str(ROOT/"source"),
             "source_files":source_files,"source_sha256":{k:v["sha256"] for k,v in source_files.items()},
             "input_manifest":{"path":str(ROOT/"design/input_manifest.json"),"sha256":sha(ROOT/"design/input_manifest.json")},
             "implementation":{"path":str(ROOT/"design/IMPLEMENTATION.md"),"sha256":sha(ROOT/"design/IMPLEMENTATION.md")},
             "strategy":"<=220Hz 12 integer partials with Q16 independent extra decay and smoothed restrike; >220Hz unchanged formal V1. No detuning or random phase. Current formal ADSR unchanged.",
             "formal_build_baseline":{"head":head,"not_legacy_54774f1":True,"cc64":"preserve current formal router; full candidate regression pending",
                                      "stat":"preserve normal seven-field formal STAT; full candidate regression pending",
                                      "hdmi":"not in current formal top; NOT added; no audiovisual coexistence claim"},
             "dependencies":dependencies,"commands":commands,
             "rtl_integration":{"replace":"source/rtl/polyphonic_envelope_bank.sv",
                                "add":"source/rtl/piano_dds_oscillator_v3.sv","keep_v1_oscillator":True,
                                "include_dir":"source/rtl","wave_rom_file":"V1 piano_band_4x256_8191.mem, NOT new sine ROM",
                                "sine_rom_file":"source/rom/sine_v3_1024_32767.mem relative to tool cwd",
                                "exclude_tb_from_synthesis":True,"tick_to_wave_clocks":37,"tick_to_snapshot_clocks":41,
                                "cancel_guard_clocks":40},
             "performed":{"model_invariants":"PASS; formal float ADSR reference is not RTL bit exact",
                          "oscillator_rtl_exact_samples":10240,"bank_stub_rtl_exact_commits":128,
                          "bank_stub_advance_count":129,"old_files_sha_unchanged":True},
             "acceptance":{"functional_full_top":"NOT_RUN_BY_IMPLEMENTER","beat_perception":"NOT_ACCEPTED",
                           "lowest_C1_pair":"no improvement in normalized slow/fast diagnostics",
                           "other_low_pairs":"partial slow proxy reduction with increased fast proxy; not proven listening benefit",
                           "synthesis":"NOT_RUN_BY_IMPLEMENTER","pnr_timing":"NOT_RUN_BY_IMPLEMENTER",
                           "bitstream":"NOT_GENERATED","board":"NOT_RUN","flash":"NOT_TOUCHED"},
             "limitations":["Candidate remains lower RMS at same peak; raw quieter is NOT beat success.",
                            "Eight Gaussian analysis bands are diagnostic only, not ISO roughness or loudness.",
                            "WAV uses static lanes, FLOAT formal ADSR and diagnostic PCM16, not full PCM24 chain.",
                            "Bank TB uses router stub; M2 must verify real allocator/CC64/voice steals.",
                            "Resources are estimates only; no actual timing or device compilation proof.",
                            "No HDMI integration, no blind listening or board capture."],
             "freeze_rule":"No more source writes; append design/ISSUES.md only. Source rework requires explicit authorization/main2 halt.",
             "release_rule":"Research/validation gate only, not permission to program board or call low-note beat repaired."}
    save("DESIGN_READY.json",payload)
    print("FROZEN",len(source_files),"source files;",old_count,"old files unchanged;",len(reference_inputs),"formal dependencies unchanged")
    print("Gate",ready,"SHA256",sha(ready))
