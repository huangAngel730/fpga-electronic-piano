"""Seal local resume evidence; never stage, commit, push or run HDL tools."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--c-archive", type=Path, required=True)
    parser.add_argument("--c-sha", required=True)
    args = parser.parse_args()
    old = HERE.parent / "M3_NIGHT_HANDOFF_20261016_LOCAL_PARTIAL.zip"
    a = ROOT / "code/docs/test/m3_r05_functional_integration_20261015/night_20261016/RESUME_R01/SEAL_RESUME_FAILURE/M3_NIGHT_A_RESUME_R01_FAILED_ORIGINALS.zip"
    d = ROOT / "code/docs/test/m3_dual_slider_138k_candidate_20261015/night_20261016/RESUME_R01/D_FOUR_RTL_NEGATIVES_COMPLETE_RESUME_R01_20261016.zip"
    packages = {
        "BASE_FOUR_PACKAGES.zip": (old, "6aeae78cd3abaf674588517d36121c7f145f1606e0795371347795661751e09a"),
        "A_RESUME_FAILED_ORIGINALS.zip": (a, "cbbae0f9301d628048e9fb754436f24a84f7bb3f62cba73fe478f5411c77d52f"),
        "D_FOUR_RTL_NEGATIVES_COMPLETE.zip": (d, "d95def3980b6f09daac320934244986419a756bddd6b505e5a2b715992e4f885"),
        "C_RESUME_SOFTWARE_PARTIAL.zip": (args.c_archive, args.c_sha),
    }
    contents = {}
    syntax_checked = 0
    for name, (path, expected) in packages.items():
        raw = path.read_bytes()
        assert sha(raw) == expected, path
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            for member in archive.namelist():
                if "RESUME_R01/" in member and member.endswith(".py"):
                    ast.parse(archive.read(member).decode("utf-8-sig"), filename=member)
                    syntax_checked += 1
        contents[name] = raw
    plan = json.loads((HERE.parent / "PUBLICATION_PLAN.json").read_text(encoding="utf-8"))
    for name, item in plan["file_identities"].items():
        raw = (ROOT / name).read_bytes()
        assert {"bytes": len(raw), "sha256": sha(raw)} == item, name
    gate = json.loads((HERE.parent / "gate_R01/GATE_RECEIPT.json").read_text(encoding="utf-8"))
    cached = subprocess.check_output(["git", "diff", "--cached", "--binary"], cwd=ROOT)
    assert sha(cached) == gate["before"]["staged_diff_sha256"], "old staged tree drift"
    assert not subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT)
    for path in sorted(HERE.iterdir()):
        if path.is_file() and path.suffix in (".md", ".txt", ".json", ".py"):
            contents["COORDINATOR/" + path.name] = path.read_bytes()
    state = {
        "status": "LOCAL_PARTIAL_NOT_COMMITTED_NOT_PUSHED",
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
        "communication": "1_DISPATCHED_2_3_4_AND_RECEIVED_DIRECT_REPORTS",
        "A": "3_OF_3_FUNCTIONAL_GROUPS_FAILED_MAIN_TICKS_0_NO_READY",
        "C": "SOFTWARE_PARTIAL_REAL_FAILED_RECEIPT_REJECTED_NO_SUCCESSFUL_CAPTURE",
        "D": "FOUR_RTL_BEHAVIORAL_NEGATIVES_COMPLETE_1_OF_3_GROUPS_CONSUMED",
        "B": "OLD_DIRECTED_STA_REUSED_NO_NEW_EDA",
        "previous_staged_77_tree_unchanged": True,
        "previous_gate": "9_OF_9_PASS_APPLIES_ONLY_TO_PREVIOUS_77_TREE",
        "resume_repository_publication_gate": "NOT_RUN_REMOTE_FETCH_FAILED_BEFORE_PUBLICATION",
        "python_archive_source_ast_checks": syntax_checked,
        "hardware_invocations": 0, "n32_new_work": 0,
        "board_release_allowed": False,
        "M2_delivery": "WAITING_USER_FORWARD_NOT_DELIVERED",
    }
    contents["COORDINATION_STATE.json"] = (json.dumps(state, indent=2) + "\n").encode()
    manifest = {name: {"bytes": len(raw), "sha256": sha(raw)} for name, raw in contents.items()}
    manifest_path = HERE / "BUNDLE_MANIFEST.json"
    with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    contents["BUNDLE_MANIFEST.json"] = manifest_path.read_bytes()
    output = HERE / "M3_NIGHT_RESUME_R01_HANDOFF_LOCAL_PARTIAL.zip"
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in contents.items():
            archive.writestr(name, raw)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        for name, raw in contents.items():
            assert archive.read(name) == raw, name
    receipt = {"path": str(output), "bytes": output.stat().st_size,
               "sha256": sha(output.read_bytes()), "status": state["status"],
               "members_verified": len(contents), "all_previous_staged_files_unchanged": True}
    with (HERE / "BUNDLE_SHA.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
