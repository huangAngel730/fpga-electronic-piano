"""Seal real saturation evidence and exact gated publication; no builds/devices."""
import argparse
import base64
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from deliver_b2e import bound, dump, sha

ROOT = Path(__file__).resolve().parents[4]
DOC = Path(__file__).resolve().parent
STATUS = "B2G_N32_REAL_SATURATION_PASS_T061_PARTIAL"
DOCS = ("B2G_IMPLEMENTATION_20261011.md", "B2G_DELIVERY_20261011.md",
        "M2_HANDOFF_B2G_20261011.md", "deliver_b2g.py")


def qualified(receipt):
    if (receipt["status"] != STATUS or receipt["exit_code"] != 0
            or receipt["candidate_sources_before"] != receipt["candidate_sources_after"]
            or receipt["frozen_inputs_before"] != receipt["frozen_inputs_after"]
            or receipt["old_seal_and_shared_before"] != receipt["old_seal_and_shared_after"]
            or receipt["actual_RTL_capture_reuse"] or receipt["elapsed_seconds"] > 1800):
        raise ValueError("UNQUALIFIED_RUN_OR_IDENTITY")
    for step in receipt["steps"]:
        if (step["exit_code"] != step["expected_exit"] or step["timed_out"]
                or step.get("elapsed_limit_exceeded")):
            raise ValueError("UNQUALIFIED_STEP:"+step["label"])


def verify(package):
    manifest = json.loads((package/"manifest.json").read_text(encoding="utf-8"))
    carrier = (package/"evidence.zip.b64").read_bytes()
    raw = base64.b64decode(carrier, validate=True)
    if sha(raw) != manifest["zip_sha256"] or sha(carrier) != manifest["carrier_sha256"]:
        raise ValueError("ARCHIVE_SHA")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if (archive.testzip() or len(set(names)) != len(names)
                or set(names) != set(manifest["members"])):
            raise ValueError("ZIP_CRC_DUPLICATE_OR_MEMBERS")
        for name, item in manifest["members"].items():
            data = archive.read(name)
            if len(data) != item["bytes"] or sha(data) != item["sha256"]:
                raise ValueError("MEMBER_SHA:"+name)
        receipt = json.loads(archive.read(manifest["qualified_receipt"]))
        qualified(receipt)
        for item in bound(receipt):
            data = archive.read(item["path"])
            if len(data) != item["bytes"] or sha(data) != item["sha256"]:
                raise ValueError("RECEIPT_BOUND_BYTES:"+item["path"])
        run = Path(manifest["qualified_receipt"]).parent.as_posix()
        labels = {step["label"]: step for step in receipt["steps"]}
        for response in (1, 8):
            report = json.loads(archive.read(f"{run}/B2G_N32_R{response}.json"))
            if (report["status"] != STATUS or report["N"] != 32 or report["long_case"]
                    or report["wave_response_cycles"] != response
                    or not report["sample_deadline_qualified"]
                    or report["nonzero_slots"] != list(range(32))
                    or not all(report["verified_output_classes"].values())):
                raise ValueError("PROFILE_OR_COVERAGE")
            for suffix in ("compile", "simulate", "replay"):
                if labels[f"B2G_N32_R{response}_{suffix}"]["exit_code"]:
                    raise ValueError("MISSING_REAL_POSITIVE")
        tests = json.loads(archive.read(run+"/checker_tests/report.json"))
        if (tests["exit_code"] or tests["unit_tests"] != 4 or len(tests["complete_negatives"]) != 12
                or any(item["expected"] != item["actual"] for item in tests["complete_negatives"])):
            raise ValueError("CHECKER_TESTS")
        for name in ("POSITIVE_LIMIT_MINUS_ONE", "NEGATIVE_LIMIT_PLUS_ONE"):
            for suffix, expected in (("compile", 0), ("simulate", 0), ("replay", 1)):
                if labels[name+"_"+suffix]["exit_code"] != expected:
                    raise ValueError("BEHAVIOR_MUTANT_EXIT")
            rejected = json.loads(archive.read(run+"/mutant_"+name+"/rejection.json"))
            if rejected != dict(status="REJECT", reason="MATH_STEREO_SATURATION"):
                raise ValueError("BEHAVIOR_MUTANT_REASON")
        for path in manifest["failed_receipts"]:
            failure = json.loads(archive.read(path))
            if failure["status"] != "FAIL" or failure["exit_code"] == 0:
                raise ValueError("HISTORICAL_FAILURE_NOT_PRESERVED")
    return dict(status="B2G_REAL_SATURATION_SEAL_VERIFIED_T061_PARTIAL", members=len(names),
                zip_sha256=sha(raw), zip_bytes=len(raw), task_complete=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("seal", "verify", "forward"))
    parser.add_argument("--run", type=Path)
    parser.add_argument("--failure", type=Path, action="append", default=[])
    parser.add_argument("--package", type=Path, default=DOC/"B2G_20261011")
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
        run.relative_to(ROOT/"code/output")
        receipt = json.loads((run/"receipt.json").read_text(encoding="utf-8"))
        qualified(receipt)
        paths = {p for p in run.rglob("*") if p.is_file()}
        paths.update(ROOT/item["path"] for item in bound(receipt))
        paths.update(DOC/name for name in DOCS)
        paths.add(DOC/"deliver_b2e.py")
        paths.add(ROOT/"code/software/polyphony_scaling_candidate/inventory.py")
        paths.add(ROOT/"code/rtl/138K_try/hold_trials_20261005/L_locations_guard065/input_manifest.json")
        failures = []
        for directory in args.failure:
            directory = directory.resolve()
            directory.relative_to(ROOT/"code/output")
            failures.append((directory/"receipt.json").relative_to(ROOT).as_posix())
            paths.update(p for p in directory.rglob("*") if p.is_file())
        payload = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in paths}
        for item in bound(receipt):
            if sha(payload[item["path"]]) != item["sha256"]:
                raise ValueError("SOURCE_CHANGED:"+item["path"])
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(payload.items()):
                archive.writestr(name, data)
        raw = stream.getvalue()
        carrier = base64.b64encode(raw)
        package.mkdir(parents=True, exist_ok=False)
        dump(package/"manifest.json", dict(stage="B2G_N32_REAL_SATURATION", task_complete=False,
             qualified_receipt=(run/"receipt.json").relative_to(ROOT).as_posix(), failed_receipts=failures,
             zip_sha256=sha(raw), zip_bytes=len(raw), carrier_sha256=sha(carrier),
             members={n: dict(bytes=len(d), sha256=sha(d)) for n, d in sorted(payload.items())}))
        (package/"evidence.zip.b64").write_bytes(carrier)
        result = verify(package)
        dump(package/"seal_receipt.json", dict(command=[sys.executable, *sys.argv], exit_code=0,
             sealer_sha256=sha(Path(__file__).read_bytes()), result=result))
        print(json.dumps(result))
        return
    gate = args.gate.resolve()
    gate.relative_to(ROOT/"code/output")
    gated = json.loads((gate/"receipt.json").read_text(encoding="utf-8"))
    out = args.output.resolve()
    out.relative_to(ROOT/"code/output")
    out.mkdir(parents=True, exist_ok=False)
    steps = []

    def git(label, argv):
        result = subprocess.run(["git", *argv], cwd=ROOT, capture_output=True, timeout=90)
        for suffix, data in (("stdout", result.stdout), ("stderr", result.stderr)):
            (out/(label+"."+suffix+".bin")).write_bytes(data)
        steps.append(dict(command=["git", *argv], exit_code=result.returncode,
                          stdout_sha256=sha(result.stdout), stderr_sha256=sha(result.stderr)))
        if result.returncode:
            raise ValueError("GIT_COMMAND:"+label)
        return result.stdout.decode("utf-8").strip()

    head = git("head", ["rev-parse", "HEAD"])
    tree = git("tree", ["rev-parse", "HEAD^{tree}"])
    branch = git("branch", ["branch", "--show-current"])
    remote = git("remote", ["-c", "http.version=HTTP/1.1", "-c", "http.lowSpeedLimit=1",
                            "-c", "http.lowSpeedTime=30", "ls-remote", "origin", "refs/heads/develop"]).split()[0]
    if (gated["status"] != "EXACT_INDEX_SNAPSHOT_9_GATES_PASS" or gated["exit_code"]
            or gated["staged_tree"] != tree or branch != "develop" or head != remote):
        raise ValueError("NOT_EXACT_GATED_PUSH")
    dump(out/"GIT_DELIVERY.json", dict(status="PUSH_VERIFIED", commit=head, tree=tree,
         remote_develop=remote, branch=branch, seal=verify(package), task_complete=False,
         gate_receipt_sha256=sha((gate/"receipt.json").read_bytes()), steps=steps,
         M2_notification="待用户转发，尚未送达"))
    for name in DOCS[:3]:
        shutil.copyfile(DOC/name, out/name)
    for name in ("manifest.json", "seal_receipt.json"):
        shutil.copyfile(package/name, out/name)
    (out/"B2G_evidence.zip").write_bytes(base64.b64decode((package/"evidence.zip.b64").read_bytes(), validate=True))
    (out/"M2_通知.txt").write_text(f"develop 已推送并核验：{head}\n\n"+
        (DOC/DOCS[2]).read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    target = out/"M3_T061_N32真实正负饱和补覆盖_交M2_20261011.zip"
    with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(out.iterdir()):
            if path.is_file() and path != target:
                archive.write(path, path.name)
        for path in sorted(gate.iterdir()):
            if path.is_file():
                archive.write(path, "publish_gate/"+path.name)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip():
            raise ValueError("FORWARD_CRC")
    result = dict(status="PUSH_VERIFIED_FORWARD_READY", commit=head, archive=str(target),
                  archive_bytes=target.stat().st_size, archive_sha256=sha(target.read_bytes()),
                  task_complete=False)
    dump(out/"receipt.json", result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
