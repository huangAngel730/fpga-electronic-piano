"""Metadata-only staged scope/bytes audit before the mandatory repository gate."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[5]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    plan = json.loads((DOC / "PUBLICATION_FILES.json").read_text(encoding="utf-8"))
    names = sorted(plan["paths"])
    staged = sorted(p for p in git("diff", "--cached", "--name-only", "-z").decode().split("\0") if p)
    assert staged == names, {"unexpected": sorted(set(staged) - set(names)), "missing": sorted(set(names) - set(staged))}
    assert not git("diff", "--name-only").strip(), "UNSTAGED_TRACKED_CHANGES"
    subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, check=True)
    records = {}
    for name in names:
        raw = (ROOT / name).read_bytes()
        assert git("show", ":" + name) == raw, "INDEX_BYTE_CONVERSION:" + name
        records[name] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    with (DOC / "INDEX_RECEIPT.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"status": "EXACT_SCOPE_AND_BYTES_PASS", "head": git("rev-parse", "HEAD").decode().strip(), "count": len(names), "files": records}, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"status": "PASS", "count": len(names)}))


if __name__ == "__main__":
    main()
