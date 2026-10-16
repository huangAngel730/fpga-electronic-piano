"""Seal only this dispatch's new directories; prepare explicit Git allow-list."""
import ast
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
ROOTS = [
    "code/software/m3_r05_functional_integration_20261015/chat8_20261016",
    "code/docs/test/m3_r05_functional_integration_20261015/chat8_20261016",
    "code/software/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015/chat8_readiness_20261016",
    "code/docs/test/t052_publication_acceptance_20261012/LONG_WINDOW_PREPARATION_20261015/chat8_readiness_20261016",
    "code/docs/test/m3_m2td_audio_endpoint_audit_20261015/successor_R03/chat8_20261016",
    "code/docs/test/m3_dual_slider_138k_candidate_20261015/chat8_20261016",
    "code/software/m3_r04_receipt_audit_20261015/chat8_provenance_20261016",
    "code/docs/test/m3_r04_receipt_audit_20261015/chat8_provenance_20261016",
    HERE.relative_to(REPO).as_posix(),
]


def identity(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-own-draft", action="store_true")
    args = parser.parse_args()
    assert not subprocess.check_output(["git", "diff", "--name-only"], cwd=REPO)
    if not args.refresh_own_draft:
        assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=REPO)
    else:
        for name in ("M3_CHAT8_CHAT9_LIMITED_DELIVERY_20261016.zip", "DELIVERY_RECEIPT.json", "PUBLICATION_PLAN.json"):
            assert (HERE / name).read_bytes() == (HERE / "DRAFT_R01" / name).read_bytes(), name
        old_plan = json.loads((HERE / "DRAFT_R01/PUBLICATION_PLAN.json").read_text(encoding="utf-8"))
        staged = sorted(subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=REPO, text=True).splitlines())
        assert staged == old_plan["files"], "unrelated staged files"
    payloads = {}
    publication = set()
    for relative_root in ROOTS:
        directory = REPO / relative_root
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or any(p in {"__pycache__", "_test_tmp"} for p in path.parts):
                continue
            if directory == HERE:
                local = path.relative_to(HERE)
                if local.parts[0] in {"DRAFT_R01", "gate_R01", "gate_R02"} or path.name in {
                    "M3_CHAT8_CHAT9_LIMITED_DELIVERY_20261016.zip", "DELIVERY_RECEIPT.json", "PUBLICATION_PLAN.json",
                    "REPOSITORY_GATE_R01.zip", "REPOSITORY_GATE_R02.zip",
                }:
                    continue
            assert not path.is_symlink(), str(path)
            relative = path.relative_to(REPO).as_posix()
            assert path.suffix.lower() not in {".exe", ".dll", ".fs", ".vvp", ".wlf", ".vcd", ".pr"}, relative
            blob = path.read_bytes()
            assert len(blob) < 50 * 1024 * 1024, relative
            if path.suffix == ".py":
                ast.parse(blob, filename=relative)
            payloads[relative] = blob
            if path.parent == directory and path.suffix in {".py", ".md", ".txt", ".json"}:
                publication.add(relative)
    manifest = {"schema": "M3_CHAT8_CHAT9_LIMITED_DELIVERY_V1", "board_release_allowed": False,
                "new_business_RTL_EDA_device_calls": 0,
                "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
                "files": {name: identity(blob) for name, blob in payloads.items()}}
    package = HERE / "M3_CHAT8_CHAT9_LIMITED_DELIVERY_20261016.zip"
    mode = "w" if args.refresh_own_draft else "x"
    with zipfile.ZipFile(package, mode, zipfile.ZIP_DEFLATED) as archive:
        for relative, blob in payloads.items():
            archive.writestr(relative, blob)
        archive.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    with zipfile.ZipFile(package) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(payloads) | {"MANIFEST.json"}
        for name, blob in payloads.items():
            assert archive.read(name) == blob, name
    publication.add(package.relative_to(REPO).as_posix())
    receipt_path = HERE / "DELIVERY_RECEIPT.json"
    publication.add(receipt_path.relative_to(REPO).as_posix())
    plan_path = HERE / "PUBLICATION_PLAN.json"
    publication.add(plan_path.relative_to(REPO).as_posix())
    receipt = {"package": package.relative_to(REPO).as_posix(), **identity(package.read_bytes()),
               "payloads": len(payloads), "CRC_and_all_members_verified": True,
               "original_directories": ROOTS, "source_files": manifest["files"], "board_release_allowed": False}
    with receipt_path.open(mode, encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    with plan_path.open(mode, encoding="utf-8", newline="\n") as stream:
        json.dump({"files": sorted(publication), "count": len(publication),
                   "package": identity(package.read_bytes()), "status": "NOT_PUBLISHED"}, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"files_to_stage": len(publication), "payloads_sealed": len(payloads),
                      "package": str(package), **identity(package.read_bytes())}))


if __name__ == "__main__":
    main()
