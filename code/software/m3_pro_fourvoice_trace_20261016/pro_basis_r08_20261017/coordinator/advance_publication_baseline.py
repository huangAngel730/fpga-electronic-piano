"""Metadata only: verify a published fast-forward without altering test evidence."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[5]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator"
OLD = "ef4fbc74b9d24e08de1e09d0be0eb3163118f258"
NEW = "cf370156fb882df3e8fe8bf04b45d3e12ad4c08b"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def ident(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    assert git("rev-parse", "HEAD").decode().strip() == NEW
    assert git("rev-parse", "origin/develop").decode().strip() == NEW
    subprocess.run(["git", "merge-base", "--is-ancestor", OLD, NEW], cwd=ROOT, check=True)
    assert not git("diff", "--name-only").strip()
    changed = [p for p in git("diff", "--name-only", "-z", OLD, NEW).decode().split("\0") if p]
    assert len(changed) == 17
    assert not any("m3_pro_fourvoice_trace_20261016" in p for p in changed)
    baseline = json.loads((DOC / "TRACKED_BASELINE.json").read_text(encoding="utf-8"))
    transitions = {}
    for name, expected in baseline.items():
        if name not in changed:
            assert ident((ROOT / name).read_bytes()) == expected, name
    for name in changed:
        raw = git("show", NEW + ":" + name)
        assert (ROOT / name).read_bytes() == raw, name
        actual = ident(raw)
        transitions[name] = {"before": baseline.get(name), "after": actual}
        baseline[name] = actual
    for name, value in (("PUBLICATION_BASELINE.json", baseline), ("M2_R09_PUBLICATION_ADVANCE.json", {"from_test_baseline": OLD, "to_publication_baseline": NEW, "changed_files": transitions, "M3_files_changed": 0, "new_functional_runs": 0, "R08_scope_and_consumption_unchanged": True, "M2_R09_real_unit_result": "raw_compile 0xC0000005; no raw simulation/boundary; does not grant M3 execution"})):
        with (DOC / name).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    print(json.dumps({"published_changes_verified": len(changed), "M3_changes": 0, "new_baseline": NEW}))


if __name__ == "__main__":
    main()
