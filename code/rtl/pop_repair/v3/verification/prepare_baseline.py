"""Copy a read-only current formal V1 regression baseline, NOT a V3 build."""
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

REPO=Path(r"E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano")
V3=Path(__file__).resolve().parents[1]
DEST=V3/"build/baseline_reference"
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    if DEST.exists():
        raise SystemExit("Refuse to overwrite baseline snapshot")
    project=REPO/"code/build/electronic_piano.gprj"
    doc=ET.fromstring(project.read_text(encoding="utf-8").replace('version="1"','version="1.0"'))
    files=[project]
    files.extend((project.parent/node.attrib["path"]).resolve() for node in doc.findall(".//File"))
    files.extend((REPO/"code/rtl/board").glob("*.svh"))
    files.extend((REPO/"code/model/generated/wavetables").glob("*.mem"))
    files.extend(REPO/path for path in [
        "code/model/adsr_piano.py","code/model/audio_defs.py","code/model/dds_model.py",
        "code/tb/board/tb_polyphonic_audio_core.sv",
        "code/tb/board/check_polyphonic_audio_trace.py",
        "code/tb/board/tb_t024_audio_capabilities.sv",
        "code/tb/board/check_t024_audio_capabilities.py",
        "code/tb/board/tb_sustain_audio_integration.sv"])
    hashes={}
    for source in sorted(set(files)):
        if not source.is_relative_to(REPO):
            raise ValueError("Baseline path escapes repository")
        target=DEST/source.relative_to(REPO)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        before=digest(source)
        if digest(target)!=before:
            raise ValueError("Copy hash mismatch")
        hashes[str(source)]={"destination":str(target),"sha256":before}
    (V3/"verification/baseline_reference_manifest.json").write_text(
        json.dumps({"scope":"current formal V1 RTL/model regression reference; NOT old V2 bitstream algorithm",
                    "files":hashes},indent=2)+"\n",encoding="utf-8")
    print("PASS baseline-only snapshot",len(hashes),"files")
if __name__=="__main__":
    main()
