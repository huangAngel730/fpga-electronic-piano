"""Seal only this window's files; exclude coordinator, other windows and packages."""
import hashlib
import json
from pathlib import Path
import zipfile
import argparse

ROOT = Path(__file__).resolve().parent


def identity(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", choices=("r02",), required=True)
    output = ROOT / ("delivery_" + parser.parse_args().run_id)
    if output.exists():
        raise ValueError("refuse existing seal directory")
    blobs = {}
    for path in sorted(ROOT.rglob("*")):
        name = path.relative_to(ROOT)
        if name.parts[0] == "coordinator" or name.parts[0].startswith("delivery_") or "__pycache__" in name.parts:
            continue
        if path.is_symlink():
            raise ValueError("refuse symlink in delivery")
        if path.is_file():
            blobs[name.as_posix()] = path.read_bytes()
    manifest = {"scope": "MAIN_CHAT4_ENDPOINT_PREPARATION_ONLY", "level": "L0_L1",
                "board_release_allowed": False, "new_sta_executed": False, "git_submitted": False,
                "files": {name: identity(data) for name, data in blobs.items()}}
    manifest_blob = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output.mkdir()
    (output / "MANIFEST.json").write_bytes(manifest_blob)
    dest = output / "MAIN_CHAT4_ENDPOINT_PREPARATION.zip"
    with zipfile.ZipFile(dest, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("MANIFEST.json", manifest_blob)
        for name, data in blobs.items():
            z.writestr(name, data)
    with zipfile.ZipFile(dest) as z:
        if z.testzip() is not None or set(z.namelist()) != set(blobs) | {"MANIFEST.json"}:
            raise ValueError("sealed archive member/CRC mismatch")
        for name, data in blobs.items():
            if z.read(name) != data:
                raise ValueError("sealed payload differs")
    for name, data in blobs.items():
        if (ROOT / name).read_bytes() != data:
            raise ValueError("source changed while sealing")
    receipt = {"archive": str(dest), **identity(dest.read_bytes()), "members": len(blobs) + 1,
               "manifest_sha256": hashlib.sha256(manifest_blob).hexdigest(),
               "archive_crc_and_all_bytes_verified": True, "board_release_allowed": False,
               "m2_signoff": "PENDING", "github_publication": "NOT_PERFORMED_BY_THIS_WINDOW"}
    (output / "DELIVERY.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
