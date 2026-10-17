"""Seal C9 static deltas while preserving the earlier ten original volumes."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[5]
SUFFIX = Path("m3_pro_fourvoice_trace_20261016")
DOC = ROOT / "code/docs/test" / SUFFIX / "pro_basis_r08_20261017/coordinator"
NEW = "16ac226552f6fb65347b229b8fad42146ed45644"


def ident(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def relative(path):
    return path.relative_to(ROOT).as_posix()


def main():
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    assert head == NEW
    baseline = json.loads((DOC / "PUBLICATION_BASELINE_C9.json").read_text(encoding="utf-8"))
    for name, expected in baseline.items():
        assert ident((ROOT / name).read_bytes()) == expected, "PUBLISHED_BASE_CHANGED:" + name
    old_index_raw = (DOC / "INDEX_RECEIPT.json").read_bytes()
    old_index = json.loads(old_index_raw)
    old_plan_raw = (DOC / "PUBLICATION_FILES.json").read_bytes()
    old_plan = json.loads(old_plan_raw)
    mutable_metadata = {relative(DOC / name) for name in (
        "PLAN.md", "RESULT.md", "PACKAGE_STATUS.json",
        "M2_DECISION_REQUESTS.json", "SELF_REVIEW.md",
    )}
    mutable_metadata.add(relative(Path(__file__).parent / "final_handoff.py"))
    changed = {}
    for name, expected in old_index["files"].items():
        current = ident((ROOT / name).read_bytes())
        if current != expected:
            assert name in mutable_metadata, "OLD_FROZEN_FILE_CHANGED:" + name
            changed[name] = {"before": expected, "after": current}
    packages = ROOT / "code/docs/test" / SUFFIX / "pro_basis_r07_20261017"
    b_folder = packages / "public_equivalence_tb/c9_binding"
    b_binding = json.loads((b_folder / "SOURCE_BINDING.json").read_text(encoding="utf-8"))
    b_checked = {}
    for entry in b_binding["staged_files"]:
        path = (b_folder / entry["stored_path"]).resolve()
        assert path.is_relative_to(b_folder.resolve()), "B_SOURCE_ESCAPE"
        actual = ident(path.read_bytes())
        assert actual == {k: entry[k] for k in ("bytes", "sha256")}, entry["stored_path"]
        assert entry["stored_path"] not in b_checked, "DUPLICATE_B_STORED_PATH"
        b_checked[entry["stored_path"]] = actual
    c9_intake = json.loads((DOC / "C9_INTAKE_RECEIPT.json").read_text(encoding="utf-8"))
    with zipfile.ZipFile(packages / "public_capture_tb/c9_binding/SOURCE_APPLICATION_C9.zip") as archive:
        assert archive.testzip() is None
        for name, expected in c9_intake["C9_payloads"].items():
            assert ident(archive.read(name)) == expected, "A_C9_ORIGINAL_CHANGED:" + name
    out = DOC / "DELIVERY_C9"
    out.mkdir(exist_ok=False)
    (out / "PRE_C9_INDEX_RECEIPT.json").write_bytes(old_index_raw)
    (out / "PRE_C9_PUBLICATION_FILES.json").write_bytes(old_plan_raw)
    selected = set(changed)
    direct = set(old_plan["paths"])
    for prefix in ("code/software", "code/tb/board", "code/docs/test"):
        base = ROOT / prefix / SUFFIX
        for version, package in (("pro_basis_r07_20261017", "public_capture_tb"), ("pro_basis_r07_20261017", "public_equivalence_tb"), ("pro_basis_r07_20261017", "oracle_bundle_bridge"), ("pro_basis_r08_20261017", "public_port_map")):
            for path in sorted((base / version / package / "c9_binding").rglob("*")):
                if not path.is_file() or "__pycache__" in path.parts:
                    continue
                name = relative(path)
                selected.add(name)
                # Generated raw closure members remain intact in the capsule;
                # source/code and small contracts are also ordinary Git files.
                nested = path.relative_to(base / version / package / "c9_binding").parts
                generated_raw = any(p in {"inputs", "sources", "source_closure", "rom", "RAW", "INPUT_ORIGINALS", "SOURCE_STORE"} for p in nested[:-1])
                if prefix != "code/docs/test" or (not generated_raw and path.suffix in {".md", ".json", ".f", ".zip", ".sv", ".svh", ".py"}):
                    direct.add(name)
    root_documents = ["PLAN.md", "RESULT.md", "PACKAGE_STATUS.json", "M2_DECISION_REQUESTS.json", "SELF_REVIEW.md", "M2_C9_PUBLICATION_ADVANCE.json", "C9_INTAKE_RECEIPT.json", "C9_INTEGRATION.md", "PUBLICATION_BASELINE_C9.json"]
    for name in root_documents:
        path = DOC / name
        assert path.is_file(), path
        selected.add(relative(path))
        if name != "PUBLICATION_BASELINE_C9.json":
            direct.add(relative(path))
    for path in DOC.glob("COLLECT_C9*.json"):
        selected.add(relative(path))
        direct.add(relative(path))
    for path in (DOC / "dependency_audit").glob("*C9*"):
        if path.is_file():
            selected.add(relative(path))
            direct.add(relative(path))
    for path in Path(__file__).parent.glob("*.py"):
        name = relative(path)
        if name not in old_index["files"] or name in changed:
            selected.add(name)
            direct.add(name)
    dependencies = [ROOT / "code/docs/test/m2_m1_r07_intake_20261017" / name for name in ("M1_R07_ORIGINAL.zip", "FORWARD_TO_M3.md", "M1_ERRATA_REQUIRING_CONFIRMATION.md", "ACCEPTANCE.json")]
    for folder in ("r06_public_chain_20261017", "r06_observer_20261017"):
        base = ROOT / "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016" / folder / "c9_m1_semantics_20261017"
        dependencies += [p for p in base.iterdir() if p.is_file() and p.suffix in {".json", ".md", ".zip"}]
    selected.update(relative(path) for path in dependencies)
    selected.update(relative(out / name) for name in ("PRE_C9_INDEX_RECEIPT.json", "PRE_C9_PUBLICATION_FILES.json"))
    manifest = {name: ident((ROOT / name).read_bytes()) for name in sorted(selected)}
    assert max(item["bytes"] for item in manifest.values()) < 94 * 1024 * 1024
    archive_path = out / "M3_TASK_DAY2_C9_STATIC_SUPPLEMENT.zip"
    with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in manifest:
            archive.write(ROOT / name, name)
        archive.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(set(archive.namelist()))
        for name, expected in manifest.items():
            assert ident(archive.read(name)) == expected, name
    archive_id = {"path": relative(archive_path), **ident(archive_path.read_bytes())}
    save(out / "ORIGINALS_INDEX.json", {"schema": "M3_C9_STATIC_SUPPLEMENT_V1", "baseline": NEW, "archive": archive_id, "files": manifest, "post_seal_metadata_changes": changed, "old_ten_volumes_unchanged": True, "functional_runs": 0, "C9_level": "L0_NOT_RUN", "board_release_allowed": False})
    save(out / "RECEIPT.json", {"status": "C9_STATIC_ORIGINALS_CRC_SIZE_SHA_PASS", "archive": archive_id, "payload_count": len(manifest), "B_stored_files_sha_verified": b_checked, "A_C9_original_payloads_verified": len(c9_intake["C9_payloads"]), "functional_runs": 0})
    direct.update(relative(out / name) for name in (archive_path.name, "ORIGINALS_INDEX.json", "RECEIPT.json"))
    # The old plan and index are already preserved as exact supplement members.
    (DOC / "PUBLICATION_FILES.json").write_text(json.dumps({"baseline": NEW, "prior_baseline": old_plan["baseline"], "paths": sorted(direct)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (DOC / "INDEX_RECEIPT.json").rename(DOC / "INDEX_RECEIPT_PRE_C9.json")
    print(json.dumps({"C9_payloads": len(manifest), "archive": archive_id, "publication_paths": len(direct), "added_paths": len(direct - set(old_plan["paths"])), "changed_metadata": len(changed), "functional_runs": 0}))


if __name__ == "__main__":
    main()
