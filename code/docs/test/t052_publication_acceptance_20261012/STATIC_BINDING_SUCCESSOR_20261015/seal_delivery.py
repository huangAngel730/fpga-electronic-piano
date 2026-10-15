"""Seal only this static/software delivery and preserve failed attempts."""

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[5]
SOFTWARE = ROOT / "code/software/t052_publication_acceptance_candidate_20261012/static_binding_successor_20261015"
HERE = Path(__file__).resolve().parent


def identity(path):
    data = path.read_bytes()
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--history", action="append", default=[], type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run = args.run.resolve()
    receipt = json.loads((run / "receipt.json").read_text(encoding="utf-8"))
    if (receipt["status"] != "PASS" or receipt["source_before"] != receipt["source_after"]
            or receipt["HDL_compiles"] != 0 or receipt["RTL_runs"] != 0):
        raise ValueError("FINAL_SOFTWARE_RECEIPT_NOT_PASS")
    for name, spec in receipt["source_after"].items():
        if identity(Path(name)) != {k: spec[k] for k in ("bytes", "sha256")}:
            raise ValueError("TESTED_SOURCE_DRIFT:" + name)
    output = args.output.resolve()
    if not output.is_relative_to(HERE) or output.exists():
        raise ValueError("OUTPUT_EXISTS_OR_OUTSIDE_DELIVERY_DIRECTORY")
    files = {}
    for source in sorted([*SOFTWARE.glob("*.py"), *SOFTWARE.glob("*.md"),
                          *HERE.glob("*.py"), *HERE.glob("*.md")]):
        files["sources/" + source.relative_to(ROOT).as_posix()] = source
    for label, directory in [("final_run", run)] + [
            (f"history_{i:02d}", p.resolve()) for i, p in enumerate(args.history, 1)]:
        if not directory.is_relative_to((ROOT / "code/output").resolve()):
            raise ValueError("RUN_OUTSIDE_CODE_OUTPUT")
        for source in sorted(directory.rglob("*")):
            if source.is_file():
                files[label + "/" + source.relative_to(directory).as_posix()] = source
    manifest = {name: identity(source) for name, source in files.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as archive:
        for name, source in files.items():
            archive.write(source, name)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("SEALED_ZIP_CRC")
        for name, spec in manifest.items():
            data = archive.read(name)
            if len(data) != spec["bytes"] or hashlib.sha256(data).hexdigest() != spec["sha256"]:
                raise ValueError("SEALED_MEMBER_IDENTITY:" + name)
    result = dict(schema="T052_STATIC_BINDING_SEAL_R01", archive=identity(output),
                  members=len(manifest), scope="STATIC_SOFTWARE_ONLY",
                  old_4207_completeness="UNKNOWN", complete_T052=False,
                  execution_authorized=False)
    with output.with_suffix(".receipt.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
