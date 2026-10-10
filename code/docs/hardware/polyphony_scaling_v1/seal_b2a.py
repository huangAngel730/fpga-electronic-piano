"""Seal one qualified B2a backend stage with original logs and finite receipts.

No Git/device writes. New carrier and forward directories only; old evidence
never overwritten. Final source/gate/push identities are recorded separately.
"""
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
from b2_check import check  # noqa: E402


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(package):
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    carrier = (package / "evidence.zip.b64").read_bytes()
    if sha(carrier) != manifest["carrier_sha256"]:
        raise ValueError("CARRIER_SHA")
    raw = base64.b64decode(carrier, validate=True)
    if sha(raw) != manifest["zip_sha256"] or len(raw) != manifest["zip_bytes"]:
        raise ValueError("ZIP_SHA_OR_SIZE")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.testzip() or set(archive.namelist()) != {x["member"] for x in manifest["members"]}:
            raise ValueError("ZIP_CRC_OR_MEMBERS")
        for item in manifest["members"]:
            data = archive.read(item["member"])
            if sha(data) != item["sha256"] or len(data) != item["bytes"]:
                raise ValueError("MEMBER_SHA:" + item["member"])
        receipt = json.loads(archive.read(manifest["qualified_receipt"]))
        if (receipt["status"] != "B2A_REAL_MATH_BACKEND_PASS_T061_PARTIAL" or receipt["exit_code"] != 0
                or receipt["repo_gates_passed"] is not True or receipt["elapsed_seconds"] > 1800):
            raise ValueError("UNQUALIFIED_RECEIPT")
        for key in ("frozen_inputs", "candidate_sources", "old_seal_and_shared"):
            if receipt[key + "_before"] != receipt[key + "_after"]:
                raise ValueError("CHANGED_DURING_QUALIFIED_RUN")
        positives = []
        for step in receipt["steps"]:
            if step["exit_code"] != step["expected_exit"] or step["timed_out"] or step["elapsed_seconds"] > step["timeout_seconds"]:
                raise ValueError("UNQUALIFIED_STEP:" + step["label"])
            if step["label"].startswith("B2_N") and step["label"].endswith("_simulate"):
                positives.append(check(archive.read(step["stdout"]["path"])))
        if len(positives) != 6 or positives[0]["N"] != 4 or not positives[0]["long_case"]:
            raise ValueError("MISSING_N4_FIRST_OR_PROFILES")
    return {"status": "B2A_SEAL_VERIFIED_T061_PARTIAL", "members": len(manifest["members"]),
            "zip_bytes": len(raw), "zip_sha256": sha(raw), "positive_replays": len(positives),
            "task_complete": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--forward", type=Path)
    parser.add_argument("--prior-run", action="append", type=Path, default=[])
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
    if receipt["status"] != "B2A_REAL_MATH_BACKEND_PASS_T061_PARTIAL" or receipt["repo_gates_passed"] is not True:
        raise ValueError("UNQUALIFIED_RUN")
    for key in ("candidate_sources_after", "frozen_inputs_after", "old_seal_and_shared_after", "outputs"):
        for item in receipt[key]:
            data = (ROOT / item["path"]).read_bytes()
            if sha(data) != item["sha256"] or len(data) != item["bytes"]:
                raise ValueError("BOUND_INPUT_OR_OUTPUT_CHANGED:" + item["path"])
    paths = [ROOT / item["path"] for item in receipt["candidate_sources_after"]]
    # Include actual read-only compiled dependencies and all seven ROMs so M2
    # can inspect the exact arithmetic/ROM bytes without guessing a version.
    prefix = ROOT / "code/rtl/138K_try/hold_trials_20261005/L_locations_guard065"
    paths += [prefix / "sources" / name for name in ("adsr_piano_envelope.sv", "pitch_mod_fcw_pipeline.sv",
                                                     "piano_dds_oscillator.sv", "voice_gain_q15_candidate.sv")]
    paths += list((prefix / "rom").glob("*.mem")) + [prefix / "input_manifest.json"]
    paths += list(path for path in run.rglob("*") if path.is_file())
    paths += [DOCS / name for name in ("B2A_IMPLEMENTATION_20261010.md", "DELIVERY_B2A_20261010.md",
                                     "M2_HANDOFF_B2A_20261010.md", "seal_b2a.py", "publish_b2a.py")]
    paths += [ROOT / "code/software/polyphony_scaling_candidate/README.md"]
    prior_runs = []
    for folder in args.prior_run:
        folder = folder.resolve()
        folder.relative_to(ROOT / "code/output")
        old = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))
        paths += [p for p in folder.rglob("*") if p.is_file()]
        prior_runs.append({"path": folder.relative_to(ROOT).as_posix(), "status_as_recorded": old["status"],
                           "error_as_recorded": old.get("error"), "qualified_final_evidence": False})
    payload = io.BytesIO()
    members = []
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(paths)):
            raw = path.read_bytes()
            member = path.relative_to(ROOT).as_posix()
            archive.writestr(member, raw)
            members.append({"member": member, "bytes": len(raw), "sha256": sha(raw)})
    raw = payload.getvalue()
    carrier = base64.b64encode(raw)
    manifest = {"schema": 1, "stage": "B2A_REAL_MATH_BACKEND", "task_complete": False,
                "qualified_receipt": (run / "receipt.json").relative_to(ROOT).as_posix(),
                "zip_sha256": sha(raw), "zip_bytes": len(raw), "carrier_sha256": sha(carrier),
                "prior_runs_not_final_evidence": prior_runs, "members": members}
    package.mkdir(parents=True, exist_ok=False)
    (package / "evidence.zip.b64").write_bytes(carrier)
    (package / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = verify(package)
    (package / "seal_receipt.json").write_text(json.dumps({"command": [sys.executable, *sys.argv],
            "exit_code": 0, "sealer_sha256": sha(Path(__file__).read_bytes()), "result": result}, indent=2) + "\n", encoding="utf-8")
    if args.forward:
        forward = args.forward.resolve()
        forward.relative_to(ROOT / "code/output")
        forward.mkdir(parents=True, exist_ok=False)
        (forward / "B2a_evidence.zip").write_bytes(raw)
        for name in ("B2A_IMPLEMENTATION_20261010.md", "DELIVERY_B2A_20261010.md", "M2_HANDOFF_B2A_20261010.md"):
            (forward / name).write_bytes((DOCS / name).read_bytes())
        for name in ("manifest.json", "seal_receipt.json"):
            (forward / name).write_bytes((package / name).read_bytes())
    print(json.dumps(result))


if __name__ == "__main__":
    main()
