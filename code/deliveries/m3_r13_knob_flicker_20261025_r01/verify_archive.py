"""Verify this selected source archive without executing upstream tools."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath


def main() -> None:
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / "ARCHIVE_MANIFEST.json").read_text(encoding="utf-8"))
    files = manifest["files"]
    if len(files) > 180:
        raise SystemExit("FAIL: file limit")
    expected = set(files) | {"ARCHIVE_MANIFEST.json"}
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*")
              if p.is_file() or p.is_symlink()}
    if actual != expected:
        raise SystemExit("FAIL: members missing=" + repr(sorted(expected - actual))
                         + " extra=" + repr(sorted(actual - expected)))
    total = 0
    lf_variants = 0
    for name, item in files.items():
        rel = PurePosixPath(name)
        if rel.is_absolute() or ".." in rel.parts or chr(92) in name or ":" in name:
            raise SystemExit("FAIL: unsafe path " + name)
        path = root.joinpath(*rel.parts)
        if path.is_symlink() or root not in path.resolve().parents:
            raise SystemExit("FAIL: escaping path " + name)
        data = path.read_bytes()
        total += len(data)
        if total > 4194304:
            raise SystemExit("FAIL: byte limit")
        identity = (len(data), hashlib.sha256(data).hexdigest())
        raw = (item["copied_bytes"], item["copied_sha256"])
        lf = item.get("lf_checkout_variant")
        if identity == raw:
            continue
        if lf and identity == (lf["bytes"], lf["sha256"]):
            lf_variants += 1
            continue
        raise SystemExit("FAIL: identity " + name)
    print(f"PASS selected archive: {len(files)} payloads, {total} bytes; "
          f"LF checkout variants={lf_variants}; no HDL/EDA/device run")


if __name__ == "__main__":
    main()
