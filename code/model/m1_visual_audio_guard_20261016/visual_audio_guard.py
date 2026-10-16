"""Compare two complete, aligned audio-frame contracts without hardware claims.

This M1-B model consumes exported rows. It does not capture data, inspect CDC,
run HDL, authenticate a capture, or sign off a visual integration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


FRAME_SCHEMA = "M1_VISUAL_AUDIO_FRAMES_V1"
CONTRACT_SCHEMA = "M1_VISUAL_AUDIO_COMPARE_CONTRACT_V1"
SOURCE_KINDS = {"SYNTHETIC_FRAME_CONTRACT_ONLY", "REAL_CAPTURE_DERIVED"}
ROOT_KEYS = {
    "schema", "source_kind", "clock_hz", "sample_rate_hz",
    "input_events_sha256", "basis_sha256", "window", "frames",
}
CONTRACT_KEYS = ROOT_KEYS - {"source_kind", "frames"}
WINDOW_KEYS = {"first_cycle", "last_cycle", "expected_frames"}
FRAME_KEYS = {
    "epoch", "frame", "cycle", "rst_n", "commit_seq", "commit_id",
    "commit_cycle", "pcm_left", "pcm_right", "underflow", "clip_count",
}
IDENTITY_KEYS = {
    "clock_hz", "sample_rate_hz", "input_events_sha256", "basis_sha256",
    "window",
}
SHA_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class ContractError(ValueError):
    """The input is malformed, incomplete, inconsistent, or differs."""


def _reject_constant(value: str) -> None:
    raise ContractError(f"non-finite JSON number: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ContractError(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def strict_json(text: str) -> Any:
    """Reject duplicate keys at every level and non-standard JSON numbers."""
    try:
        return json.loads(
            text, object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ContractError(f"invalid JSON: {exc}") from exc


def read_json(path: Path) -> Any:
    try:
        return strict_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise ContractError(f"cannot read JSON {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ContractError(f"cannot hash {path}: {exc}") from exc


def _object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        actual = sorted(value) if type(value) is dict else type(value).__name__
        raise ContractError(f"{label}: expected exact keys {sorted(keys)}, got {actual}")
    return value


def _int(value: Any, label: str, low: int = 0, high: int | None = None) -> int:
    if type(value) is not int or value < low or (high is not None and value > high):
        raise ContractError(f"{label}: integer outside [{low}, {high}]")
    return value


def _sha(value: Any, label: str) -> str:
    if type(value) is not str or not SHA_PATTERN.fullmatch(value):
        raise ContractError(f"{label}: expected lowercase SHA-256")
    return value


def _validate_identity(value: dict[str, Any], label: str) -> None:
    if _int(value["clock_hz"], label + ".clock_hz") != 40_000_000:
        raise ContractError(f"{label}: expected 40000000 Hz system clock")
    if _int(value["sample_rate_hz"], label + ".sample_rate_hz") != 48_000:
        raise ContractError(f"{label}: expected 48000 Hz design sample rate")
    _sha(value["basis_sha256"], label + ".basis_sha256")
    _sha(value["input_events_sha256"], label + ".input_events_sha256")
    window = _object(value["window"], WINDOW_KEYS, label + ".window")
    first = _int(window["first_cycle"], label + ".first_cycle")
    last = _int(window["last_cycle"], label + ".last_cycle", first)
    expected = _int(window["expected_frames"], label + ".expected_frames", 1)
    if expected > last - first + 1:
        raise ContractError(f"{label}: expected_frames exceeds inclusive cycle window")


def validate_contract(contract: Any, actual_basis_sha256: str) -> dict[str, Any]:
    contract = _object(contract, CONTRACT_KEYS, "contract")
    if contract["schema"] != CONTRACT_SCHEMA:
        raise ContractError("contract: unsupported schema")
    _validate_identity(contract, "contract")
    if contract["basis_sha256"] != _sha(actual_basis_sha256, "actual_basis_sha256"):
        raise ContractError("contract: actual A basis file SHA mismatch")
    return contract


def validate_frames(document: Any, contract: dict[str, Any], label: str) -> dict[str, Any]:
    """Validate the deliberately narrow export format described in the README."""
    document = _object(document, ROOT_KEYS, label)
    if document["schema"] != FRAME_SCHEMA:
        raise ContractError(f"{label}: unsupported schema")
    if type(document["source_kind"]) is not str or document["source_kind"] not in SOURCE_KINDS:
        raise ContractError(f"{label}: invalid source_kind")
    _validate_identity(document, label)
    for key in sorted(IDENTITY_KEYS):
        if document[key] != contract[key]:
            raise ContractError(f"{label}: frozen contract mismatch at {key}")
    frames = document["frames"]
    if type(frames) is not list or len(frames) != contract["window"]["expected_frames"]:
        raise ContractError(f"{label}: incomplete frame count")
    previous: dict[str, Any] | None = None
    observed_commit = False
    for index, value in enumerate(frames):
        row_label = f"{label}.frames[{index}]"
        row = _object(value, FRAME_KEYS, row_label)
        for key in ("epoch", "frame", "cycle", "commit_seq", "clip_count"):
            _int(row[key], row_label + "." + key)
        for key in ("rst_n", "underflow"):
            _int(row[key], row_label + "." + key, 0, 1)
        for key in ("pcm_left", "pcm_right"):
            _int(row[key], row_label + "." + key, -(1 << 23), (1 << 23) - 1)
        for key in ("commit_id", "commit_cycle"):
            if row[key] is not None:
                _int(row[key], row_label + "." + key)
        if row["commit_seq"] == 0:
            if row["commit_id"] is not None or row["commit_cycle"] is not None:
                raise ContractError(f"{row_label}: zero sequence has commit identity")
            if row["pcm_left"] != 0 or row["pcm_right"] != 0:
                raise ContractError(f"{row_label}: nonzero PCM before first commit")
        elif row["commit_id"] is None or row["commit_cycle"] is None:
            raise ContractError(f"{row_label}: nonzero sequence lacks commit identity")
        if row["commit_cycle"] is not None and row["commit_cycle"] > row["cycle"]:
            raise ContractError(f"{row_label}: commit later than observation boundary")
        if row["rst_n"] == 0:
            if any(row[k] != 0 for k in ("commit_seq", "pcm_left", "pcm_right", "underflow", "clip_count")):
                raise ContractError(f"{row_label}: reset row not cleared")
        if previous is None:
            if row["epoch"] != 0 or row["frame"] != 0:
                raise ContractError(f"{row_label}: window must start at epoch/frame zero")
            if row["cycle"] != contract["window"]["first_cycle"]:
                raise ContractError(f"{row_label}: missing first boundary")
        else:
            if row["cycle"] <= previous["cycle"]:
                raise ContractError(f"{row_label}: cycle not strictly increasing")
            reset_entry = previous["rst_n"] == 1 and row["rst_n"] == 0
            expected_epoch = previous["epoch"] + int(reset_entry)
            expected_frame = 0 if reset_entry else previous["frame"] + 1
            if row["epoch"] != expected_epoch or row["frame"] != expected_frame:
                raise ContractError(f"{row_label}: missing/duplicate/reordered frame or reset epoch")
            if not reset_entry:
                if row["commit_seq"] < previous["commit_seq"] or row["commit_seq"] > previous["commit_seq"] + 1:
                    raise ContractError(f"{row_label}: commit sequence skipped or regressed")
                if row["clip_count"] < previous["clip_count"]:
                    raise ContractError(f"{row_label}: clip_count regressed")
                if row["commit_seq"] == previous["commit_seq"]:
                    for key in ("commit_id", "commit_cycle", "pcm_left", "pcm_right"):
                        if row[key] != previous[key]:
                            raise ContractError(f"{row_label}: changed {key} without new commit")
                elif row["commit_cycle"] <= previous["cycle"]:
                    raise ContractError(f"{row_label}: new commit not in observed interval")
                elif previous["commit_id"] is not None and row["commit_id"] <= previous["commit_id"]:
                    raise ContractError(f"{row_label}: new commit_id not increasing within epoch")
            if previous["rst_n"] == 1 and row["rst_n"] == 1:
                gap = row["cycle"] - previous["cycle"]
                if gap not in (833, 834):
                    raise ContractError(f"{row_label}: frame cadence outside 833/834 cycles")
        if row["rst_n"] == 1 and row["commit_seq"] > 0:
            observed_commit = True
        previous = row
    if frames[-1]["cycle"] != contract["window"]["last_cycle"]:
        raise ContractError(f"{label}: missing final boundary")
    if not observed_commit:
        raise ContractError(f"{label}: no active committed frame in selected window")
    return document


def compare_documents(before: Any, after: Any, contract: Any, actual_basis_sha256: str) -> dict[str, Any]:
    """Return equality of the exported frame contract; mismatch raises."""
    contract = validate_contract(contract, actual_basis_sha256)
    before = validate_frames(before, contract, "before")
    after = validate_frames(after, contract, "after")
    if before["source_kind"] != after["source_kind"]:
        raise ContractError("source_kind differs; synthetic and real inputs cannot be combined")
    for index, (left, right) in enumerate(zip(before["frames"], after["frames"])):
        for key in sorted(FRAME_KEYS):
            if left[key] != right[key]:
                raise ContractError(f"frame[{index}] mismatch at {key}: {left[key]!r} != {right[key]!r}")
    return {
        "schema": "M1_VISUAL_AUDIO_GUARD_RESULT_V1",
        "comparison_result": "FRAME_CONTRACT_EQUAL",
        "source_kind_claim": before["source_kind"],
        "evidence_level": "L0_SOFTWARE_FRAME_CONTRACT",
        "visual_audio_nondegradation": "NOT_SIGNED_BY_THIS_SOFTWARE",
        "real_result": "PENDING_REAL_CAPTURE" if before["source_kind"] == "SYNTHETIC_FRAME_CONTRACT_ONLY" else "PENDING_RAW_CAPTURE_AND_M2_IDENTITY_REVIEW",
        "basis_sha256": contract["basis_sha256"],
        "input_events_sha256": contract["input_events_sha256"],
        "window": contract["window"],
        "compared_frames": len(before["frames"]),
        "pcm_tolerance_lsb": 0,
        "deadline_result": "NOT_EVALUATED_BY_THIS_CONTRACT",
        "board_release_allowed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("before", "after", "contract", "basis", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        paths = {name: getattr(args, name).resolve() for name in ("before", "after", "contract", "basis")}
        output = args.output.resolve()
        if output in paths.values():
            raise ContractError("output must not be an input path")
        raw = {name: path.read_bytes() for name, path in paths.items()}
        result = compare_documents(
            strict_json(raw["before"].decode("utf-8")),
            strict_json(raw["after"].decode("utf-8")),
            strict_json(raw["contract"].decode("utf-8")),
            hashlib.sha256(raw["basis"]).hexdigest(),
        )
        result["files"] = {name: {"path": str(path), "sha256": hashlib.sha256(raw[name]).hexdigest()} for name, path in paths.items()}
        if any(path.read_bytes() != raw[name] for name, path in paths.items()):
            raise ContractError("input bytes changed during comparison")
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
    except (ContractError, OSError, UnicodeError, TypeError, RecursionError) as exc:
        print(f"REJECT M1_VISUAL_AUDIO_FRAME_CONTRACT: {exc}", file=sys.stderr)
        return 2
    print(f"ACCEPT M1_VISUAL_AUDIO_FRAME_CONTRACT_ONLY frames={result['compared_frames']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
