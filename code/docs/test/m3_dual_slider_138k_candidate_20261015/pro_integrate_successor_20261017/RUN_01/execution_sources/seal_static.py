"""Archive static originals/results; its own output receipts stay external."""
import hashlib
import json
from pathlib import Path
import sys
import time
import zipfile

HERE = Path(sys.argv[1]).resolve()
PRODUCTS = Path(sys.argv[2]).resolve()
ROOT = HERE.parents[4]
CURRENT_RUN = PRODUCTS.parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    began = time.monotonic()
    result = json.loads((PRODUCTS / "RESULT.json").read_text(encoding="utf-8"))
    assert result["actual_level"] == "L0_STATIC_ONLY" and not result["board_release_allowed"]
    package = PRODUCTS / "M3_E1_PRO_INTEGRATION_STATIC_DIFF_20261017.zip"
    files = sorted(p for p in HERE.rglob("*") if p.is_file()
                   and p not in (PRODUCTS / "MANIFEST.json", PRODUCTS / "PACKAGE_STATUS.json")
                   and p != package
                   and not (p.parent == CURRENT_RUN and p.name.startswith("seal."))
                   and p.relative_to(HERE).parts[0] != "INPUT_ORIGINALS")
    entries = [{"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size,
                "sha256": sha(p.read_bytes())} for p in files]
    manifest = {"actual_level": "L0_STATIC_ONLY", "formal_integration": result["formal_integration"],
                "board_release_allowed": False, "entries": entries,
                "excludes": ["manifest self", "new package self", "PACKAGE_STATUS/FINAL_RECEIPT/COMMUNICATION_RECEIPT",
                             "current RUN seal.* external raw streams/launch/receipt",
                             "INPUT_ORIGINALS local read-only input copies; old cases/package only referenced"]}
    write(PRODUCTS / "MANIFEST.json", manifest)
    with zipfile.ZipFile(package, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for item, path in zip(entries, files):
            assert time.monotonic() - began < 80, "SEAL_LOCAL_TIME_LIMIT"
            archive.write(path, item["path"])
        archive.write(PRODUCTS / "MANIFEST.json", (PRODUCTS / "MANIFEST.json").relative_to(ROOT).as_posix())
    with zipfile.ZipFile(package) as archive:
        assert archive.testzip() is None
        for item in entries:
            data = archive.read(item["path"])
            assert len(data) == item["bytes"] and sha(data) == item["sha256"]
        assert len(archive.namelist()) == len(entries) + 1
        assert not any("/INPUT_ORIGINALS/" in name for name in archive.namelist())
        assert archive.read((PRODUCTS / "MANIFEST.json").relative_to(ROOT).as_posix()) == (PRODUCTS / "MANIFEST.json").read_bytes()
    status = {"package": str(package), "bytes": package.stat().st_size, "sha256": sha(package.read_bytes()),
              "members": len(entries) + 1, "manifest_sha256": sha((PRODUCTS / "MANIFEST.json").read_bytes()),
              "all_member_bytes_sha_crc_verified": True, "actual_level": "L0_STATIC_ONLY",
              "formal_integration": result["formal_integration"], "board_release_allowed": False,
              "submitted": False, "pushed": False}
    write(PRODUCTS / "PACKAGE_STATUS.json", status)
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
