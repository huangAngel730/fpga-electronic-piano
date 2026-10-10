"""Seal one small, fresh B0 handoff carrier; preserve all original run logs.

--verify checks member identity in memory, never extracts or overwrites files.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[4]
DOCS = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(package):
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    raw = base64.b64decode((package / "evidence.zip.b64").read_bytes(), validate=True)
    if sha(raw) != manifest["zip_sha256"] or len(raw) != manifest["zip_bytes"]:
        raise ValueError("CARRIER_IDENTITY")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        expected = {item["member"] for item in manifest["members"]}
        if len(archive.namelist()) != len(expected) or set(archive.namelist()) != expected:
            raise ValueError("MEMBER_LIST")
        for item in manifest["members"]:
            member = Path(item["member"])
            if member.is_absolute() or ".." in member.parts:
                raise ValueError("UNSAFE_MEMBER")
            data = archive.read(item["member"])
            if sha(data) != item["sha256"] or len(data) != item["bytes"]:
                raise ValueError("MEMBER_IDENTITY")
    return {"status": "CARRIER_VERIFIED", "zip_bytes": len(raw), "zip_sha256": sha(raw),
            "members": len(expected)}


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path)
    parser.add_argument("--prior-run", type=Path, action="append", default=[])
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    package = args.package.resolve()
    if args.verify:
        print(json.dumps(verify(package)))
        return
    package.relative_to(DOCS)
    receipt = json.loads((args.run / "receipt.json").read_text(encoding="utf-8"))
    if receipt["status"] != "B0_SCOPE_PASS_T061_PARTIAL" or receipt.get("repo_gates_passed") is not True:
        raise ValueError("NO_COMPLETE_B0_GATE_RECEIPT")
    for item in (receipt["candidate_sources_after"] + receipt["frozen_inputs_after"]
                 + receipt["outputs"]):
        if sha((ROOT / item["path"]).read_bytes()) != item["sha256"]:
            raise ValueError("RECEIPT_BOUND_FILE_CHANGED:" + item["path"])
    package.mkdir(parents=True, exist_ok=False)
    # Raw versions and executable identities supplement the runner receipt.
    tool_records = []
    for name, argv in (("python", [sys.executable, "--version"]),
                       ("git", [shutil.which("git"), "--version"]),
                       ("powershell", [shutil.which("pwsh") or shutil.which("powershell"),
                                       "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"] )):
        if not argv[0]:
            raise ValueError("MISSING_TOOL_VERSION:" + name)
        process = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=30, check=False)
        (package / (name + ".stdout.bin")).write_bytes(process.stdout)
        (package / (name + ".stderr.bin")).write_bytes(process.stderr)
        tool_records.append({"tool": name, "command": argv, "cwd": str(ROOT),
                             "exit_code": process.returncode,
                             "exe_sha256": sha(Path(argv[0]).read_bytes())})
        if process.returncode != 0:
            raise ValueError("TOOL_VERSION_FAILED:" + name)
    (package / "tools.json").write_text(json.dumps(tool_records, indent=2) + "\n", encoding="utf-8")
    members = []
    payload = io.BytesIO()
    paths = list((ROOT / "code/software/polyphony_scaling_candidate").glob("*"))
    paths += [ROOT / "code/scripts/run_m3_polyphony_scaling_acceptance.py"]
    paths += list(DOCS.glob("*.md")) + [Path(__file__).resolve()]
    paths += list(args.run.rglob("*"))
    for run in args.prior_run:
        if json.loads((run / "receipt.json").read_text(encoding="utf-8"))["status"] != "FAIL":
            raise ValueError("PRIOR_RUN_NOT_FAILURE")
        paths += list(run.rglob("*"))
    paths += list(package.glob("*.bin")) + [package / "tools.json"]
    paths += [ROOT / "code/rtl/138K_try/hold_trials_20261005/L_locations_guard065/input_manifest.json",
              ROOT / "code/rtl/138K_try/hold_trials_20261005/L_locations_guard065/impl/pnr/audio_visual_coexistence_top.rpt.txt",
              ROOT / "code/docs/evidence/pcm_waveform_L_baseline_20261007.json"]
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(p.resolve() for p in paths if p.is_file())):
            member = path.relative_to(ROOT).as_posix()
            raw = path.read_bytes()
            archive.writestr(member, raw)
            members.append({"member": member, "bytes": len(raw), "sha256": sha(raw)})
    raw = payload.getvalue()
    (package / "evidence.zip.b64").write_bytes(base64.b64encode(raw))
    manifest = {"schema": 1, "scope": "B0 only; T061 incomplete; not candidate RTL/audio/STA",
                "zip_bytes": len(raw), "zip_sha256": sha(raw), "members": members,
                "carrier_sha256": sha(base64.b64encode(raw)),
                "repository_gate_note": "Existing repo gates include legacy T007/T019 simulations; no NEW candidate HDL compiled."}
    (package / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    result = verify(package)
    seal_receipt = {"command": [sys.executable, *sys.argv], "cwd": str(ROOT),
                    "utc": datetime.now(timezone.utc).isoformat(), "exit_code": 0,
                    "elapsed_seconds": round(time.monotonic() - started, 6),
                    "result": result, "tools": tool_records,
                    "manifest_sha256": sha((package / "manifest.json").read_bytes()),
                    "current_run_receipt_sha256": sha((args.run / "receipt.json").read_bytes()),
                    "scope": "carrier integrity only; no new HDL/audio/synthesis/STA validation"}
    (package / "seal_receipt.json").write_text(json.dumps(seal_receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
