"""Seal verified night deliverables and repository gate, preserving raw archives."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit")
    parser.add_argument("--blocker")
    args = parser.parse_args()
    assert bool(args.commit) != bool(args.blocker)
    plan = json.loads((HERE / "PUBLICATION_PLAN.json").read_text(encoding="utf-8"))
    gate = json.loads((HERE / "gate_R01/GATE_RECEIPT.json").read_text(encoding="utf-8"))
    assert gate["status"] == "PASS" and gate["pass_count"] == 9
    assert gate["exact_inputs_unchanged"] and gate["exit_code"] == 0
    assert gate["before"]["head"] == plan["baseline"]
    names = sorted(plan["files"] + [(HERE / "PUBLICATION_PLAN.json").relative_to(ROOT).as_posix()])
    records = {}
    contents = {}
    for name in names:
        raw = (ROOT / name).read_bytes()
        if name in plan["file_identities"]:
            assert {"bytes": len(raw), "sha256": sha(raw)} == plan["file_identities"][name], name
        contents[name] = raw
        records[name] = {"bytes": len(raw), "sha256": sha(raw)}
    if args.commit:
        commit = git("rev-parse", args.commit).decode().strip()
        assert git("rev-parse", "HEAD").decode().strip() == commit
        assert git("rev-parse", "origin/develop").decode().strip() == commit
        assert not git("diff", "--name-only") and not git("diff", "--cached", "--name-only")
        changed = sorted(git("diff-tree", "--no-commit-id", "--name-only", "-r", commit).decode().splitlines())
        assert names == changed
        for name in names:
            blob = git("show", commit + ":" + name)
            raw = contents[name]
            assert blob == raw or (not name.endswith(".zip") and blob == raw.replace(b"\r\n", b"\n")), name
            records[name]["git_blob_sha256"] = sha(blob)
            records[name]["LF_normalization_only"] = blob != raw
            contents[name] = blob
        status = "PUBLISHED_REMOTE_SHA_VERIFIED"
        suffix = commit[:7]
    else:
        commit = None
        assert git("rev-parse", "HEAD").decode().strip() == plan["baseline"]
        status = "LOCAL_SEALED_NOT_COMMITTED_NOT_PUSHED"
        suffix = "LOCAL_PARTIAL"
    receipt = {"status": status, "task_status": "PARTIAL", "commit": commit,
               "github": None if commit is None else "https://github.com/huangAngel730/fpga-electronic-piano/commit/" + commit,
               "publication_blocker": args.blocker, "files": records,
               "gate": {k: gate[k] for k in ("status", "exit_code", "pass_count", "elapsed_seconds", "exact_inputs_unchanged")},
               "delivery": "WAITING_FOR_USER_FORWARD_NOT_DELIVERED", "board_release_allowed": False}
    (HERE / "PUBLICATION_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    archive_path = HERE / ("M3_NIGHT_HANDOFF_20261016_" + suffix + ".zip")
    b_original = ROOT / "code/docs/test/m3_m2td_audio_endpoint_audit_20261015/successor_R03/delivery_night_r03/B_DIRECTED_STA_CANDIDATE_20261016.zip"
    assert sha(b_original.read_bytes()) == "59f40000f25bccc492199e4a0f6e843e4a7ccf68ddaeab5823c756b888d44ce3"
    with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in contents.items():
            archive.writestr(name, raw)
        archive.write(HERE / "PUBLICATION_RECEIPT.json", "PUBLICATION_RECEIPT.json")
        archive.write(HERE / "REPOSITORY_GATE_R01.zip", "REPOSITORY_GATE_R01.zip")
        archive.write(b_original, "B_REUSED_ORIGINAL/B_DIRECTED_STA_CANDIDATE_20261016.zip")
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        for name, raw in contents.items():
            assert archive.read(name) == raw
    result = {"archive": str(archive_path), "bytes": archive_path.stat().st_size,
              "sha256": sha(archive_path.read_bytes()), "status": status, "commit": commit}
    (HERE / "FORWARD_PACKAGE_SHA.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
