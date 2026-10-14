"""Seal D preparation evidence without executing a vendor tool."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prepare_d


def verify(destination):
    seal = json.loads((destination / "seal.json").read_text(encoding="utf-8"))
    manifest_raw = (destination / "MANIFEST.json").read_bytes()
    prepare_d.require(prepare_d.blob_identity(manifest_raw) == seal["manifest"], "D_SEAL_MANIFEST")
    raw = base64.b64decode((destination / "snapshot.zip.b64").read_bytes().strip(), validate=True)
    prepare_d.require(prepare_d.blob_identity(raw) == seal["snapshot"], "D_SEAL_ARCHIVE")
    manifest = json.loads(manifest_raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        prepare_d.require(len(bundle.namelist()) == len(set(bundle.namelist())) and
                          set(bundle.namelist()) == set(manifest["files"]) | {"MANIFEST.json"}, "D_SEAL_MEMBER_SET")
        prepare_d.require(bundle.read("MANIFEST.json") == manifest_raw, "D_SEAL_MEMBER_MANIFEST")
        for name, expected in manifest["files"].items():
            prepare_d.require(prepare_d.blob_identity(bundle.read(name)) == expected, "D_SEAL_MEMBER_SHA:" + name)
    return {"status": "D_SEAL_VERIFY_PASS", "members": seal["members"], "snapshot_sha256": seal["snapshot"]["sha256"]}


def seal(project, evidence, destination, history):
    prepare_d.require(not destination.exists(), "D_NEW_SEAL_REQUIRED")
    report = prepare_d.verify(project)
    receipt = json.loads((evidence / "receipt.json").read_text(encoding="utf-8"))
    prepare_d.require(receipt["status"] == "N32_D_PREPARATION_AND_SOFTWARE_CHECKS_PASS" and
                      receipt["exit_code"] == 0 and receipt["actual_EDA_calls"] == 0 and
                      receipt["RTL_calls"] == 0, "D_REAL_SOFTWARE_RECEIPT_REQUIRED")
    prepare_d.require(prepare_d.identity(project / "manifest.json") == receipt["manifest"], "D_PROJECT_RECEIPT_PIN")
    actual = {p.relative_to(project).as_posix(): prepare_d.identity(p)
              for p in project.rglob("*") if p.is_file()}
    prepare_d.require(actual == receipt["project_files"], "D_PROJECT_AFTER_DRIFT")
    for path, identity in receipt["sources_after"].items():
        prepare_d.require(prepare_d.identity(path) == identity, "D_CHECK_SOURCE_AFTER_DRIFT:" + path)
    sources = {}

    def collect(prefix, folder):
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                name = prefix + "/" + path.relative_to(folder).as_posix()
                prepare_d.require(name not in sources, "D_SEAL_DUPLICATE")
                sources[name] = path

    collect("project", project)
    collect("execution", evidence)
    for folder in history:
        collect("history/" + folder.name, folder)
    for path in sorted(HERE.iterdir()):
        if path.is_file() and path.suffix in (".py", ".sv", ".md"):
            sources["implementation/" + path.name] = path
    for path in sorted(prepare_d.GUARD_DIR.iterdir()):
        if path.is_file() and path.suffix in (".py", ".md"):
            sources["guard/" + path.name] = path
    identities = {name: prepare_d.identity(path) for name, path in sources.items()}
    manifest = {"schema": "N32_D_DELIVERY_MANIFEST_V1", "status": "PREPARED_L0_L1_ONLY",
                "files": identities, "project_manifest": receipt["manifest"],
                "receipt": prepare_d.identity(evidence / "receipt.json"), "static_guard": report,
                "actual_EDA_calls": 0, "RTL_calls": 0, "resources": "UNKNOWN", "STA": "NOT_RUN",
                "T061_complete": False, "tools_included": False,
                "C_scope": "SEGMENTED_NOT_CONTINUOUS", "synthesis_authorized": False}
    destination.mkdir(parents=True)
    (destination / "MANIFEST.json").write_bytes(prepare_d.canonical(manifest))
    archive = destination / "snapshot.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for name, path in sources.items():
            prepare_d.require(prepare_d.identity(path) == identities[name], "D_SEAL_INPUT_DRIFT")
            bundle.write(path, name)
        bundle.write(destination / "MANIFEST.json", "MANIFEST.json")
    (destination / "snapshot.zip.b64").write_bytes(base64.b64encode(archive.read_bytes()) + b"\n")
    record = {"status": "PREPARED_L0_L1_ONLY", "members": len(identities) + 1,
              "manifest": prepare_d.identity(destination / "MANIFEST.json"),
              "snapshot": prepare_d.identity(archive), "actual_EDA_calls": 0,
              "T061_complete": False, "synthesis_authorized": False}
    (destination / "seal.json").write_bytes(prepare_d.canonical(record))
    return verify(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("seal", "verify"))
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--project", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--history", type=Path, nargs="*", default=[])
    args = parser.parse_args()
    result = (verify(args.destination) if args.command == "verify" else
              seal(args.project.resolve(), args.evidence.resolve(), args.destination, args.history))
    print(json.dumps(result, sort_keys=True))
