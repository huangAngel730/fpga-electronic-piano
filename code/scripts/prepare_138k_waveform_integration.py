"""Materialize a NEW sealed-L waveform integration; never change the original."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ROOT / "code/rtl/138K_try/t058_waveform_integration_20261008"
BUILD_ROOT = ROOT / "code/build/138k_waveform"
PROJECT = "audio_visual_coexistence_top.gprj"
sys.path.insert(0, str(ROOT / "code/scripts"))
import prepare_138k_l_project as original


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def inputs(output):
    truth = original.archive_truth()
    tree, entries, old_root = original.project_description(truth["project"])
    manifest = json.loads((SCOPE / "integration_manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["overlays"].items():
        if sha((SCOPE / "overlay" / name).read_bytes()) != expected:
            raise ValueError("OVERLAY_SHA " + name)
    adapted, provenance = original.adapted_inputs(truth["inputs"], old_root, output / "inputs")
    for name in ["audio_visual_coexistence_top.sv", "audio_visual_display_probe.sv"]:
        path = "sources/" + name
        raw = (SCOPE / "overlay" / name).read_bytes()
        text = raw.decode("utf-8").replace(old_root, (output / "inputs").as_posix())
        adapted[path] = text.encode("utf-8")
        provenance[path]["integration_overlay_sha256"] = sha(raw)
        provenance[path]["adapted_sha256"] = sha(adapted[path])
    path = "constraints/audio_visual_hold055.sdc"
    adapted[path] = (SCOPE / "overlay/audio_visual_hold055.sdc").read_bytes()
    provenance[path]["integration_overlay_sha256"] = sha(adapted[path])
    provenance[path]["adapted_sha256"] = sha(adapted[path])
    for relative, expected in manifest["added_source_sha256"].items():
        raw = (ROOT / relative).read_bytes()
        if sha(raw) != expected:
            raise ValueError("NEW_SOURCE_SHA " + relative)
        name = Path(relative).name
        adapted["sources/" + name] = raw
        provenance["sources/" + name] = {"repo_reference": relative, "adapted_sha256": expected}
    for entry in entries:
        relative = entry.attrib["path"].replace("\\", "/").removeprefix(old_root + "/")
        entry.attrib["path"] = (output / "inputs" / relative).as_posix()
    fl = tree.find("FileList")
    # Appended source modules have no package dependencies; original47 ordering preserved.
    for relative in manifest["added_source_sha256"]:
        ET.SubElement(fl, "File", path=(output / "inputs/sources" / Path(relative).name).as_posix(), type="file.verilog", enable="1")
    gprj = ET.tostring(tree, encoding="utf-8", xml_declaration=True)
    run, count = re.subn(r"open_project\s+\{[^}]+\}", "open_project {" + (output / PROJECT).as_posix() + "}", truth["run_tcl"].decode("utf-8"), count=1)
    if count != 1 or old_root in run or len(adapted) != 59 or len(list(fl)) != 50:
        raise ValueError("PROJECT_INPUT_COUNTS_OR_PATHS")
    return adapted, provenance, gprj, run.encode("utf-8"), manifest


def validate(output):
    output = output.resolve()
    output.relative_to(BUILD_ROOT.resolve())
    expected, provenance, gprj, run, manifest = inputs(output)
    receipt = json.loads((output / "frozen_receipt.json").read_text(encoding="utf-8"))
    for relative, raw in expected.items():
        if (output / "inputs" / relative).read_bytes() != raw:
            raise ValueError("EXACT_INTEGRATED_INPUT " + relative)
    if (output / PROJECT).read_bytes() != gprj or (output / "run.tcl").read_bytes() != run:
        raise ValueError("EXACT_PROJECT_OR_RUN_TCL")
    if receipt["inputs"] != provenance or receipt["integration_manifest_sha256"] != sha((SCOPE / "integration_manifest.json").read_bytes()):
        raise ValueError("FROZEN_RECEIPT_IDENTITY")
    if receipt["project_sha256"] != sha(gprj) or receipt["run_tcl_sha256"] != sha(run):
        raise ValueError("FROZEN_RECEIPT_BUILD_INPUT")
    if receipt["device"] != original.EXPECTED_DEVICE or receipt["programmed"] or receipt["source_archive_sha256"] != original.ARCHIVE_SHA256:
        raise ValueError("TARGET_OR_ORIGINAL_ARCHIVE")
    print("PASS integration frozen59inputs/50projectentries; originalCST/PLL/ROM/math unchanged", flush=True)
    return receipt


def prepare(output):
    output = output.resolve()
    output.relative_to(BUILD_ROOT.resolve())
    if output == BUILD_ROOT.resolve() or output.exists():
        raise ValueError("REFUSE_OVERWRITE_OR_ROOT")
    expected, provenance, gprj, run, manifest = inputs(output)
    output.mkdir(parents=True)
    for relative, raw in expected.items():
        p = output / "inputs" / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
    (output / PROJECT).write_bytes(gprj)
    (output / "run.tcl").write_bytes(run)
    receipt = dict(date="2026-10-08", source_archive_sha256=original.ARCHIVE_SHA256,
                   source_project_sha256=original.SOURCE_PROJECT_SHA256,
                   integration_manifest_sha256=sha((SCOPE / "integration_manifest.json").read_bytes()),
                   inputs=provenance, input_count=59, project_file_count=50,
                   device=original.EXPECTED_DEVICE, project_sha256=sha(gprj),
                   run_tcl_sha256=sha(run), programmed=False,
                   existing_candidate_or_production_changed=False, externally_added_ports=False)
    dump(output / "frozen_receipt.json", receipt)
    return validate(output)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    validate(args.output) if args.check else prepare(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
