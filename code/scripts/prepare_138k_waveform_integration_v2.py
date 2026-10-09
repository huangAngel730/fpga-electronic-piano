"""New T058 project with one scoped GSC; original 59 logical inputs unchanged."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code/scripts"))
import prepare_138k_waveform_integration as parent

BUILD_ROOT = parent.BUILD_ROOT
PROJECT = parent.PROJECT
SCOPE = parent.SCOPE / "retained_payload_v2"
GSC_REL = "constraints/waveform_payload_preserve.gsc"
VERSION = "retained_payload_v2"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def inputs(output):
    manifest = json.loads((SCOPE / "revision_manifest.json").read_bytes())
    bindings = {
        "parent_prepare_sha256": Path(parent.__file__),
        "parent_manifest_sha256": parent.SCOPE / "integration_manifest.json",
        "parent_SDC_SHA256": parent.SCOPE / "overlay/audio_visual_hold055.sdc",
        "gsc_sha256": SCOPE / "waveform_payload_preserve.gsc",
    }
    for key, path in bindings.items():
        if sha(path.read_bytes()) != manifest[key]:
            raise ValueError("REVISION_INPUT_SHA " + key)
    adapted, provenance, gprj, run, parent_manifest = parent.inputs(output)
    original59 = dict(adapted)
    tree = ET.fromstring(gprj)
    files = tree.find("FileList")
    if files is None or len(files) != 50 or len(adapted) != 59:
        raise ValueError("PARENT_INPUT_COUNTS")
    gsc = (SCOPE / "waveform_payload_preserve.gsc").read_bytes()
    adapted[GSC_REL] = gsc
    provenance[GSC_REL] = {"repo_reference": (SCOPE / Path(GSC_REL).name).relative_to(ROOT).as_posix(),
                           "adapted_sha256": sha(gsc), "purpose": "scoped register preservation only"}
    ET.SubElement(files, "File", path=(output / "inputs" / GSC_REL).as_posix(),
                  type="file.gsc", enable="1")
    if {k: v for k, v in adapted.items() if k != GSC_REL} != original59:
        raise ValueError("LOGICAL_INPUT_CHANGED")
    return adapted, provenance, ET.tostring(tree, encoding="utf-8", xml_declaration=True), run, manifest


def validate(output):
    output = output.resolve()
    output.relative_to(BUILD_ROOT.resolve())
    record = json.loads((output / "frozen_receipt.json").read_bytes())
    if (record.get("version") != VERSION or record.get("input_count") != 60
            or record.get("project_file_count") != 51 or record.get("programmed") is not False):
        raise ValueError("V2_FROZEN_PROFILE")
    expected, provenance, gprj, run, manifest = inputs(output)
    actual = {p.relative_to(output / "inputs").as_posix(): p.read_bytes()
              for p in (output / "inputs").rglob("*") if p.is_file()}
    if actual != expected:
        raise ValueError("EXACT60_INPUTS_OR_HIDDEN_FILE")
    if (output / PROJECT).read_bytes() != gprj or (output / "run.tcl").read_bytes() != run:
        raise ValueError("EXACT_PROJECT_OR_OPTIONS")
    if (record.get("inputs") != provenance
            or record.get("revision_manifest_sha256") != sha((SCOPE / "revision_manifest.json").read_bytes())
            or record.get("source_archive_sha256") != parent.original.ARCHIVE_SHA256
            or record.get("device") != parent.original.EXPECTED_DEVICE
            or record.get("project_sha256") != sha(gprj)
            or record.get("run_tcl_sha256") != sha(run)
            or record.get("original59_logical_inputs_unchanged") is not True):
        raise ValueError("V2_RECEIPT_IDENTITY")
    print("PASS v2 frozen60inputs/51entries; scopedGSC; original59inputs unchanged", flush=True)
    return record


def prepare(output):
    output = output.resolve()
    output.relative_to(BUILD_ROOT.resolve())
    if output == BUILD_ROOT.resolve() or output.exists():
        raise ValueError("REFUSE_OVERWRITE_OR_ROOT")
    expected, provenance, gprj, run, manifest = inputs(output)
    output.mkdir(parents=True)
    for relative, raw in expected.items():
        path = output / "inputs" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    (output / PROJECT).write_bytes(gprj)
    (output / "run.tcl").write_bytes(run)
    record = dict(date="2026-10-08", version=VERSION,
                  source_archive_sha256=parent.original.ARCHIVE_SHA256,
                  source_project_sha256=parent.original.SOURCE_PROJECT_SHA256,
                  revision_manifest_sha256=sha((SCOPE / "revision_manifest.json").read_bytes()),
                  inputs=provenance, input_count=60, project_file_count=51,
                  device=parent.original.EXPECTED_DEVICE, project_sha256=sha(gprj),
                  run_tcl_sha256=sha(run), programmed=False,
                  original59_logical_inputs_unchanged=True,
                  existing_candidate_or_production_changed=False, externally_added_ports=False)
    dump(output / "frozen_receipt.json", record)
    return validate(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    validate(args.output) if args.check else prepare(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
