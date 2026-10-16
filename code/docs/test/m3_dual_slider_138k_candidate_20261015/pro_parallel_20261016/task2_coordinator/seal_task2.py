"""Collect final immutable package receipts and original archives once."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

COORD = Path(__file__).resolve().parent
ROOT = COORD.parents[5]
OUT = COORD / "DELIVERY"


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def identity(path):
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def path_in_repo(name):
    path = (ROOT / name).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError("MISSING_OR_OUTSIDE_REPO:" + name)
    return path


def main():
    intake = json.loads((COORD / "INTAKE_FINAL.json").read_text(encoding="utf-8"))
    if intake["immutable_packages_received"] != ["E1", "E2", "E3", "E4"]:
        raise ValueError("ALL_FOUR_FINAL_INTAKES_REQUIRED")
    archives = []
    manifests = []
    nested_checks = []
    for entry in intake["original_archives"]:
        path = path_in_repo(entry["path"])
        if identity(path) != {k: entry[k] for k in ("bytes", "sha256")}:
            raise ValueError("ARCHIVE_IDENTITY:" + entry["path"])
        manifest_path = path_in_repo(entry["manifest_path"])
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
        rows = value if isinstance(value, list) else value.get("files", value.get("entries"))
        if rows is None:
            raise ValueError("UNRECOGNIZED_CHILD_MANIFEST:" + entry["manifest_path"])
        if isinstance(rows, dict):
            rows = [{"archive_path": key, **info} for key, info in rows.items()]
        names = set()
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            if bad is not None:
                raise ValueError("CHILD_ARCHIVE_CRC:" + entry["path"] + ":" + bad)
            for row in rows:
                name = row.get("archive_member", row.get("archive_path", row.get("path")))
                names.add(name)
                data = archive.read(name)
                if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
                    raise ValueError("CHILD_MEMBER_SIZE_SHA:" + entry["path"] + ":" + name)
            extras = set(archive.namelist()) - names
            if any(Path(name).name not in ("MANIFEST.json", "SEAL_MANIFEST.json") for name in extras):
                raise ValueError("UNLISTED_CHILD_MEMBERS:" + repr(extras))
            if len(archive.namelist()) != len(set(archive.namelist())):
                raise ValueError("DUPLICATE_CHILD_MEMBER")
        nested_checks.append({"archive": entry["path"], "listed_payloads": len(rows),
                              "extra_manifest_members": sorted(extras),
                              "manifest": identity(manifest_path), "CRC_size_SHA": "PASS"})
        archives.append(path)
        manifests.append(manifest_path)
    publication = set(intake["source_and_summary_publication_paths"])
    root_files = {p for p in COORD.iterdir() if p.is_file()}
    # Raw original task text remains byte-for-byte inside the ZIP. The active
    # index records its exact hash; Git need not normalize another loose copy.
    publication.update(p.relative_to(ROOT).as_posix() for p in root_files
                       if p.name not in ("USER_TASK_ORIGINAL.md", "PUBLICATION_FILES.json"))
    for name in ("M3_TASK2_FOUR_EXTENSIONS_ORIGINALS_20261017.zip",
                 "MANIFEST.json", "VERIFICATION.json", "DELIVERY.json"):
        publication.add((OUT / name).relative_to(ROOT).as_posix())
    publication.add((COORD / "PUBLICATION_FILES.json").relative_to(ROOT).as_posix())
    OUT.mkdir(exist_ok=False)
    save(COORD / "PUBLICATION_FILES.json", {
        "schema": "M3_TASK2_PUBLICATION_V1", "paths": sorted(publication),
        "policy": "Only new authorized task2 files; raw bytes retained in aggregate ZIP",
        "shared_status_and_numbered_documents_modified": False})
    payload = root_files | set(archives) | set(manifests) | {COORD / "PUBLICATION_FILES.json"}
    payload.update(path_in_repo(p) for p in intake["source_and_summary_publication_paths"])
    manifest = [{"path": p.relative_to(ROOT).as_posix(), **identity(p)}
                for p in sorted(payload)]
    save(OUT / "MANIFEST.json", {"schema": "M3_TASK2_ORIGINALS_V1", "files": manifest})
    target = OUT / "M3_TASK2_FOUR_EXTENSIONS_ORIGINALS_20261017.zip"
    with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for entry in manifest:
            archive.write(ROOT / entry["path"], entry["path"])
        archive.write(OUT / "MANIFEST.json", "MANIFEST.json")
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise ValueError("AGGREGATE_CRC")
        if set(archive.namelist()) != {e["path"] for e in manifest} | {"MANIFEST.json"}:
            raise ValueError("AGGREGATE_MEMBERS")
        for entry in manifest:
            data = archive.read(entry["path"])
            if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise ValueError("AGGREGATE_MEMBER:" + entry["path"])
    save(OUT / "VERIFICATION.json", {
        "status": "PASS", "payload_files": len(manifest), "members": len(manifest) + 1,
        "archive": {"path": target.relative_to(ROOT).as_posix(), **identity(target)},
        "nested_archives_crc_verified": len(archives), "nested_checks": nested_checks,
        "sizes_and_sha_verified": True})
    save(OUT / "DELIVERY.json", {
        "status": "PARTIAL_FULL_FEATURES_PENDING_FORMAL_PRO_AND_BOARD",
        "utc": datetime.now(timezone.utc).isoformat(),
        "archive": {"path": target.relative_to(ROOT).as_posix(), **identity(target)},
        "manifest": identity(OUT / "MANIFEST.json"),
        "verification": identity(OUT / "VERIFICATION.json"),
        "packages": intake["package_results"],
        "physical_rounds": 0, "hardware_calls": 0, "board_release_allowed": False,
        "publication_gate": "PENDING_SEPARATE_POST_SEAL_RECEIPT",
        "git": "NOT_COMMITTED_NOT_PUSHED_AT_SEAL",
        "human_handoff": "WAITING_FOR_USER_FORWARD_NOT_DELIVERED"})
    print(json.dumps({"archive": identity(target), "payload_files": len(manifest),
                      "publication_paths": len(publication)}))


if __name__ == "__main__":
    main()
