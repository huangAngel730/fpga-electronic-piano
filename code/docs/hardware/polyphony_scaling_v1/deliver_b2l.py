"""Seal/verify preparation evidence, or forward a verified ordinary develop push."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[4]
DOC = Path(__file__).resolve().parent
NOTE = DOC / "B2L_PREPARATION_20261011.md"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def qualify(receipt):
    if (receipt["status"] != "B2L_PREPARATION_L1_PASS_T061_PARTIAL"
            or type(receipt["exit_code"]) is not int or receipt["exit_code"] != 0
            or receipt["elapsed_seconds"] > 1800
            or receipt["step_limit_seconds"] != 900 or receipt["workflow_limit_seconds"] != 1800
            or any(receipt[k] is not False for k in (
                "new_synthesis", "new_PnR", "new_RTL_simulation", "task_complete"))
            or receipt["new_elaboration"] is not True):
        raise ValueError("UNQUALIFIED_PREPARATION")
    for key in ("sources", "protected", "frozen"):
        if receipt[key+"_before"] != receipt[key+"_after"]:
            raise ValueError("CHANGED_INPUTS")
    labels = ["preparation_unit", "iverilog_version"]
    labels += [f"N{n}_{s}" for n in (4, 8, 16, 32) for s in ("prepare", "verify", "elaborate")]
    if [s["label"] for s in receipt["steps"]] != labels:
        raise ValueError("REQUIRED_STEPS")
    for step in receipt["steps"]:
        if (step["exit_code"] != 0 or step["expected_exit"] != 0 or step["timed_out"]
                or step["elapsed_limit_exceeded"] or step["timeout_seconds"] > 900):
            raise ValueError("UNQUALIFIED_STEP")
    if [(p["configuration"]["N"], p["configuration"]["response"]) for p in receipt["profiles"]] != [
            (n, 1) for n in (4, 8, 16, 32)]:
        raise ValueError("PROFILE_SET")


def verify(package):
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    carrier = (package / "evidence.zip.b64").read_bytes()
    raw = base64.b64decode(carrier, validate=True)
    if sha(raw) != manifest["zip_sha256"] or sha(carrier) != manifest["carrier_sha256"]:
        raise ValueError("ARCHIVE_SHA")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names) or set(names) != set(manifest["members"]) or archive.testzip():
            raise ValueError("MEMBER_SET_OR_CRC")
        blobs = {}
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name:
                raise ValueError("UNSAFE_MEMBER")
            data, expected = archive.read(name), manifest["members"][name]
            if len(data) != expected["bytes"] or sha(data) != expected["sha256"]:
                raise ValueError("MEMBER_SHA")
            blobs[name] = data
    receipt = json.loads(blobs[manifest["qualified_receipt"]])
    qualify(receipt)
    for item in receipt["outputs"] + receipt["sources_before"]:
        if item["path"].endswith(".vvp"):
            if item not in manifest["excluded_compiled_images"]:
                raise ValueError("UNDISCLOSED_IMAGE")
            continue
        if len(blobs[item["path"]]) != item["bytes"] or sha(blobs[item["path"]]) != item["sha256"]:
            raise ValueError("RECEIPT_BYTES")
    return dict(status="B2L_SEAL_VERIFIED", members=len(blobs), zip_sha256=sha(raw),
                workflow_elapsed_seconds=receipt["elapsed_seconds"], new_synthesis=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("seal", "verify", "forward"))
    parser.add_argument("--package", type=Path, default=DOC / "B2L_20261011_02")
    parser.add_argument("--run", type=Path)
    parser.add_argument("--gate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    package = args.package.resolve()
    package.relative_to(DOC)
    if args.mode == "verify":
        print(json.dumps(verify(package)))
        return
    if args.mode == "seal":
        run = args.run.resolve()
        run.relative_to(ROOT / "code/output")
        receipt = json.loads((run / "receipt.json").read_text(encoding="utf-8"))
        qualify(receipt)
        files = [p for p in run.rglob("*") if p.is_file() and p.suffix != ".vvp"]
        files += [ROOT / p["path"] for p in receipt["sources_before"]]
        files += [Path(__file__), NOTE, ROOT / "code/scripts/run_m3_polyphony_scaling_acceptance.py"]
        payload = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in files}
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(payload.items()):
                archive.writestr(name, data)
        raw = stream.getvalue()
        package.mkdir(parents=True, exist_ok=False)
        dump(package / "manifest.json", dict(
            stage="T061_B2L_PREPARATION_ONLY", qualified_receipt=(run / "receipt.json").relative_to(ROOT).as_posix(),
            zip_sha256=sha(raw), carrier_sha256=sha(base64.b64encode(raw)),
            excluded_compiled_images=[p for p in receipt["outputs"] if p["path"].endswith(".vvp")],
            members={n: dict(bytes=len(d), sha256=sha(d)) for n, d in sorted(payload.items())}))
        (package / "evidence.zip.b64").write_bytes(base64.b64encode(raw))
        result = verify(package)
        dump(package / "seal_receipt.json", dict(command=[sys.executable, *sys.argv], exit_code=0,
                                                 sealer_sha256=sha(Path(__file__).read_bytes()), result=result))
        print(json.dumps(result))
        return
    verified = verify(package)
    out, gate = args.output.resolve(), args.gate.resolve()
    out.relative_to(ROOT / "code/output")
    gate.relative_to(ROOT / "code/output")
    out.mkdir(parents=True, exist_ok=False)
    results = []
    def git(label, argv):
        result = subprocess.run(["git", *argv], cwd=ROOT, capture_output=True, timeout=90)
        for name, data in (("stdout", result.stdout), ("stderr", result.stderr)):
            (out / (label + "." + name + ".bin")).write_bytes(data)
        results.append(dict(label=label, argv=argv, exit_code=result.returncode))
        if result.returncode:
            raise ValueError("GIT_"+label)
        return result.stdout.decode("utf-8").strip()
    head, tree = git("head", ["rev-parse", "HEAD"]), git("tree", ["rev-parse", "HEAD^{tree}"])
    remote = git("remote", ["ls-remote", "origin", "refs/heads/develop"]).split()[0]
    branch = git("branch", ["branch", "--show-current"])
    gated = json.loads((gate / "receipt.json").read_text(encoding="utf-8"))
    if (head != remote or branch != "develop" or tree != gated["staged_tree"]
            or gated["status"] != "EXACT_INDEX_SNAPSHOT_9_GATES_PASS" or gated["exit_code"] != 0):
        raise ValueError("NOT_EXACT_GATED_PUSH")
    dump(out / "GIT_DELIVERY.json", dict(status="PUSH_VERIFIED", commit=head, tree=tree,
         remote_develop=remote, steps=results, seal=verified, M2_notification="待用户转发，尚未送达"))
    target = out / "M3_T061_综合前准备_B2L_交M2_20261011.zip"
    with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED) as archive:
        archive.write(NOTE, NOTE.name)
        archive.write(out / "GIT_DELIVERY.json", "GIT_DELIVERY.json")
        archive.writestr("B2L_evidence.zip", base64.b64decode((package / "evidence.zip.b64").read_bytes(), validate=True))
        for name in ("manifest.json", "seal_receipt.json"):
            archive.write(package / name, name)
        for p in sorted(gate.iterdir()):
            if p.is_file():
                archive.write(p, "publish_gate/"+p.name)
        for p in sorted(out.glob("*.bin")):
            archive.write(p, "publication/"+p.name)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip():
            raise ValueError("FORWARD_CRC")
    result = dict(status="PUSH_VERIFIED_FORWARD_READY", commit=head, archive=str(target),
                  archive_bytes=target.stat().st_size, archive_sha256=sha(target.read_bytes()))
    dump(out / "receipt.json", result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
