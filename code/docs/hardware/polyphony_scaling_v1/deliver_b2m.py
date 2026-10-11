"""Seal, independently replay, tamper-test and forward software-only B2M."""
import argparse
import base64
import copy
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[4]
DOC = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "code/software/polyphony_scaling_candidate"))

RUN_STATUS = "B2M_RECOVERY_PCM_SOFTWARE_PASS_T061_PARTIAL"
DOCUMENT = "B2M_IMPLEMENTATION_20261011.md"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def metadata(raw):
    return dict(bytes=len(raw), sha256=sha(raw))


def dump(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def qualified(r):
    from b2m_check import STATUS

    if (r["status"] != RUN_STATUS or type(r["exit_code"]) is not int or r["exit_code"] != 0
            or r["task_complete"] is not False or r["total_limit_seconds"] != 300
            or r["step_limit_seconds"] != 90 or not 0 < r["elapsed_seconds"] <= 300
            or r["tests_run"] != 12 or len(r["steps"]) != 16 or len(r["negatives"]) != 6
            or any(r[k] is not False for k in (
                "new_RTL_simulation", "new_synthesis", "new_PnR", "device_operations"))):
        raise ValueError("B2M_RECEIPT_SCOPE")
    for key in ("protected", "sources"):
        if r[key + "_before"] != r[key + "_after"]:
            raise ValueError("B2M_RECEIPT_DRIFT")
    for step in r["steps"]:
        if (type(step["exit_code"]) is not int or step["exit_code"] != step["expected_exit"]
                or step["timed_out"] is not False
                or not 0 <= step["elapsed_seconds"] <= step["timeout_seconds"] <= 90):
            raise ValueError("B2M_RECEIPT_STEP")
    if [(p["N"], p["response"]) for p in r["profiles"]] != [(4, 1), (32, 1), (32, 64)]:
        raise ValueError("B2M_PROFILES")
    for p in r["profiles"]:
        if (p["status"] != STATUS or p["task_complete"] is not False
                or p["counts"]["published_pcm_checked"] != 21
                or p["counts"]["first_valid_checked"] != 21
                or p["lane_math_fields_observed"] is not False
                or p["LFO_nonrollback_proved"] is not False
                or p["production_admitted"] is not False or p["physical_STA"] is not None):
            raise ValueError("B2M_PROFILE_SCOPE")


def checked(manifest, raw):
    # Historical replay API is retained, but must not import worktree models.
    raise ValueError("B2M_LEGACY_CLOSURE_INCOMPLETE_USE_CLOSURE_VERIFY")


def historical_checked_not_executable(manifest, raw):
    """Preserved historical algorithm; deliberately unreachable from CLI."""
    from b2m_check import check
    from b2m_inputs import CARRIER_SHA, PACKAGE, ZIP_SHA
    from b2m_run import changed

    if sha(raw) != manifest["zip_sha256"]:
        raise ValueError("B2M_ARCHIVE_SHA")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if archive.testzip() or len(set(names)) != len(names) or set(names) != set(manifest["members"]):
            raise ValueError("B2M_MEMBERS")
        payload = {}
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name:
                raise ValueError("B2M_PATH")
            data = archive.read(name)
            if metadata(data) != manifest["members"][name]:
                raise ValueError("B2M_MEMBER_SHA")
            payload[name] = data
    r = json.loads(payload[manifest["qualified_receipt"]])
    qualified(r)
    for item in r["sources_before"] + r["protected_before"] + r["artifacts"]:
        if metadata(payload[item["path"]]) != {k: item[k] for k in ("bytes", "sha256")}:
            raise ValueError("B2M_RECEIPT_BOUND_BYTES")
    old_package = PACKAGE.relative_to(ROOT).as_posix()
    old_carrier = payload[old_package + "/evidence.zip.b64"]
    old_zip = base64.b64decode(old_carrier, validate=True)
    if sha(old_zip) != ZIP_SHA or sha(old_carrier) != CARRIER_SHA:
        raise ValueError("B2M_OLD_SEAL_IDENTITY")
    old_manifest = json.loads(payload[old_package + "/manifest.json"])
    with zipfile.ZipFile(io.BytesIO(old_zip)) as archive:
        if archive.testzip():
            raise ValueError("B2M_OLD_CRC")
        old_receipt = archive.read(old_manifest["qualified_receipt"])
        if sha(old_receipt) != r["original_seal"]["receipt_sha256"]:
            raise ValueError("B2M_OLD_RECEIPT_SHA")
        for label, item in r["original_inputs"].items():
            restored = payload[item["restored_identity"]["path"]]
            if restored != archive.read(item["original_member"]):
                raise ValueError("B2M_ORIGINAL_CAPTURE_CHANGED")
            actual = check(restored)
            profile = next(p for p in r["profiles"] if label == f"N{p['N']}_R{p['response']}")
            if json.loads(json.dumps(actual)) != profile:
                raise ValueError("B2M_PROFILE_REPLAY")
    run = PurePosixPath(manifest["qualified_receipt"]).parent
    for negative in r["negatives"]:
        kind = negative["kind"]
        label = negative["profile"]
        original = payload[r["original_inputs"][label]["restored_identity"]["path"]]
        expected, cycles = changed(original, kind, negative["request"])
        if expected != payload[str(run / (kind + ".capture"))] or cycles != negative["modified_cycles"]:
            raise ValueError("B2M_NEGATIVE_BINDING")
        old_step = next(s for s in r["steps"] if s["label"] == kind + "_old_clock_accepts")
        new_step = next(s for s in r["steps"] if s["label"] == kind + "_math_rejects")
        reason = json.loads(payload[new_step["stdout"]["path"]])
        if (old_step["exit_code"] != 0 or new_step["exit_code"] != 1
                or reason["status"] != "B2M_REJECTED" or not reason["diagnostic"].startswith("B2M_PCM:")):
            raise ValueError("B2M_NEGATIVE_DIAGNOSTIC")
    return r, payload


def verify(package):
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    carrier = (package / "evidence.zip.b64").read_bytes()
    if sha(carrier) != manifest["carrier_sha256"]:
        raise ValueError("B2M_CARRIER_SHA")
    raw = base64.b64decode(carrier, validate=True)
    r, payload = checked(manifest, raw)
    return dict(status="B2M_SEAL_REPLAY_VERIFIED_PARTIAL", members=len(payload),
                zip_sha256=sha(raw), original_capture_replays=3,
                original_workflow_seconds=r["elapsed_seconds"], task_complete=False)


def encode(payload, manifest):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(payload.items()):
            archive.writestr(name, data)
    raw = out.getvalue()
    carrier = base64.b64encode(raw)
    manifest.update(zip_sha256=sha(raw), carrier_sha256=sha(carrier),
                    members={n: metadata(d) for n, d in payload.items()})
    return raw, carrier


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("closure-seal", "closure-verify"):
        from b2m_closure import main as closure_main

        mode = {"closure-seal": "seal", "closure-verify": "verify"}[sys.argv[1]]
        return closure_main([mode, *sys.argv[2:]])
    raise ValueError("B2M_LEGACY_CLOSURE_INCOMPLETE_USE_CLOSURE_VERIFY")


def historical_main_not_executable():
    """Keep the old entry description for audit, never CLI-dispatched."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("seal", "verify", "selftest", "forward"))
    parser.add_argument("--package", type=Path, default=DOC / "B2M_20261011")
    parser.add_argument("--run", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--gate", type=Path)
    parser.add_argument("--selftest", type=Path)
    args = parser.parse_args()
    package = args.package.resolve()
    if package == DOC or not package.is_relative_to(DOC):
        raise ValueError("B2M_PACKAGE_SCOPE")
    if args.mode == "seal":
        run = args.run.resolve()
        if not run.is_relative_to(ROOT / "code/output") or run == ROOT / "code/output":
            raise ValueError("B2M_RUN_SCOPE")
        r = json.loads((run / "receipt.json").read_text(encoding="utf-8"))
        qualified(r)
        paths = set(run.iterdir())
        paths.update(ROOT / item["path"] for item in r["sources_before"] + r["protected_before"])
        paths.update((DOC / DOCUMENT, Path(__file__)))
        payload = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in sorted(paths) if p.is_file()}
        manifest = dict(qualified_receipt=(run / "receipt.json").relative_to(ROOT).as_posix(),
                        stage="T061_B2M_RECOVERY_PCM", committed_at_seal=False,
                        pushed_at_seal=False, task_complete=False)
        raw, carrier = encode(payload, manifest)
        checked(manifest, raw)
        package.mkdir(exist_ok=False)
        (package / "evidence.zip.b64").write_bytes(carrier)
        dump(package / "manifest.json", manifest)
        result = dict(status="B2M_SEAL_REPLAY_VERIFIED_PARTIAL", members=len(payload),
            zip_sha256=sha(raw), original_capture_replays=3,
            original_workflow_seconds=r["elapsed_seconds"], task_complete=False)
        dump(package / "seal_receipt.json", dict(result=result, exit_code=0,
             command=[sys.executable, *sys.argv], sealer_sha256=sha(Path(__file__).read_bytes())))
    elif args.mode == "verify":
        result = verify(package)
    elif args.mode == "selftest":
        normal = verify(package)
        out = args.output.resolve()
        if out == ROOT / "code/output" or not out.is_relative_to(ROOT / "code/output"):
            raise ValueError("B2M_SELFTEST_SCOPE")
        out.mkdir(parents=True, exist_ok=False)
        manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
        with zipfile.ZipFile(io.BytesIO(base64.b64decode((package / "evidence.zip.b64").read_bytes()))) as archive:
            original = {n: archive.read(n) for n in archive.namelist()}
        tests = []
        for label, reason in (("archive_hash", "B2M_ARCHIVE_SHA"),
                              ("missing_member", "B2M_MEMBERS"),
                              ("false_complete", "B2M_RECEIPT_SCOPE"),
                              ("boolean_exit", "B2M_RECEIPT_SCOPE"),
                              ("forged_pcm_report", "B2M_PROFILE_REPLAY")):
            payload, m = dict(original), copy.deepcopy(manifest)
            r = json.loads(payload[m["qualified_receipt"]])
            if label == "missing_member":
                del payload[m["qualified_receipt"]]
            elif label == "false_complete":
                r["task_complete"] = True
            elif label == "boolean_exit":
                r["exit_code"] = False
            elif label == "forged_pcm_report":
                r["profiles"][0]["published_outputs"][0]["pcm"] += 1
            payload[m["qualified_receipt"]] = json.dumps(r).encode()
            if label == "missing_member":
                del payload[m["qualified_receipt"]]
            raw, _ = encode(payload, m)
            if label == "archive_hash":
                m["zip_sha256"] = "0" * 64
            elif label == "missing_member":
                m["members"] = manifest["members"]
            try:
                checked(m, raw)
            except ValueError as error:
                if str(error) != reason:
                    raise ValueError("B2M_WRONG_TAMPER_DIAGNOSTIC:" + str(error)) from error
                tests.append(dict(case=label, diagnostic=str(error), rejected=True))
            else:
                raise ValueError("B2M_TAMPER_ACCEPTED:" + label)
        result = dict(normal=normal, specified_rejections=tests, exit_code=0)
        dump(out / "receipt.json", result)
    else:
        result = verify(package)
        gate = args.gate.resolve()
        g = json.loads((gate / "receipt.json").read_text(encoding="utf-8"))
        def git(*argv):
            return subprocess.check_output(["git", *argv], cwd=ROOT, timeout=30).decode().strip()
        head, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
        remote = git("ls-remote", "origin", "refs/heads/develop").split()[0]
        if (head != remote or git("branch", "--show-current") != "develop"
                or g["staged_tree"] != tree or type(g["exit_code"]) is not int or g["exit_code"] != 0
                or g["status"] != "EXACT_INDEX_SNAPSHOT_9_GATES_PASS"):
            raise ValueError("B2M_PUSH_OR_GATE_UNVERIFIED")
        test = json.loads(args.selftest.read_text(encoding="utf-8"))
        if test["exit_code"] != 0 or test["normal"] != result or len(test["specified_rejections"]) != 5:
            raise ValueError("B2M_SELFTEST_UNVERIFIED")
        out = args.output.resolve()
        if out == ROOT / "code/output" or not out.is_relative_to(ROOT / "code/output"):
            raise ValueError("B2M_FORWARD_SCOPE")
        out.mkdir(parents=True, exist_ok=False)
        delivery = dict(commit=head, tree=tree, remote_develop=remote, status="PUSH_VERIFIED",
                        task_complete=False, M2_notification="待用户转发，尚未送达")
        dump(out / "GIT_DELIVERY.json", delivery)
        target = out / "M3_T061_B2M_取消恢复PCM补核_交M2_20261011.zip"
        with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("evidence.zip", base64.b64decode((package / "evidence.zip.b64").read_bytes(), validate=True))
            for p in (package / "manifest.json", package / "seal_receipt.json", DOC / DOCUMENT, out / "GIT_DELIVERY.json"):
                archive.write(p, p.name)
            archive.write(args.selftest, "sealer_selftest.json")
            for p in gate.iterdir():
                if p.is_file():
                    archive.write(p, "final_gate/" + p.name)
        with zipfile.ZipFile(target) as archive:
            if archive.testzip():
                raise ValueError("B2M_FORWARD_CRC")
        result = dict(delivery, path=str(target), **metadata(target.read_bytes()))
        dump(out / "forward_receipt.json", result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
