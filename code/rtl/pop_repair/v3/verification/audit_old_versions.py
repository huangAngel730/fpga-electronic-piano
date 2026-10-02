"""Read-only old-file SHA audit; only writes reports next to this script."""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(r"E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano")
ROOTS = [Path(r"E:\FPGA\GAOYUNFPGA\pop_repair"), REPO / "code/rtl/pop_repair"]
CACHE = {"__pycache__", ".pytest_cache", ".git"}

def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()

def inventory():
    result = {}
    for root in ROOTS:
        entries = {}
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if not path.is_file() or rel.parts[0] == "v3" or CACHE.intersection(rel.parts):
                continue
            entries[rel.as_posix()] = {"sha256": sha(path), "bytes": path.stat().st_size}
        result[str(root)] = entries
    return result

def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["capture", "verify"])
    args = parser.parse_args()
    baseline = HERE / "old_versions_baseline.json"
    current = inventory()
    payload = {"utc": datetime.now(timezone.utc).isoformat(), "git_head": git("rev-parse", "HEAD"),
               "git_status": git("status", "--short"), "roots": current,
               "exclusions": ["v3 (first component)", *sorted(CACHE)]}
    if args.mode == "capture":
        if baseline.exists():
            raise SystemExit("Refusing to replace existing baseline")
        baseline.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print("PASS captured", {root: len(files) for root, files in current.items()})
        return
    expected = json.loads(baseline.read_text(encoding="utf-8"))["roots"]
    diffs = []
    for root in set(expected) | set(current):
        old, new = expected.get(root, {}), current.get(root, {})
        for name in sorted(set(old) | set(new)):
            if old.get(name) != new.get(name):
                diffs.append({"root": root, "path": name, "before": old.get(name), "after": new.get(name)})
    payload["differences"] = diffs
    payload["old_files_unchanged"] = not diffs
    (HERE / "old_versions_final_audit.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("PASS" if not diffs else "FAIL", "old-file integrity", len(diffs), "differences")
    raise SystemExit(bool(diffs))

if __name__ == "__main__":
    main()
