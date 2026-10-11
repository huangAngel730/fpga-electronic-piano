"""Seal fresh in-flight cancellation evidence and forward an exact gated push."""
import argparse
import base64
import copy
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[4]
DOC = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/"code/software/polyphony_scaling_candidate"))
from b2k_check import STATUS, check  # noqa: E402

DOCS = ("B2K_IMPLEMENTATION_20261011.md", "B2K_DELIVERY_20261011.md", "M2_HANDOFF_B2K_20261011.md")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def qualified(r):
    if (r["status"] != STATUS or type(r["exit_code"]) is not int or r["exit_code"] != 0
            or r["step_limit_seconds"] != 900 or r["workflow_limit_seconds"] != 1800
            or r["elapsed_seconds"] > 1800 or r["functional_revision"] != "52ad3dc"
            or r["new_functional_HDL"] is not False or r["new_TB"] is not True
            or r["new_RTL_simulation"] is not True or r["new_synthesis"] is not False
            or r["new_PnR"] is not False or r["device_operations"] is not False
            or r["task_complete"] is not False):
        raise ValueError("UNQUALIFIED_RECEIPT")
    for key in ("candidate_sources", "frozen_inputs", "old_seal_and_shared"):
        if r[key+"_before"] != r[key+"_after"]:
            raise ValueError("CHANGED_INPUTS")
    labels = [step["label"] for step in r["steps"]]
    for label in ("cancel_unit", "B2K_N4_R1_check", "B2K_N32_R1_check", "B2K_N32_R64_check"):
        if labels.count(label) != 1:
            raise ValueError("MISSING_REQUIRED_STEP")
    for step in r["steps"]:
        if (type(step["exit_code"]) is not int or step["exit_code"] != step["expected_exit"]
                or step["timed_out"] or step["elapsed_limit_exceeded"]
                or step["timeout_seconds"] > 900):
            raise ValueError("UNQUALIFIED_STEP")
    if len(r["negatives"]) != 8 or len(r["compiled_negatives"]) != 2:
        raise ValueError("NEGATIVE_COVERAGE")
    if [(p["N"], p["response"]) for p in r["profiles"]] != [(4, 1), (32, 1), (32, 64)]:
        raise ValueError("PROFILE_COVERAGE")


def checked(manifest, raw):
    if sha(raw) != manifest["zip_sha256"]:
        raise ValueError("ARCHIVE_SHA")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names) or set(names) != set(manifest["members"]) or archive.testzip():
            raise ValueError("MEMBERS_OR_CRC")
        payload = {}
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name:
                raise ValueError("UNSAFE_MEMBER_PATH")
            data, item = archive.read(name), manifest["members"][name]
            if sha(data) != item["sha256"] or len(data) != item["bytes"]:
                raise ValueError("MEMBER_SHA")
            payload[name] = data
    r = json.loads(payload[manifest["qualified_receipt"]])
    qualified(r)
    for item in r["outputs"]+r["candidate_sources_before"]+r["frozen_inputs_before"]:
        data = payload[item["path"]]
        if len(data) != item["bytes"] or sha(data) != item["sha256"]:
            raise ValueError("RECEIPT_BOUND_BYTES")
    for profile in r["profiles"]:
        label = f"B2K_N{profile['N']}_R{profile['response']}"
        step = next(s for s in r["steps"] if s["label"] == label+"_simulate")
        # Python's immutable plan tuples serialize to JSON arrays in the receipt.
        # Compare the JSON representation, without changing any captured bytes.
        if json.loads(json.dumps(check(payload[step["stdout"]["path"]]))) != profile:
            raise ValueError("PROFILE_REPLAY_MISMATCH")
    return r, payload


def verify(package):
    manifest = json.loads((package/"manifest.json").read_text(encoding="utf-8"))
    carrier = (package/"evidence.zip.b64").read_bytes()
    if sha(carrier) != manifest["carrier_sha256"]:
        raise ValueError("CARRIER_SHA")
    raw = base64.b64decode(carrier, validate=True)
    receipt, payload = checked(manifest, raw)
    return dict(status="B2K_SEAL_VERIFIED", members=len(payload), zip_sha256=sha(raw),
                workflow_elapsed_seconds=receipt["elapsed_seconds"], task_complete=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("seal", "verify", "forward"))
    parser.add_argument("--package", type=Path, default=DOC/"B2K_20261011")
    parser.add_argument("--run", type=Path)
    parser.add_argument("--prior-run", type=Path, action="append", default=[])
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
        for prior in args.prior_run:
            prior = prior.resolve()
            prior.relative_to(ROOT/"code/output")
            paths.update(p for p in prior.rglob("*") if p.is_file())
        paths.update(ROOT/item["path"] for item in receipt["candidate_sources_before"]+receipt["frozen_inputs_before"])
        paths.update(DOC/name for name in DOCS)
        paths.add(Path(__file__).resolve())
        payload = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in paths}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(payload.items()):
                archive.writestr(name, data)
        raw = buffer.getvalue()
        carrier = base64.b64encode(raw)
        manifest = dict(stage="T061_B2K_INFLIGHT_CANCEL", task_complete=False,
            qualified_receipt=(run/"receipt.json").relative_to(ROOT).as_posix(),
            zip_sha256=sha(raw), carrier_sha256=sha(carrier), zip_bytes=len(raw),
            historical_runs=[p.as_posix() for p in args.prior_run],
            historical_note="Prior raw logs/compiled images/receipts retained; prior source identities are historical, not claimed to match final sources",
            members={name: dict(bytes=len(data), sha256=sha(data)) for name, data in sorted(payload.items())})
        checked(manifest, raw)
        rejections = 0
        for key, value in (("exit_code", False), ("status", "PASS"), ("new_synthesis", True),
                           ("new_functional_HDL", True), ("task_complete", True), ("workflow_limit_seconds", 2700)):
            bad = copy.deepcopy(receipt)
            bad[key] = value
            try:
                qualified(bad)
            except ValueError:
                rejections += 1
            else:
                raise ValueError("RECEIPT_MUTATION_ACCEPTED")
        bad = copy.deepcopy(manifest)
        bad["members"][next(iter(payload))]["sha256"] = "0"*64
        try:
            checked(bad, raw)
        except ValueError:
            rejections += 1
        else:
            raise ValueError("MEMBER_MUTATION_ACCEPTED")
        package.mkdir(parents=True, exist_ok=False)
        dump(package/"manifest.json", manifest)
        (package/"evidence.zip.b64").write_bytes(carrier)
        dump(package/"seal_receipt.json", dict(command=[sys.executable, *sys.argv], exit_code=0,
             sealer_sha256=sha(Path(__file__).read_bytes()), normal_roundtrip=True,
             specific_tampering_rejections=rejections, result=verify(package)))
        print(json.dumps(verify(package)))
        return
    out, gate = args.output.resolve(), args.gate.resolve()
    out.relative_to(ROOT/"code/output")
    gate.relative_to(ROOT/"code/output")
    out.mkdir(parents=True, exist_ok=False)
    steps = []

    def git(label, argv):
        command = ["git", *argv]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=90, check=False)
        for stream, data in (("stdout", result.stdout), ("stderr", result.stderr)):
            (out/(label+"."+stream+".bin")).write_bytes(data)
        steps.append(dict(command=command, exit_code=result.returncode,
                          stdout_sha256=sha(result.stdout), stderr_sha256=sha(result.stderr)))
        if result.returncode:
            raise ValueError("GIT_COMMAND:"+label)
        return result.stdout.decode("utf-8").strip()

    head = git("head", ["rev-parse", "HEAD"])
    tree = git("tree", ["rev-parse", "HEAD^{tree}"])
    branch = git("branch", ["branch", "--show-current"])
    remote = git("remote", ["-c", "http.version=HTTP/1.1", "-c", "http.lowSpeedLimit=1", "-c", "http.lowSpeedTime=30",
                            "ls-remote", "origin", "refs/heads/develop"]).split()[0]
    gated = json.loads((gate/"receipt.json").read_text(encoding="utf-8"))
    if (gated["status"] != "EXACT_INDEX_SNAPSHOT_9_GATES_PASS" or gated["exit_code"] != 0
            or gated["staged_tree"] != tree or branch != "develop" or head != remote):
        raise ValueError("NOT_EXACT_GATED_PUSH")
    dump(out/"GIT_DELIVERY.json", dict(status="PUSH_VERIFIED", commit=head, tree=tree,
         remote_develop=remote, branch=branch, seal=verify(package), task_complete=False,
         gate_receipt_sha256=sha((gate/"receipt.json").read_bytes()), steps=steps,
         M2_notification="待用户转发，尚未送达"))
    for name in DOCS:
        shutil.copyfile(DOC/name, out/name)
    for name in ("manifest.json", "seal_receipt.json"):
        shutil.copyfile(package/name, out/name)
    (out/"B2K_evidence.zip").write_bytes(base64.b64decode((package/"evidence.zip.b64").read_bytes(), validate=True))
    (out/"M2_通知.txt").write_text(f"develop已推送并核验：{head}\n\n"+(DOC/DOCS[2]).read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    target = out/"M3_T061_在途取消与复位排空_B2K_交M2_20261011.zip"
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
