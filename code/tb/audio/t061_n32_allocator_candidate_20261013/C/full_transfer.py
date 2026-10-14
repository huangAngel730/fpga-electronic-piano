"""Package the exact published continuous-C seal and real publication receipts."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile


def identity(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "seal-dir", "evidence", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--seal-sha", required=True)
    args = parser.parse_args()
    seal_raw = (args.seal_dir/"seal.json").read_bytes()
    if identity(seal_raw)["sha256"] != args.seal_sha:
        raise ValueError("C_FULL_EXTERNAL_SEAL_PIN")
    seal = json.loads(seal_raw)
    if seal["status"] != "N32_C_FULL_CONTINUOUS_FUNCTION_MATH_PASS_T061_PARTIAL":
        raise ValueError("C_FULL_SEAL_SCOPE")
    manifest_raw = (args.seal_dir/"MANIFEST.json").read_bytes()
    raw = base64.b64decode((args.seal_dir/"snapshot.zip.b64").read_bytes().strip(), validate=True)
    if identity(raw) != seal["snapshot"] or identity(manifest_raw) != seal["manifest"]:
        raise ValueError("C_FULL_ARCHIVE_IDENTITY")
    original = json.loads(manifest_raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        if (len(bundle.namelist()) != seal["members"] or len(set(bundle.namelist())) != seal["members"]
                or set(bundle.namelist()) != set(original["files"]) | {"MANIFEST.json"}
                or bundle.read("MANIFEST.json") != manifest_raw):
            raise ValueError("C_FULL_ARCHIVE_MEMBER_SET")
        for name, expected in original["files"].items():
            if identity(bundle.read(name)) != expected:
                raise ValueError("C_FULL_ARCHIVE_MEMBER:" + name)
    publication = json.loads((args.evidence/"publication_receipt.json").read_bytes())
    gate = json.loads((args.evidence/"gate_receipt.json").read_bytes())
    if (publication["commit"] != args.commit or publication["remote_commit"] != args.commit
            or gate["commit"] != args.commit or gate["exit_code"] != 0 or gate["pass_count"] != 9):
        raise ValueError("C_FULL_PUBLICATION_NOT_VERIFIED")
    files = {"C_FULL/snapshot.zip": raw, "C_FULL/seal.json": seal_raw,
             "C_FULL/MANIFEST.json": manifest_raw}
    roots = ["code/tb/audio/t061_n32_allocator_candidate_20261013/C",
             "code/software/t061_n32_stress_plan_candidate_20261013"]
    def git(*arguments):
        return subprocess.check_output(["git", "-C", str(args.repo), *arguments], timeout=90)
    names = git("ls-tree", "-r", "--name-only", "-z", args.commit, "--", *roots).split(b"\0")
    for name in filter(None, names):
        name = name.decode("utf-8")
        if not name.endswith((".zip", ".zip.b64")):
            files["source/" + name] = git("show", args.commit + ":" + name)
    for path in sorted(args.evidence.rglob("*")):
        if path.is_file():
            files["publication/" + path.relative_to(args.evidence).as_posix()] = path.read_bytes()
    manifest = encode({"commit": args.commit, "T061_complete": False, "EDA_calls": 0,
                       "files": {name: identity(body) for name, body in sorted(files.items())}})
    files["MANIFEST.json"] = manifest
    args.out.mkdir(parents=True, exist_ok=False)
    target = args.out/"M3_N32_C_FULL_20261014.zip"
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for name, body in sorted(files.items()):
            bundle.writestr(name, body)
    with zipfile.ZipFile(target) as bundle:
        if set(bundle.namelist()) != set(files):
            raise ValueError("C_FULL_TRANSFER_MEMBER_SET")
        for name, body in files.items():
            if bundle.read(name) != body:
                raise ValueError("C_FULL_TRANSFER_MEMBER:" + name)
    (args.out/"MANIFEST.json").write_bytes(manifest)
    result = {"commit": args.commit, "zip": identity(target.read_bytes()),
              "members": len(files), "manifest": identity(manifest),
              "status": "READY_TO_FORWARD_NOT_DELIVERED"}
    (args.out/"transfer_receipt.json").write_bytes(encode(result))
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
