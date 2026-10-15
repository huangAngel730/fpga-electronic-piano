#!/usr/bin/env python3
"""Create an R04 input identity snapshot without executing ModelSim."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any, Sequence

from receipt_check import (
    R04_ARCHIVE_SHA256,
    R04_MANIFEST_SHA256,
    ReceiptFormatError,
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_snapshot(package_path: Path, input_root: Path) -> dict[str, Any]:
    archive_sha = _sha256_file(package_path)
    if archive_sha != R04_ARCHIVE_SHA256:
        raise ReceiptFormatError(
            f"archive SHA mismatch: expected {R04_ARCHIVE_SHA256}, got {archive_sha}"
        )
    try:
        with zipfile.ZipFile(package_path) as archive:
            manifest_bytes = archive.read("MANIFEST.json")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ReceiptFormatError("invalid R04 archive or missing MANIFEST.json") from exc
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest_sha != R04_MANIFEST_SHA256:
        raise ReceiptFormatError(
            f"manifest SHA mismatch: expected {R04_MANIFEST_SHA256}, got {manifest_sha}"
        )
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    identities: dict[str, dict[str, int | str]] = {}
    missing: list[str] = []
    for member in manifest["members"]:
        target = input_root / Path(member)
        if not target.is_file():
            missing.append(member)
            continue
        identities[member] = {
            "bytes": target.stat().st_size,
            "sha256": _sha256_file(target),
        }
    if missing:
        raise ReceiptFormatError(
            f"input root lacks {len(missing)} expected member(s): {missing[:3]}"
        )
    manifest_on_disk = input_root / "MANIFEST.json"
    if not manifest_on_disk.is_file():
        raise ReceiptFormatError("input root lacks MANIFEST.json")
    return {
        "source_archive_sha256": archive_sha,
        "manifest_sha256": _sha256_file(manifest_on_disk),
        "members": identities,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hash the extracted, frozen R04 package; never launches EDA."
    )
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        print(f"R04_SNAPSHOT_INVALID: output already exists: {args.output}", file=sys.stderr)
        return 2
    try:
        payload = build_snapshot(args.package, args.input_root)
    except (OSError, ValueError, KeyError, ReceiptFormatError) as exc:
        print(f"R04_SNAPSHOT_INVALID: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"PASS R04_INPUT_SNAPSHOT members={len(payload['members'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
