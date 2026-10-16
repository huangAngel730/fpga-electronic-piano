"""Read sealed archives and verify every declared byte without executing tests."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    members = manifest.get("members", manifest.get("files", manifest))
    if not isinstance(members, dict):
        raise ValueError("unsupported manifest")
    with zipfile.ZipFile(args.archive) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert len(names) == len(set(names)), "duplicate ZIP name"
        for name, entry in members.items():
            raw = archive.read(name)
            assert len(raw) == entry["bytes"], name
            assert hashlib.sha256(raw).hexdigest() == entry["sha256"], name
        extra = sorted(set(names) - set(members))
        assert all(Path(n).name == "MANIFEST.json" for n in extra), extra
    result = {"status": "PASS", "scope": "READ_ONLY_ARCHIVE_BYTES",
              "archive": str(args.archive.resolve()),
              "sha256": hashlib.sha256(args.archive.read_bytes()).hexdigest(),
              "bytes": args.archive.stat().st_size,
              "verified_members": len(members), "extra_manifest_entries": extra,
              "new_rtl_or_eda_invocations": 0}
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
