"""Fail-closed verification for a local T056 138K SRAM-only release bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DEVICE = "GW5AST-138C"
EXPECTED_PART = "GW5AST-LV138PG484AC1/I0"
EXPECTED_BITSTREAM_SHA256 = (
    "598ec9bdf4fe20718f0f0a79a94cc6daed518103c1c4007ce2fec6231f2fff48"
)
EXPECTED_SOURCE_COMMIT = "0bb5c66862dcbd9dc3894b055d9703e2b3cd0e76"
EXPECTED_BUILD_COMMIT = "a0cb805"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_output(path: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to((ROOT / "code/output").resolve())
    return resolved


def check(release: Path) -> dict[str, object]:
    release = require_output(release)
    manifest_path = release / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if manifest.get("release_kind") != "SRAM-only":
        errors.append("release kind is not SRAM-only")
    if manifest.get("device") != EXPECTED_DEVICE:
        errors.append("device mismatch")
    if manifest.get("part") != EXPECTED_PART:
        errors.append("part mismatch")
    if manifest.get("source_commit") != EXPECTED_SOURCE_COMMIT:
        errors.append("source commit mismatch")
    if manifest.get("build_runner_commit") != EXPECTED_BUILD_COMMIT:
        errors.append("build runner commit mismatch")
    if manifest.get("programmed") is not False:
        errors.append("release claims programming")
    if manifest.get("flash_modified") is not False:
        errors.append("release claims flash modification")
    if manifest.get("programmer_operation_index") != 2:
        errors.append("operation index is not SRAM Program")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        errors.append("file manifest missing")
        files = {}
    for relative, record in files.items():
        path = (release / relative).resolve()
        try:
            path.relative_to(release)
        except ValueError:
            errors.append("manifest path escapes release: " + relative)
            continue
        if not path.is_file():
            errors.append("missing release file: " + relative)
            continue
        if path.stat().st_size != record.get("bytes"):
            errors.append("size mismatch: " + relative)
        if sha256(path) != record.get("sha256"):
            errors.append("SHA mismatch: " + relative)
    bitstream = release / manifest.get("bitstream", "")
    if not bitstream.is_file() or sha256(bitstream) != EXPECTED_BITSTREAM_SHA256:
        errors.append("bitstream SHA mismatch")
    assessment = json.loads((release / "evidence/assessment.json").read_text(encoding="utf-8"))
    build_receipt = json.loads(
        (release / "evidence/build_receipt.json").read_text(encoding="utf-8")
    )
    if not assessment.get("passed") or assessment.get("board_release_allowed") is not False:
        errors.append("assessment identity or release boundary mismatch")
    if (
        build_receipt.get("exit_code") != 0
        or build_receipt.get("attempt_count") != 1
        or build_receipt.get("timed_out") is not False
        or build_receipt.get("programmed") is not False
    ):
        errors.append("build receipt contract mismatch")
    result = {
        "date": "2026-10-06",
        "release": str(release),
        "manifest_sha256": sha256(manifest_path),
        "bitstream_sha256": sha256(bitstream) if bitstream.is_file() else None,
        "file_count": len(files),
        "errors": errors,
        "passed": not errors,
        "programmed": False,
        "flash_modified": False,
        "board_release_allowed": False,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    try:
        result = check(args.release)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        result = {
            "date": "2026-10-06",
            "passed": False,
            "errors": ["missing or malformed release: " + str(error)],
            "programmed": False,
            "flash_modified": False,
            "board_release_allowed": False,
        }
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.json:
        destination = args.json.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
