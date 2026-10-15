#!/usr/bin/env python3
"""Strict offline acceptance checker for the frozen R04 ModelSim run.

This program only parses already-produced files.  It never launches ModelSim
or any other EDA tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


R04_ARCHIVE_SHA256 = (
    "1101f1af0809530a150143456aab8ff9a1c66373e9ccbc174c6459e8c916b3bf"
)
R04_MANIFEST_SHA256 = (
    "015bf0199c5118ecfe7ec96bfd0b216d8f195daaf4989ec6bc08779def180815"
)
R04_PASS_MARKER = "PASS M2_M1TD_REAL_CHAIN_BOARD_FUNCTIONAL_ONLY"

_COMPILE_PASS_RE = re.compile(
    r"^\s*(?:#\s*)?Errors\s*:\s*0\b",
    re.IGNORECASE | re.MULTILINE,
)
_COMPILE_ERROR_RE = re.compile(
    r"^\s*(?:#\s*)?\*\*\s*Error\b|"
    r"^\s*(?:#\s*)?Errors\s*:\s*[1-9][0-9]*\b",
    re.IGNORECASE | re.MULTILINE,
)
_FATAL_OR_TIMEOUT_RE = re.compile(
    r"^\s*(?:#\s*)?\*\*\s*Fatal\b|"
    r"\bfatal\b|\btimeout\b|\btimed\s+out\b",
    re.IGNORECASE | re.MULTILINE,
)
_ERROR_OR_FAILURE_RE = re.compile(
    r"\berror\s*:|\*\*\s*error\b|"
    r"\berrors\s*:\s*[1-9][0-9]*\b|\b(?:fail|failed|failure)\b",
    re.IGNORECASE,
)


class ReceiptFormatError(ValueError):
    """The receipt cannot be interpreted without guessing."""


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class Result:
    status: str
    checks: list[Check]
    scope: str = "R04_LOG_AND_INPUT_IDENTITY_ONLY"

    @property
    def accepted(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["accepted"] = self.accepted
        data["real_execution_validated"] = False
        data["per_request_deadline"] = "UNKNOWN"
        data["required_real_receipt_contract"] = "REAL_RECEIPT_CONTRACT.md"
        return data


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ReceiptFormatError(f"not UTF-8: {path}") from exc


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise ReceiptFormatError(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReceiptFormatError(f"JSON root must be an object: {path}")
    return value


def _normal_sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise ReceiptFormatError(f"{field} must be a 64-digit SHA-256")
    return value.lower()


def _load_expected_package(
    package_path: Path,
    expected_archive_sha256: str,
    expected_manifest_sha256: str,
) -> Mapping[str, Any]:
    package_bytes = package_path.read_bytes()
    archive_sha = _sha256(package_bytes)
    if archive_sha != expected_archive_sha256:
        raise ReceiptFormatError(
            "sealed R04 archive identity mismatch: "
            f"expected {expected_archive_sha256}, got {archive_sha}"
        )
    try:
        with zipfile.ZipFile(package_path) as archive:
            manifest_bytes = archive.read("MANIFEST.json")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ReceiptFormatError("sealed R04 archive lacks a valid MANIFEST.json") from exc
    manifest_sha = _sha256(manifest_bytes)
    if manifest_sha != expected_manifest_sha256:
        raise ReceiptFormatError(
            "sealed R04 manifest identity mismatch: "
            f"expected {expected_manifest_sha256}, got {manifest_sha}"
        )
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReceiptFormatError("sealed R04 MANIFEST.json is invalid") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("members"), dict):
        raise ReceiptFormatError("sealed R04 manifest has no members object")
    return manifest


def _parse_step_status(status: Mapping[str, Any], step: str) -> tuple[int, bool]:
    value = status.get(step)
    if not isinstance(value, dict):
        raise ReceiptFormatError(f"run status missing object: {step}")
    exit_code = value.get("exit_code")
    timed_out = value.get("timed_out")
    if type(exit_code) is not int:
        raise ReceiptFormatError(f"{step}.exit_code must be an integer")
    if type(timed_out) is not bool:
        raise ReceiptFormatError(f"{step}.timed_out must be boolean")
    return exit_code, timed_out


def _parse_member_map(
    value: Any,
    label: str,
) -> dict[str, tuple[int, str]]:
    if not isinstance(value, dict):
        raise ReceiptFormatError(f"{label}.members must be an object")
    result: dict[str, tuple[int, str]] = {}
    for path, identity in value.items():
        if not isinstance(path, str) or not path:
            raise ReceiptFormatError(f"{label}.members has an invalid path")
        if not isinstance(identity, dict):
            raise ReceiptFormatError(f"{label}.members[{path!r}] must be an object")
        size = identity.get("bytes")
        if type(size) is not int or size < 0:
            raise ReceiptFormatError(f"{label}.members[{path!r}].bytes is invalid")
        sha = _normal_sha(identity.get("sha256"), f"{label}.{path}.sha256")
        result[path] = (size, sha)
    return result


def _identity_check(
    observed: Mapping[str, Any],
    expected_members: dict[str, tuple[int, str]],
    label: str,
    expected_archive_sha256: str,
    expected_manifest_sha256: str,
) -> Check:
    archive_sha = _normal_sha(
        observed.get("source_archive_sha256"),
        f"{label}.source_archive_sha256",
    )
    manifest_sha = _normal_sha(
        observed.get("manifest_sha256"),
        f"{label}.manifest_sha256",
    )
    actual_members = _parse_member_map(observed.get("members"), label)

    errors: list[str] = []
    if archive_sha != expected_archive_sha256:
        errors.append("archive SHA mismatch")
    if manifest_sha != expected_manifest_sha256:
        errors.append("manifest SHA mismatch")

    missing = sorted(set(expected_members) - set(actual_members))
    extra = sorted(set(actual_members) - set(expected_members))
    changed = sorted(
        path
        for path in set(expected_members) & set(actual_members)
        if expected_members[path] != actual_members[path]
    )
    if missing:
        errors.append(f"missing {len(missing)} member(s): {missing[:3]}")
    if extra:
        errors.append(f"unexpected {len(extra)} member(s): {extra[:3]}")
    if changed:
        errors.append(f"changed {len(changed)} member(s): {changed[:3]}")

    if errors:
        return Check(f"{label}_input_identity", False, "; ".join(errors))
    return Check(
        f"{label}_input_identity",
        True,
        f"archive, manifest and {len(expected_members)} member identities match",
    )


def check_receipt(
    *,
    package_path: Path,
    vlog_log_path: Path,
    vsim_log_path: Path,
    run_status_path: Path,
    inputs_before_path: Path,
    inputs_after_path: Path,
    expected_archive_sha256: str | None = None,
    expected_manifest_sha256: str | None = None,
    pass_marker: str = R04_PASS_MARKER,
) -> Result:
    """Return a strict, diagnostic-rich result for one already-finished run."""

    if expected_archive_sha256 is None:
        expected_archive_sha256 = R04_ARCHIVE_SHA256
    if expected_manifest_sha256 is None:
        expected_manifest_sha256 = R04_MANIFEST_SHA256
    manifest = _load_expected_package(
        package_path,
        expected_archive_sha256,
        expected_manifest_sha256,
    )
    expected_members = _parse_member_map(manifest["members"], "expected")
    vlog_log = _read_text(vlog_log_path)
    vsim_log = _read_text(vsim_log_path)
    status = _read_json(run_status_path)
    before = _read_json(inputs_before_path)
    after = _read_json(inputs_after_path)
    vlog_exit, vlog_timeout = _parse_step_status(status, "vlog")
    vsim_exit, vsim_timeout = _parse_step_status(status, "vsim")

    checks: list[Check] = [
        Check("vlog_exit_zero", vlog_exit == 0, f"exit_code={vlog_exit}"),
        Check("vsim_exit_zero", vsim_exit == 0, f"exit_code={vsim_exit}"),
        Check(
            "bounded_execution_no_timeout",
            not vlog_timeout and not vsim_timeout,
            f"vlog_timed_out={vlog_timeout}, vsim_timed_out={vsim_timeout}",
        ),
        Check(
            "vlog_compile_success_marker",
            bool(_COMPILE_PASS_RE.search(vlog_log)),
            "found 'Errors: 0'" if _COMPILE_PASS_RE.search(vlog_log) else "missing 'Errors: 0'",
        ),
        Check(
            "vlog_no_compile_error",
            not bool(_COMPILE_ERROR_RE.search(vlog_log)),
            "no ModelSim compile error summary" if not _COMPILE_ERROR_RE.search(vlog_log)
            else "compile error marker found",
        ),
        Check(
            "logs_no_fatal_or_timeout",
            not bool(_FATAL_OR_TIMEOUT_RE.search(vlog_log + "\n" + vsim_log)),
            "no FATAL/timeout token" if not _FATAL_OR_TIMEOUT_RE.search(vlog_log + "\n" + vsim_log)
            else "FATAL/timeout token found",
        ),
        Check(
            "logs_no_error_or_failure",
            not bool(_ERROR_OR_FAILURE_RE.search(vlog_log + "\n" + vsim_log)),
            "Error:/nonzero Errors:/** Error/FAIL/FAILED/Failure is absent"
            if not _ERROR_OR_FAILURE_RE.search(vlog_log + "\n" + vsim_log)
            else "error or failure diagnostic found; PASS does not override it",
        ),
        Check(
            "vsim_required_pass_marker",
            bool(
                re.search(
                    rf"(?m)^\s*(?:#\s*)?{re.escape(pass_marker)}\s*$",
                    vsim_log,
                )
            ),
            f"required marker: {pass_marker}",
        ),
        _identity_check(
            before,
            expected_members,
            "before",
            expected_archive_sha256,
            expected_manifest_sha256,
        ),
        _identity_check(
            after,
            expected_members,
            "after",
            expected_archive_sha256,
            expected_manifest_sha256,
        ),
    ]
    status_text = "PASS" if all(item.passed for item in checks) else "FAIL"
    return Result(status=status_text, checks=checks)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline-only strict receipt checker for frozen R04 ModelSim evidence."
    )
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--vlog-log", required=True, type=Path)
    parser.add_argument("--vsim-log", required=True, type=Path)
    parser.add_argument("--run-status", required=True, type=Path)
    parser.add_argument("--inputs-before", required=True, type=Path)
    parser.add_argument("--inputs-after", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = check_receipt(
            package_path=args.package,
            vlog_log_path=args.vlog_log,
            vsim_log_path=args.vsim_log,
            run_status_path=args.run_status,
            inputs_before_path=args.inputs_before,
            inputs_after_path=args.inputs_after,
        )
    except (OSError, ReceiptFormatError) as exc:
        print(f"R04_RECEIPT_INVALID: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
    print(payload)
    if args.json_out is not None:
        if args.json_out.exists():
            print(f"R04_RECEIPT_INVALID: output already exists: {args.json_out}", file=sys.stderr)
            return 2
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    return 0 if result.accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
