"""Create an immutable N32-B PLAN or RESULT package for both reviewers."""
from __future__ import annotations

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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import b_harness  # noqa: E402

BASE = "0b5f45388f974ce4ae0a2081eac7add93181c32a"
LOADER_REVIEW_DEPENDENCIES = (
    b_harness.HELPERS / "runner.py",
    b_harness.HELPERS / "runner_tail_20261013.py",
    b_harness.HELPERS / "windows_job.py",
)


def digest(raw: bytes) -> dict:
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def encode(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def binary_diff(paths: list[Path]) -> tuple[bytes, dict]:
    """Return Git's binary-safe patch for every repository-local authored file."""
    git = shutil.which("git")
    b_harness.require(git is not None, "GIT_MISSING")
    patches = []
    for path in sorted({Path(item).resolve() for item in paths}):
        b_harness.require(path.is_file() and path.is_relative_to(b_harness.ROOT),
                          "DIFF_PATH_SCOPE:" + str(path))
        relative = path.relative_to(b_harness.ROOT).as_posix()
        exists = subprocess.run(
            [git, "cat-file", "-e", BASE + ":" + relative],
            cwd=b_harness.ROOT, capture_output=True, timeout=10,
        )
        b_harness.require(exists.returncode in (0, 128), "BASE_LOOKUP_FAILED")
        argv = ([git, "diff", "--binary", BASE, "--", relative]
                if exists.returncode == 0 else
                [git, "diff", "--no-index", "--binary", "--",
                 "/dev/null", relative])
        result = subprocess.run(
            argv, cwd=b_harness.ROOT, capture_output=True, timeout=30,
        )
        b_harness.require(result.returncode in (0, 1),
                          "DIFF_FAILED:" + relative)
        patches.append(result.stdout)
    return b"".join(patches), {"path": git, **b_harness.identity(git)}


def _authored_files() -> list[Path]:
    roots = [b_harness.B_RTL, HERE]
    result = []
    for root in roots:
        for path in root.rglob("*"):
            if (path.is_file() and "__pycache__" not in path.parts
                    and not any(part.startswith("SEALED_") for part in path.parts)):
                result.append(path)
    return sorted(set(result))


def _loader_review_inputs() -> list[Path]:
    return sorted(set(_authored_files() + [path.resolve()
                                           for path in LOADER_REVIEW_DEPENDENCIES]))


def _binding_rows(raw_by_relative: dict[str, bytes]) -> list[dict]:
    return [
        {"repo_relative": relative, **digest(raw)}
        for relative, raw in sorted(raw_by_relative.items())
    ]


def _binding_sha(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(
        rows, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def validate_loader_input_binding(rows: list[dict],
                                  raw_by_relative: dict[str, bytes]) -> str:
    """Reject any source/test/helper drift relative to tested frozen bytes."""
    expected = {row["repo_relative"]: {key: row[key]
                                       for key in ("bytes", "sha256")}
                for row in rows}
    b_harness.require(len(expected) == len(rows), "LOADER_INPUT_DUPLICATE")
    actual = {name: digest(raw) for name, raw in raw_by_relative.items()}
    b_harness.require(set(actual) == set(expected),
                      "LOADER_INPUT_SET_DRIFT")
    b_harness.require(actual == expected, "LOADER_INPUT_IDENTITY_DRIFT")
    return _binding_sha(rows)


def validate_loader_receipt_raw(receipt: dict, command_raw: bytes,
                                inputs_raw: bytes, stdout: bytes,
                                stderr: bytes) -> None:
    """Recompute the receipt contract from one read of every raw evidence file."""
    b_harness.require(receipt.get("schema")
                      == "T061_N32_B_LOADER_SOFTWARE_EVIDENCE_V2",
                      "LOADER_EVIDENCE_SCHEMA")
    b_harness.require(receipt.get("status") == "PASS"
                      and receipt.get("exit_code") == 0
                      and receipt.get("timed_out") is False
                      and receipt.get("HDL_tool_calls") == 0
                      and receipt.get("EDA_calls") == 0
                      and receipt.get("environment_bat_invoked") is False,
                      "LOADER_EVIDENCE_NOT_PASS")
    b_harness.require(receipt.get("command") == digest(command_raw),
                      "LOADER_COMMAND_DRIFT")
    b_harness.require(receipt.get("inputs") == digest(inputs_raw),
                      "LOADER_INPUT_MANIFEST_DRIFT")
    b_harness.require(receipt.get("stdout") == digest(stdout),
                      "LOADER_STDOUT_DRIFT")
    b_harness.require(receipt.get("stderr") == digest(stderr),
                      "LOADER_STDERR_DRIFT")


def collect_loader_evidence(output: Path) -> dict:
    """Freeze loader inputs first, then run only new tests from that snapshot."""
    output = b_harness.under_output(output)
    b_harness.require(not output.exists(), "LOADER_EVIDENCE_EXISTS")
    output.mkdir(parents=True)
    snapshot_root = output / "snapshot"
    raw_by_relative = {}
    for source in _loader_review_inputs():
        source = source.resolve()
        b_harness.require(source.is_file() and source.is_relative_to(b_harness.ROOT),
                          "LOADER_INPUT_SCOPE")
        relative = source.relative_to(b_harness.ROOT).as_posix()
        raw = source.read_bytes()
        raw_by_relative[relative] = raw
        target = snapshot_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    rows = _binding_rows(raw_by_relative)
    binding_sha = validate_loader_input_binding(rows, raw_by_relative)
    inputs_raw = encode({"binding_sha256": binding_sha, "files": rows})
    (output / "inputs.json").write_bytes(inputs_raw)

    snapshot_here = snapshot_root / HERE.relative_to(b_harness.ROOT)
    command = [
        sys.executable, "-B", "-X", "utf8", "-m", "unittest",
        "test_b_loader_contract.py",
    ]
    command_record = {
        "argv": command,
        "cwd": str(snapshot_here),
        "timeout_seconds": 120,
        "input_binding_sha256": binding_sha,
        "automatic_retries": 0,
        "HDL_tool_calls": 0,
        "EDA_calls": 0,
        "environment_bat_invoked": False,
    }
    command_raw = encode(command_record)
    (output / "command.json").write_bytes(command_raw)
    started = time.monotonic()
    timed_out = False
    try:
        result = subprocess.run(
            command, cwd=snapshot_here, capture_output=True, timeout=120,
        )
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired as error:
        timed_out = True
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        exit_code = None
    elapsed = time.monotonic() - started
    (output / "stdout.bin").write_bytes(stdout)
    (output / "stderr.bin").write_bytes(stderr)

    snapshot_after = {
        row["repo_relative"]: b_harness.safe_member(
            snapshot_root, row["repo_relative"]
        ).read_bytes()
        for row in rows
    }
    after_sha = validate_loader_input_binding(rows, snapshot_after)
    status = ("PASS" if exit_code == 0 and not timed_out
              and after_sha == binding_sha else "FAIL_PARTIAL")
    receipt = {
        "schema": "T061_N32_B_LOADER_SOFTWARE_EVIDENCE_V2",
        "status": status,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "elapsed_seconds": elapsed,
        "stdout": digest(stdout),
        "stderr": digest(stderr),
        "command": digest(command_raw),
        "inputs": digest(inputs_raw),
        "input_binding_sha256": binding_sha,
        "inputs_before_sha256": binding_sha,
        "inputs_after_sha256": after_sha,
        "python": {"path": sys.executable, **b_harness.identity(sys.executable)},
        "automatic_retries": 0,
        "HDL_tool_calls": 0,
        "EDA_calls": 0,
        "environment_bat_invoked": False,
    }
    (output / "receipt.json").write_bytes(encode(receipt))
    return receipt


def _read_loader_evidence(
        evidence_root: Path) -> tuple[dict, dict[str, bytes], dict[str, bytes]]:
    names = ("command.json", "inputs.json", "stdout.bin", "stderr.bin",
             "receipt.json")
    raw = {name: (evidence_root / name).read_bytes() for name in names}
    receipt = json.loads(raw["receipt.json"].decode("utf-8"))
    validate_loader_receipt_raw(
        receipt, raw["command.json"], raw["inputs.json"],
        raw["stdout.bin"], raw["stderr.bin"],
    )
    inputs = json.loads(raw["inputs.json"].decode("utf-8"))
    rows = inputs["files"]
    b_harness.require(inputs.get("binding_sha256") == _binding_sha(rows)
                      == receipt.get("input_binding_sha256")
                      == receipt.get("inputs_before_sha256")
                      == receipt.get("inputs_after_sha256"),
                      "LOADER_BINDING_SHA_DRIFT")
    snapshot_root = evidence_root / "snapshot"
    snapshot_here = snapshot_root / HERE.relative_to(b_harness.ROOT)
    command = json.loads(raw["command.json"].decode("utf-8"))
    b_harness.require(command.get("argv") == [
        receipt["python"]["path"], "-B", "-X", "utf8", "-m", "unittest",
        "test_b_loader_contract.py",
    ], "LOADER_COMMAND_ARGV")
    b_harness.require(command.get("cwd") == str(snapshot_here)
                      and command.get("timeout_seconds") == 120
                      and command.get("input_binding_sha256")
                      == inputs["binding_sha256"]
                      and command.get("automatic_retries") == 0
                      and command.get("HDL_tool_calls") == 0
                      and command.get("EDA_calls") == 0
                      and command.get("environment_bat_invoked") is False,
                      "LOADER_COMMAND_CONTRACT")
    expected_snapshot = {row["repo_relative"] for row in rows}
    actual_snapshot_paths = {
        path.relative_to(snapshot_root).as_posix(): path
        for path in snapshot_root.rglob("*") if path.is_file()
    }
    b_harness.require(set(actual_snapshot_paths) == expected_snapshot,
                      "LOADER_SNAPSHOT_SET_DRIFT")
    snapshot_raw = {
        relative: b_harness.safe_member(snapshot_root, relative).read_bytes()
        for relative in sorted(expected_snapshot)
    }
    validate_loader_input_binding(rows, snapshot_raw)
    python = Path(receipt["python"]["path"])
    b_harness.require(b_harness.identity(python)
                      == {key: receipt["python"][key]
                          for key in ("bytes", "sha256")},
                      "LOADER_PYTHON_DRIFT")
    return inputs, raw, snapshot_raw


def _loader_evidence_members(core_raw: dict[str, bytes],
                             snapshot_raw: dict[str, bytes]) -> dict[str, bytes]:
    """Build archive members only from already validated, single-read bytes."""
    result = dict(core_raw)
    result.update({"snapshot/" + name: raw
                   for name, raw in snapshot_raw.items()})
    return result


def seal_loader_review(evidence_root: Path, target: Path,
                       review_key: str) -> dict:
    """Seal exactly the loader bytes that produced the frozen PASS evidence."""
    b_harness.require(review_key.startswith("T061-N32-B-LOADER-"),
                      "LOADER_REVIEW_KEY")
    target = Path(target).resolve()
    b_harness.require(target.is_relative_to(HERE) and target != HERE,
                      "DELIVERY_OUTSIDE_B_WRITESET")
    b_harness.require(not target.exists(), "DELIVERY_EXISTS")
    evidence_root = b_harness.under_output(evidence_root)
    b_harness.require(evidence_root.is_dir(), "LOADER_EVIDENCE_MISSING")
    inputs, core_evidence, validated_snapshot = _read_loader_evidence(
        evidence_root
    )
    rows = inputs["files"]

    current_raw = {}
    for source in _loader_review_inputs():
        source = source.resolve()
        relative = source.relative_to(b_harness.ROOT).as_posix()
        current_raw[relative] = source.read_bytes()
    binding_sha = validate_loader_input_binding(rows, current_raw)
    b_harness.require(binding_sha == inputs["binding_sha256"],
                      "LOADER_CURRENT_BINDING_SHA")

    members = {}
    authored_relatives = {
        path.resolve().relative_to(b_harness.ROOT).as_posix()
        for path in _authored_files()
    }
    for relative, raw in sorted(current_raw.items()):
        prefix = "authored/" if relative in authored_relatives else "dependencies/"
        members[prefix + relative] = raw
    evidence_files = []
    evidence_members = _loader_evidence_members(
        core_evidence, validated_snapshot
    )
    for relative, raw in sorted(evidence_members.items()):
        name = "evidence/" + relative
        members[name] = raw
        evidence_files.append({"member": name, **digest(raw)})
    authored = _authored_files()
    patch_raw, diff_tool = binary_diff(authored)
    members["changes.patch"] = patch_raw
    current_after_diff = {
        path.resolve().relative_to(b_harness.ROOT).as_posix(): path.read_bytes()
        for path in _loader_review_inputs()
    }
    validate_loader_input_binding(rows, current_after_diff)

    evidence_manifest = {
        "root": str(evidence_root),
        "files": evidence_files,
        "receipt": digest(core_evidence["receipt.json"]),
        "input_binding_sha256": binding_sha,
        "software_only": True,
        "HDL_tool_calls": 0,
        "EDA_calls": 0,
    }
    evidence_raw = encode(evidence_manifest)
    manifest = {
        "review_key": review_key,
        "stage": "N32-B-LOADER",
        "base": BASE,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "M3 / main-dialogue-4 / b_delivery.py loader-seal",
        "diff_tool": diff_tool,
        "diff_scope": (
            "The exact B-authored and helper bytes tested from the frozen "
            "snapshot, their fixed-base binary patch, and recomputed evidence."
        ),
        "state": "SEALED-UNCOMMITTED",
        "input_binding_sha256": binding_sha,
        "files": {name: digest(raw) for name, raw in sorted(members.items())},
        "evidence_manifest": digest(evidence_raw),
        "permission": (
            "Loader-contract read-only review only; no N32-B execution, "
            "Icarus, VVP, Gowin, T052, T060, EDA, or devices."
        ),
    }
    manifest_raw = encode(manifest)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, raw in sorted(members.items()):
            bundle.writestr(name, raw)
        bundle.writestr("EVIDENCE_MANIFEST.json", evidence_raw)
        bundle.writestr("MANIFEST.json", manifest_raw)
    archive = stream.getvalue()

    target.mkdir(parents=True, exist_ok=False)
    (target / "snapshot.zip.b64").write_bytes(base64.b64encode(archive) + b"\n")
    (target / "MANIFEST.json").write_bytes(manifest_raw)
    (target / "EVIDENCE_MANIFEST.json").write_bytes(evidence_raw)
    seal_receipt = {
        "review_key": review_key,
        "snapshot": digest(archive),
        "scope": digest(manifest_raw),
        "evidence": digest(evidence_raw),
        "input_binding_sha256": binding_sha,
        "base": BASE,
        "members": len(members) + 2,
        "state": "SEALED-UNCOMMITTED",
    }
    (target / "seal.json").write_bytes(encode(seal_receipt))
    return seal_receipt


def seal(plan_path: Path, target: Path, review_key: str,
         evidence_roots: list[Path]) -> dict:
    target = Path(target).resolve()
    b_harness.require(target.is_relative_to(HERE) and target != HERE,
                      "DELIVERY_OUTSIDE_B_WRITESET")
    b_harness.require(not target.exists(), "DELIVERY_EXISTS")
    plan_path = Path(plan_path).resolve()
    plan = b_harness.verify(plan_path)
    prepared = Path(plan["prepared"]).resolve()

    members = {}
    for source in sorted(prepared.rglob("*")):
        if source.is_file() and "__pycache__" not in source.parts:
            relative = source.relative_to(prepared).as_posix()
            members["prepared/" + relative] = source.read_bytes()

    authored = _authored_files()
    for source in authored:
        relative = source.relative_to(b_harness.ROOT).as_posix()
        members["authored/" + relative] = source.read_bytes()

    evidence_files = []
    for root_arg in evidence_roots:
        root = b_harness.under_output(root_arg)
        b_harness.require(root.is_dir(), "EVIDENCE_ROOT_MISSING:" + str(root))
        for source in sorted(root.rglob("*")):
            if (source.is_file() and source.suffix.lower() not in (".vvp", ".pyc")
                    and "__pycache__" not in source.parts):
                name = "evidence/" + root.name + "/" + source.relative_to(root).as_posix()
                raw = source.read_bytes()
                members[name] = raw
                evidence_files.append({"member": name, **digest(raw)})

    patch_paths = authored + [plan_path]
    for root_arg in evidence_roots:
        root = Path(root_arg).resolve()
        patch_paths.extend(
            path for path in root.rglob("*")
            if (path.is_file() and path.suffix.lower() not in (".vvp", ".pyc")
                and "__pycache__" not in path.parts)
        )
    members["changes.patch"], diff_tool = binary_diff(patch_paths)

    evidence_manifest = {
        "roots": [str(Path(root).resolve()) for root in evidence_roots],
        "files": evidence_files,
        "excluded_suffixes": [".vvp", ".pyc"],
        "none": not evidence_files,
    }
    evidence_raw = encode(evidence_manifest)
    manifest = {
        "review_key": review_key,
        "stage": "N32-B",
        "base": BASE,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "M3 / main-dialogue-4 / b_delivery.py",
        "diff_tool": diff_tool,
        "diff_scope": (
            "All B-authored files, exact plan, and archived evidence. Prepared "
            "source/tool copies are byte-manifested in the archive and are not "
            "duplicated as repository diffs."
        ),
        "state": "SEALED-UNCOMMITTED",
        "plan": digest(plan_path.read_bytes()),
        "prepared": str(prepared),
        "files": {name: digest(raw) for name, raw in sorted(members.items())},
        "evidence_manifest": digest(evidence_raw),
        "permission": "Bounded N32-B selftest only; no T052/T060/EDA/devices",
    }
    manifest_raw = encode(manifest)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, raw in sorted(members.items()):
            bundle.writestr(name, raw)
        bundle.writestr("EVIDENCE_MANIFEST.json", evidence_raw)
        bundle.writestr("MANIFEST.json", manifest_raw)
    archive = stream.getvalue()

    target.mkdir(parents=True, exist_ok=False)
    (target / "snapshot.zip.b64").write_bytes(base64.b64encode(archive) + b"\n")
    (target / "MANIFEST.json").write_bytes(manifest_raw)
    (target / "EVIDENCE_MANIFEST.json").write_bytes(evidence_raw)
    receipt = {
        "review_key": review_key,
        "snapshot": digest(archive),
        "scope": digest(manifest_raw),
        "evidence": digest(evidence_raw),
        "plan": digest(plan_path.read_bytes()),
        "members": len(members) + 2,
        "state": "SEALED-UNCOMMITTED",
    }
    (target / "seal.json").write_bytes(encode(receipt))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("plan", "loader-evidence", "loader-seal"),
                        default="plan")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--review-key")
    parser.add_argument("--evidence", type=Path, action="append", default=[])
    args = parser.parse_args()
    try:
        if args.mode == "plan":
            b_harness.require(args.plan is not None and args.target is not None
                              and args.review_key, "PLAN_SEAL_ARGUMENTS")
            result = seal(args.plan, args.target, args.review_key, args.evidence)
        elif args.mode == "loader-evidence":
            b_harness.require(args.output is not None, "LOADER_EVIDENCE_ARGUMENT")
            result = collect_loader_evidence(args.output)
        else:
            b_harness.require(args.evidence and len(args.evidence) == 1
                              and args.target is not None and args.review_key,
                              "LOADER_SEAL_ARGUMENTS")
            result = seal_loader_review(
                args.evidence[0], args.target, args.review_key
            )
        print(json.dumps(result, sort_keys=True))
        if args.mode == "loader-evidence":
            return 0 if result.get("status") == "PASS" else 1
        return 0
    except Exception as error:
        print(json.dumps({"status": "FAIL",
                          "diagnostic": type(error).__name__ + ":" + str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
