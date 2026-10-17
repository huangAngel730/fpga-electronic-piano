#!/usr/bin/env python3
"""Validate a Tang Mega 138K Pro hardware-identity evidence record.

This tool is deliberately fail-closed.  Reference schematics may describe a
candidate design, but they can never prove the identity or electrical state of
the physical unit on the bench.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


ALLOWED_STATUS = {"OBSERVED", "PENDING", "UNKNOWN", "NOT_APPLICABLE"}
REFERENCE_KINDS = {
    "OFFICIAL_SCHEMATIC",
    "OFFICIAL_DATASHEET",
    "REFERENCE_CST",
    "DERIVED_STATIC_AUDIT",
    "HISTORICAL_OTHER_BOARD",
}
PHYSICAL_KINDS = {
    "PHYSICAL_PHOTO",
    "RAW_MEASUREMENT_CSV",
    "INSTRUMENT_EXPORT",
    "CONTINUITY_LOG",
    "WAVEFORM_CSV",
    "PNP_ENUMERATION",
    "TOOL_FILE_IDENTITY",
    "TOOL_RUNTIME_RECEIPT",
}
SENSITIVE_KEY = re.compile(
    r"(^|_)(password|passwd|secret|token|private_key|license_key|license_server)($|_)",
    re.IGNORECASE,
)
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ValidationError(Exception):
    """A stable, user-facing validation failure."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot read JSON {path}: {exc}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be an object")
    return value


def _require_keys(obj: dict[str, Any], keys: set[str], label: str) -> None:
    missing = sorted(keys - obj.keys())
    if missing:
        raise ValidationError(f"{label} missing required field(s): {', '.join(missing)}")


def _require_exact_keys(
    obj: dict[str, Any], required: set[str], optional: set[str], label: str
) -> None:
    _require_keys(obj, required, label)
    extra = sorted(obj.keys() - required - optional)
    if extra:
        raise ValidationError(f"{label} has unknown field(s): {', '.join(extra)}")


def _scan_sensitive(value: Any, path: str = "record") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if SENSITIVE_KEY.search(str(key)):
                raise ValidationError(f"sensitive field prohibited: {path}.{key}")
            _scan_sensitive(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_sensitive(child, f"{path}[{index}]")
    elif isinstance(value, str) and "-----BEGIN PRIVATE KEY-----" in value:
        raise ValidationError(f"private-key material prohibited: {path}")


def _safe_repo_file(repo_root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValidationError("evidence path must be a non-empty string")
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValidationError(f"evidence path must be repo-relative: {relative}")
    root = repo_root.resolve()
    unresolved = root / candidate
    cursor = root
    for part in candidate.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValidationError(f"evidence path contains a symlink: {relative}")
    resolved = unresolved.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValidationError(f"evidence path escapes repository: {relative}") from exc
    if not resolved.is_file():
        raise ValidationError(f"evidence file missing or unsafe: {relative}")
    return resolved


def _validate_index(
    index: Any, repo_root: Path, allow_fixture: bool, record_fixture: bool
) -> dict[str, dict[str, Any]]:
    _scan_sensitive(index, "evidence_index")
    obj = _require_mapping(index, "evidence index")
    _require_exact_keys(
        obj,
        {"schema_version", "sources"},
        {"generated_for"},
        "evidence index",
    )
    if obj["schema_version"] != "hardware-evidence-index-v1":
        raise ValidationError("unsupported evidence index schema_version")
    if not isinstance(obj["sources"], list) or not obj["sources"]:
        raise ValidationError("evidence index sources must be a non-empty array")
    by_id: dict[str, dict[str, Any]] = {}
    for number, raw in enumerate(obj["sources"]):
        source = _require_mapping(raw, f"sources[{number}]")
        _require_exact_keys(
            source,
            {"id", "kind", "path", "sha256", "bytes", "applicability", "authority"},
            {"pages", "fixture_only", "unit_id", "session_id", "captured_at", "raw_metadata"},
            f"sources[{number}]",
        )
        source_id = source["id"]
        if not isinstance(source_id, str) or not source_id or source_id in by_id:
            raise ValidationError(f"sources[{number}].id invalid or duplicate")
        kind = source["kind"]
        if not isinstance(kind, str) or kind not in REFERENCE_KINDS | PHYSICAL_KINDS:
            raise ValidationError(f"source {source_id} has unsupported kind {kind!r}")
        for field in ("applicability", "authority"):
            if not isinstance(source[field], str) or not source[field].strip():
                raise ValidationError(f"source {source_id} {field} must be non-empty")
        is_fixture = source.get("fixture_only", False)
        if not isinstance(is_fixture, bool):
            raise ValidationError(f"source {source_id} fixture_only must be boolean")
        if is_fixture and (not allow_fixture or not record_fixture):
            raise ValidationError(f"fixture evidence prohibited for this record: {source_id}")
        if kind in PHYSICAL_KINDS:
            physical_fields = {"unit_id", "session_id", "captured_at", "raw_metadata"}
            missing_physical = sorted(physical_fields - source.keys())
            if missing_physical:
                raise ValidationError(
                    f"physical source {source_id} missing metadata: {', '.join(missing_physical)}"
                )
            if not all(
                isinstance(source[field], str) and source[field].strip()
                for field in ("unit_id", "session_id", "captured_at")
            ) or not isinstance(source["raw_metadata"], dict):
                raise ValidationError(f"physical source {source_id} metadata has wrong type")
        if kind == "OFFICIAL_SCHEMATIC":
            pages = source.get("pages")
            if not isinstance(pages, list) or not pages or not all(
                isinstance(page, int) and not isinstance(page, bool) and page > 0 for page in pages
            ):
                raise ValidationError(f"official schematic {source_id} requires positive page numbers")
        if not isinstance(source["sha256"], str) or not HEX_SHA256.fullmatch(source["sha256"]):
            raise ValidationError(f"source {source_id} has invalid sha256")
        path = _safe_repo_file(repo_root, source["path"])
        if not isinstance(source["bytes"], int) or isinstance(source["bytes"], bool) or source["bytes"] < 0:
            raise ValidationError(f"source {source_id} has invalid byte count")
        if path.stat().st_size != source["bytes"]:
            raise ValidationError(f"source {source_id} byte count mismatch")
        if _sha256(path) != source["sha256"]:
            raise ValidationError(f"source {source_id} sha256 mismatch")
        by_id[source_id] = source
    return by_id


def _validate_claim(
    claim: Any,
    label: str,
    sources: dict[str, dict[str, Any]],
    required_physical_kinds: set[str],
    unit_id: str,
    session_id: str,
) -> str:
    obj = _require_mapping(claim, label)
    _require_exact_keys(obj, {"status", "value", "evidence", "note"}, set(), label)
    status = obj["status"]
    if not isinstance(status, str) or status not in ALLOWED_STATUS:
        raise ValidationError(f"{label}.status unsupported: {status!r}")
    if status == "NOT_APPLICABLE":
        raise ValidationError(f"{label} is mandatory and cannot be NOT_APPLICABLE")
    if not isinstance(obj["note"], str) or not obj["note"].strip():
        raise ValidationError(f"{label}.note must be a non-empty string")
    evidence = obj["evidence"]
    if not isinstance(evidence, list) or not all(isinstance(x, str) for x in evidence):
        raise ValidationError(f"{label}.evidence must be an array of source ids")
    unknown_ids = sorted(set(evidence) - sources.keys())
    if unknown_ids:
        raise ValidationError(f"{label} references unknown evidence: {', '.join(unknown_ids)}")
    if status == "OBSERVED":
        if obj["value"] is None:
            raise ValidationError(f"{label} OBSERVED value cannot be null")
        physical = {sources[item]["kind"] for item in evidence} & PHYSICAL_KINDS
        if not physical:
            raise ValidationError(f"{label} falsely observed from reference evidence only")
        if required_physical_kinds and not (physical & required_physical_kinds):
            expected = ", ".join(sorted(required_physical_kinds))
            raise ValidationError(f"{label} lacks required physical evidence kind: {expected}")
        for item in evidence:
            source = sources[item]
            if source["kind"] in PHYSICAL_KINDS and (
                source.get("unit_id") != unit_id or source.get("session_id") != session_id
            ):
                raise ValidationError(f"{label} mixes a different physical unit/session")
            if source["kind"] == "HISTORICAL_OTHER_BOARD":
                raise ValidationError(f"{label} cannot use historical other-board evidence")
    elif status in {"PENDING", "UNKNOWN"}:
        if obj["value"] is not None:
            raise ValidationError(f"{label} {status} value must be null")
    return status


def validate(record: Any, index: Any, repo_root: Path, allow_fixture: bool = False) -> dict[str, Any]:
    _scan_sensitive(record)
    obj = _require_mapping(record, "record")
    _require_exact_keys(
        obj,
        {
            "schema_version",
            "record_id",
            "board_family",
            "fixture_only",
            "board_release_allowed",
            "unit_id",
            "session_id",
            "identity",
            "banks",
            "midi_input",
            "audio_path",
            "commercial_tools",
            "raw_evidence_requirements",
        },
        set(),
        "record",
    )
    if obj["schema_version"] != "hardware-identity-v1":
        raise ValidationError("unsupported record schema_version")
    if obj["board_family"] != "TANG_MEGA_138K_PRO":
        raise ValidationError("wrong board_family; expected TANG_MEGA_138K_PRO")
    if not isinstance(obj["fixture_only"], bool):
        raise ValidationError("fixture_only must be boolean")
    if obj["fixture_only"] and not allow_fixture:
        raise ValidationError("fixture record prohibited without --allow-fixture")
    if not all(
        isinstance(obj[field], str) and obj[field].strip()
        for field in ("record_id", "unit_id", "session_id")
    ):
        raise ValidationError("record_id, unit_id and session_id must be non-empty strings")
    if not isinstance(obj["board_release_allowed"], bool):
        raise ValidationError("board_release_allowed must be boolean")
    if obj["board_release_allowed"]:
        raise ValidationError("this validator cannot grant board release")
    sources = _validate_index(index, repo_root, allow_fixture, obj["fixture_only"])
    unit_id = obj["unit_id"]
    session_id = obj["session_id"]
    pending: list[str] = []

    identity = _require_mapping(obj["identity"], "identity")
    _require_exact_keys(
        identity,
        {"chip_marking", "chip_stepping", "core_revision", "dock_revision"},
        set(),
        "identity",
    )
    for name in ("chip_marking", "chip_stepping", "core_revision", "dock_revision"):
        status = _validate_claim(
            identity[name], f"identity.{name}", sources, {"PHYSICAL_PHOTO"}, unit_id, session_id
        )
        if status in {"PENDING", "UNKNOWN"}:
            pending.append(f"identity.{name}")
        elif not isinstance(identity[name]["value"], str) or not identity[name]["value"].strip():
            raise ValidationError(f"identity.{name} observed value must be a non-empty string")

    banks = obj["banks"]
    if not isinstance(banks, list):
        raise ValidationError("banks must be an array")
    numbers: list[int] = []
    for item in banks:
        bank_item = _require_mapping(item, "bank item")
        number = bank_item.get("bank")
        if not isinstance(number, int) or isinstance(number, bool):
            raise ValidationError("bank number must be an integer")
        numbers.append(number)
    if len(banks) != 3 or set(numbers) != {3, 4, 5} or len(set(numbers)) != 3:
        raise ValidationError("banks must contain exactly one each of Bank 3, 4 and 5")
    for item in banks:
        bank = _require_mapping(item, "bank item")
        _require_exact_keys(
            bank,
            {"bank", "expected_logic", "measurement", "assessment"},
            set(),
            f"Bank {bank.get('bank')}",
        )
        if not isinstance(bank["expected_logic"], str) or not bank["expected_logic"].strip():
            raise ValidationError(f"Bank {bank['bank']} expected_logic must be non-empty")
        if bank["assessment"] not in {"UNASSESSED", "MATCH", "CONFLICT"}:
            raise ValidationError(f"Bank {bank['bank']} assessment unsupported")
        label = f"banks[{bank['bank']}].measurement"
        status = _validate_claim(
            bank["measurement"],
            label,
            sources,
            {"RAW_MEASUREMENT_CSV", "INSTRUMENT_EXPORT"},
            unit_id,
            session_id,
        )
        if bank["assessment"] == "CONFLICT":
            raise ValidationError(f"Bank {bank['bank']} voltage conflict")
        if status == "OBSERVED":
            value = _require_mapping(bank["measurement"]["value"], f"{label}.value")
            _require_keys(
                value,
                {"voltage_v", "unit", "test_point", "ground_reference", "instrument", "range", "captured_at"},
                f"{label}.value",
            )
            voltage = value["voltage_v"]
            if (
                value["unit"] != "V"
                or not isinstance(voltage, (int, float))
                or isinstance(voltage, bool)
                or not math.isfinite(voltage)
                or voltage < 0
                or voltage > 5.5
            ):
                raise ValidationError(f"{label} requires a numeric voltage in V")
            for field in ("test_point", "ground_reference", "instrument", "range", "captured_at"):
                if not isinstance(value[field], str) or not value[field].strip():
                    raise ValidationError(f"{label}.value.{field} must be non-empty")
            if bank["assessment"] != "MATCH":
                raise ValidationError(f"Bank {bank['bank']} observed measurement must be assessed MATCH")
        else:
            pending.append(label)

    midi = _require_mapping(obj["midi_input"], "midi_input")
    _require_exact_keys(
        midi,
        {"direction", "fpga_side_voltage", "common_ground"},
        set(),
        "midi_input",
    )
    midi_evidence = {
        "direction": {"RAW_MEASUREMENT_CSV", "INSTRUMENT_EXPORT"},
        "fpga_side_voltage": {"RAW_MEASUREMENT_CSV", "INSTRUMENT_EXPORT", "WAVEFORM_CSV"},
        "common_ground": {"CONTINUITY_LOG", "INSTRUMENT_EXPORT"},
    }
    for name in midi:
        label = f"midi_input.{name}"
        status = _validate_claim(
            midi[name],
            label,
            sources,
            midi_evidence[name],
            unit_id,
            session_id,
        )
        if status in {"PENDING", "UNKNOWN"}:
            pending.append(label)
    if all(midi[name]["status"] == "OBSERVED" for name in midi):
        if midi["direction"]["value"] != "ADAPTER_OUTPUT_TO_FPGA_INPUT":
            raise ValidationError("midi_input.direction must be ADAPTER_OUTPUT_TO_FPGA_INPUT")
        voltage = _require_mapping(midi["fpga_side_voltage"]["value"], "midi_input.fpga_side_voltage.value")
        _require_exact_keys(voltage, {"idle_v", "high_v", "low_v", "unit", "connector_pin"}, set(), "midi_input.fpga_side_voltage.value")
        for field in ("idle_v", "high_v", "low_v"):
            number = voltage[field]
            if (
                not isinstance(number, (int, float))
                or isinstance(number, bool)
                or not math.isfinite(number)
                or number < 0
                or number > 5.5
            ):
                raise ValidationError(f"midi_input.fpga_side_voltage.value.{field} must be finite numeric")
        if voltage["unit"] != "V" or not isinstance(voltage["connector_pin"], str) or not voltage["connector_pin"].strip():
            raise ValidationError("midi_input voltage unit/connector_pin invalid")
        if midi["common_ground"]["value"] is not True:
            raise ValidationError("midi_input.common_ground must be true when observed")

    audio = _require_mapping(obj["audio_path"], "audio_path")
    _require_exact_keys(
        audio,
        {"pt8211_identity", "serial_wiring", "pa_path", "safe_load"},
        set(),
        "audio_path",
    )
    audio_evidence = {
        "pt8211_identity": {"PHYSICAL_PHOTO"},
        "serial_wiring": {"CONTINUITY_LOG", "WAVEFORM_CSV", "INSTRUMENT_EXPORT"},
        "pa_path": {"CONTINUITY_LOG", "WAVEFORM_CSV", "INSTRUMENT_EXPORT"},
        "safe_load": {"PHYSICAL_PHOTO"},
    }
    for name in audio:
        label = f"audio_path.{name}"
        status = _validate_claim(
            audio[name], label, sources, audio_evidence[name], unit_id, session_id
        )
        if status in {"PENDING", "UNKNOWN"}:
            pending.append(label)
    if audio["pt8211_identity"]["status"] == "OBSERVED":
        value = _require_mapping(audio["pt8211_identity"]["value"], "audio_path.pt8211_identity.value")
        _require_exact_keys(value, {"component", "reference_designator", "marking"}, set(), "audio_path.pt8211_identity.value")
        if not all(isinstance(value[field], str) and value[field].strip() for field in value):
            raise ValidationError("audio_path.pt8211_identity.value fields must be non-empty strings")
    if audio["serial_wiring"]["status"] == "OBSERVED":
        value = _require_mapping(audio["serial_wiring"]["value"], "audio_path.serial_wiring.value")
        _require_exact_keys(value, {"bck", "ws", "din", "method"}, set(), "audio_path.serial_wiring.value")
        if not all(isinstance(value[field], str) and value[field].strip() for field in value):
            raise ValidationError("audio_path.serial_wiring.value fields must be non-empty strings")
    if audio["pa_path"]["status"] == "OBSERVED":
        value = _require_mapping(audio["pa_path"]["value"], "audio_path.pa_path.value")
        _require_exact_keys(value, {"component", "enable_pin", "enable_polarity", "method"}, set(), "audio_path.pa_path.value")
        if not all(isinstance(value[field], str) and value[field].strip() for field in value):
            raise ValidationError("audio_path.pa_path.value fields must be non-empty strings")
    if audio["safe_load"]["status"] == "OBSERVED":
        value = _require_mapping(audio["safe_load"]["value"], "audio_path.safe_load.value")
        _require_exact_keys(value, {"connector", "load_type", "rated_impedance"}, set(), "audio_path.safe_load.value")
        if not all(isinstance(value[field], str) and value[field].strip() for field in value):
            raise ValidationError("audio_path.safe_load.value fields must be non-empty strings")

    tools = obj["commercial_tools"]
    if not isinstance(tools, list) or not tools:
        raise ValidationError("commercial_tools must be a non-empty array")
    for item in tools:
        tool = _require_mapping(item, "commercial tool")
        _require_exact_keys(
            tool,
            {"name", "binary_identity", "runtime_license"},
            set(),
            "commercial tool",
        )
        if not isinstance(tool["name"], str) or not tool["name"].strip():
            raise ValidationError("commercial tool name must be non-empty")
        for name, physical in (
            ("binary_identity", {"TOOL_FILE_IDENTITY"}),
            ("runtime_license", {"TOOL_RUNTIME_RECEIPT"}),
        ):
            label = f"commercial_tools[{tool['name']}].{name}"
            status = _validate_claim(
                tool[name], label, sources, physical, unit_id, session_id
            )
            if status in {"PENDING", "UNKNOWN"}:
                pending.append(label)
            elif name == "binary_identity":
                value = _require_mapping(tool[name]["value"], f"{label}.value")
                _require_exact_keys(
                    value,
                    {"path", "bytes", "sha256", "version"},
                    set(),
                    f"{label}.value",
                )
                if not isinstance(value["path"], str) or not value["path"].strip():
                    raise ValidationError(f"{label}.value.path must be non-empty")
                if not isinstance(value["bytes"], int) or isinstance(value["bytes"], bool) or value["bytes"] < 0:
                    raise ValidationError(f"{label}.value.bytes invalid")
                if not isinstance(value["sha256"], str) or not HEX_SHA256.fullmatch(value["sha256"]):
                    raise ValidationError(f"{label}.value.sha256 invalid")
                if not isinstance(value["version"], str) or not value["version"].strip():
                    raise ValidationError(f"{label}.value.version must be non-empty")
            else:
                value = _require_mapping(tool[name]["value"], f"{label}.value")
                _require_exact_keys(
                    value,
                    {"status", "command", "exit_code", "captured_at"},
                    set(),
                    f"{label}.value",
                )
                if value["status"] not in {"AVAILABLE", "UNAVAILABLE"}:
                    raise ValidationError(f"{label}.value.status invalid")
                if not isinstance(value["command"], list) or not all(isinstance(part, str) for part in value["command"]):
                    raise ValidationError(f"{label}.value.command invalid")
                if not isinstance(value["exit_code"], int) or isinstance(value["exit_code"], bool):
                    raise ValidationError(f"{label}.value.exit_code invalid")
                if not isinstance(value["captured_at"], str) or not value["captured_at"].strip():
                    raise ValidationError(f"{label}.value.captured_at invalid")

    requirements = obj["raw_evidence_requirements"]
    if not isinstance(requirements, list) or not all(isinstance(item, str) for item in requirements):
        raise ValidationError("raw_evidence_requirements must be an array")
    required = {"board_photos", "raw_measurement_csv", "official_source_pages", "instrument_metadata"}
    if set(requirements) != required:
        raise ValidationError("raw_evidence_requirements is incomplete or contains unknown items")
    return {
        "result": "VALID_PENDING" if pending else "VALID_COMPLETE",
        "record_id": obj["record_id"],
        "board_release_allowed": obj["board_release_allowed"],
        "pending": sorted(pending),
        "source_count": len(sources),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--allow-fixture", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = validate(
            _load_json(args.record),
            _load_json(args.index),
            args.repo_root,
            args.allow_fixture,
        )
        result["exit_code"] = 0
        text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
        sys.stdout.write(text)
        return 0
    except ValidationError as exc:
        result = {"result": "REJECTED", "reason": str(exc), "exit_code": 2}
        text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
        sys.stderr.write(text)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
