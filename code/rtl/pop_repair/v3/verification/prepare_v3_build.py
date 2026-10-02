"""Verify the real freeze contract, then construct a new owned build snapshot.

Only path/include adaptations in the copied build files; never changes source.
Original frozen source hashes and transformed staged hashes are both retained.
"""
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPO = Path("E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano")
DEST = ROOT / "build/candidate_20261002_141443_r2"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ready = ROOT / "design/DESIGN_READY.json"
    gate = json.loads(ready.read_text(encoding="utf-8"))
    assert gate["status"] == "DESIGN_READY_SOURCE_FROZEN_RESEARCH_CANDIDATE"
    if DEST.exists():
        raise SystemExit("Never overwrite existing snapshot")
    expected = gate["source_files"]
    actual = {p.relative_to(ROOT).as_posix() for p in (ROOT / "source").rglob("*") if p.is_file()}
    if actual != set(expected):
        raise ValueError("Frozen source inventory differs")
    for name, metadata in expected.items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT / "source") or sha(path) != metadata["sha256"]:
            raise ValueError("Frozen SHA mismatch " + name)
    for name in ("input_manifest", "implementation"):
        item = gate[name]
        if sha(Path(item["path"])) != item["sha256"]:
            raise ValueError("Freeze dependency SHA mismatch " + name)
    baseline = json.loads((ROOT / "verification/baseline_reference_manifest.json").read_text(encoding="utf-8"))
    for original, item in baseline["files"].items():
        if sha(Path(item["destination"])) != item["sha256"]:
            raise ValueError("Regression snapshot modified " + original)
    DEST.mkdir(parents=True)
    shutil.copytree(ROOT / "source", DEST / "source")
    shutil.copytree(ROOT / "build/baseline_reference/code", DEST / "code")
    shutil.copy2(ready, DEST / "DESIGN_READY.json")
    origins = {Path(item["destination"]).relative_to(ROOT / "build/baseline_reference").as_posix():
               {"source":original,"sha256":item["sha256"]} for original,item in baseline["files"].items()}
    header = REPO / "code/rtl/common/sine_table.svh"
    shutil.copy2(header, DEST / "code/rtl/common/sine_table.svh")
    origins["code/rtl/common/sine_table.svh"] = {"source":str(header),"sha256":sha(header)}
    # Cross-check unchanged baseline modules used by the frozen candidate.
    for name, relative in {
        "piano_dds_oscillator.sv":"rtl/audio/piano_dds_oscillator.sv",
        "adsr_piano_envelope.sv":"rtl/audio/adsr_piano_envelope.sv",
        "note_pitch.sv":"rtl/common/note_pitch.sv",
        "polyphonic_audio_core.sv":"rtl/board/polyphonic_audio_core.sv"}.items():
        if sha(DEST / "source/baseline" / name) != sha(DEST / "code" / relative):
            raise ValueError("Candidate/formal baseline mismatch " + name)
    shutil.copy2(DEST / "source/rtl/polyphonic_envelope_bank.sv",
                 DEST / "code/rtl/board/polyphonic_envelope_bank.sv")
    origins["code/rtl/board/polyphonic_envelope_bank.sv"] = {
        "source":str(ROOT / "source/rtl/polyphonic_envelope_bank.sv"),
        "sha256":gate["source_files"]["source/rtl/polyphonic_envelope_bank.sv"]["sha256"]}
    # These are literal path-only substitutions in a build copy, not algorithm edits.
    replacements = {}
    for path in (DEST / "code/model/generated/wavetables").glob("*.mem"):
        replacements["model/generated/wavetables/"+path.name] = path.as_posix()
    replacements["source/rom/sine_v3_1024_32767.mem"] = (DEST / "source/rom/sine_v3_1024_32767.mem").as_posix()
    replacements["source/baseline/piano_band_4x256_8191.mem"] = (DEST / "source/baseline/piano_band_4x256_8191.mem").as_posix()
    # Keep include basenames: Icarus's preprocessor does not accept Windows
    # drive-prefixed absolute include literals. Both tools get include dirs.
    adaptations = []
    for path in [*(DEST / "code/rtl").rglob("*.sv"), DEST / "source/rtl/piano_dds_oscillator_v3.sv"]:
        before = path.read_text(encoding="utf-8")
        after = before
        used = []
        for old, new in replacements.items():
            if old in after:
                after = after.replace(old, new)
                used.append({"old":old,"new":new})
        if before != after:
            old_hash = sha(path)
            path.write_text(after, encoding="utf-8", newline="\n")
            adaptations.append({"path":path.relative_to(DEST).as_posix(),
                                "before_sha256":old_hash,"after_sha256":sha(path),"path_only":used})
    project = DEST / "code/build/electronic_piano.gprj"
    document = ET.fromstring(project.read_text(encoding="utf-8").replace('version="1"','version="1.0"'))
    entries = document.find("FileList")
    paths = [(project.parent / node.attrib["path"]).resolve() for node in list(entries)]
    entries.clear()
    priority = ["audio_defs_pkg.sv","sustain_control_contract_pkg.sv"]
    paths = sorted(paths, key=lambda p:priority.index(p.name) if p.name in priority else 10)
    paths.append(DEST / "source/rtl/piano_dds_oscillator_v3.sv")
    for path in paths:
        if not path.is_relative_to(DEST) or not path.exists():
            raise ValueError("GPRJ references outside/missing input")
        ET.SubElement(entries,"File",{"path":path.as_posix(),"type":
            "file.cst" if path.suffix==".cst" else "file.sdc" if path.suffix==".sdc" else "file.verilog","enable":"1"})
    new_project = project.with_name("electronic_piano_v3.gprj")
    ET.ElementTree(document).write(new_project,encoding="utf-8",xml_declaration=True)
    (DEST / "extra_rtl.json").write_text(json.dumps(["source/rtl/piano_dds_oscillator_v3.sv"])+"\n")
    staged = [{"path":p.relative_to(DEST).as_posix(),"sha256":sha(p)}
              for p in sorted(DEST.rglob("*")) if p.is_file()]
    report = {"gate_sha256":sha(ready),"original_source_files":expected,
              "formal_baseline_head":gate["formal_build_baseline"]["head"],
              "copied_baseline_origins":origins,"path_only_adaptations":adaptations,
              "project":str(new_project),"staged_files":staged,
              "cc64":"preserved; test pending","STAT":"preserved; test pending",
              "HDMI":"absent; not added","no_old_code_modified":True}
    (DEST / "frozen_input_manifest.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("PASS frozen SHA",len(expected),"files; path-only build snapshot",DEST)


if __name__ == "__main__":
    main()
