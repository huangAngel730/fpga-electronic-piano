"""New v3 reset-input classification and stricter directed minimum delay."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code/scripts"))
import prepare_138k_waveform_integration_v2 as parent

BUILD_ROOT = parent.BUILD_ROOT
PROJECT = parent.PROJECT
SCOPE = parent.SCOPE.parent / "reset_hold_v3"
GSC_REL = "constraints/waveform_payload_preserve.gsc"
VERSION = "reset_hold_v3"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def inputs(output):
    manifest = json.loads((SCOPE / "revision_manifest.json").read_bytes())
    if sha(Path(parent.__file__).read_bytes()) != manifest["v2_prepare_SHA256"]:
        raise ValueError("V2_PREPARE_IDENTITY")
    for relative, expected in manifest["static_reset_contract_sources"].items():
        if sha((ROOT / relative).read_bytes()) != expected:
            raise ValueError("STATIC_RESET_PROOF_SOURCE_CHANGED " + relative)
    adapted, provenance, gprj, run, old_manifest = parent.inputs(output)
    raw = (SCOPE / "audio_visual_hold055.sdc").read_bytes()
    original_sdc = adapted["constraints/audio_visual_hold055.sdc"]
    if sha(original_sdc) != manifest["parent_SDC_sha256"] or sha(raw) != manifest["SDC_sha256"]:
        raise ValueError("V3_SDC_IDENTITY")
    if not raw.startswith(original_sdc):
        raise ValueError("ORIGINAL_SDC_REWRITTEN")
    if sha(adapted[GSC_REL]) != manifest["GSC_sha256"]:
        raise ValueError("PRESERVE_GSC_CHANGED")
    adapted["constraints/audio_visual_hold055.sdc"] = raw
    provenance["constraints/audio_visual_hold055.sdc"]["v3_overlay_sha256"] = sha(raw)
    provenance["constraints/audio_visual_hold055.sdc"]["adapted_sha256"] = sha(raw)
    return adapted, provenance, gprj, run, manifest


def validate(output):
    output = output.resolve()
    output.relative_to(BUILD_ROOT.resolve())
    record = json.loads((output / "frozen_receipt.json").read_bytes())
    if (record.get("version") != VERSION or record.get("input_count") != 60
            or record.get("project_file_count") != 51 or record.get("programmed") is not False):
        raise ValueError("V3_FROZEN_PROFILE")
    expected, provenance, gprj, run, manifest = inputs(output)
    actual = {p.relative_to(output / "inputs").as_posix(): p.read_bytes()
              for p in (output / "inputs").rglob("*") if p.is_file()}
    if actual != expected:
        raise ValueError("EXACT60_INPUTS_OR_HIDDEN_FILE")
    if (output / PROJECT).read_bytes() != gprj or (output / "run.tcl").read_bytes() != run:
        raise ValueError("EXACT_PROJECT_OR_OPTIONS")
    if (record.get("inputs") != provenance
            or record.get("revision_manifest_sha256") != sha((SCOPE / "revision_manifest.json").read_bytes())
            or record.get("source_archive_sha256") != parent.parent.original.ARCHIVE_SHA256
            or record.get("device") != parent.parent.original.EXPECTED_DEVICE
            or record.get("project_sha256") != sha(gprj)
            or record.get("run_tcl_sha256") != sha(run)
            or record.get("original58_and_GSC_inputs_unchanged_SDC_exact_append") is not True):
        raise ValueError("V3_RECEIPT_IDENTITY")
    print("PASS v3 frozen60inputs/51entries; original58+GSC unchanged; SDC exactappend", flush=True)
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
                  source_archive_sha256=parent.parent.original.ARCHIVE_SHA256,
                  source_project_sha256=parent.parent.original.SOURCE_PROJECT_SHA256,
                  revision_manifest_sha256=sha((SCOPE / "revision_manifest.json").read_bytes()),
                  inputs=provenance, input_count=60, project_file_count=51,
                  device=parent.parent.original.EXPECTED_DEVICE, project_sha256=sha(gprj),
                  run_tcl_sha256=sha(run), programmed=False,
                  original58_and_GSC_inputs_unchanged_SDC_exact_append=True,
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
