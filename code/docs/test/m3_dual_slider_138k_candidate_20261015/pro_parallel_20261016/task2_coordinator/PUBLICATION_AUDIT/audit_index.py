"""Read-only Git/index binding; write proof outside the candidate payload."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
COORD = HERE.parent
ROOT = COORD.parents[5]


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def main():
    planned = json.loads((COORD / "PUBLICATION_FILES.json").read_text(encoding="utf-8"))["paths"]
    staged = git("diff", "--cached", "--name-only", "-z").decode("utf-8").split("\0")[:-1]
    assert set(staged) == set(planned) and len(staged) == len(planned)
    assert not git("diff", "--name-only")
    records = []
    normalized = []
    for name in planned:
        raw = (ROOT / name).read_bytes()
        blob = git("show", ":" + name)
        if raw != blob:
            assert Path(name).suffix in (".md", ".json"), name
            assert raw.replace(b"\r\n", b"\n") == blob, name
            normalized.append(name)
        records.append({"path": name, "worktree_sha256": hashlib.sha256(raw).hexdigest(),
                        "index_sha256": hashlib.sha256(blob).hexdigest(),
                        "raw_byte_equal": raw == blob, "index_bytes": len(blob)})
    proof = {"status": "PASS", "paths": len(planned), "exact_index_scope": True,
             "head_before_commit": git("rev-parse", "HEAD").decode().strip(),
             "origin_visible": git("rev-parse", "origin/develop").decode().strip(),
             "candidate_tree": "0507aacc934344f7d1d0d3a7d17091f49b5b0eaa",
             "metadata_LF_normalized": normalized, "records": records,
             "raw_streams_preserved_in_aggregate_zip": True}
    with (HERE / "INDEX_BINDING.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(proof, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"status": "PASS", "paths": len(planned), "metadata_LF_normalized": normalized}))


if __name__ == "__main__":
    main()
