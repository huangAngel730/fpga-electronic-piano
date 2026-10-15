"""Seal exact static preparation inputs and raw software evidence, not RTL results."""
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
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            hasher.update(chunk)
    return dict(bytes=path.stat().st_size, sha256=hasher.hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(".receipt.json").exists():
        parser.error("OUTPUT_EXISTS")
    run = args.run.resolve()
    receipt = json.loads((run / "receipt.json").read_text(encoding="utf-8"))
    proposal = json.loads((run / "prepared/proposal.json").read_text(encoding="utf-8"))
    if receipt["status"] != "STATIC_PREPARATION_PASS" or proposal["execution_authorized"] is not False:
        raise ValueError("STATIC_RECEIPT_OR_LOCK")
    for source, spec in receipt["after"].items():
        if identity(Path(source)) != {key: spec[key] for key in ("bytes", "sha256")}:
            raise ValueError("TESTED_SOURCE_DRIFT:" + source)
    files = {}
    for directory in (SOFTWARE, TB):
        for p in directory.iterdir():
            if p.is_file() and p.suffix in {".py", ".md", ".sv"}:
                files[p.relative_to(ROOT).as_posix()] = p
    for p in HERE.iterdir():
        if p.is_file() and p.suffix in {".py", ".md"}:
            files[p.relative_to(ROOT).as_posix()] = p
    for p in run.rglob("*"):
        if p.is_file():
            files["run/"+p.relative_to(run).as_posix()] = p
    before = {name: identity(path) for name, path in sorted(files.items())}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, path in sorted(files.items()):
            archive.write(path, name)
        archive.writestr("MANIFEST.json", json.dumps(dict(
            status="STATIC_PREPARATION_ONLY_PENDING_M2", execution_authorized=False,
            members=before, HDL_compiles=0, RTL_runs=0, PCM_math_verified=False),
            indent=2, ensure_ascii=False)+"\n")
    if before != {name: identity(path) for name, path in sorted(files.items())}:
        raise ValueError("SEAL_INPUT_DRIFT")
    with zipfile.ZipFile(args.output) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP_CRC")
        for name, spec in before.items():
            hasher = hashlib.sha256()
            count = 0
            with archive.open(name) as stream:
                for data in iter(lambda: stream.read(1 << 20), b""):
                    hasher.update(data)
                    count += len(data)
            if dict(bytes=count, sha256=hasher.hexdigest()) != spec:
                raise ValueError("ZIP_MEMBER_IDENTITY:"+name)
    result = dict(status="SEAL_PASS", package=identity(args.output),
                  members=len(before)+1, input_sha256=proposal["input"]["sha256"],
                  HDL_compiles=0, RTL_runs=0, execution_authorized=False)
    with args.output.with_suffix(".receipt.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
