"""Seal revised sources plus raw SOFTWARE evidence, preserving the old R01 ZIP."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SOFTWARE = ROOT / "code/software/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015"
TB = ROOT / "code/tb/audio/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015"


def identity(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return {"bytes": path.stat().st_size, "sha256": h.hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    files = {}
    for directory in (SOFTWARE, TB, HERE):
        for path in directory.iterdir():
            if path.is_file() and path.suffix in {".py", ".sv", ".md"}:
                files[path.relative_to(ROOT).as_posix()] = path
    old = HERE / "T052_LONG_STATIC_R01.zip"
    if identity(old)["sha256"] != "43d2c43ce0a59fc1c91dd09b2c6842ef40b856b3de74d66f4c513706e0275252":
        raise ValueError("OLD_SEAL_CHANGED")
    files["readonly_original/T052_LONG_STATIC_R01.zip"] = old
    for directory in args.evidence:
        directory = directory.resolve()
        for path in directory.rglob("*"):
            if path.is_file():
                files["software_evidence/" + directory.name + "/" + path.relative_to(directory).as_posix()] = path
    members = {name: identity(path) for name, path in sorted(files.items())}
    with zipfile.ZipFile(args.output, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, path in sorted(files.items()):
            archive.write(path, name)
        archive.writestr("MANIFEST.json", json.dumps({
            "schema": "T052_LONG_RUNNER_SOFTWARE_R02",
            "validation": "L0_STATIC_AND_SOFTWARE_FAKE_PROCESSES_ONLY",
            "actual_new_T052_HDL_compiles": 0, "actual_new_T052_RTL_runs": 0,
            "execution_authorized": False, "members": members}, indent=2) + "\n")
    if members != {name: identity(path) for name, path in sorted(files.items())}:
        raise ValueError("SEAL_INPUT_DRIFT")
    with zipfile.ZipFile(args.output) as archive:
        if archive.testzip():
            raise ValueError("ZIP_CRC")
        for name, expected in members.items():
            raw = archive.read(name)
            if {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} != expected:
                raise ValueError("ZIP_MEMBER_SHA:" + name)
    result = {"status": "SEAL_PASS_SOFTWARE_ONLY", "members": len(members)+1,
              "package": identity(args.output), "execution_authorized": False}
    with args.output.with_suffix(".receipt.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
