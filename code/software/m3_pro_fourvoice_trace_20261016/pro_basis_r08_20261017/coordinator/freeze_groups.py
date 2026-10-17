"""Metadata-only snapshot and case-spec preparation; never imports candidates."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[5]
SUFFIX = Path("m3_pro_fourvoice_trace_20261016")
DOC = ROOT / "code/docs/test" / SUFFIX / "pro_basis_r08_20261017/coordinator"
SW = ROOT / "code/software" / SUFFIX
TB = ROOT / "code/tb/board" / SUFFIX
INPUT_DOC = ROOT / "code/docs/test" / SUFFIX


def ident(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def candidate_inputs():
    for base in (SW, TB, INPUT_DOC):
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(base)
            if any(p == "coordinator" or p.startswith("coordinator_") or p == "__pycache__" for p in relative.parts):
                continue
            yield path
    m2 = ROOT / "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/r06_public_chain_20261017"
    yield m2 / "SOURCE_CLOSURE_R06C6.zip"
    yield m2 / "SOURCE_DECISION_R06C6.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--groups", default="RSCTH")
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--defect-basis", default="")
    args = parser.parse_args()
    assert args.label.replace("_", "").isalnum()
    assert set(args.groups) <= set("RSCTH")
    assert len(set(args.groups)) == len(args.groups)
    if args.repair:
        assert len(args.groups) == 1 and args.case and args.defect_basis
    else:
        assert not args.case
    planned = {g: [] for g in args.groups}
    case_bytes = {}
    definitions = list((TB / "pro_basis_r08_20261017").glob("*/CASES.json"))
    integration = TB / "pro_basis_r06_20261017/normalized_intake/r08_integration/CASES.json"
    if integration.exists():
        definitions.append(integration)
    for path in sorted(definitions):
        raw = path.read_bytes()
        case_bytes[path.relative_to(ROOT).as_posix()] = raw
        document = json.loads(raw)
        assert document["schema"] == "M3_R08_CASES_V1", path
        group = document["group"]
        if group not in planned:
            continue
        component = path.parent.name
        selftest = SW / path.relative_to(TB).parent / "selftest.py"
        assert selftest.is_file(), selftest
        for case in document["cases"]:
            key = component + ":" + case["id"]
            if args.repair and key not in args.case:
                continue
            planned[group].append({"component": component, "id": case["id"], "expected": case["expected"], "description": case["description"], "selftest": selftest.relative_to(ROOT).as_posix(), "case_manifest": path.relative_to(ROOT).as_posix()})
    for group, cases in planned.items():
        assert cases, group
        if not args.repair:
            assert len({c["component"] for c in cases}) == (1 if group == "R" else 6), group
        assert len(cases) == len({(c["component"], c["id"]) for c in cases})
    if args.repair:
        assert set(args.case) == {c["component"] + ":" + c["id"] for cases in planned.values() for c in cases}
    folder = DOC / ("FREEZE_" + args.label)
    folder.mkdir(exist_ok=False)
    frozen = json.loads((DOC / "TRACKED_BASELINE.json").read_text(encoding="utf-8"))
    external = {}
    for declaration in (INPUT_DOC / "pro_basis_r08_20261017").glob("*/EXTERNAL_INPUTS.json"):
        document = json.loads(declaration.read_text(encoding="utf-8"))
        for item in document["files"]:
            path = Path(item["path"])
            assert path.is_absolute() and path.is_file()
            assert not any(p.is_symlink() or p.is_junction() for p in (path, *path.parents))
            actual = ident(path.read_bytes())
            assert actual == {k: item[k] for k in ("bytes", "sha256")}, path
            external[str(path.resolve())] = actual
    archived = {}
    archive_path = folder / "INPUTS.zip"
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for path in candidate_inputs():
            rel = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            if rel in case_bytes:
                assert data == case_bytes[rel], "CASE_MANIFEST_CHANGED_DURING_FREEZE:" + rel
                data = case_bytes[rel]
            actual = ident(data)
            if rel in frozen:
                assert frozen[rel] == actual, "TRACKED_INPUT_CHANGED:" + rel
            frozen[rel] = actual
            archived[rel] = actual
            archive.writestr(rel, data)
        # Coordinator entry itself is frozen without capturing mutable ledger.
        for path in sorted(Path(__file__).parent.glob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            frozen[rel] = ident(data)
            archived[rel] = ident(data)
            archive.writestr(rel, data)
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(set(archive.namelist()))
        for name, expected in archived.items():
            assert ident(archive.read(name)) == expected, name
    manifest_path = folder / "FROZEN_FILES.json"
    save(manifest_path, {"schema": "M3_R08_FROZEN_INPUTS_V1", "baseline": "ef4fbc74b9d24e08de1e09d0be0eb3163118f258", "files": frozen, "external_files": external, "archived_files": archived, "archive": ident(archive_path.read_bytes()), "external_policy": "Installed tool files are read/hash only, never loaded/executed or redistributed. Identity is not execution admission.", "tracked_external_dependencies": "Exact identities from baseline; original bytes retained in Git and gathered from read_inputs at final delivery."})
    for group, cases in planned.items():
        phase = "repair" if args.repair else "initial"
        runner = Path(__file__).parent / "run_group.py"
        runner_identity = archived[runner.relative_to(ROOT).as_posix()]
        assert ident(runner.read_bytes()) == runner_identity, "ENTRY_CHANGED_DURING_FREEZE"
        for case in cases:
            for key in ("case_manifest", "selftest"):
                assert ident((ROOT / case[key]).read_bytes()) == archived[case[key]], "CASE_SOURCE_CHANGED_DURING_FREEZE:" + case[key]
        spec_path = folder / f"SPEC_{group}.json"
        spec = {"schema": "M3_R08_RUN_SPEC_V1", "group": group, "phase": phase, "limit_s": 60 if args.repair else 90,
                "python": ident(Path(sys.executable).read_bytes()), "entry": runner_identity,
                "argv": [sys.executable, "-B", "-X", "utf8", str(runner), str(spec_path)], "cwd": str(ROOT),
                "output": str(DOC / "RUNS" / group / ("R02" if args.repair else "R01")),
                "frozen_manifest": {"path": manifest_path.relative_to(ROOT).as_posix(), **ident(manifest_path.read_bytes())},
                "cases": cases, "defect_basis": args.defect_basis, "subprocess_allowed": False, "real_admission": False}
        save(spec_path, spec)
    print(json.dumps({"folder": str(folder), "archived_count": len(archived), "frozen_count": len(frozen), "cases": {g: len(c) for g, c in planned.items()}}))


if __name__ == "__main__":
    main()
