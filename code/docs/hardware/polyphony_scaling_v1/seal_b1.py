"""Seal qualified B1 raw evidence; no old file overwrite, Git write or device action."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[4]
DOCS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "code/software/polyphony_scaling_candidate"))
from b1_check import replay  # noqa: E402


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(package):
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    carrier = (package / "evidence.zip.b64").read_bytes()
    if sha(carrier) != manifest["carrier_sha256"]:
        raise ValueError("CARRIER_SHA")
    raw = base64.b64decode(carrier, validate=True)
    if sha(raw) != manifest["zip_sha256"] or len(raw) != manifest["zip_bytes"]:
        raise ValueError("ZIP_IDENTITY")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.testzip() or set(archive.namelist()) != {item["member"] for item in manifest["members"]}:
            raise ValueError("ZIP_MEMBERS")
        for item in manifest["members"]:
            data = archive.read(item["member"])
            if len(data) != item["bytes"] or sha(data) != item["sha256"]:
                raise ValueError("MEMBER_SHA:" + item["member"])
        receipt = json.loads(archive.read(manifest["qualified_receipt"]))
        if (receipt["status"] != "B1_PROTOCOL_RTL_PASS_T061_PARTIAL" or receipt["exit_code"] != 0
                or receipt["repo_gates_passed"] is not True or receipt["elapsed_seconds"] > 1800):
            raise ValueError("UNQUALIFIED_RECEIPT")
        positives = 0
        for step in receipt["steps"]:
            if (step["exit_code"] != step["expected_exit"] or step["timed_out"]
                    or step["elapsed_seconds"] > step["timeout_seconds"]):
                raise ValueError("UNQUALIFIED_STEP:" + step["label"])
            if step["label"].startswith("N") and step["label"].endswith("_simulate"):
                replay(archive.read(step["stdout"]["path"]))
                positives += 1
        if positives != 9:
            raise ValueError("MISSING_POSITIVE")
    return {"status": "B1_SEAL_VERIFIED_NOT_T061_CLOSED", "members": len(manifest["members"]),
            "zip_sha256": manifest["zip_sha256"], "positive_RTL_replays": positives,
            "task_complete": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--prior-run", type=Path, action="append", default=[])
    parser.add_argument("--forward", type=Path)
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
    if receipt["status"] != "B1_PROTOCOL_RTL_PASS_T061_PARTIAL" or receipt["repo_gates_passed"] is not True:
        raise ValueError("UNQUALIFIED_RUN")
    for key in ("candidate_sources_after", "frozen_inputs_after", "old_seal_and_shared_after", "outputs"):
        for item in receipt[key]:
            raw = (ROOT / item["path"]).read_bytes()
            if sha(raw) != item["sha256"] or len(raw) != item["bytes"]:
                raise ValueError("BOUND_FILE_CHANGED:" + item["path"])
    paths = [ROOT / item["path"] for item in receipt["candidate_sources_after"]]
    paths += [path for path in run.rglob("*") if path.is_file()]
    paths += [DOCS / name for name in ("B1_IMPLEMENTATION_20261010.md", "M2_HANDOFF_B1_20261010.md", "DELIVERY_B1_20261010.md", "publish_b1.py", "seal_b1.py",
                                     "B1_CONTRACT.md")]
    paths += [ROOT / "code/software/polyphony_scaling_candidate/README.md"]
    paths += [ROOT / name for name in ("code/docs/M3_音频黄金与复音工程分担_2026-10-09.md",
                                      "code/docs/成果优先收缩与时序准入_2026-10-09.md",
                                      "code/rtl/138K_try/hold_trials_20261005/L_locations_guard065/input_manifest.json")]
    prior = []
    for folder in args.prior_run:
        folder = folder.resolve()
        folder.relative_to(ROOT / "code/output")
        paths += [path for path in folder.rglob("*") if path.is_file()]
        old = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))
        prior.append({"path": folder.relative_to(ROOT).as_posix(), "status_as_recorded": old["status"],
                      "error": old.get("error"), "qualified_final_evidence": False})
    payload = io.BytesIO()
    members = []
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(paths)):
            raw = path.read_bytes()
            member = path.relative_to(ROOT).as_posix()
            archive.writestr(member, raw)
            members.append({"member": member, "bytes": len(raw), "sha256": sha(raw)})
        # Original M2 authorization/review is read-only input, never interpreted
        # as broader authority than the human user's task.
        for name in ("M2_B0_REVIEW.md", "M2_REPLY_TO_M3 (2).md"):
            raw = (Path("E:/FPGA/GAOYUNFPGA/CallBack") / name).read_bytes()
            member = "review_input/" + name
            archive.writestr(member, raw)
            members.append({"member": member, "bytes": len(raw), "sha256": sha(raw)})
    raw = payload.getvalue()
    carrier = base64.b64encode(raw)
    manifest = {"schema": 1, "stage": "B1_TRANSPORT_ONLY", "task_complete": False,
                "qualified_receipt": (run / "receipt.json").relative_to(ROOT).as_posix(),
                "zip_sha256": sha(raw), "zip_bytes": len(raw), "carrier_sha256": sha(carrier),
                "prior_runs_not_final_evidence": prior, "members": members}
    package.mkdir(parents=True, exist_ok=False)
    (package / "evidence.zip.b64").write_bytes(carrier)
    (package / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = verify(package)
    (package / "seal_receipt.json").write_text(json.dumps({"utc": datetime.now(timezone.utc).isoformat(),
        "command": [sys.executable, *sys.argv], "exit_code": 0, "sealer_sha256": sha(Path(__file__).read_bytes()),
        "result": result}, indent=2) + "\n", encoding="utf-8")
    if args.forward:
        forward = args.forward.resolve()
        forward.relative_to(ROOT / "code/output")
        forward.mkdir(parents=True, exist_ok=False)
        (forward / "B1_evidence.zip").write_bytes(raw)
        for name in ("B1_IMPLEMENTATION_20261010.md", "M2_HANDOFF_B1_20261010.md", "DELIVERY_B1_20261010.md"):
            (forward / name).write_bytes((DOCS / name).read_bytes())
        for name in ("manifest.json", "seal_receipt.json"):
            (forward / name).write_bytes((package / name).read_bytes())
        print(json.dumps({**result, "forward_directory": str(forward), "zip_bytes": len(raw)}))
    else:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
