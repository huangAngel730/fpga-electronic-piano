"""Package only task5 additions; reference previous artifacts without copying."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
BASE = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017"
OUT = BASE / "LIGHTWEIGHT"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    started = time.monotonic()
    OUT.mkdir(exist_ok=False)
    launch = {"argv": sys.orig_argv, "cwd": str(Path.cwd()), "pid": os.getpid(),
              "start_utc": datetime.now(timezone.utc).isoformat(),
              "purpose": "PACKAGING_METADATA_ONLY_NO_FUNCTIONAL_ROUND", "python": sys.version,
              "python_sha256": sha(sys.executable), "script_sha256": sha(__file__)}
    dump(OUT / "LAUNCH.json", launch)
    intake = json.loads((BASE / "INTAKE.json").read_text(encoding="utf-8"))
    supplements = json.loads((BASE / "SUPPLEMENT_SOURCE_LOCATIONS.json").read_text(encoding="utf-8"))
    originals = {r["path"]: {k: r[k] for k in ("path", "bytes", "sha256")} for r in intake["artifacts"] if r["present"]}
    for link in intake["receipt_link_checks"]:
        if link["actual"]["present"]:
            r = link["actual"]
            originals[r["path"]] = {k: r[k] for k in ("path", "bytes", "sha256")}
    for archive in intake["archive_checks"]:
        r = archive["identity"]
        originals[r["path"]] = {k: r[k] for k in ("path", "bytes", "sha256")}
    for r in supplements:
        originals[str(ROOT / r["path"])] = {"path": str(ROOT / r["path"]), "bytes": r["bytes"], "sha256": r["sha256"]}
    relative = sorted({Path(p).relative_to(ROOT).as_posix() for p in originals if Path(p).is_relative_to(ROOT)})
    calls = []

    def git(label, args):
        argv = ["git", *args]
        begin = datetime.now(timezone.utc).isoformat()
        process = subprocess.run(argv, cwd=ROOT, capture_output=True, check=True)
        (OUT / f"{label}.stdout").write_bytes(process.stdout)
        (OUT / f"{label}.stderr").write_bytes(process.stderr)
        calls.append({"argv": argv, "cwd": str(ROOT), "start_utc": begin,
                      "end_utc": datetime.now(timezone.utc).isoformat(), "exit_code": process.returncode,
                      "stdout_sha256": sha(OUT / f"{label}.stdout"), "stderr_sha256": sha(OUT / f"{label}.stderr")})
        return process.stdout

    head = git("git_head", ["rev-parse", "HEAD"]).decode().strip()
    raw_tree = git("git_references", ["ls-tree", "-r", "-z", "--full-tree", head, "--", *relative])
    tree = {}
    for entry in raw_tree.split(b"\0"):
        if entry:
            info, name = entry.split(b"\t", 1)
            tree[name.decode("utf-8")] = info.decode().split()[2]
    group_results = {
        "C": "code/docs/test/m3_pro_fourvoice_trace_20261016/C/RESULT.md",
        "D": "code/docs/test/m3_pro_fourvoice_trace_20261016/D/RESULT.md",
        "monitor": "code/docs/test/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017/RESULT.md",
        "E2": "code/docs/test/m3_pro_waveform_successor_20261017/RESULT.json",
        "E3": "code/docs/test/m3_pro_min_transfer_successor_20261017/RESULT.md",
    }
    provenance = {group: git(f"git_last_{group}", ["log", "-1", "--format=%H", "--", path]).decode().strip()
                  for group, path in group_results.items()}
    references = []
    for path, record in sorted(originals.items()):
        source = Path(path)
        rel = source.relative_to(ROOT).as_posix() if source.is_relative_to(ROOT) else None
        present = source.is_file()
        group = None
        if rel:
            if "m3_pro_waveform_successor_20261017" in rel:
                group = "E2"
            elif "m3_pro_min_transfer_successor_20261017" in rel:
                group = "E3"
            elif "D/pro_monitor_20261017" in rel:
                group = "monitor"
            elif "m3_pro_fourvoice_trace_20261016/C/" in rel:
                group = "C"
            elif "m3_pro_fourvoice_trace_20261016/D/" in rel:
                group = "D"
        references.append(dict(record, repository_snapshot_commit=head,
              git_tree_commit=head if rel in tree else None, git_blob=tree.get(rel),
              package_result_commit=provenance.get(group),
              git_binding="TRACKED_AT_FULL_COMMIT" if rel in tree else "LOCAL_OR_EXTERNAL_ONLY_NOT_A_GIT_BLOB",
              readable_at_original_path=present,
              note="Original bytes remain in place; not copied into lightweight payload. Package-result commit does not assert that an untracked ZIP is stored in Git."))
    dump(OUT / "OLD_REFERENCE_LEDGER.json", {"repository_snapshot_commit": head, "package_result_commits": provenance,
          "references": references, "old_payload_copies": 0, "functional_rounds_added": 0})
    dump(OUT / "READ_ONLY_GIT_RECEIPTS.json", calls)
    first = json.loads((BASE / "DELIVERY_RECEIPT.json").read_text(encoding="utf-8"))
    notice = (
        "# 正式采用的轻量后继\n\n"
        "本后继只修正交付封装，原审计事实、9项结果、1/2轮消费、L0+L1和Pro PENDING均不变。\n"
        "首个9MB包、INPUT_ORIGINALS副本及原审计日志完整保留，不删除、不覆盖；首包不作为正式发布载荷。\n"
        "本包只包含本轮新脚本、身份/源码位置清单、实际新日志/收据、结果、自审和拒绝说明。"
        "旧C/D/monitor/E2/E3源码、捕获、正常/负例和ZIP均不再复制进来，按OLD_REFERENCE_LEDGER.json原路径直接读取。\n"
        "每项给完整仓库快照提交、可核Git blob绑定（若确实在Git中）、大小/SHA及原路径；"
        "旧包结果提交不冒称未跟踪ZIP本体也在该提交。\n"
        "未重新执行audit、9项检查或旧案例；仅一次封存CRC/成员大小/SHA核验，新增功能轮0。"
        "总控只读领取并统一发布，尚未直接发送成功，也不代表真人M2签收。\n\n"
        f"保留首包：{first['archive']}\nSHA256 {first['sha256']}，{first['bytes']} bytes。\n"
    )
    (OUT / "README.md").write_text(notice, encoding="utf-8", newline="\n")
    selected = ["START.md", "RESULT.md", "SELF_REVIEW.md", "INTAKE.json", "SOURCE_LOCATIONS.json",
                "SUPPLEMENT_SOURCE_LOCATIONS.json", "MISSING_ITEMS.json", "RECEIPT.json", "SELF_CHECKS.json",
                "COMMUNICATION_AUTH_CHECK.json", "COMMUNICATION_RESULT.json"]
    paths = [BASE / name for name in selected]
    paths += sorted(p for p in (BASE / "ROUND_01").iterdir() if p.is_file())
    paths += sorted(HERE.glob("*.py"))
    paths += sorted(p for p in OUT.iterdir() if p.is_file())
    members = [{"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)} for p in paths]
    for record in members:
        name = record["path"]
        if "/INPUT_ORIGINALS/" in name or name.endswith(".zip"):
            raise RuntimeError("Old package/source copy included in lightweight payload")
    dump(OUT / "MANIFEST.json", {"members": members, "payload_policy": "NEW_TASK5_FILES_ONLY", "old_case_payloads": 0})
    package = OUT / "M3_TASK5_INTAKE_LIGHTWEIGHT_20261017.zip"
    with zipfile.ZipFile(package, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for record in members:
            archive.write(ROOT / record["path"], record["path"])
        archive.write(OUT / "MANIFEST.json", "MANIFEST.json")
    with zipfile.ZipFile(package) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Lightweight CRC failure")
        for record in members:
            raw = archive.read(record["path"])
            if len(raw) != record["bytes"] or hashlib.sha256(raw).hexdigest() != record["sha256"]:
                raise RuntimeError("Lightweight member mismatch")
    receipt = {"status": "LIGHTWEIGHT_ADOPTED_FIRST_PACKAGE_PRESERVED", "archive": str(package),
               "bytes": package.stat().st_size, "sha256": sha(package), "payload_files": len(members),
               "zip_members": len(members) + 1, "crc_size_sha_verified_once": True,
               "old_case_source_archive_copies_in_payload": 0, "functional_rounds_added": 0,
               "audit_rounds_consumed_unchanged": 1, "actual_level_unchanged": "L0_STATIC_PLUS_L1_PYTHON_AUDIT",
               "pro_status": "PENDING_PRO_SOURCE_OR_TRACE", "board_release_allowed": False,
               "first_package_preserved": first, "git_writes": 0, "direct_send": "NOT_ATTEMPTED_READ_ONLY_PICKUP",
               "manifest_sha256": sha(OUT / "MANIFEST.json")}
    dump(OUT / "RECEIPT.json", receipt)
    message = json.dumps(receipt, ensure_ascii=False) + "\n"
    (OUT / "seal.stdout").write_text(message, encoding="utf-8", newline="\n")
    (OUT / "seal.stderr").write_bytes(b"")
    dump(OUT / "EXECUTION.json", dict(launch, end_utc=datetime.now(timezone.utc).isoformat(),
          elapsed_seconds=time.monotonic() - started, exit_code=0,
          stdout_sha256=sha(OUT / "seal.stdout"), stderr_sha256=sha(OUT / "seal.stderr")))
    print(message, end="")


if __name__ == "__main__":
    main()
