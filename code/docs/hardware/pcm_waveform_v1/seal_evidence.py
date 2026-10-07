"""Seal small original byte logs/captures/report without changing output runs."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--acceptance", type=Path, required=True)
    cli.add_argument("--synthesis", type=Path, required=True)
    args = cli.parse_args()
    target = Path(__file__).resolve().parent / "evidence"
    if target.exists():
        cli.error("refusing to overwrite evidence")
    for source in [args.acceptance, args.synthesis]:
        if not json.loads((source / "receipt.json").read_text(encoding="utf-8"))["passed"]:
            cli.error("only complete PASS receipts may be sealed")
    selected = []
    for source, prefix in [(args.acceptance, "acceptance"), (args.synthesis, "synthesis")]:
        for path in source.rglob("*"):
            if path.is_file() and (path.suffix == ".log" or path.name in
                ("receipt.json", "source_manifest.json", "capture.txt", "mutant.sv", "waveform_syn.rpt.html", "waveform.sdc", "waveform.gprj")):
                selected.append((path, prefix + "/" + path.relative_to(source).as_posix()))
    target.mkdir()
    manifest = {}
    for source, relative in selected:
        raw = source.read_bytes()
        dest = target / (relative + ".b64")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(base64.encodebytes(raw))
        manifest[relative + ".b64"] = {"raw_bytes": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest()}
    (target / "raw_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("SEALED", len(manifest), "original byte artifacts", target)


if __name__ == "__main__":
    main()
