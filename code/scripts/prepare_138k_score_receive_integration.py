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
import prepare_138k_waveform_integration_v3 as parent

BUILD_ROOT = ROOT / "code/build/138k_score_receive"
PROJECT = parent.PROJECT
SCOPE = ROOT / "code/rtl/138K_try/score_receive_integration_20261009"
GSC_REL = "constraints/waveform_payload_preserve.gsc"
VERSION = "score_receive_integration_1"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def inputs(output):
    manifest = json.loads((SCOPE / "integration_manifest.json").read_bytes())
    if sha(Path(parent.__file__).read_bytes()) != manifest["parent_prepare_sha256"]:
        raise ValueError("parent prepare identity changed")
    adapted, provenance, gprj, run, old_manifest = parent.inputs(output)
    for name, digest in manifest["uart_dependencies_SHA256"].items():
        if sha(adapted["sources/" + name]) != digest:
            raise ValueError("common UART dependency differs")
    for name, digest in manifest["overlays"].items():
        raw = (SCOPE / "overlay" / name).read_bytes()
        if sha(raw) != digest:
            raise ValueError("new overlay identity changed")
        key = "sources/" + name if name.endswith(".sv") else "constraints/" + name
        if name == "audio_visual_coexistence_top.sv":
            truth = parent.parent.parent.original.archive_truth()
            _, _, old_root = parent.parent.parent.original.project_description(truth["project"])
            raw = raw.decode("utf-8").replace(old_root, (output / "inputs").as_posix()).encode("utf-8")
        elif not raw.startswith(adapted[key]):
            raise ValueError("old CST/SDC commands changed, must only append")
        adapted[key] = raw
        provenance[key]["score_overlay_sha256"] = digest
        provenance[key]["adapted_sha256"] = sha(raw)
    tree = ET.fromstring(gprj)
    files = tree.find("FileList")
    for relative, digest in manifest["added_source_sha256"].items():
        raw = (ROOT / relative).read_bytes()
        if sha(raw) != digest:
            raise ValueError("score candidate source changed")
        name = Path(relative).name
        adapted["sources/" + name] = raw
        provenance["sources/" + name] = {"repo_reference": relative, "adapted_sha256": digest}
        ET.SubElement(files, "File", path=(output / "inputs/sources" / name).as_posix(), type="file.verilog", enable="1")
    if len(adapted) != 61 or len(files) != 52:
        raise ValueError("score project counts")
    return adapted, provenance, ET.tostring(tree, encoding="utf-8", xml_declaration=True), run, manifest


def validate(output):
    output = output.resolve()
    output.relative_to(BUILD_ROOT.resolve())
    record = json.loads((output / "frozen_receipt.json").read_bytes())
    if (record.get("version") != VERSION or record.get("input_count") != 61
            or record.get("project_file_count") != 52 or record.get("programmed") is not False):
        raise ValueError("SCORE_FROZEN_PROFILE")
    expected, provenance, gprj, run, manifest = inputs(output)
    actual = {p.relative_to(output / "inputs").as_posix(): p.read_bytes()
              for p in (output / "inputs").rglob("*") if p.is_file()}
    if actual != expected:
        raise ValueError("EXACT61_INPUTS_OR_HIDDEN_FILE")
    if (output / PROJECT).read_bytes() != gprj or (output / "run.tcl").read_bytes() != run:
        raise ValueError("EXACT_PROJECT_OR_OPTIONS")
    if (record.get("inputs") != provenance
            or record.get("revision_manifest_sha256") != sha((SCOPE / "integration_manifest.json").read_bytes())
            or record.get("source_archive_sha256") != parent.parent.parent.original.ARCHIVE_SHA256
            or record.get("device") != parent.parent.parent.original.EXPECTED_DEVICE
            or record.get("project_sha256") != sha(gprj)
            or record.get("run_tcl_sha256") != sha(run)
            or record.get("old_audio_wave_sources_unchanged_2newUARTports") is not True):
        raise ValueError("SCORE_RECEIPT_IDENTITY")
    print("PASS score frozen61inputs/52entries; old audio/wave unchanged; dedicated2UART", flush=True)
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
                  source_archive_sha256=parent.parent.parent.original.ARCHIVE_SHA256,
                  source_project_sha256=parent.parent.parent.original.SOURCE_PROJECT_SHA256,
                  revision_manifest_sha256=sha((SCOPE / "integration_manifest.json").read_bytes()),
                  inputs=provenance, input_count=61, project_file_count=52,
                  device=parent.parent.parent.original.EXPECTED_DEVICE, project_sha256=sha(gprj),
                  run_tcl_sha256=sha(run), programmed=False,
                  old_audio_wave_sources_unchanged_2newUARTports=True,
                  existing_candidate_or_production_changed=False, externally_added_ports=["score_uart_rx", "score_uart_tx"])
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
