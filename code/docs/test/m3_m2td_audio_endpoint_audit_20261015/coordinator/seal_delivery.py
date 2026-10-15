"""Seal this bounded preparation package without invoking EDA or Git writes."""

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    coordinator = Path(__file__).resolve().parent
    repo = coordinator.parents[4]
    output = Path(args.output).resolve()
    if output.parent != coordinator or output.exists():
        parser.error("Output must be a NEW immediate child of coordinator")
    roots = [
        repo / "code/software/m3_m2td_audio_endpoint_audit_20261015",
        coordinator.parent,
    ]
    entries = {}
    for root in roots:
        if not root.is_dir():
            parser.error("Both implementation directories must exist")
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                parser.error(f"Symlink not allowed: {path}")
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if path.suffix in {".pyc", ".zip"}:
                continue
            relative = path.relative_to(repo).as_posix()
            entries[relative] = path.read_bytes()
    physical = repo / (
        "code/docs/evidence/m2_m1td_physical_20261015/"
        "M2_138K_M1TD_整机PnR_STA_20261015.zip"
    )
    expected = "17e71ebd5b54743fd0214af5fbfdfd1a4cca4eddbcedab56f7b3df7b3ca521ff"
    if sha256(physical.read_bytes()) != expected:
        parser.error("Physical source archive identity mismatch")
    manifest = {
        "scope": "M3_40MHz_AUDIO_ENDPOINT_PREPARATION_ONLY",
        "verification_ceiling": "L0/L1",
        "board_release_allowed": False,
        "eda_invoked_by_sealer": False,
        "source_archive_sha256": expected,
        "files": {
            key: {"bytes": len(value), "sha256": sha256(value)}
            for key, value in sorted(entries.items())
        },
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output.mkdir()
    (output / "MANIFEST.json").write_bytes(manifest_bytes)
    package = output / "M3_40MHz_AUDIO_ENDPOINT_PREPARATION.zip"
    with zipfile.ZipFile(package, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("MANIFEST.json", manifest_bytes)
        for name, data in sorted(entries.items()):
            archive.writestr(name, data)
    with zipfile.ZipFile(package) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(entries) | {"MANIFEST.json"}:
            raise ValueError("Package member/CRC verification failed")
        for name, data in entries.items():
            if archive.read(name) != data or (repo / name).read_bytes() != data:
                raise ValueError(f"Package/source changed while sealing: {name}")
    receipt = {
        "status": "SEALED_BYTES_VERIFIED_NOT_STA_ACCEPTANCE",
        "package": str(package),
        "package_sha256": sha256(package.read_bytes()),
        "manifest_sha256": sha256(manifest_bytes),
        "member_count": len(entries),
        "board_release_allowed": False,
    }
    (output / "SEAL_RECEIPT.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
