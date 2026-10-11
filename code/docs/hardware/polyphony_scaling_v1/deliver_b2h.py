"""Seal N32 long evidence, losslessly deduplicate full negative captures.

No RTL execution, Git writes, EDA or device operations. Restore verifies every
physical and reconstructed member before writing into a new output directory.
"""
import argparse
import base64
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import zipfile

from deliver_b2e import bound, dump, sha

ROOT = Path(__file__).resolve().parents[4]
DOC = Path(__file__).resolve().parent
STATUS = "B2H_N32_LONG_LIFECYCLE_PASS_T061_PARTIAL"
DOCS = ("B2H_IMPLEMENTATION_20261011.md", "B2H_DELIVERY_20261011.md",
        "M2_HANDOFF_B2H_20261011.md", "deliver_b2h.py")


def qualified(receipt):
    if (receipt["status"] != STATUS or receipt["exit_code"] != 0
            or receipt["candidate_sources_before"] != receipt["candidate_sources_after"]
            or receipt["frozen_inputs_before"] != receipt["frozen_inputs_after"]
            or receipt["old_seal_and_shared_before"] != receipt["old_seal_and_shared_after"]
            or receipt["actual_RTL_capture_reuse"] or receipt["preflight_only"]
            or receipt["step_limit_seconds"] != 1800
            or receipt["workflow_limit_seconds"] != 2700
            or receipt["elapsed_seconds"] > 2700):
        raise ValueError("UNQUALIFIED_RUN_OR_IDENTITY")
    for step in receipt["steps"]:
        if (step["exit_code"] != step["expected_exit"] or step["timed_out"]
                or step.get("elapsed_limit_exceeded") or step["timeout_seconds"] > 1800):
            raise ValueError("UNQUALIFIED_STEP:"+step["label"])


def delta(base, changed, normalize_newlines=False):
    """One byte splice: preserve even newline/ordering changes exactly."""
    physical_sha = sha(base)
    if normalize_newlines:
        base = base.replace(b"\r\n", b"\n")
    block = 1024*1024
    limit = min(len(base), len(changed))
    prefix = 0
    while prefix < limit:
        size = min(block, limit-prefix)
        left, right = base[prefix:prefix+size], changed[prefix:prefix+size]
        if left != right:
            prefix += next(i for i, (a, b) in enumerate(zip(left, right)) if a != b)
            break
        prefix += size
    suffix = 0
    while suffix < limit-prefix:
        size = min(block, limit-prefix-suffix)
        left = base[len(base)-suffix-size:len(base)-suffix]
        right = changed[len(changed)-suffix-size:len(changed)-suffix]
        if left != right:
            suffix += next(i for i, (a, b) in enumerate(zip(reversed(left), reversed(right))) if a != b)
            break
        suffix += size
    return dict(prefix_bytes=prefix, remove_bytes=len(base)-prefix-suffix,
                replacement_b64=base64.b64encode(changed[prefix:len(changed)-suffix]).decode("ascii"),
                base_normalization="CRLF_TO_LF" if normalize_newlines else "NONE",
                physical_base_sha256=physical_sha, base_sha256=sha(base),
                bytes=len(changed), sha256=sha(changed))


def reconstruct(base, item):
    if sha(base) != item["physical_base_sha256"]:
        raise ValueError("DELTA_PHYSICAL_BASE_SHA")
    if item["base_normalization"] == "CRLF_TO_LF":
        base = base.replace(b"\r\n", b"\n")
    elif item["base_normalization"] != "NONE":
        raise ValueError("DELTA_NORMALIZATION")
    p, count = item["prefix_bytes"], item["remove_bytes"]
    if (type(p) is not int or type(count) is not int or p < 0 or count < 0
            or p+count > len(base) or sha(base) != item["base_sha256"]):
        raise ValueError("DELTA_BASE_OR_RANGE")
    raw = base[:p]+base64.b64decode(item["replacement_b64"], validate=True)+base[p+count:]
    if len(raw) != item["bytes"] or sha(raw) != item["sha256"]:
        raise ValueError("DELTA_RESULT_SHA")
    return raw


def self_test():
    cases = ((b"", b""), (b"abc", b"abc"), (b"abc", b"axc"),
             (b"abc", b"abXYc"), (b"abc", b"ac"), (b"a\nb\nc\n", b"b\na\nc\n"),
             (b"x"*(1024*1024+2), b"x"*(1024*1024)+b"yz"))
    for base, changed in cases:
        if reconstruct(base, delta(base, changed)) != changed:
            raise ValueError("DELTA_ROUNDTRIP")
    if reconstruct(b"a\r\nb\r\n", delta(b"a\r\nb\r\n", b"a\nx\n", True)) != b"a\nx\n":
        raise ValueError("DELTA_CRLF_ROUNDTRIP")
    bad = delta(b"abc", b"axc")
    for field, value in (("prefix_bytes", -1), ("base_sha256", "0"*64), ("sha256", "0"*64),
                         ("physical_base_sha256", "0"*64), ("base_normalization", "UNKNOWN")):
        try:
            reconstruct(b"abc", dict(bad, **{field: value}))
        except ValueError:
            pass
        else:
            raise ValueError("DELTA_TAMPERING_ACCEPTED")
    return dict(roundtrip_cases=len(cases)+1, tampering_rejections=5)


def verified_archive(package):
    manifest = json.loads((package/"manifest.json").read_text(encoding="utf-8"))
    carrier = (package/"evidence.zip.b64").read_bytes()
    raw = base64.b64decode(carrier, validate=True)
    if sha(raw) != manifest["zip_sha256"] or sha(carrier) != manifest["carrier_sha256"]:
        raise ValueError("ARCHIVE_SHA")
    archive = zipfile.ZipFile(io.BytesIO(raw))
    names = archive.namelist()
    derived = manifest["lossless_derived_members"]
    if (archive.testzip() or len(set(names)) != len(names)
            or set(names) != set(manifest["members"]) or set(names) & set(derived)):
        raise ValueError("ZIP_CRC_DUPLICATE_OR_MEMBERS")
    cache = {}

    def read(name):
        if name not in derived:
            return archive.read(name)
        item = derived[name]
        base = item["base_member"]
        if base not in manifest["members"]:
            raise ValueError("DELTA_REQUIRES_PHYSICAL_BASE")
        if base not in cache:
            cache[base] = archive.read(base)
        return reconstruct(cache[base], item)

    for name, item in manifest["members"].items():
        data = read(name)
        if len(data) != item["bytes"] or sha(data) != item["sha256"]:
            raise ValueError("MEMBER_SHA:"+name)
    receipt = json.loads(read(manifest["qualified_receipt"]))
    qualified(receipt)
    for item in bound(receipt):
        data = read(item["path"])
        if len(data) != item["bytes"] or sha(data) != item["sha256"]:
            raise ValueError("RECEIPT_BOUND_BYTES:"+item["path"])
    run = Path(manifest["qualified_receipt"]).parent.as_posix()
    report = json.loads(read(run+"/B2H_N32_R1_long1.json"))
    if (report["status"] != STATUS or not report["long_case"] or report["N"] != 32
            or report["response"] != 1 or not report["sample_deadline_qualified"]
            or report["deadline_misses"]
            or not all(report["coverage"].get("nonzero_slot_"+str(i), 0) for i in range(32))
            or not all(report["real_retirements_by_slot"])
            or report["public_ADSR_states_by_slot"][31] != list(range(5))
            or report["exact_833_request_intervals"] < 10000
            or not report["same_identity_3_11_27_active_frames"]
            or not report["same_identity_11_retired_3_27_active_frames"]):
        raise ValueError("N32_LONG_COVERAGE")
    tests = json.loads(read(run+"/checker_tests/report.json"))
    negatives = tests["complete_long_negatives"]
    expected_paths = {run+"/checker_tests/"+item["name"]+".txt" for item in negatives}
    if (tests["exit_code"] or tests["unit_tests"] != 4 or len(negatives) != 10
            or set(derived) != expected_paths
            or any(item["expected"] != item["actual"] for item in negatives)):
        raise ValueError("COMPLETE_CAPTURE_COUNTEREXAMPLES")
    for item in negatives:
        if sha(read(run+"/checker_tests/"+item["name"]+".txt")) != item["sha256"]:
            raise ValueError("COUNTEREXAMPLE_SHA")
    labels = {step["label"]: step for step in receipt["steps"]}
    for suffix in ("compile", "simulate", "replay"):
        if labels["B2H_N32_R1_long1_"+suffix]["exit_code"]:
            raise ValueError("MISSING_REAL_LONG_STEP")
    for name, exits in (("B1_MUTANT_IGNORE_GENERATION", (("compile", 0), ("simulate", 1))),
                        ("B2_MUTANT_GAIN_ZERO", (("compile", 0), ("simulate", 0), ("replay", 1)))):
        for suffix, code in exits:
            if labels[name+"_"+suffix]["exit_code"] != code:
                raise ValueError("BEHAVIOR_MUTANT_EXIT")
    for path in manifest["preflight_receipts"]:
        preflight = json.loads(read(path))
        if not preflight["preflight_only"] or preflight["status"] not in (
                "FAIL", "B2H_PREFLIGHT_COMPILE_ONLY_NOT_LONG_PASS"):
            raise ValueError("PREFLIGHT_NOT_LONG_ACCEPTANCE")
    result = dict(status="B2H_N32_LONG_SEAL_VERIFIED_T061_PARTIAL", physical_members=len(names),
                  exact_reconstructed_members=len(derived), zip_bytes=len(raw),
                  zip_sha256=sha(raw), task_complete=False)
    return archive, manifest, read, result


def verify(package):
    archive, _, _, result = verified_archive(package)
    archive.close()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("seal", "verify", "restore", "forward", "self-test"))
    parser.add_argument("--run", type=Path)
    parser.add_argument("--preflight", type=Path, action="append", default=[])
    parser.add_argument("--package", type=Path, default=DOC/"B2H_20261011")
    parser.add_argument("--gate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    package = args.package.resolve()
    package.relative_to(DOC)
    if args.mode == "self-test":
        print(json.dumps(self_test()))
        return
    if args.mode == "verify":
        print(json.dumps(verify(package)))
        return
    if args.mode == "restore":
        archive, manifest, read, result = verified_archive(package)
        out = args.output.resolve()
        out.relative_to(ROOT/"code/output")
        out.mkdir(parents=True, exist_ok=False)
        for name in sorted(set(manifest["members"]) | set(manifest["lossless_derived_members"])):
            relative = PurePosixPath(name)
            if relative.is_absolute() or ".." in relative.parts or ":" in name or "\\" in name:
                raise ValueError("UNSAFE_ARCHIVE_PATH")
            target = out/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(read(name))
        archive.close()
        dump(out/"restore_receipt.json", result)
        print(json.dumps(result))
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
        preflights = []
        for directory in args.preflight:
            directory = directory.resolve()
            directory.relative_to(ROOT/"code/output")
            preflights.append((directory/"receipt.json").relative_to(ROOT).as_posix())
            paths.update(p for p in directory.rglob("*") if p.is_file())
        labels = {step["label"]: step for step in receipt["steps"]}
        base_name = labels["B2H_N32_R1_long1_simulate"]["stdout"]["path"]
        base = (ROOT/base_name).read_bytes()
        tests = json.loads((run/"checker_tests/report.json").read_text(encoding="utf-8"))
        derived = {}
        for item in tests["complete_long_negatives"]:
            path = run/"checker_tests"/(item["name"]+".txt")
            changed = path.read_bytes()
            if sha(changed) != item["sha256"]:
                raise ValueError("COUNTEREXAMPLE_CHANGED")
            patch = dict(delta(base, changed, normalize_newlines=True), base_member=base_name)
            if reconstruct(base, patch) != changed:
                raise ValueError("NONLOSSLESS_CAPTURE_PATCH")
            derived[path.relative_to(ROOT).as_posix()] = patch
            paths.remove(path)
        payload = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in paths}
        for item in bound(receipt):
            data = reconstruct(base, derived[item["path"]]) if item["path"] in derived else payload[item["path"]]
            if len(data) != item["bytes"] or sha(data) != item["sha256"]:
                raise ValueError("SOURCE_OR_OUTPUT_CHANGED:"+item["path"])
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(payload.items()):
                archive.writestr(name, data)
        raw = stream.getvalue()
        carrier = base64.b64encode(raw)
        package.mkdir(parents=True, exist_ok=False)
        dump(package/"manifest.json", dict(stage="B2H_N32_LONG_LIFECYCLE", task_complete=False,
             authorization="User allowed this B2h run: step1800/workflow2700 seconds; no EDA/devices",
             qualified_receipt=(run/"receipt.json").relative_to(ROOT).as_posix(), preflight_receipts=preflights,
             zip_sha256=sha(raw), zip_bytes=len(raw), carrier_sha256=sha(carrier),
             lossless_derived_members=derived,
             members={n: dict(bytes=len(d), sha256=sha(d)) for n, d in sorted(payload.items())}))
        (package/"evidence.zip.b64").write_bytes(carrier)
        result = verify(package)
        dump(package/"seal_receipt.json", dict(command=[sys.executable, *sys.argv], exit_code=0,
             self_test=self_test(), sealer_sha256=sha(Path(__file__).read_bytes()), result=result))
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
    (out/"B2H_evidence.zip").write_bytes(base64.b64decode((package/"evidence.zip.b64").read_bytes(), validate=True))
    (out/"M2_通知.txt").write_text(f"develop 已推送并核验：{head}\n\n"+
        (DOC/DOCS[2]).read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    target = out/"M3_T061_N32完整长程生命周期_交M2_20261011.zip"
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
                  archive_bytes=target.stat().st_size, archive_sha256=sha(target.read_bytes()), task_complete=False)
    dump(out/"receipt.json", result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
