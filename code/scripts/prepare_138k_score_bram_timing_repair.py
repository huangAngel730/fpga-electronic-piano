"""Prepare isolated same-cycle parser and directed Hold candidate, no tools."""
from pathlib import Path
import argparse
import hashlib
import json

import prepare_138k_score_bram_integration as parent

ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = ROOT / "code/build/138k_score_bram_timing_repair"
SCOPE = ROOT / "code/rtl/138K_try/score_bram_timing_repair_20261010"
VERSION = "score_bram_parser_compare_hold_v1"
PROJECT = parent.PROJECT


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def guard(output):
    output = output.resolve()
    output.relative_to(BUILD_ROOT.resolve())
    if output == BUILD_ROOT.resolve():
        raise ValueError("REFUSE_ROOT")
    return output


def inputs(output):
    manifest = json.loads((SCOPE / "revision_manifest.json").read_bytes())
    if (manifest.get("new_EDA_runs") != 0 or manifest.get("physical_STA_passed") is not False
            or manifest.get("programmed") is not False):
        raise ValueError("REVISION_SCOPE")
    data, provenance, project, tcl, _ = parent.inputs(output)
    key = "sources/midi_event_parser.sv"
    original = data[key]
    candidate = (SCOPE / key).read_bytes()
    if (sha(original) != manifest["frozen_parser_sha256"]
            or sha(candidate) != manifest["candidate_parser_sha256"]):
        raise ValueError("PARSER_EXACT_SOURCE_SHA")
    data[key] = candidate
    provenance[key].update(frozen_RAM_parser_sha256=sha(original),
                           adapted_sha256=sha(candidate),
                           repair_scope="fixed-channel compare, fixed-slot CE, no sequential change")
    key = "constraints/audio_visual_hold055.sdc"
    old = data[key]
    commands = manifest["additional_hold_sdc_commands"]
    if (len(commands) != 3 or not commands[0].startswith("set_min_delay -from ")
            or not commands[0].endswith(" 0.100")
            or not commands[1].startswith("report_timing -setup ")
            or not commands[2].startswith("report_timing -hold ")):
        raise ValueError("EXACT_DIRECTED_HOLD_COMMANDS")
    data[key] = old + ("\n# M2 exact reported PitchMod short path; keep650ps uncertainty.\n"
                       + "\n".join(commands) + "\n").encode("utf-8")
    provenance[key].update(frozen_RAM_SDC_sha256=sha(old), adapted_sha256=sha(data[key]),
                           repair_scope="append one exact min_delay and two directed reports")
    if len(data) != 62:
        raise ValueError("EXACT62_INPUTS")
    return data, provenance, project, tcl


def expected(output):
    data, provenance, project, tcl = inputs(output)
    receipt = {"date": "2026-10-10", "version": VERSION, "input_count": 62, "project_file_count": 53,
               "inputs": provenance, "prepare_script_sha256": sha(Path(__file__).read_bytes()),
               "parent_prepare_sha256": sha(Path(parent.__file__).read_bytes()),
               "revision_manifest_sha256": sha((SCOPE / "revision_manifest.json").read_bytes()),
               "project_sha256": sha(project), "run_tcl_sha256": sha(tcl),
               "device": parent.base.parent.parent.parent.original.EXPECTED_DEVICE,
               "no_registers_or_latency_added": True, "clocks_ROM_PLL_CST_unchanged": True,
               "fulltop_simulation_completed": False, "physical_STA_passed": False,
               "ready_for_PnR": False, "board_release_allowed": False, "programmed": False}
    return data, project, tcl, receipt


def receipt_bytes(record):
    return (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def validate(output):
    output = guard(output)
    data, project, tcl, record = expected(output)
    actual = {p.relative_to(output / "inputs").as_posix(): p.read_bytes()
              for p in (output / "inputs").rglob("*") if p.is_file()}
    if data != actual:
        raise ValueError("EXACT62_REPAIR_INPUTS_OR_HIDDEN_FILE")
    if (output / PROJECT).read_bytes() != project or (output / "run.tcl").read_bytes() != tcl:
        raise ValueError("EXACT_REPAIR_PROJECT_OPTIONS")
    if (output / "frozen_receipt.json").read_bytes() != receipt_bytes(record):
        raise ValueError("EXACT_REPAIR_RECEIPT_BYTES")
    print("PASS isolated timingrepair62/53 identity only; no tools/physical release", flush=True)
    return record


def prepare(output):
    output = guard(output)
    if output.exists():
        raise ValueError("REFUSE_OVERWRITE")
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
