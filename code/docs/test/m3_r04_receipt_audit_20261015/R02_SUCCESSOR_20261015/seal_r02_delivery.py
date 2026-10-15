"""Seal R02 software increment only; never invoke tests or EDA."""

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / "code/software/m3_r04_receipt_audit_20261015/r02_successor_20261015"


def identity(path):
    raw = path.read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--m1-input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = json.loads((args.run / "receipt.json").read_text(encoding="utf-8"))
    if (receipt["status"] != "PASS" or receipt["exit_code"] != 0
            or receipt["source_before"] != receipt["source_after"]
            or receipt["protected_main2_before"] != receipt["protected_main2_after"]):
        raise ValueError("SOFTWARE_RECEIPT_OR_PARENT_PROTECTION_FAILED")
    for name, expected in (receipt["source_after"] | receipt["protected_main2_after"]).items():
        if identity(ROOT / name) != expected:
            raise ValueError("TESTED_SOURCE_DRIFT:" + name)
    m1 = args.m1_input.resolve()
    primary = m1 / "M1回复M3_R04离线配套判据与补测决定_R02.md"
    if identity(primary)["sha256"] != "f04626580ca36674543ba9decedcb31db569b44324c893aaa3f9f1a19eb811ac":
        raise ValueError("M1_INPUT_IDENTITY")
    output = args.output.resolve()
    if not output.is_relative_to(HERE) or output.exists():
        raise ValueError("OUTPUT_EXISTS_OR_OUTSIDE_DELIVERY")
    files = {}
    for path in [*SOURCE.glob("*.py"), *SOURCE.glob("*.md"), *HERE.glob("*.py"), *HERE.glob("*.md")]:
        files["sources/" + path.relative_to(ROOT).as_posix()] = path
    for label, directory in (("software_run", args.run.resolve()),
                             ("baseline_gap", args.baseline.resolve())):
        if not directory.is_relative_to((ROOT / "code/output").resolve()):
            raise ValueError("RUN_PATH_OUTSIDE_OUTPUT")
        for path in directory.rglob("*"):
            if path.is_file():
                files[label + "/" + path.relative_to(directory).as_posix()] = path
    for name in (primary.name, "STATIC_REVIEW_EVIDENCE_R02.json", "REVIEW_RECEIPT_R02.md", "MANIFEST.json"):
        files["m1_input/" + name] = m1 / name
    manifest = {name: identity(path) for name, path in files.items()}
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as archive:
        for name, path in files.items():
            archive.write(path, name)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("ARCHIVE_CRC")
        for name, expected in manifest.items():
            raw = archive.read(name)
            actual = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            if actual != expected:
                raise ValueError("SEALED_MEMBER_IDENTITY:" + name)
    result = dict(scope="M1_R02_SOFTWARE_INCREMENT_ONLY", archive=identity(output),
                  members=len(manifest), parent_main2_unchanged=True, real_R04_executed=False)
    with output.with_suffix(".receipt.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
