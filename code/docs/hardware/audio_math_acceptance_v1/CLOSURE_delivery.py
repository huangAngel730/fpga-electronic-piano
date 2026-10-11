"""Seal/verify T060 counter audit and prepare a user-forwarded evidence ZIP."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[4]
DOC = Path(__file__).resolve().parent
STATUS = "T060_COUNTER_AUDIT_L1_PASS_PARTIAL"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as out:
        json.dump(value, out, ensure_ascii=False, indent=2)
        out.write("\n")


def verify(package):
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    carrier = (package / "evidence.zip.b64").read_bytes()
    raw = base64.b64decode(carrier, validate=True)
    if sha(carrier) != manifest["carrier_sha256"] or sha(raw) != manifest["zip_sha256"]:
        raise ValueError("CLOSURE_ARCHIVE_SHA")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if archive.testzip() or len(names) != len(set(names)) or set(names) != set(manifest["members"]):
            raise ValueError("CLOSURE_ARCHIVE_MEMBERS")
        for name, meta in manifest["members"].items():
            if ".." in Path(name).parts or name.startswith(("/", "\\")) or ":" in name:
                raise ValueError("CLOSURE_ARCHIVE_PATH")
            data = archive.read(name)
            if len(data) != meta["bytes"] or sha(data) != meta["sha256"]:
                raise ValueError("CLOSURE_MEMBER_SHA:" + name)
        r = json.loads(archive.read(manifest["qualified_receipt"]))
        if r["status"] != STATUS or type(r["exit_code"]) is not int or r["exit_code"] != 0:
            raise ValueError("CLOSURE_RECEIPT_STATUS")
        if r["t060_complete"] is not False or r["elapsed_seconds"] > 300 or len(r["steps"]) != 4:
            raise ValueError("CLOSURE_RECEIPT_SCOPE")
        for prefix in ("protected", "sources", "inputs"):
            if r[prefix + "_before"] != r[prefix + "_after"]:
                raise ValueError("CLOSURE_RECEIPT_DRIFT")
        bindings = dict(r["sources_before"], **r["inputs_before"], **r["protected_before"])
        for path, meta in bindings.items():
            name = manifest["input_member_map"][path]
            data = archive.read(name)
            if sha(data) != meta["sha256"] or len(data) != meta["bytes"]:
                raise ValueError("CLOSURE_RECEIPT_INPUT_SHA")
        run = Path(manifest["qualified_receipt"]).parent
        for name, meta in r["artifact_sha"].items():
            data = archive.read((run / name).as_posix())
            if sha(data) != meta["sha256"] or len(data) != meta["bytes"]:
                raise ValueError("CLOSURE_RECEIPT_ARTIFACT_SHA")
        for step in r["steps"]:
            if step["timed_out"] or step["exit_code"] != step["expected_exit"] or step["elapsed_seconds"] > step["timeout_seconds"]:
                raise ValueError("CLOSURE_RECEIPT_STEP")
    return dict(status="T060_CLOSURE_SEAL_VERIFIED_PARTIAL", members=len(manifest["members"]),
                zip_sha256=sha(raw), t060_complete=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("seal", "verify", "selftest", "forward"))
    parser.add_argument("--package", type=Path, default=DOC / "CLOSURE_20261011_02")
    parser.add_argument("--run", type=Path)
    parser.add_argument("--gate", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--selftest", type=Path)
    args = parser.parse_args()
    package = args.package.resolve()
    if not package.is_relative_to(DOC) or package == DOC:
        raise ValueError("CLOSURE_PACKAGE_SCOPE")
    if args.mode == "seal":
        run = args.run.resolve()
        if not run.is_relative_to(ROOT / "code/output"):
            raise ValueError("CLOSURE_RUN_SCOPE")
        receipt = json.loads((run / "receipt.json").read_text(encoding="utf-8"))
        if receipt["status"] != STATUS:
            raise ValueError("CLOSURE_UNQUALIFIED_RUN")
        payload = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in run.iterdir() if p.is_file()}
        mapping = {}
        for section in ("sources_before", "inputs_before", "protected_before"):
            for path in receipt[section]:
                p = Path(path)
                name = (p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT)
                        else "original_Golden/" + p.name)
                raw = p.read_bytes()
                if name in payload and payload[name] != raw:
                    raise ValueError("CLOSURE_MEMBER_COLLISION")
                payload[name] = raw
                mapping[path] = name
        for p in (DOC / "CLOSURE_AUDIT_20261011.md", Path(__file__)):
            payload[p.relative_to(ROOT).as_posix()] = p.read_bytes()
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, raw in sorted(payload.items()):
                archive.writestr(name, raw)
        raw = stream.getvalue()
        carrier = base64.b64encode(raw)
        package.mkdir(exist_ok=False)
        (package / "evidence.zip.b64").write_bytes(carrier)
        dump(package / "manifest.json", dict(zip_sha256=sha(raw), carrier_sha256=sha(carrier),
             qualified_receipt=(run / "receipt.json").relative_to(ROOT).as_posix(),
             input_member_map=mapping, members={n: dict(bytes=len(d), sha256=sha(d)) for n, d in payload.items()},
             committed_at_seal=False, pushed_at_seal=False, t060_complete=False))
        result = verify(package)
        dump(package / "seal_receipt.json", dict(result=result, exit_code=0,
             command=[sys.executable, *sys.argv], sealer_sha256=sha(Path(__file__).read_bytes())))
    elif args.mode == "verify":
        result = verify(package)
    elif args.mode == "selftest":
        normal = verify(package)
        out = args.output.resolve()
        if not out.is_relative_to(ROOT / "code/output") or out == ROOT / "code/output":
            raise ValueError("CLOSURE_SELFTEST_SCOPE")
        out.mkdir(parents=True, exist_ok=False)
        original_m = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
        with zipfile.ZipFile(io.BytesIO(base64.b64decode((package / "evidence.zip.b64").read_bytes()))) as archive:
            original = {n: archive.read(n) for n in archive.namelist()}
        tests = []
        for label, expected in (("bad_carrier", "CLOSURE_ARCHIVE_SHA"),
                                ("missing_member", "CLOSURE_ARCHIVE_MEMBERS"),
                                ("forged_complete", "CLOSURE_RECEIPT_SCOPE"),
                                ("rebound_audit", "CLOSURE_RECEIPT_ARTIFACT_SHA")):
            payload = dict(original)
            manifest = json.loads(json.dumps(original_m))
            if label == "missing_member":
                del payload[manifest["qualified_receipt"]]
            elif label == "forged_complete":
                r = json.loads(payload[manifest["qualified_receipt"]])
                r["t060_complete"] = True
                payload[manifest["qualified_receipt"]] = json.dumps(r).encode()
            elif label == "rebound_audit":
                name = (Path(manifest["qualified_receipt"]).parent / "audit.json").as_posix()
                payload[name] = b"{}"
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, data in payload.items():
                    archive.writestr(name, data)
            raw = stream.getvalue()
            carrier = base64.b64encode(raw)
            manifest.update(zip_sha256=sha(raw), carrier_sha256=sha(carrier))
            if label in ("forged_complete", "rebound_audit"):
                manifest["members"] = {n: dict(bytes=len(d), sha256=sha(d)) for n, d in payload.items()}
            if label == "bad_carrier":
                carrier = b"A" + carrier[1:]
            folder = out / label
            folder.mkdir()
            (folder / "evidence.zip.b64").write_bytes(carrier)
            dump(folder / "manifest.json", manifest)
            try:
                verify(folder)
            except ValueError as error:
                if str(error) != expected:
                    raise ValueError("CLOSURE_SEAL_WRONG_DIAGNOSTIC:" + str(error)) from error
                tests.append(dict(case=label, diagnostic=str(error)))
            else:
                raise ValueError("CLOSURE_TAMPER_ACCEPTED:" + label)
        result = dict(normal=normal, specified_rejections=tests, exit_code=0)
        dump(out / "receipt.json", result)
    else:
        result = verify(package)
        gate = args.gate.resolve()
        if not gate.is_relative_to(ROOT / "code/output"):
            raise ValueError("CLOSURE_GATE_SCOPE")
        def git(*argv):
            return subprocess.check_output(["git", *argv], cwd=ROOT, timeout=30).decode().strip()
        head = git("rev-parse", "HEAD")
        tree = git("rev-parse", "HEAD^{tree}")
        remote = git("ls-remote", "origin", "refs/heads/develop").split()[0]
        g = json.loads((gate / "receipt.json").read_text(encoding="utf-8"))
        if (head != remote or g["staged_tree"] != tree or g["exit_code"] != 0
                or g["status"] != "EXACT_INDEX_SNAPSHOT_9_GATES_PASS"
                or git("branch", "--show-current") != "develop"):
            raise ValueError("CLOSURE_PUSH_OR_GATE_NOT_VERIFIED")
        out = args.output.resolve()
        if not out.is_relative_to(ROOT / "code/output") or out == ROOT / "code/output":
            raise ValueError("CLOSURE_FORWARD_SCOPE")
        out.mkdir(parents=True, exist_ok=False)
        delivery = dict(head=head, remote_develop=remote, tree=tree, status="PUSH_VERIFIED",
                        t060_complete=False, notification="待用户转发，尚未送达")
        test = args.selftest.resolve()
        if not test.is_relative_to(ROOT / "code/output"):
            raise ValueError("CLOSURE_SELFTEST_RECEIPT_SCOPE")
        tested = json.loads(test.read_text(encoding="utf-8"))
        if tested["exit_code"] != 0 or tested["normal"] != result or len(tested["specified_rejections"]) != 4:
            raise ValueError("CLOSURE_SELFTEST_NOT_VERIFIED")
        delivery["sealer_selftest_sha256"] = sha(test.read_bytes())
        dump(out / "GIT_DELIVERY.json", delivery)
        zip_path = out / "M3_T060_两个计数补核及剩余清单_交M2_20261011.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("evidence.zip", base64.b64decode((package / "evidence.zip.b64").read_bytes(), validate=True))
            for p in (package / "manifest.json", package / "seal_receipt.json", DOC / "CLOSURE_AUDIT_20261011.md", out / "GIT_DELIVERY.json"):
                archive.write(p, p.name)
            archive.write(test, "sealer_selftest.json")
            for p in gate.iterdir():
                if p.is_file():
                    archive.write(p, "final_gate/" + p.name)
        with zipfile.ZipFile(zip_path) as archive:
            if archive.testzip():
                raise ValueError("CLOSURE_FORWARD_CRC")
        result = dict(delivery, path=str(zip_path), bytes=zip_path.stat().st_size,
                      sha256=sha(zip_path.read_bytes()))
        dump(out / "forward_receipt.json", result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
