"""Exact new-cache RAM + same-edge MIDI repair + directed Hold candidate."""
from pathlib import Path
import argparse
import hashlib
import json

import prepare_138k_score_bram_timing_repair as repair
import prepare_138k_score_bram_integration as old_ram

ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = ROOT / "code/build/138k_night_cache_combo"
SCOPE = ROOT / "code/rtl/138K_try/night_cache_combo_20261010"
VERSION = "night_cache_parser_hold_20261010_v1"
PROJECT = repair.PROJECT
base = old_ram.base


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def guard(output):
    output = output.resolve()
    output.relative_to(BUILD_ROOT.resolve())
    if output == BUILD_ROOT.resolve():
        raise ValueError("REFUSE_COMBO_ROOT")
    return output


def inputs(output):
    manifest = json.loads((SCOPE / "integration_manifest.json").read_bytes())
    if (manifest["version"] != VERSION or manifest["physical_STA_passed"] is not False
            or manifest["board_release_allowed"] is not False
            or sha(Path(repair.__file__).read_bytes()) != manifest["repair_prepare_sha256"]):
        raise ValueError("EXACT_COMBO_SCOPE")
    data, provenance, project, tcl = repair.inputs(output)
    for relative, expected in manifest["new_RAM_sha256"].items():
        raw = (ROOT / relative).read_bytes()
        if sha(raw) != expected:
            raise ValueError("NEW_RAM_SOURCE_DRIFT:" + relative)
        key = "sources/" + Path(relative).name
        old = data[key]
        data[key] = raw
        provenance[key].update(frozen_previous_RAM_sha256=sha(old), adapted_sha256=expected,
                               repo_reference=relative, reference_commit=manifest["new_RAM_commit"])
    if (sha(data["sources/midi_event_parser.sv"]) != manifest["candidate_parser_sha256"]
            or len(data) != 62):
        raise ValueError("COMBO_PARSER_OR_COUNTS")
    return data, provenance, project, tcl


def expected(output):
    data, provenance, project, tcl = inputs(output)
    receipt = {"date": "2026-10-10", "version": VERSION, "input_count": 62, "project_file_count": 53,
               "inputs": provenance, "prepare_script_sha256": sha(Path(__file__).read_bytes()),
               "integration_manifest_sha256": sha((SCOPE / "integration_manifest.json").read_bytes()),
               "project_sha256": sha(project), "run_tcl_sha256": sha(tcl),
               "device": repair.parent.base.parent.parent.parent.original.EXPECTED_DEVICE,
               "new_RAM_reference_commit": "5e1d13c398fd1cf749c613a30b9238d1a46319b4",
               "MIDI_same_cycle_repair": True, "expected_score_BSRAM": 9,
               "clocks_ROM_PLL_CST_unchanged": True, "fulltop_simulation_completed": False,
               "physical_STA_passed": False, "ready_for_PnR": False,
               "board_release_allowed": False, "programmed": False}
    return data, project, tcl, receipt


def receipt_bytes(record):
    return (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def validate(output):
    output = guard(output)
    data, project, tcl, record = expected(output)
    actual = {p.relative_to(output / "inputs").as_posix(): p.read_bytes()
              for p in (output / "inputs").rglob("*") if p.is_file()}
    if actual != data:
        raise ValueError("EXACT62_COMBO_INPUTS_OR_HIDDEN")
    if (output / PROJECT).read_bytes() != project or (output / "run.tcl").read_bytes() != tcl:
        raise ValueError("EXACT53_COMBO_PROJECT_OPTIONS")
    if (output / "frozen_receipt.json").read_bytes() != receipt_bytes(record):
        raise ValueError("EXACT_COMBO_RECEIPT_BYTES")
    print("PASS exact newcache/MIDIrepair/Hold combo62/53 identity; no physical release", flush=True)
    return record


def prepare(output):
    output = guard(output)
    if output.exists():
        raise ValueError("REFUSE_COMBO_OVERWRITE")
    data, project, tcl, record = expected(output)
    output.mkdir(parents=True, exist_ok=False)
    for relative, raw in data.items():
        target = output / "inputs" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (output / PROJECT).write_bytes(project)
    (output / "run.tcl").write_bytes(tcl)
    (output / "frozen_receipt.json").write_bytes(receipt_bytes(record))
    return validate(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    validate(args.output) if args.check else prepare(args.output)
