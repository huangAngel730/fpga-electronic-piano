"""Seal new review evidence, preserve original lists, and build a small handoff."""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[5]
DOC_ROOT = ROOT / "code/docs/hardware"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--phase", choices=("wave", "ble"), required=True)
    cli.add_argument("--run", type=Path, required=True)
    cli.add_argument("--gate", type=Path, required=True)
    cli.add_argument("--bundle", type=Path)
    cli.add_argument("--verify-only", action="store_true")
    args = cli.parse_args()
    docs = DOC_ROOT / ("pcm_waveform_v1" if args.phase == "wave" else "score_ble_v1")
    revision = docs / "review_repair_20261008"
    evidence = revision / "evidence"
    run, gate = args.run.resolve(), args.gate.resolve()
    for folder in (run, gate):
        if not folder.is_relative_to((ROOT / "code/output").resolve()):
            cli.error("run and gate must be under code/output")
    if not args.verify_only:
        if evidence.exists():
            cli.error("refuse evidence overwrite")
        result = json.loads((run / "receipt.json").read_text(encoding="utf-8"))
        gate_meta = json.loads((gate / "receipt.json").read_text(encoding="utf-8"))
        if not gate_meta["passed"] or gate_meta["exit"] != 0:
            raise ValueError("GATE_NOT_PASS")
        if not result["passed" if args.phase == "wave" else "desktop_passed"]:
            raise ValueError("RUN_NOT_PASS")
        if args.phase == "ble" and not json.loads((run / "fragment_audit/receipt.json").read_text(encoding="utf-8"))["passed"]:
            raise ValueError("BYTE_AUDIT_NOT_PASS")
        context_file = gate / "child_context.json"
        if not context_file.exists():
            context = {"logs": {}, "historical_rom_errors": [],
                       "boundary": "Nine-gate PASS does not assert old timbre ROM read success"}
            for name in ("tb_electronic_piano_top", "tb_key_to_tone", "tb_midi_top_integration"):
                path = ROOT / "code/output" / name / "run.log"
                data = path.read_bytes()
                (gate / (name + "_child.log")).write_bytes(data)
                context["logs"][name] = {"source": str(path), "sha256": sha(data),
                                        "modified_ns": path.stat().st_mtime_ns}
                context["historical_rom_errors"].extend(line for line in data.decode("utf-8", errors="replace").splitlines()
                                                       if "$readmemh" in line and "ERROR:" in line)
            context_file.write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8", newline="\n")
        evidence.mkdir()
        files = []
        for path in run.rglob("*"):
            if path.is_file() and path.suffix in (".txt", ".json", ".jsonl", ".log", ".py", ".c"):
                files.append(("run/" + path.relative_to(run).as_posix(), path.read_bytes()))
        for path in gate.rglob("*"):
            if path.is_file() and path.suffix in (".json", ".log"):
                files.append(("gate/" + path.relative_to(gate).as_posix(), path.read_bytes()))
        # Archive original manifests/documents from the exact delivery commit,
        # not the newly amended workspace files.
        commit = "4739e39" if args.phase == "wave" else "dd689ec"
        for name in ("FILE_LIST.json", "DELIVERY.md"):
            relative = (docs / name).relative_to(ROOT).as_posix()
            original = subprocess.run(["git", "show", commit + ":" + relative], cwd=ROOT,
                                      capture_output=True, timeout=30, check=False)
            if original.returncode:
                raise ValueError("LEGACY_MANIFEST_SNAPSHOT")
            files.append(("legacy/" + name, original.stdout))
        manifest = {}
        for name, data in files:
            carrier = name.replace("/", "__") + ".gz.b64"
            packed = gzip.compress(data, mtime=0)
            (evidence / carrier).write_bytes(base64.encodebytes(packed))
            manifest[carrier] = {"original": name, "raw_bytes": len(data),
                                 "raw_sha256": sha(data), "gzip_sha256": sha(packed)}
        (evidence / "raw_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    metadata = json.loads((evidence / "raw_manifest.json").read_text(encoding="utf-8"))
    raw = {}
    for name, item in metadata.items():
        packed = base64.b64decode((evidence / name).read_bytes())
        data = gzip.decompress(packed)
        if sha(packed) != item["gzip_sha256"] or sha(data) != item["raw_sha256"] or len(data) != item["raw_bytes"]:
            raise ValueError("SEALED_RAW_IDENTITY")
        raw[item["original"]] = data
    # Preserve the original list and update its existing keys plus just this
    # revision. Night delivery remains a separate immutable list/receipt.
    listing = docs / "FILE_LIST.json"
    original_list = json.loads(raw["legacy/FILE_LIST.json"])
    selected = set(original_list)
    selected.update(p.relative_to(ROOT).as_posix() for p in revision.rglob("*") if p.is_file())
    test_revision = ROOT / ("code/tb/input/pcm_waveform_candidate/review_repair_20261008"
                            if args.phase == "wave" else
                            "code/software/score_ble_test_candidate/review_repair_20261008")
    selected.update(p.relative_to(ROOT).as_posix() for p in test_revision.rglob("*")
                    if p.is_file() and "__pycache__" not in p.parts)
    if not args.verify_only:
        listing.write_text(json.dumps({name: {"bytes": (ROOT / name).stat().st_size,
                            "sha256": sha((ROOT / name).read_bytes())} for name in sorted(selected)}, indent=2) + "\n",
                           encoding="utf-8", newline="\n")
    current = json.loads(listing.read_text(encoding="utf-8"))
    if set(current) != selected:
        raise ValueError("FILE_LIST_MEMBERS")
    for name, item in current.items():
        data = (ROOT / name).read_bytes()
        if len(data) != item["bytes"] or sha(data) != item["sha256"]:
            raise ValueError("FILE_LIST_SHA " + name)
    if args.bundle:
        package = args.bundle.resolve()
        if package.exists() or not package.is_relative_to((ROOT / "code/output").resolve()):
            cli.error("require new bundle under code/output")
        package.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(package, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(selected | {listing.relative_to(ROOT).as_posix()}):
                archive.write(ROOT / name, name)
        with zipfile.ZipFile(package) as archive:
            if archive.testzip() is not None or set(archive.namelist()) != selected | {listing.relative_to(ROOT).as_posix()}:
                raise ValueError("ZIP_INTEGRITY")
            for name in archive.namelist():
                if archive.read(name) != (ROOT / name).read_bytes():
                    raise ValueError("ZIP_SOURCE_BYTES")
        print("BUNDLE", package, "bytes", package.stat().st_size, "SHA256", sha(package.read_bytes()))
    print("PASS", args.phase, len(raw), "new raw artifacts;", len(current), "listed files")


if __name__ == "__main__":
    raise SystemExit(main())
