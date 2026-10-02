"""Prepare a new PnR project using the already tested, synthesized V3."""
import hashlib
import argparse
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "build/candidate_20261002_141443_r2"
DEST = ROOT / "build/pnr_attempt_1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    global DEST
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="pnr_attempt_1", choices=["pnr_attempt_1", "pnr_attempt_2"])
    DEST = ROOT / "build" / parser.parse_args().name
    if DEST.exists():
        raise SystemExit("Never overwrite an existing PnR attempt")
    gate = json.loads((ROOT / "design/DESIGN_READY.json").read_text(encoding="utf-8"))
    manifest = json.loads((SNAP / "frozen_input_manifest.json").read_text(encoding="utf-8"))
    assert sha(ROOT / "design/DESIGN_READY.json") == manifest["gate_sha256"]
    for name, item in gate["source_files"].items():
        assert sha(ROOT / name) == item["sha256"], name
    for item in manifest["staged_files"]:
        assert sha(SNAP / item["path"]) == item["sha256"], item["path"]
    synth = SNAP / "gowin_synthesis"
    result = json.loads((synth / "result.json").read_text(encoding="utf-8"))
    assert result["exit_code"] == 0 and result["vg_created"]
    for relative in ("tests_oscillator/result.json", "tests_lifecycle/v3_golden.json"):
        assert json.loads((SNAP / relative).read_text(encoding="utf-8"))["status"] == "PASS"
    DEST.mkdir()
    syn_dir = DEST / "impl/gwsynthesis"
    shutil.copytree(synth, syn_dir)
    constraints = DEST / "constraints"
    constraints.mkdir()
    project = ET.parse(manifest["project"])
    for node in project.findall(".//File"):
        if node.attrib["type"] in {"file.cst", "file.sdc"}:
            original = Path(node.attrib["path"])
            target = constraints / original.name
            shutil.copy2(original, target)
            assert sha(target) == sha(original)
            node.set("path", target.as_posix())
    project_path = DEST / "electronic_piano_v3.gprj"
    project.write(project_path, encoding="utf-8", xml_declaration=True)
    provenance = {
        "status": "PNR_PREPARED_NOT_RUN", "research_candidate": True,
        "beat_perception": "NOT_ACCEPTED", "board": "NOT_RUN",
        "source_snapshot": str(SNAP), "project": str(project_path),
        "frozen_gate_sha256": manifest["gate_sha256"],
        "original_source_files": gate["source_files"],
        "frozen_design_files": {p.relative_to(ROOT).as_posix(): sha(p)
                                for p in (ROOT / "design").rglob("*") if p.is_file()},
        "reused_netlist": {"origin": str(synth / "electronic_piano_v3.vg"),
                           "path": str(syn_dir / "electronic_piano_v3.vg"),
                           "sha256": sha(synth / "electronic_piano_v3.vg")},
        "unchanged_constraints": {p.name: sha(p) for p in constraints.iterdir()},
        "modification": "New GPRJ constraint paths only; source and netlist unchanged",
        "device": "GW5AT-60B-PBGA484A-1", "part": "GW5AT-LV60PG484AC1/I0",
        "top": "electronic_piano_top", "tool": "Gowin 1.9.11.03 Education",
        "never_program_board": True,
    }
    (DEST / "preparation_manifest.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print("PASS source22/staged72, reused actual synthesis; new project:", project_path)


if __name__ == "__main__":
    main()
