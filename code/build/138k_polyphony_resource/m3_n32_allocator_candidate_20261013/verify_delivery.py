"""Standalone read-only ZIP verification; no repository or vendor tools needed."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def digest(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--seal", type=Path, required=True)
    parser.add_argument("--seal-sha", required=True)
    args = parser.parse_args()
    seal_raw = args.seal.read_bytes()
    if digest(seal_raw)["sha256"] != args.seal_sha:
        raise ValueError("D_EXTERNAL_SEAL_SHA")
    seal = json.loads(seal_raw)
    manifest_raw = args.manifest.read_bytes()
    if digest(manifest_raw) != seal["manifest"] or digest(args.zip.read_bytes()) != seal["snapshot"]:
        raise ValueError("D_ARCHIVE_OR_MANIFEST_IDENTITY")
    manifest = json.loads(manifest_raw)
    with zipfile.ZipFile(args.zip) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)) or set(names) != set(manifest["files"]) | {"MANIFEST.json"}:
            raise ValueError("D_MEMBER_SET")
        if bundle.read("MANIFEST.json") != manifest_raw:
            raise ValueError("D_MANIFEST_MEMBER")
        for name, identity in manifest["files"].items():
            if digest(bundle.read(name)) != identity:
                raise ValueError("D_MEMBER_IDENTITY:" + name)
    print(json.dumps({"status": "D_OFFLINE_ARCHIVE_VERIFY_PASS", "members": len(names),
                      "EDA_calls": 0, "executed_archive_code": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
