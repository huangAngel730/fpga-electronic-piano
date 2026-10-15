#!/usr/bin/env python3
"""Read-only R04 evidence consistency audit; never starts any tool."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

from receipt_check import (
    R04_ARCHIVE_SHA256,
    R04_MANIFEST_SHA256,
    R04_PASS_MARKER,
    _COMPILE_PASS_RE,
    _has_error_diagnostic,
    _identity_check,
    _load_expected_package,
    _normal_sha,
    _parse_member_map,
    _read_json,
    _read_text,
    ReceiptFormatError,
)


def relative_file(root: Path, name: Any) -> Path:
    if not isinstance(name, str) or not name:
        raise ReceiptFormatError("missing evidence-relative file path")
    candidate = (root / name).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ReceiptFormatError("evidence path escapes its root")
    if not candidate.is_file():
        raise ReceiptFormatError(f"missing original file: {name}")
    return candidate


def file_identity(root: Path, value: Any) -> Path:
    if not isinstance(value, dict):
        raise ReceiptFormatError("missing original stream descriptor")
    path = relative_file(root, value.get("path"))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != _normal_sha(value.get("sha256"), "original stream SHA"):
        raise ReceiptFormatError(f"stream SHA mismatch: {value.get('path')}")
    return path


def audit(root: Path, record: Path, confirmation: Path, confirmation_sha: str) -> dict:
    """Check declared evidence against a separately supplied M2 SHA reference.

    A consistent record is still unauthenticated until M2 reviews its origin.
    A caller-supplied hash is a binding, not a signature or execution permit.
    """
    raw_confirmation = confirmation.read_bytes()
    if hashlib.sha256(raw_confirmation).hexdigest() != _normal_sha(
        confirmation_sha, "independent M2 confirmation SHA"
    ):
        raise ReceiptFormatError("M2 confirmation SHA mismatch")
    actual = _read_json(record)
    approved = _read_json(confirmation)
    reasons: list[str] = []
    if actual.get("schema") != "r04_original_receipt_v1":
        raise ReceiptFormatError("unsupported execution record schema")
    if actual.get("evidence_kind") != "REAL_TOOL_OUTPUT":
        reasons.append("SYNTHETIC_OR_UNDECLARED_EVIDENCE")
    if approved.get("schema") != "r04_m2_confirmation_v1":
        raise ReceiptFormatError("unsupported M2 confirmation schema")
    if not isinstance(approved.get("reference"), str) or not approved["reference"]:
        raise ReceiptFormatError("missing independent M2 confirmation reference")
    if not isinstance(actual.get("machine"), str) or not actual["machine"]:
        raise ReceiptFormatError("missing execution machine")
    if actual["machine"] != approved.get("machine"):
        reasons.append("MACHINE_IDENTITY_MISMATCH")
    if actual.get("source_archive_sha256") != R04_ARCHIVE_SHA256:
        reasons.append("SOURCE_ARCHIVE_IDENTITY_MISMATCH")
    if approved.get("source_archive_sha256") != R04_ARCHIVE_SHA256:
        reasons.append("CONFIRMED_ARCHIVE_IDENTITY_MISMATCH")
    total_budget = approved.get("total_budget_seconds")
    if type(total_budget) not in (int, float) or not math.isfinite(total_budget):
        raise ReceiptFormatError("invalid confirmed total budget")
    total_elapsed = actual.get("total_elapsed_seconds")
    if type(total_elapsed) not in (int, float) or not math.isfinite(total_elapsed):
        raise ReceiptFormatError("invalid execution total elapsed")
    if total_budget <= 0 or total_elapsed < 0:
        raise ReceiptFormatError("invalid total time range")
    if total_elapsed > total_budget:
        reasons.append("TOTAL_BUDGET_EXCEEDED")

    package = relative_file(root, actual.get("package"))
    manifest = _load_expected_package(package, R04_ARCHIVE_SHA256, R04_MANIFEST_SHA256)
    members = _parse_member_map(manifest["members"], "frozen")
    for label in ("before", "after"):
        snapshot = _read_json(relative_file(root, actual.get(f"inputs_{label}")))
        check = _identity_check(
            snapshot, members, label, R04_ARCHIVE_SHA256, R04_MANIFEST_SHA256
        )
        if not check.passed:
            reasons.append(f"{label.upper()}_INPUT_IDENTITY: {check.detail}")

    steps = actual.get("steps")
    confirmed_steps = approved.get("steps")
    if not isinstance(steps, dict) or set(steps) != {"vlib", "vlog", "vsim"}:
        raise ReceiptFormatError("need all and only vlib/vlog/vsim original steps")
    if not isinstance(confirmed_steps, dict) or set(confirmed_steps) != set(steps):
        raise ReceiptFormatError("missing confirmed vlib/vlog/vsim plans")
    step_elapsed = 0.0
    streams: dict[str, tuple[str, str]] = {}
    for name in ("vlib", "vlog", "vsim"):
        step = steps[name]
        plan = confirmed_steps[name]
        if not isinstance(step, dict) or not isinstance(plan, dict):
            raise ReceiptFormatError(f"{name}: malformed step/plan")
        command = step.get("command")
        if (not isinstance(command, list) or not command
                or any(not isinstance(arg, str) or not arg for arg in command)):
            raise ReceiptFormatError(f"{name}: missing literal argument vector")
        cwd = step.get("cwd")
        if not isinstance(cwd, str) or not cwd:
            raise ReceiptFormatError(f"{name}: missing original cwd")
        tool = step.get("tool")
        if not isinstance(tool, dict):
            raise ReceiptFormatError(f"{name}: missing tool identity")
        for key in ("path", "version"):
            if not isinstance(tool.get(key), str) or not tool[key]:
                raise ReceiptFormatError(f"{name}: missing tool {key}")
        _normal_sha(tool.get("sha256"), f"{name}.tool.sha256")
        dependencies = tool.get("dependencies")
        if not isinstance(dependencies, list) or not dependencies:
            raise ReceiptFormatError(f"{name}: missing actual runtime dependencies")
        for dependency in dependencies:
            if not isinstance(dependency, dict) or not dependency.get("path"):
                raise ReceiptFormatError(f"{name}: malformed dependency")
            _normal_sha(dependency.get("sha256"), f"{name}.dependency.sha256")
        for key in ("command", "cwd", "tool"):
            if step[key] != plan.get(key):
                reasons.append(f"{name.upper()}_CONFIRMED_{key.upper()}_MISMATCH")
        elapsed = step.get("elapsed_seconds")
        budget = plan.get("budget_seconds")
        if (type(elapsed) not in (int, float) or type(budget) not in (int, float)
                or not math.isfinite(elapsed) or not math.isfinite(budget)
                or elapsed < 0 or budget <= 0):
            raise ReceiptFormatError(f"{name}: invalid elapsed/budget")
        step_elapsed += elapsed
        exit_code = step.get("exit_code")
        timeout = step.get("timed_out")
        if type(exit_code) is not int or type(timeout) is not bool:
            raise ReceiptFormatError(f"{name}: malformed process result")
        if exit_code != 0 or timeout or elapsed > budget:
            reasons.append(f"{name.upper()}_PROCESS_OR_BUDGET_FAILURE")
        stdout = _read_text(file_identity(root, step.get("stdout")))
        stderr = _read_text(file_identity(root, step.get("stderr")))
        streams[name] = (stdout, stderr)
        # Scan each stream independently: an unterminated stdout line must not
        # hide a diagnostic or manufacture a PASS at the start of stderr.
        for stream_name, text in (("stdout", stdout), ("stderr", stderr)):
            if _has_error_diagnostic(text):
                reasons.append(f"{name.upper()}_{stream_name.upper()}_DIAGNOSTIC")
            if re.search(r"\bsynthetic\b", text, re.IGNORECASE):
                reasons.append("SYNTHETIC_OR_UNDECLARED_EVIDENCE")
    if total_elapsed < step_elapsed:
        reasons.append("TOTAL_ELAPSED_LESS_THAN_STEPS")
    if not any(_COMPILE_PASS_RE.search(text) for text in streams["vlog"]):
        reasons.append("VLOG_COMPILE_SUCCESS_MISSING")
    marker = re.compile(rf"^\s*(?:#\s*)?{re.escape(R04_PASS_MARKER)}\s*$", re.MULTILINE)
    if not any(marker.search(text) for text in streams["vsim"]):
        reasons.append("VSIM_EXACT_PASS_MISSING")
    return {
        "status": "FAIL" if reasons else "CONSISTENT_PENDING_M2",
        "reasons": sorted(set(reasons)),
        "scope": "ORIGINAL_RECEIPT_CONSISTENCY_ONLY",
        "confirmation_reference": approved["reference"],
        "confirmation_sha256": confirmation_sha,
        "record_sha256": hashlib.sha256(record.read_bytes()).hexdigest(),
        "evidence_authenticity": "REQUIRES_INDEPENDENT_M2_REVIEW",
        "real_execution_validated": False,
        "per_request_deadline": "UNKNOWN",
        "board_release_allowed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--record", required=True, type=Path)
    parser.add_argument("--m2-confirmation", required=True, type=Path)
    parser.add_argument("--m2-confirmation-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = audit(
            args.evidence_root, args.record, args.m2_confirmation,
            args.m2_confirmation_sha256,
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "PENDING_OR_INVALID", "detail": str(exc),
                          "real_execution_validated": False}), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
