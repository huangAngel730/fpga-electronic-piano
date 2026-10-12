"""Seal and verify the exact pin-projection run without executing its code."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DOC = ROOT / "code/docs/hardware/polyphony_frame_acceptance_20261012/pin_projection_20261012"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or archive.testzip():
            raise ValueError("SEAL_DUPLICATE_OR_CRC")
        manifest = json.loads(archive.read("MEMBERS.json").decode("utf-8"))
        if set(names) != set(manifest) | {"MEMBERS.json"}:
            raise ValueError("SEAL_MEMBERS")
        for name, expected in manifest.items():
            path = Path(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
                raise ValueError("SEAL_UNSAFE_PATH")
            raw_member = archive.read(name)
            actual = {"bytes": len(raw_member), "sha256": sha(raw_member)}
            if actual != expected:
                raise ValueError("SEAL_MEMBER_SHA:" + name)
        receipt = json.loads(archive.read("run/receipt.json").decode("utf-8"))
        if receipt["exit_code"] or receipt["status"] != "PIN_PROJECTION_SOFTWARE_L0_L1_PASS":
            raise ValueError("SEAL_RUN_NOT_PASS")
    return {"status": "PIN_PROJECTION_SEAL_VERIFIED", "sha256": sha(raw),
            "bytes": len(raw), "members": len(names), "executed": False}


def seal(run, output, prior_failure=None):
    run = run.resolve()
    run.relative_to(ROOT / "code/output")
    output = output.resolve()
    output.relative_to(DOC)
    if output.exists():
        raise ValueError("SEAL_REFUSE_OVERWRITE")
    files = {"run/" + path.relative_to(run).as_posix(): path.read_bytes()
             for path in run.rglob("*") if path.is_file()}
    if prior_failure is not None:
        prior_failure = prior_failure.resolve()
        prior_failure.relative_to(ROOT / "code/output")
        prior_receipt = json.loads((prior_failure / "receipt.json").read_text(encoding="utf-8"))
        if prior_receipt["exit_code"] == 0:
            raise ValueError("PRIOR_FAILURE_WAS_PASS")
        files.update({"prior_failure/" + path.relative_to(prior_failure).as_posix(): path.read_bytes()
                      for path in prior_failure.rglob("*") if path.is_file()})
    manifest = {name: {"bytes": len(raw), "sha256": sha(raw)}
                for name, raw in files.items()}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 13, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
        archive.writestr("MEMBERS.json", json.dumps(manifest, indent=2).encode("utf-8"))
    raw = stream.getvalue()
    result = verify(raw)
    output.mkdir(parents=True)
    (output / "PIN_PROJECTION_SEAL.zip.b64").write_bytes(base64.encodebytes(raw))
    (output / "seal_receipt.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("seal", "verify"))
    parser.add_argument("--run", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--base64", type=Path)
    parser.add_argument("--prior-failure", type=Path)
    args = parser.parse_args()
    if args.mode == "seal":
        result = seal(args.run, args.output, args.prior_failure)
    else:
        result = verify(base64.decodebytes(args.base64.read_bytes()))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
