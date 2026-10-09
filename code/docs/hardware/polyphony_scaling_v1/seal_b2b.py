"""Seal/verify qualified B2b evidence, including original errors; no git/device."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[4]
DOCS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "code/software/polyphony_scaling_candidate"))
from b2b_check import check  # noqa: E402
from b2b_run import sources  # noqa: E402
from inventory import FROZEN  # noqa: E402

STATUS = "B2B_N4_EVENT_AUDIO_PASS_T061_PARTIAL"
DOC_NAMES = ("B2B_IMPLEMENTATION_20261010.md", "DELIVERY_B2B_20261010.md", "M2_HANDOFF_B2B_20261010.md")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(package):
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    carrier = (package / "evidence.zip.b64").read_bytes()
    if sha(carrier) != manifest["carrier_sha256"]:
        raise ValueError("CARRIER_SHA")
    raw = base64.b64decode(carrier, validate=True)
    if sha(raw) != manifest["zip_sha256"] or len(raw) != manifest["zip_bytes"]:
        raise ValueError("ZIP_SHA")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.testzip() or len(archive.namelist()) != len(set(archive.namelist())) or set(archive.namelist()) != {x["member"] for x in manifest["members"]}:
            raise ValueError("ZIP_CRC_OR_MEMBERS")
        for item in manifest["members"]:
            data = archive.read(item["member"])
            if sha(data) != item["sha256"] or len(data) != item["bytes"]:
                raise ValueError("MEMBER_SHA:" + item["member"])
        receipt = json.loads(archive.read(manifest["qualified_receipt"]))
        if receipt["status"] != STATUS or receipt["exit_code"] != 0 or receipt["repo_gates_passed"] is not True or receipt["elapsed_seconds"] > 1800:
            raise ValueError("UNQUALIFIED_RECEIPT")
        for key in ("frozen_inputs", "candidate_sources", "old_seal_and_shared"):
            if receipt[key + "_before"] != receipt[key + "_after"]:
                raise ValueError("QUALIFIED_INPUT_CHANGED")
        reports = []
        for step in receipt["steps"]:
            if step["exit_code"] != step["expected_exit"] or step["timed_out"] or step["elapsed_seconds"] > step["timeout_seconds"]:
                raise ValueError("UNQUALIFIED_STEP")
            if step["label"].startswith("B2B_N4_") and step["label"].endswith("_simulate"):
                reports.append(check(archive.read(step["stdout"]["path"])))
        if len(reports) != 2 or not reports[0]["long_case"] or reports[1]["response"] != 3:
            raise ValueError("MISSING_N4_PROFILES")
    return {"status": "B2B_SEAL_VERIFIED_T061_PARTIAL", "members": len(manifest["members"]),
            "zip_bytes": len(raw), "zip_sha256": sha(raw), "independent_replays": len(reports), "task_complete": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--forward", type=Path)
    parser.add_argument("--prior-run", action="append", default=[], type=Path)
    parser.add_argument("--pre-repair-seal", type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    package = args.package.resolve()
    if args.verify:
        print(json.dumps(verify(package)))
        return
    package.relative_to(DOCS)
    run = args.run.resolve()
    run.relative_to(ROOT / "code/output")
    receipt = json.loads((run / "receipt.json").read_text(encoding="utf-8"))
    if receipt["status"] != STATUS or receipt["repo_gates_passed"] is not True:
        raise ValueError("UNQUALIFIED_RUN")
    for key in ("candidate_sources_after", "frozen_inputs_after", "old_seal_and_shared_after", "outputs"):
        for item in receipt[key]:
            raw = (ROOT / item["path"]).read_bytes()
            if sha(raw) != item["sha256"] or len(raw) != item["bytes"]:
                raise ValueError("BOUND_FILE_CHANGED:" + item["path"])
    paths = [ROOT / x["path"] for x in receipt["candidate_sources_after"]]
    paths += sources() + [FROZEN / "include/sustain_controller_ports.svh", FROZEN / "input_manifest.json"]
    paths += list((FROZEN / "rom").glob("*.mem"))
    paths += [p for p in run.rglob("*") if p.is_file()]
    paths += [DOCS / n for n in (*DOC_NAMES, "seal_b2b.py", "publish_b2b.py", "publish_b2a.py")]
    paths += [ROOT / "code/software/polyphony_scaling_candidate/README.md"]
    prior = []
    for folder in args.prior_run:
        folder = folder.resolve()
        folder.relative_to(ROOT / "code/output")
        paths += [p for p in folder.rglob("*") if p.is_file()]
        prior.append({"path": folder.relative_to(ROOT).as_posix(), "qualified_final_evidence": False,
                      "scope": "development diagnostics only; no retrospective PASS or source reconstruction claim"})
    payload = io.BytesIO()
    members = []
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(paths)):
            raw = path.read_bytes()
            member = path.relative_to(ROOT).as_posix()
            archive.writestr(member, raw)
            members.append({"member": member, "bytes": len(raw), "sha256": sha(raw)})
        if args.pre_repair_seal:
            old = args.pre_repair_seal.resolve()
            old.relative_to(ROOT / "code/output")
            old_manifest_raw = (old / "manifest.json").read_bytes()
            old_manifest = json.loads(old_manifest_raw)
            encoded = (old / "evidence.zip.b64").read_bytes()
            if sha(encoded) != old_manifest["carrier_sha256"]:
                raise ValueError("PRE_REPAIR_CARRIER_SHA")
            old_raw = base64.b64decode(encoded, validate=True)
            if sha(old_raw) != old_manifest["zip_sha256"]:
                raise ValueError("PRE_REPAIR_ZIP_SHA")
            selected = {"code/rtl/common/polyphony_scaling_candidate/b2b_event_audio.sv",
                        "code/tb/common/polyphony_scaling_candidate/tb_b2b_event_audio.sv",
                        "code/software/polyphony_scaling_candidate/b2b_check.py",
                        "code/scripts/run_m3_polyphony_scaling_acceptance.py"}
            old_id = {x["member"]: x for x in old_manifest["members"]}
            with zipfile.ZipFile(io.BytesIO(old_raw)) as old_archive:
                for member in sorted(selected):
                    data = old_archive.read(member)
                    if sha(data) != old_id[member]["sha256"]:
                        raise ValueError("PRE_REPAIR_MEMBER_SHA")
                    target = "pre_repair_sources/" + member
                    archive.writestr(target, data)
                    members.append({"member": target, "bytes": len(data), "sha256": sha(data)})
            target = "pre_repair_sources/original_seal_manifest.json"
            archive.writestr(target, old_manifest_raw)
            members.append({"member": target, "bytes": len(old_manifest_raw), "sha256": sha(old_manifest_raw)})
    raw = payload.getvalue()
    carrier = base64.b64encode(raw)
    manifest = {"stage": "B2B_N4_EVENT_AUDIO", "task_complete": False,
                "qualified_receipt": (run / "receipt.json").relative_to(ROOT).as_posix(),
                "zip_bytes": len(raw), "zip_sha256": sha(raw), "carrier_sha256": sha(carrier),
                "prior_runs_not_final_evidence": prior, "members": members}
    package.mkdir(parents=True, exist_ok=False)
    (package / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (package / "evidence.zip.b64").write_bytes(carrier)
    result = verify(package)
    (package / "seal_receipt.json").write_text(json.dumps({"command": [sys.executable, *sys.argv], "exit_code": 0,
        "sealer_sha256": sha(Path(__file__).read_bytes()), "result": result}, indent=2) + "\n", encoding="utf-8")
    if args.forward:
        forward = args.forward.resolve()
        forward.relative_to(ROOT / "code/output")
        forward.mkdir(parents=True, exist_ok=False)
        (forward / "B2b_evidence.zip").write_bytes(raw)
        for name in (*DOC_NAMES, "manifest.json", "seal_receipt.json"):
            source = DOCS if name in DOC_NAMES else package
            (forward / name).write_bytes((source / name).read_bytes())
    print(json.dumps(result))


if __name__ == "__main__":
    main()
