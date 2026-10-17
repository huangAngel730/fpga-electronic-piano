"""Verify a portable source identity bundle; never execute bundled inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath


SCHEMA = "M2_PRO_SAME_VERSION_STATIC_BINDING_V1"
STATUS = "PARTIAL_PENDING_PRO_MAPPING_TOOL_OR_PHYSICAL"
REFERENCE_COMMIT = "f32f1210d097fbe9292a3c34bbd9f50f57e1fb81"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"DUPLICATE_JSON_KEY: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def child(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("INVALID_RELATIVE_PATH")
    parts = PurePosixPath(value).parts
    if (PurePosixPath(value).is_absolute() or "\\" in value or ":" in value
            or value != "/".join(parts)
            or any(part in (".", "..") or part.endswith((".", " ")) for part in parts)):
        raise ValueError(f"UNSAFE_PATH: {value}")
    candidate = root.joinpath(*parts)
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"PATH_ESCAPES_ROOT: {value}")
    return candidate


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def verify(root: Path, expected: str) -> dict[str, object]:
    require(bool(re.fullmatch(r"[0-9a-f]{64}", expected)), "INVALID_EXPECTED_SHA256")
    manifest_path = root / "MANIFEST.json"
    require(digest(manifest_path.read_bytes()) == expected, "MANIFEST_SHA_MISMATCH")
    manifest = read_json(manifest_path)
    require(manifest.get("schema") == "M2_PRO_SOURCE_BUNDLE_MANIFEST_V1", "MANIFEST_SCHEMA")
    rows = manifest["files"]
    require(isinstance(rows, list) and bool(rows), "EMPTY_MANIFEST")
    seen: set[str] = set()
    for row in rows:
        relative = row["path"]
        path = child(root, relative)
        require(relative.casefold() not in seen, "DUPLICATE_PATH")
        seen.add(relative.casefold())
        require(path.is_file() and not path.is_symlink(), f"MISSING_FILE: {relative}")
        data = path.read_bytes()
        require(type(row["bytes"]) is int and len(data) == row["bytes"], f"SIZE_MISMATCH: {relative}")
        require(digest(data) == row["sha256"], f"FILE_SHA_MISMATCH: {relative}")
        require(path.suffix.lower() not in (".fs", ".bit", ".vcd", ".vvp"), "FORBIDDEN_ARTIFACT")
    actual = {p.relative_to(root).as_posix().casefold() for p in root.rglob("*") if p.is_file()}
    require(actual == seen | {"manifest.json"}, "UNLISTED_OR_MISSING_PAYLOAD")

    binding = read_json(root / "SOURCE_BINDING.json")
    require(binding.get("schema") == SCHEMA, "BINDING_SCHEMA")
    require(binding.get("scope") == "STATIC_SOURCE_IDENTITY_AND_OBSERVABILITY_ONLY", "SCOPE_ESCALATION")
    require(binding.get("status") == STATUS, "STATUS_ESCALATION")
    for name in ("pro_dut_pass", "board_release_allowed", "physical_ip_verified", "capture_completed"):
        require(binding.get(name) is False, f"FORBIDDEN_PASS_CLAIM: {name}")
    target = binding["target"]
    require(target.get("family_package_candidate") == "Tang Mega 138K Pro / FPG676", "WRONG_PACKAGE")
    for name in ("complete_device_symbol", "device_version", "actual_core_revision", "actual_dock_revision", "bank_voltage_verified"):
        require(target.get(name) is None, f"UNSUPPORTED_PHYSICAL_IDENTITY: {name}")
    require(binding["m3_reference"]["commit"] == REFERENCE_COMMIT, "M3_REFERENCE_VERSION")
    require(binding["source_basis"]["r05_archive_sha256"] == "dcf15f5d3ded1a0b160f55eab43066c728f80b3c329c44ea9f099c63f178696a", "R05_ARCHIVE_IDENTITY")
    require(digest((root / "originals/R05_SOURCE_ARCHIVE.zip").read_bytes()) == binding["source_basis"]["r05_archive_sha256"], "R05_ARCHIVE_CHANGED")
    closure = read_json(root / "source_closure/MANIFEST.json")
    require(len(closure["files"]) == 93, "P10_CLOSURE_COUNT")
    for row in closure["files"]:
        path = child(root / "source_closure", row["path"])
        require(path.is_file() and digest(path.read_bytes()) == row["sha256"], "P10_CLOSURE_CHANGED")
    roms = binding["roms"]
    require(len(roms) == 9 and len({r["path"] for r in roms}) == 9, "ROM_IDENTITY_COUNT")
    for row in roms:
        path = child(root, row["path"])
        require(path.is_file() and digest(path.read_bytes()) == row["sha256"], "ROM_IDENTITY_MISMATCH")
    mapping = read_json(root / "PUBLIC_OBSERVATION_MAP.json")
    contract = read_json(root / "references/B1_OBSERVATION_CONTRACT.json")
    fields = mapping["fields"]
    require(len(fields) == 61 and {f["name"] for f in fields} == {f["name"] for f in contract["fields"]}, "OBSERVATION_FIELD_SET")
    require(mapping.get("real_public_trace_exported") is False, "FALSE_EXPORT_CLAIM")
    categories = {"EXISTING_PUBLIC_PORT", "M2_INTERNAL_PENDING_CONTROLLED_EXPORT", "M1_INTERNAL_PENDING_OWNER_MAPPING", "NOT_IMPLEMENTED_IN_CURRENT_SOURCE"}
    for row in fields:
        require(row["category"] in categories, "OBSERVATION_CATEGORY")
        require(row.get("bound_at_pro_top") is (row["name"] in {"bclk", "ws", "din", "pa_en"}), "FALSE_TOP_PORT_CLAIM")
        for ref in row["references"]:
            path = child(root, ref["path"])
            require(digest(path.read_bytes()) == ref["sha256"], "OBSERVATION_REFERENCE_SHA")
            lines = path.read_text(encoding="utf-8").splitlines()
            require(type(ref["line"]) is int and 1 <= ref["line"] <= len(lines), "OBSERVATION_REFERENCE_LINE")
            require(ref["text"] == lines[ref["line"] - 1].strip(), "OBSERVATION_REFERENCE_TEXT")
    return {"result": "PASS_STATIC_SOURCE_IDENTITY_ONLY", "level": "L0_STATIC_SOURCE_AND_OBSERVABILITY", "files_verified": len(rows), "roms_verified": len(roms), "observation_fields": len(fields), "status": STATUS, "authority_verified": False, "real_trace_calendar_checked": False, "pro_dut_pass": False, "board_release_allowed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.artifact_root.resolve(), args.expected_manifest_sha256), ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({"result": "REJECTED", "reason": str(error), "pro_dut_pass": False, "board_release_allowed": False}, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
