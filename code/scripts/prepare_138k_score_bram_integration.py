"""Prepare exact RAM fulltop addressing only; never run FPGA tools or release."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code/scripts"))
import prepare_138k_score_receive_integration as base

BUILD_ROOT = ROOT / "code/build/138k_score_bram"
SCOPE = ROOT / "code/rtl/138K_try/score_bram_integration_20261010"
VERSION = "score_bram_fulltop_prepare_v2"
PROJECT = base.PROJECT


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def receipt_bytes(record):
    return (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def guard(output):
    output = output.resolve()
    output.relative_to(BUILD_ROOT.resolve())
    if output == BUILD_ROOT.resolve():
        raise ValueError("REFUSE_BUILD_ROOT")
    return output


def inputs(output):
    manifest = json.loads((SCOPE / "integration_manifest.json").read_bytes())
    if (manifest.get("version") != VERSION
            or manifest.get("expected_input_count") != 62
            or manifest.get("expected_project_file_count") != 53
            or manifest.get("parent_prepare_file") != "code/scripts/prepare_138k_score_receive_integration.py"
            or manifest.get("old_audio_wave_ROM_PLL_CST_SDC_unchanged") is not True
            or manifest.get("fulltop_simulation_completed") is not False
            or manifest.get("build_or_program_authorization_from_this_file") is not False
            or manifest.get("physical_STA_passed") is not False
            or manifest.get("board_release_allowed") is not False
            or sha(Path(base.__file__).read_bytes()) != manifest["parent_prepare_sha256"]):
        raise ValueError("PARENT_OR_SCOPE_IDENTITY")
    data, provenance, gprj, tcl, old = base.inputs(output)
    old_key = "sources/score_transfer_candidate.sv"
    old_sha = sha(data[old_key])
    del data[old_key]
    del provenance[old_key]
    top_key = "sources/audio_visual_coexistence_top.sv"
    before = data[top_key]
    old_token = b"score_transfer_candidate #"
    new_token = b"score_transfer_bram_candidate #"
    if before.count(old_token) != 1:
        raise ValueError("TOP_INSTANCE_NOT_UNIQUE")
    data[top_key] = before.replace(old_token, new_token)
    if data[top_key].replace(new_token, old_token) != before:
        raise ValueError("TOP_INSTANCE_CHANGE_NOT_REVERSIBLE")
    provenance[top_key].update(RAM_instance_only=True,
                               old_RAM_overlay_sha256=sha(before),
                               adapted_sha256=sha(data[top_key]))
    tree = ET.fromstring(gprj)
    files = tree.find("FileList")
    matches = [n for n in files if Path(n.attrib["path"]).name == "score_transfer_candidate.sv"]
    if len(matches) != 1:
        raise ValueError("OLD_PROJECT_ENTRY_NOT_UNIQUE")
    files.remove(matches[0])
    for relative, expected in manifest["RAM_source_sha256"].items():
        raw = (ROOT / relative).read_bytes()
        if sha(raw) != expected:
            raise ValueError("RAM_SOURCE_DRIFT:" + relative)
        name = Path(relative).name
        key = "sources/" + name
        if key in data:
            raise ValueError("DUPLICATE_RAM_SOURCE")
        data[key] = raw
        provenance[key] = {"repo_reference": relative, "adapted_sha256": expected,
                           "reference_commit": manifest["source_reference_commit"]}
        ET.SubElement(files, "File", path=(output / "inputs/sources" / name).as_posix(),
                      type="file.verilog", enable="1")
    if len(data) != 62 or len(files) != 53:
        raise ValueError("RAM_PROJECT_COUNTS")
    project = ET.tostring(tree, encoding="utf-8", xml_declaration=True)
    return data, provenance, project, tcl, old_sha


def expected_receipt(output):
    data, provenance, project, tcl, old_sha = inputs(output)
    record = {"date": "2026-10-10", "version": VERSION, "inputs": provenance,
              "input_count": 62, "project_file_count": 53,
              "source_manifest_sha256": sha((SCOPE / "integration_manifest.json").read_bytes()),
              "prepare_script_sha256": sha(Path(__file__).read_bytes()),
              "old_removed_score_source_sha256": old_sha,
              "parent": base.VERSION,
              "device": base.parent.parent.parent.original.EXPECTED_DEVICE,
              "project_sha256": sha(project), "run_tcl_sha256": sha(tcl),
              "audio_wave_ROM_PLL_CST_SDC_unchanged": True,
              "external_ports_changed": False, "playback_connected": False,
              "prepared_only": True, "fulltop_simulation_completed": False,
              "ready_for_PnR": False, "physical_STA_passed": False,
              "board_release_allowed": False, "programmed": False}
    return data, project, tcl, record


def validate(output):
    output = guard(output)
    data, project, tcl, record = expected_receipt(output)
    actual = {p.relative_to(output / "inputs").as_posix(): p.read_bytes()
              for p in (output / "inputs").rglob("*") if p.is_file()}
    if data != actual:
        raise ValueError("EXACT62_INPUTS_OR_HIDDEN_FILE")
    if ((output / PROJECT).read_bytes() != project
            or (output / "run.tcl").read_bytes() != tcl):
        raise ValueError("EXACT_PROJECT_OPTIONS")
    # Canonical frozen bytes also reject bool/int/float substitutions and
    # duplicate JSON keys; Python dictionary equality is not type-sensitive.
    if (output / "frozen_receipt.json").read_bytes() != receipt_bytes(record):
        raise ValueError("EXACT_RAM_FROZEN_RECEIPT")
    print("PASS prepared62/53 identity only; no tools/STA/programming release", flush=True)
    return record


def prepare(output):
    output = guard(output)
    if output.exists():
        raise ValueError("REFUSE_OVERWRITE")
    data, project, tcl, record = expected_receipt(output)
    output.mkdir(parents=True, exist_ok=False)
    for relative, raw in data.items():
        p = output / "inputs" / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
    (output / PROJECT).write_bytes(project)
    (output / "run.tcl").write_bytes(tcl)
    (output / "frozen_receipt.json").write_bytes(receipt_bytes(record))
    return validate(output)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--check", action="store_true")
    args = cli.parse_args()
    validate(args.output) if args.check else prepare(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
