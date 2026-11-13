"""Verify the tracked R13 Lissajous source archive without launching EDA."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "project"
MANIFEST = ROOT / "ARCHIVE_MANIFEST.json"
TCL_INPUT = re.compile(
    r"^\s*add_file -type \w+ \[file join \$package_root (\{[^{}]+\}|[^\[\]]+)\]\s*$"
)


def project_inputs():
    tcl_lines = (PROJECT / "rebuild.tcl").read_text(encoding="utf-8").splitlines()
    tcl = []
    for line in tcl_lines:
        if line.lstrip().startswith("add_file "):
            match = TCL_INPUT.fullmatch(line)
            if not match:
                raise ValueError(f"Unexpected Tcl registration: {line}")
            tcl.append("/".join(match[1].strip("{}").split()))
    gui = [
        f"project/{entry.attrib['path']}"
        for entry in ET.parse(PROJECT / "pro_audio.gprj").findall("./FileList/File")
        if entry.attrib.get("enable") == "1"
    ]
    if len(tcl) != 131 or len(gui) != 131 or len(set(tcl)) != 131 or set(tcl) != set(gui):
        raise ValueError("Tcl and .gprj do not register the same 131 unique inputs")
    return set(tcl)


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["schema"] != "n32.c1.r13.lissajous.source_archive.v1":
        raise ValueError("Unsupported manifest")
    members = manifest["files"]
    if len(members) != manifest["payload_count"]:
        raise ValueError("Manifest count mismatch")
    names = set()
    for member in members:
        name = member["path"]
        relative = PurePosixPath(name)
        if (
            relative.is_absolute()
            or name != relative.as_posix()
            or ".." in relative.parts
            or "\\" in name
            or ":" in name
            or name in names
        ):
            raise ValueError(f"Invalid or duplicate manifest path: {name}")
        names.add(name)
        path = ROOT / relative
        if not path.resolve().is_relative_to(ROOT) or path.is_symlink():
            raise ValueError(f"Path leaves the archive: {name}")
        data = path.read_bytes()
        if len(data) != member["bytes"] or hashlib.sha256(data).hexdigest() != member["sha256"]:
            raise ValueError(f"Size or SHA-256 mismatch: {name}")
    registrations = project_inputs()
    if not registrations <= names:
        raise ValueError(f"Missing registered project inputs: {sorted(registrations - names)}")
    print(f"PASS: {len(members)} archive payload files, {len(registrations)} registered inputs")


if __name__ == "__main__":
    main()
