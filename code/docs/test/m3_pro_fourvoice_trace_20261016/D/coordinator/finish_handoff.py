"""Post-publication originals handoff; no changes to committed source or evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[6]
COORD = Path(__file__).resolve().parent
OUT = COORD / "HANDOFF_FINAL"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": digest(data)}


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          check=True).stdout


def main():
    OUT.mkdir(exist_ok=False)
    head = git("rev-parse", "HEAD").decode().strip()
    remote = git("rev-parse", "origin/develop").decode().strip()
    tree = git("rev-parse", "HEAD^{tree}").decode().strip()
    assert head == remote == "ad2de2169230dc8fd9f4b6f8157d384306c2479a"
    assert tree == "a8d6dd9fb1e7f683585db30bdd14408d83c3aa64"
    source_zip = COORD / "DELIVERY/M3_NIGHT_20261017_OFFLINE_ORIGINALS.zip"
    blob = git("show", head + ":" + source_zip.relative_to(ROOT).as_posix())
    assert blob == source_zip.read_bytes()
    assert digest(blob) == "1849b9ce4ba89ec0f29756071615e6678a9a191b7083486ec1380157a98a6481"
    gate = json.loads((COORD / "PUBLICATION_GATE/GATE_RECEIPT.json").read_text(encoding="utf-8"))
    first = json.loads((COORD / "PUBLICATION_GATE_R01/GATE_RECEIPT.json").read_text(encoding="utf-8"))
    assert gate["status"] == "PASS" and gate["pass_count"] == 9 and gate["exit_code"] == 0
    assert gate["input_bytes_unchanged"]
    paths = json.loads((COORD / "PUBLICATION_FILES.json").read_text(encoding="utf-8"))["paths"]
    bindings = []
    for rel in paths:
        current = (ROOT / rel).read_bytes()
        committed = git("show", head + ":" + rel)
        equal = current == committed
        normalized = not equal and current.replace(b"\r\n", b"\n") == committed
        assert equal or normalized, rel
        bindings.append({"path": rel, "worktree_sha256": digest(current),
                         "git_blob_sha256": digest(committed), "byte_equal": equal,
                         "crlf_to_lf_metadata_only": normalized})
    normalized = [r["path"] for r in bindings if r["crlf_to_lf_metadata_only"]]
    assert len(normalized) == 4
    assert all(p.endswith(".json") and "/coordinator/" in p for p in normalized)
    save(COORD / "PUBLICATION_AUDIT/INDEX_BINDING_FINAL.json", bindings)
    now = datetime.now(timezone.utc)
    status = {
        "status": "PUBLISHED_DEVELOP_AND_REMOTE_SHA_VERIFIED",
        "utc": now.isoformat(), "head": head, "origin_develop_after_fetch": remote,
        "candidate_and_commit_tree": tree, "published_files": len(paths),
        "github_commit": "https://github.com/huangAngel730/fpga-electronic-piano/commit/" + head,
        "source_archive": identity(source_zip), "source_archive_equals_git_blob": True,
        "gate_receipt": identity(COORD / "PUBLICATION_GATE/GATE_RECEIPT.json"),
        "gate": {k: gate[k] for k in ("status", "seconds", "exit_code", "pass_count",
                                     "candidate_input_count", "input_bytes_unchanged")},
        "gate_first_failure": {k: first[k] for k in ("status", "seconds", "exit_code", "pass_count")},
        "gate_first_failure_cause": "PowerShell script loading disabled; zero checks started",
        "gate_repair": "PSExecutionPolicyPreference=Bypass in invocation process only; no persistent policy change",
        "commit_push_final_fetch_exit_codes": [0, 0, 0],
        "push_tool_output_text": "To https://github.com/huangAngel730/fpga-electronic-piano.git\n   b6f28911..ad2de216  develop -> develop\n",
        "tracked_worktree_and_index_diffs": "EMPTY",
        "local_raw_copies": "Retained as untracked evidence; originals ZIP committed",
        "metadata_eol_normalization": normalized,
        "runtime_source_and_originals_zip_byte_equal_git": True,
        "metadata_original_bytes": "Included in final handoff; four Git JSON metadata files follow repository LF policy",
        "quota": {"C_rounds": 2, "C_limit": 6, "D_D2_rounds": 3, "D3_rounds": 2,
                  "D_shared_rounds": 5, "D_limit": 6, "slider_rounds": 1, "slider_limit": 6,
                  "C_D_functional_seconds": 13.093, "C_D_seconds_limit": 4500,
                  "slider_functional_seconds": 100.282, "repository_gate_attempts_separate": 2,
                  "modelsim": 0, "gowin": 0, "hardware": 0},
        "account_usage_snapshot": {"used_percent": 37, "remaining_percent": 63,
                                   "window_minutes": 10080, "resets_at_unix": 1792649760,
                                   "scope": "shared account during publication",
                                   "per_thread_tokens_or_cost": "UNKNOWN_NOT_PROVIDED_NO_START_SNAPSHOT"},
        "elapsed_from_T0_seconds": (now - datetime(2026, 10, 16, 16, 21,
                                                  tzinfo=timezone.utc)).total_seconds(),
        "timebox_seconds": 18000, "board_release_allowed": False,
        "real_pro_status": "PENDING_NEW_PRO_SOURCE_ROM_TOP_TRACE_INTERFACE_PHYSICAL_HARDWARE",
        "night_2_3_4_final_returns": "RECEIVED_UNDER_RENEWED_DIRECT_USER_AUTHORIZATION",
        "M1_M2_human_handoff": "WAITING_FOR_USER_FORWARD_NOT_DELIVERED",
        "registration": "M2 final review/shared-state/verification registration requested; no V/D/T preallocated"}
    save(COORD / "PUBLICATION_STATUS.json", status)
    for role in ("M1", "M2"):
        path = COORD / ("给" + role + "_待用户转发.md")
        supplement = (
            "\n\n发布后补充：普通push及重新fetch均退出0；HEAD与origin/develop完整SHA "
            + head + "，tree " + tree
            + "。九项门禁9/9 PASS、exit0、141.438秒、13127输入前后不变；首次执行策略失败也在附件。"
            "原件ZIP 5,284,872字节/SHA1849b9ce4ba89ec0f29756071615e6678a9a191b7083486ec1380157a98a6481"
            "与Git blob逐字节相同。四个总控JSON元数据按仓库LF规范归一，原始字节在本附件中；"
            "源码和原件ZIP未改变。发布不代表真人已收到，仍待用户转发。\n")
        (OUT / path.name).write_text(path.read_text(encoding="utf-8") + supplement,
                                    encoding="utf-8", newline="\n")
    readme = (
        "10/17 M3授权离线任务已完成并发布develop。C/D为L1夹具、双滑块为L2隔离RTL；"
        "真实Pro同版/实物PENDING，board_release_allowed=false。\n\n"
        "请将此ZIP及对应给M2/M1文字转发。主原件ZIP含688载荷和全部正负/首失败原件；"
        "PUBLICATION_STATUS含发布SHA、门禁、消费和边界；GATE目录保留成功及首次失败双流。"
        "原件先解压至独立审阅目录，避免覆盖已有实验；复跑需新输出和有效许可。\n\n"
        "Git commit: " + head + "\nGitHub: " + status["github_commit"] + "\n")
    (OUT / "README.txt").write_text(readme, encoding="utf-8", newline="\n")
    entries = {}
    def add(path, name):
        assert name not in entries
        entries[name] = path
    add(source_zip, source_zip.name)
    add(COORD / "PUBLICATION_STATUS.json", "PUBLICATION_STATUS.json")
    add(Path(__file__), "POST_PUBLICATION/finish_handoff.py")
    add(COORD / "PUBLICATION_AUDIT/INDEX_BINDING_FINAL.json", "PUBLICATION_AUDIT/INDEX_BINDING_FINAL.json")
    for name in ("DELIVERY.json", "MANIFEST.json", "VERIFICATION.json"):
        add(COORD / "DELIVERY" / name, "ORIGINAL_DELIVERY_METADATA/" + name)
    for folder, prefix in (("PUBLICATION_GATE", "GATE_PASS"),
                           ("PUBLICATION_GATE_R01", "GATE_FIRST_FAILURE")):
        for path in sorted((COORD / folder).rglob("*")):
            if path.is_file():
                add(path, prefix + "/" + path.relative_to(COORD / folder).as_posix())
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            add(path, path.name)
    manifest = [{"path": name, "bytes": path.stat().st_size,
                 "sha256": digest(path.read_bytes())} for name, path in sorted(entries.items())]
    save(OUT / "HANDOFF_MANIFEST.json", manifest)
    archive = OUT / "M3_NIGHT_20261017_HANDOFF_COMPLETE.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as zout:
        for name, path in sorted(entries.items()):
            zout.write(path, name)
        zout.write(OUT / "HANDOFF_MANIFEST.json", "HANDOFF_MANIFEST.json")
    with zipfile.ZipFile(archive) as zin:
        assert zin.testzip() is None
        assert set(zin.namelist()) == set(entries) | {"HANDOFF_MANIFEST.json"}
        for item in manifest:
            data = zin.read(item["path"])
            assert len(data) == item["bytes"] and digest(data) == item["sha256"]
    receipt = {"status": "HANDOFF_COMPLETE_ORIGINALS_GATE_PUBLICATION_INCLUDED",
               "archive": identity(archive), "members": len(manifest) + 1,
               "crc_sizes_sha_all_pass": True, "published_commit": head,
               "source_zip_git_blob_sha256": digest(blob),
               "human_handoff": "WAITING_FOR_USER_FORWARD_NOT_DELIVERED",
               "board_release_allowed": False}
    save(OUT / "FINAL_DELIVERY.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
