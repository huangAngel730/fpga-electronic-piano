"""Seal tested task-local software and raw evidence, never run EDA or Git."""

import argparse
import json
from pathlib import Path
import sys
import zipfile

from endpoint_audit import sha256
from run_selftest import HERE, file_id, snapshot, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run = args.run.resolve()
    output = args.output.resolve()
    if run.parent != (HERE / "runs").resolve() or output.parent != HERE.resolve():
        raise ValueError("run/output must stay in owned task directory")
    if output.exists():
        raise FileExistsError(output)
    receipt = json.loads((run / "RUN_RECEIPT.json").read_text(encoding="utf-8"))
    if receipt["status"] != "SOFTWARE_SELFTEST_PASS":
        raise ValueError("tested software did not pass")
    if receipt["source_before"] != receipt["source_after"] or receipt["source_after"] != snapshot():
        raise ValueError("current source differs from tested source")
    members = {}
    for path in HERE.iterdir():
        if path.is_file() and path.suffix in (".py", ".md", ".json"):
            members[path.name] = path
    for path in sorted((HERE / "runs").rglob("*")):
        if path.is_file():
            members[path.relative_to(HERE).as_posix()] = path
    for name, item in members.items():
        if item.is_symlink() or "coordinator" in Path(name).parts:
            raise ValueError("not owned member")
    manifest = {
        "scope": "SOFTWARE_L0_L1_ONLY", "board_release_allowed": False,
        "new_sta_executed": False, "physical_signoff": False,
        "tested_run": run.name, "files": {
            name: {"bytes": p.stat().st_size, "sha256": sha256(p.read_bytes())}
            for name, p in sorted(members.items())
        },
    }
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        for name, p in sorted(members.items()):
            archive.writestr(name, p.read_bytes())
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failure")
        for name, identity in manifest["files"].items():
            data = archive.read(name)
            if len(data) != identity["bytes"] or sha256(data) != identity["sha256"]:
                raise ValueError(f"ZIP member identity failure: {name}")
    seal = {
        "status": "SEALED_SOFTWARE_ONLY", "archive": file_id(output),
        "members": len(members), "tested_run": run.name,
        "receipt_sha256": sha256((run / "RUN_RECEIPT.json").read_bytes()),
        "board_release_allowed": False, "new_sta_executed": False,
        "physical_signoff": False,
    }
    seal_file = output.with_suffix(".receipt.json")
    if seal_file.exists():
        raise FileExistsError(seal_file)
    write_json(seal_file, seal)
    print(json.dumps(seal, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
