"""Read metadata and bytes only; never imports READY implementations."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[5]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator"


def ident(path):
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("documents", nargs="+")
    args = parser.parse_args()
    assert args.label.replace("_", "").isalnum()
    verified = {}
    def walk(value):
        if isinstance(value, dict):
            if {"path", "bytes", "sha256"} <= value.keys():
                path = Path(value["path"])
                if not path.is_absolute():
                    path = ROOT / path
                path = path.resolve()
                path.relative_to(ROOT)
                actual = ident(path)
                assert actual == {k: value[k] for k in ("bytes", "sha256")}, path
                verified[path.relative_to(ROOT).as_posix()] = actual
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    for name in args.documents:
        path = ROOT / name
        document = json.loads(path.read_text(encoding="utf-8"))
        walk(document)
        for artifact in document.get("artifacts", []):
            directory = artifact["directory"]
            version = "pro_basis_r06_20261017" if artifact["id"] == "R08-SW-R" else "pro_basis_r08_20261017"
            suffix = Path("m3_pro_fourvoice_trace_20261016") / version / directory
            software = ROOT / "code/software" / suffix
            testbench = ROOT / "code/tb/board" / suffix
            paths = {"source_sha256": software / (directory + ".py"), "selftest_sha256": software / "selftest.py", "cases_sha256": testbench / "CASES.json", "hdl_sha256": testbench / "r7a_reset_edges_component.sv", "integration_diff_sha256": testbench / "R7A_MINIMAL_INTEGRATION.diff"}
            for key, target in paths.items():
                if key in artifact:
                    actual = ident(target)
                    assert actual["sha256"] == artifact[key], target
                    verified[target.relative_to(ROOT).as_posix()] = actual
        for component in document.get("components", []):
            ready = component.get("ready")
            if ready:
                walk(json.loads(Path(ready["path"]).read_text(encoding="utf-8")))
    archives = {}
    for name in list(verified):
        if name.endswith(".zip"):
            with zipfile.ZipFile(ROOT / name) as archive:
                assert archive.testzip() is None
                assert len(archive.namelist()) == len(set(archive.namelist()))
                archives[name] = len(archive.namelist())
    with (DOC / ("COLLECT_" + args.label + ".json")).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"status": "IDENTITIES_PASS_STATIC_ONLY", "documents": args.documents, "verified": verified, "archive_member_counts": archives, "candidate_imports": 0, "functional_executions": 0}, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"verified": len(verified), "archives": len(archives), "functional_executions": 0}))


if __name__ == "__main__":
    main()
