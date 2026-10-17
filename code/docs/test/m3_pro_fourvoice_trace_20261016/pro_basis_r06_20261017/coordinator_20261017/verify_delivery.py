from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[6]
SOFTWARE_ROOT = (
    REPO_ROOT
    / "code/software/m3_pro_fourvoice_trace_20261016"
    / "pro_basis_r06_20261017"
)
TB_ROOT = (
    REPO_ROOT
    / "code/tb/board/m3_pro_fourvoice_trace_20261016"
    / "pro_basis_r06_20261017"
)
EVIDENCE_ROOT = Path(__file__).resolve().parent.parent
STATUS_PATH = Path(__file__).resolve().with_name("PACKAGE_STATUS.json")
NORMALIZATION_PATH = Path(__file__).resolve().with_name(
    "POST_SEAL_WHITESPACE_NORMALIZATION.json"
)
EXPECTED_PACKAGES = {
    "source_target_audit",
    "midi_stimulus",
    "normalized_intake",
    "tool_plan_adapter",
    "event_calendar",
    "tx_clock_reset_checker",
    "hardware_identity",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    errors: list[str] = []
    python_files = sorted(SOFTWARE_ROOT.rglob("*.py"))
    json_files = sorted(
        path
        for root in (SOFTWARE_ROOT, TB_ROOT, EVIDENCE_ROOT)
        if root.exists()
        for path in root.rglob("*.json")
    )

    for path in python_files:
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except Exception as exc:  # pragma: no cover - delivery diagnostic
            errors.append(f"PYTHON {path.relative_to(REPO_ROOT)}: {exc}")

    for path in json_files:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - delivery diagnostic
            errors.append(f"JSON {path.relative_to(REPO_ROOT)}: {exc}")

    status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    archive_path = STATUS_PATH.parent / status["evidence_bundle"]["path"]
    actual_archive_hash = sha256(archive_path)
    expected_archive_hash = status["evidence_bundle"]["sha256"]
    if actual_archive_hash != expected_archive_hash:
        errors.append(
            "ARCHIVE_SHA: "
            f"expected {expected_archive_hash}, got {actual_archive_hash}"
        )

    with zipfile.ZipFile(archive_path) as archive:
        roots = {
            Path(name.replace("\\", "/")).parts[0]
            for name in archive.namelist()
            if name and not name.endswith("/")
        }
    if roots != EXPECTED_PACKAGES:
        errors.append(
            f"ARCHIVE_ROOTS: expected {sorted(EXPECTED_PACKAGES)}, got {sorted(roots)}"
        )

    normalization = json.loads(NORMALIZATION_PATH.read_text(encoding="utf-8"))
    for entry in normalization["files"]:
        path = REPO_ROOT / entry["path"]
        actual_hash = sha256(path)
        actual_bytes = path.stat().st_size
        if actual_hash != entry["after_sha256"]:
            errors.append(
                f"NORMALIZED_SHA {entry['path']}: "
                f"expected {entry['after_sha256']}, got {actual_hash}"
            )
        if actual_bytes != entry["after_bytes"]:
            errors.append(
                f"NORMALIZED_SIZE {entry['path']}: "
                f"expected {entry['after_bytes']}, got {actual_bytes}"
            )
        if entry["before_bytes"] != entry["after_bytes"] + 1:
            errors.append(f"NORMALIZATION_DELTA {entry['path']}: not exactly one byte")

    result = {
        "status": "PASS" if not errors else "FAIL",
        "python_files_compiled": len(python_files),
        "json_files_parsed": len(json_files),
        "archive_sha256": actual_archive_hash,
        "archive_roots": sorted(roots),
        "normalized_files_verified": len(normalization["files"]),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
