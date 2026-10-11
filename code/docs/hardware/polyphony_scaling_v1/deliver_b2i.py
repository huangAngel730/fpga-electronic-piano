"""Small software-ledger seal and exact-tree Git forwarding, no RTL/EDA."""
import argparse
import base64
import copy
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[4]
DOC = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "code/software/polyphony_scaling_candidate"))
from b2i_audit import STATUS, render, sha  # noqa: E402

DOCS = ("B2I_IMPLEMENTATION_20261011.md", "B2I_DELIVERY_20261011.md", "M2_HANDOFF_B2I_20261011.md")


def dump(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def qualified(receipt):
    if (receipt["status"] != STATUS or type(receipt["exit_code"]) is not int or receipt["exit_code"] != 0
            or receipt["step_limit_seconds"] != 900 or receipt["workflow_limit_seconds"] != 1800
            or receipt["candidate_sources_before"] != receipt["candidate_sources_after"]
            or receipt["frozen_inputs_before"] != receipt["frozen_inputs_after"]
            or receipt["old_seal_and_shared_before"] != receipt["old_seal_and_shared_after"]
            or receipt["new_candidate_HDL"] or receipt["new_RTL_simulation"]
            or receipt["elapsed_seconds"] > 1800):
        raise ValueError("UNQUALIFIED_SOFTWARE_RECEIPT")
    for step in receipt["steps"]:
        if (step["exit_code"] != 0 or step["expected_exit"] != 0 or step["timed_out"]
                or step["elapsed_limit_exceeded"] or step["timeout_seconds"] > 900):
            raise ValueError("UNQUALIFIED_SOFTWARE_STEP")
    for required in ("actual_hybrid_budget", "actual_hybrid_budget_tests", "python_unit", "budget"):
        if sum(s["label"] == required for s in receipt["steps"]) != 1:
            raise ValueError("REQUIRED_STEP_MISSING")


def checked(manifest, raw):
    if sha(raw) != manifest["zip_sha256"]:
        raise ValueError("ARCHIVE_SHA")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names) or set(names) != set(manifest["members"]) or archive.testzip():
            raise ValueError("ZIP_MEMBERS_OR_CRC")
        payload = {}
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name:
                raise ValueError("UNSAFE_MEMBER_PATH")
            data, item = archive.read(name), manifest["members"][name]
            if sha(data) != item["sha256"] or len(data) != item["bytes"]:
                raise ValueError("MEMBER_SHA")
            payload[name] = data
    receipt = json.loads(payload[manifest["qualified_receipt"]])
    qualified(receipt)
    for item in receipt["outputs"] + receipt["candidate_sources_before"] + receipt["frozen_inputs_before"]:
        data = payload[item["path"]]
        if len(data) != item["bytes"] or sha(data) != item["sha256"]:
            raise ValueError("RECEIPT_BOUND_BYTES")
    report = json.loads(payload[manifest["audit_json"]])
    if (report["status"] != STATUS or report["task_complete"] is not False
            or report["new_RTL_simulation"] is not False or report["new_synthesis"] is not False
            or report["new_PnR"] is not False or report["device_operations"] is not False):
        raise ValueError("AUDIT_SCOPE")
    if payload[manifest["audit_markdown"]].decode("utf-8") != render(report):
        raise ValueError("JSON_MARKDOWN_NOT_SAME_OBJECT")
    for row in report["configurations"]:
        if (sum(f["declared_bits"] for f in row["storage"]) != row["declared_sequential_payload_bits"]
                or sum(r["logical_runtime_bits"] for r in row["roms"]) != row["runtime_ROM_bits"]
                or any(v is not None for v in row["mapped_resources"].values())
                or row["physical_40MHz_STA"] is not None or row["production_admitted"] is not False):
            raise ValueError("RESOURCE_ACCOUNTING_OR_UPGRADE")
    return payload, receipt, report


def verify(package):
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    carrier = (package / "evidence.zip.b64").read_bytes()
    if sha(carrier) != manifest["carrier_sha256"]:
        raise ValueError("CARRIER_SHA")
    raw = base64.b64decode(carrier, validate=True)
    payload, receipt, report = checked(manifest, raw)
    return dict(status="B2I_SOFTWARE_SEAL_VERIFIED", members=len(payload),
                zip_sha256=sha(raw), source_run_elapsed_seconds=receipt["elapsed_seconds"],
                configurations=len(report["configurations"]), historical_reports=len(report["historical_reports"]),
                task_complete=False)


def self_test(manifest, raw):
    payload, receipt, _ = checked(manifest, raw)
    negatives = 0
    for field, value in (("exit_code", False), ("status", "PASS"), ("new_RTL_simulation", True),
                         ("step_limit_seconds", 1800), ("workflow_limit_seconds", 2700)):
        bad = copy.deepcopy(receipt)
        bad[field] = value
        try:
            qualified(bad)
        except ValueError:
            negatives += 1
        else:
            raise ValueError("RECEIPT_MUTANT_ACCEPTED")
    for field, value in (("zip_sha256", "0"*64), ("audit_markdown", manifest["audit_json"])):
        bad = copy.deepcopy(manifest)
        bad[field] = value
        try:
            checked(bad, raw)
        except ValueError:
            negatives += 1
        else:
            raise ValueError("SEAL_MUTANT_ACCEPTED")
    bad = copy.deepcopy(manifest)
    first = next(iter(payload))
    bad["members"][first]["sha256"] = "0"*64
    try:
        checked(bad, raw)
    except ValueError:
        negatives += 1
    else:
        raise ValueError("MEMBER_MUTANT_ACCEPTED")
    return dict(normal_roundtrip=True, specific_tampering_rejections=negatives)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("seal", "verify", "forward"))
    parser.add_argument("--package", type=Path, default=DOC / "B2I_20261011")
    parser.add_argument("--run", type=Path)
    parser.add_argument("--prior-run", action="append", default=[], type=Path)
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
        qualified(receipt)
        paths = {p for p in run.rglob("*") if p.is_file()}
        for prior in args.prior_run:
            prior = prior.resolve()
            prior.relative_to(ROOT / "code/output")
            paths.update(p for p in prior.rglob("*") if p.is_file())
        paths.update(ROOT / item["path"] for item in receipt["candidate_sources_before"]+receipt["frozen_inputs_before"])
        paths.update(DOC / name for name in DOCS)
        paths.add(Path(__file__).resolve())
        paths.add(ROOT / "code/rtl/138K_try/hold_trials_20261005/L_locations_guard065/input_manifest.json")
        report = json.loads((run / "actual_budget/audit.json").read_text(encoding="utf-8"))
        for prior in report["historical_provenance"]:
            paths.add(ROOT / prior["manifest"]["path"])
        paths.add(ROOT / report["capacities"]["B0_seal_provenance"]["manifest"]["path"])
        payload = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in paths}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(payload.items()):
                archive.writestr(name, data)
        raw = buffer.getvalue()
        carrier = base64.b64encode(raw)
        manifest = dict(stage="B2I_ACTUAL_HYBRID_SOURCE_BUDGET", task_complete=False,
            qualified_receipt=(run / "receipt.json").relative_to(ROOT).as_posix(),
            audit_json=(run / "actual_budget/audit.json").relative_to(ROOT).as_posix(),
            audit_markdown=(run / "actual_budget/audit.md").relative_to(ROOT).as_posix(),
            zip_sha256=sha(raw), zip_bytes=len(raw), carrier_sha256=sha(carrier),
            note="Prior full capture carriers remain in their original Git seals; selected original reports/receipts only, no new RTL proof",
            members={name: dict(bytes=len(data), sha256=sha(data)) for name, data in sorted(payload.items())})
        tests = self_test(manifest, raw)
        package.mkdir(parents=True, exist_ok=False)
        dump(package / "manifest.json", manifest)
        (package / "evidence.zip.b64").write_bytes(carrier)
        dump(package / "seal_receipt.json", dict(command=[sys.executable, *sys.argv], exit_code=0,
             self_test=tests, sealer_sha256=sha(Path(__file__).read_bytes()), result=verify(package)))
        print(json.dumps(verify(package)))
        return
    out, gate = args.output.resolve(), args.gate.resolve()
    out.relative_to(ROOT / "code/output")
    gate.relative_to(ROOT / "code/output")
    out.mkdir(parents=True, exist_ok=False)
    steps = []

    def git(label, argv):
        command = ["git", *argv]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=90, check=False)
        for stream, data in (("stdout", result.stdout), ("stderr", result.stderr)):
            (out / (label+"."+stream+".bin")).write_bytes(data)
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
    gated = json.loads((gate / "receipt.json").read_text(encoding="utf-8"))
    if (gated["status"] != "EXACT_INDEX_SNAPSHOT_9_GATES_PASS" or gated["exit_code"] != 0
            or gated["staged_tree"] != tree or branch != "develop" or head != remote):
        raise ValueError("NOT_EXACT_GATED_PUSH")
    dump(out / "GIT_DELIVERY.json", dict(status="PUSH_VERIFIED", commit=head, tree=tree,
         remote_develop=remote, branch=branch, seal=verify(package), task_complete=False,
         gate_receipt_sha256=sha((gate / "receipt.json").read_bytes()), steps=steps,
         M2_notification="待用户转发，尚未送达"))
    for name in DOCS:
        shutil.copyfile(DOC / name, out / name)
    for name in ("manifest.json", "seal_receipt.json"):
        shutil.copyfile(package / name, out / name)
    (out / "B2I_evidence.zip").write_bytes(base64.b64decode((package / "evidence.zip.b64").read_bytes(), validate=True))
    (out / "M2_通知.txt").write_text(f"develop已推送并核验：{head}\n\n"+(DOC / DOCS[2]).read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    target = out / "M3_T061_实际混合候选预算_B2I_交M2_20261011.zip"
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
    dump(out / "receipt.json", result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
