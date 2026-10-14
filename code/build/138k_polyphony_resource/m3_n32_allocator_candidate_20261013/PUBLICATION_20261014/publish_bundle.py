"""Read-only seal verification and post-push offline transfer packaging."""
import argparse
import ast
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile


ROOTS = (
    "code/rtl/common/m3_n32_allocator_candidate_20261013",
    "code/software/t061_allocator_reference_candidate_20261013",
    "code/software/t061_n32_stress_plan_candidate_20261013",
    "code/software/t061_clock_contract_guard_candidate_20261013",
    "code/tb/audio/t061_n32_allocator_candidate_20261013",
    "code/build/138k_polyphony_resource/m3_n32_allocator_candidate_20261013",
)
SEALS = {
    "A": (ROOTS[1] + "/SEALED_FUNCTION_RECOVERY_RESULT_20261014_R01",
          "da5451dd7f75f9d9cb01bae4fac47298f389e83fbd8e9c84a96c5046a0d2b1b0"),
    "B": (ROOTS[4] + "/B/SEALED_RESULT_R01",
          "ec8b918d598f205b6b4a37aa2ee670e809180778941184a9eecbeb62c8f48409"),
    "C": (ROOTS[4] + "/C/SEALED_SEGMENTED_RESULT_R07",
          "ab5f5d3b08ecc1002323b59547007d9021ecee653feb1529cb33472e844a726e"),
    "D": (ROOTS[5] + "/SEALED_PREPARED_RESULT_R02",
          "bdcc3ce5e3ecc08cd5986fbdda5b04fcfe0b225a4dff1c585d4ff0550ceaa456"),
}


def identity(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], timeout=90)


def verify_seals(repo):
    members = {}
    reports = {}
    for label, (relative, expected_seal) in SEALS.items():
        folder = repo / relative
        seal_raw = (folder / "seal.json").read_bytes()
        if identity(seal_raw)["sha256"] != expected_seal:
            raise ValueError("EXTERNAL_SEAL_SHA:" + label)
        seal = json.loads(seal_raw)
        manifest_raw = (folder / "MANIFEST.json").read_bytes()
        raw = base64.b64decode(b"".join((folder / "snapshot.zip.b64").read_bytes().split()), validate=True)
        if identity(raw) != seal["snapshot"]:
            raise ValueError("SNAPSHOT_IDENTITY:" + label)
        if (folder / "snapshot.zip").exists() and (folder / "snapshot.zip").read_bytes() != raw:
            raise ValueError("RAW_ZIP_DIFFERS:" + label)
        if "manifest" in seal and identity(manifest_raw) != seal["manifest"]:
            raise ValueError("MANIFEST_IDENTITY:" + label)
        manifest = json.loads(manifest_raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
            names = bundle.namelist()
            if len(names) != len(set(names)) or len(names) != seal["members"]:
                raise ValueError("MEMBER_COUNT:" + label)
            if set(names) != set(manifest["files"]) | {"MANIFEST.json"}:
                raise ValueError("MEMBER_SET:" + label)
            if bundle.read("MANIFEST.json") != manifest_raw:
                raise ValueError("MANIFEST_MEMBER:" + label)
            for name, expected in manifest["files"].items():
                if identity(bundle.read(name)) != expected:
                    raise ValueError("MEMBER_IDENTITY:" + label + ":" + name)
        members[label + "/snapshot.zip"] = raw
        members[label + "/seal.json"] = seal_raw
        members[label + "/MANIFEST.json"] = manifest_raw
        reports[label] = {"seal": identity(seal_raw), "snapshot": identity(raw),
                          "manifest": identity(manifest_raw), "members": len(names)}
    return members, reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--commit")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    members, reports = verify_seals(args.repo)
    python_count = 0
    for root in ROOTS:
        for path in (args.repo / root).rglob("*.py"):
            if "prepared" in path.parts or "__pycache__" in path.parts:
                continue
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            python_count += 1
    if args.verify_only:
        print(json.dumps({"status": "FOUR_SEALS_AND_PYTHON_SYNTAX_PASS", "seals": reports,
                          "python_files": python_count, "RTL_runs": 0, "EDA_calls": 0}))
        return 0
    if not args.commit or args.evidence is None or args.out is None:
        parser.error("post-push packaging needs --commit, --evidence, --out")
    receipt = json.loads((args.evidence / "publication_receipt.json").read_bytes())
    gate = json.loads((args.evidence / "gate_receipt.json").read_bytes())
    if receipt["commit"] != args.commit or receipt["remote_commit"] != args.commit:
        raise ValueError("PUSH_NOT_VERIFIED")
    if gate["commit"] != args.commit or gate["exit_code"] != 0 or gate["pass_count"] != 9:
        raise ValueError("EXACT_GATE_NOT_PASS")
    names = git(args.repo, "ls-tree", "-r", "--name-only", "-z", args.commit, "--", *ROOTS).split(b"\0")
    for name_raw in filter(None, names):
        name = name_raw.decode("utf-8")
        if name.endswith((".zip", ".zip.b64")):
            continue  # Four complete archives above retain exact executed bytes/history.
        members["source/" + name] = git(args.repo, "show", args.commit + ":" + name)
    for path in sorted(args.evidence.rglob("*")):
        if path.is_file() and ".git" not in path.parts:
            # Explicit evidence folder only; gate checkout is a sibling, never included.
            members["publication/" + path.relative_to(args.evidence).as_posix()] = path.read_bytes()
    members["README.md"] = (
        "# M3 N32 A/B/C/D offline handoff\n\n"
        + "Git develop: " + args.commit + "\n\n"
        + "A: independent L2; B: limited L2/math L3; C: segmented L2/math L3; "
        + "D: prepare L0/L1 ONLY, resources UNKNOWN, STA NOT_RUN. T061 PARTIAL.\n"
        + "Original failed runs and generation-time UNCOMMITTED notes remain unchanged.\n"
        + "Four archives contain executed sources, capture, ROM, logs, commands and receipts. "
        + "No tool binaries; no execution permission is conveyed.\n"
        + "Pending user forwarding to M2; not yet delivered or formally accepted.\n"
    ).encode("utf-8")
    manifest_raw = json_bytes({"commit": args.commit, "seals": reports,
                               "T061_complete": False, "EDA_calls": 0,
                               "files": {name: identity(raw) for name, raw in sorted(members.items())}})
    members["MANIFEST.json"] = manifest_raw
    args.out.mkdir(parents=True, exist_ok=False)
    target = args.out / "M3_N32_ABCD_20261014_COMPLETE.zip"
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for name, raw in sorted(members.items()):
            bundle.writestr(name, raw)
    with zipfile.ZipFile(target) as bundle:
        if set(bundle.namelist()) != set(members):
            raise ValueError("TRANSFER_MEMBER_SET")
        for name, raw in members.items():
            if bundle.read(name) != raw:
                raise ValueError("TRANSFER_MEMBER_BYTES:" + name)
    (args.out / "MANIFEST.json").write_bytes(manifest_raw)
    transfer = {"zip": identity(target.read_bytes()), "manifest": identity(manifest_raw),
                "members": len(members), "commit": args.commit, "status": "READY_TO_FORWARD_NOT_DELIVERED"}
    (args.out / "transfer_receipt.json").write_bytes(json_bytes(transfer))
    print(json.dumps(transfer))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
