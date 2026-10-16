"""Package published Git blobs, original sealed evidence and gate receipts."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--gate", required=True, choices=("R01", "R02"))
    args = parser.parse_args()
    commit = git("rev-parse", args.commit).decode().strip()
    assert git("rev-parse", "HEAD").decode().strip() == commit
    assert git("rev-parse", "origin/develop").decode().strip() == commit
    assert not git("diff", "--name-only") and not git("diff", "--cached", "--name-only")
    plan = json.loads((HERE / "PUBLICATION_PLAN.json").read_text(encoding="utf-8"))
    expected = sorted(plan["files"] + [(HERE / "PUBLICATION_PLAN.json").relative_to(REPO).as_posix()])
    actual = sorted(git("diff-tree", "--no-commit-id", "--name-only", "-r", commit).decode("utf-8").splitlines())
    assert actual == expected, "unexpected committed files"
    gate = json.loads((HERE / ("gate_" + args.gate) / "GATE_RECEIPT.json").read_text(encoding="utf-8"))
    assert gate["status"] == "PASS" and gate["pass_count"] == 9 and gate["exit_code"] == 0
    assert gate["exact_inputs_unchanged"] and gate["before"]["head"] == git("rev-parse", commit + "^").decode().strip()
    records = {}
    blobs = {}
    for relative in expected:
        original = (REPO / relative).read_bytes()
        if relative in plan["file_identities"]:
            assert {"bytes": len(original), "sha256": sha(original)} == plan["file_identities"][relative], relative
        blob = git("show", commit + ":" + relative)
        assert blob == original or (not relative.endswith(".zip") and blob == original.replace(b"\r\n", b"\n")), relative
        if relative.endswith(".py"):
            ast.parse(blob, filename=relative)
        records[relative] = {"working_sha256": sha(original), "git_blob_sha256": sha(blob), "bytes": len(blob),
                             "LF_normalization_only": blob != original}
        blobs[relative] = blob
    receipt = {"status": "PUBLISHED_AND_REMOTE_TRACKING_SHA_VERIFIED", "commit": commit,
               "github": "https://github.com/huangAngel730/fpga-electronic-piano/commit/" + commit,
               "remote_tracking_after_fetch": commit, "branch": "develop", "files": records,
               "gate": {k: gate[k] for k in ("status", "exit_code", "pass_count", "elapsed_seconds", "exact_inputs_unchanged")},
               "new_A_B_C_D_regression_calls_by_coordinator": 0, "board_release_allowed": False,
               "delivery_state": "WAITING_FOR_USER_FORWARD_NOT_DELIVERED"}
    with (HERE / "PUBLICATION_RECEIPT.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    message = ("M2，M3四包已由总控集中核查并发布develop，提交 " + commit + "。\n"
               "A的7ms watchdog隔离候选真实ModelSim通过（32软件测试、6接受/4活动声部/303提交）；原6ms失败保留。\n"
               "B同版138K C/40MHz一次定向PnR/STA通过，五对端点中最低Setup +1.736ns、Hold 0.000ns，仅限报告范围。\n"
               "C公开PCM/PT8211模块仿真及20软件例通过；D新授权修复最终99检查和4故障负例通过。\n"
               "四份原件封包、源码、双流/退出码、输入输出SHA、失败历史及九项发布门禁随附件；详细范围见HANDOFF_TO_M2.txt。\n"
               "请限定复核并登记。A逐请求账本、真实R05串行逐样本、正式音画共存及本轮板测/模拟延迟未签；"
               "board_release_allowed=false，不据此放行码流。B旧包中的D PARTIAL以本次D修复报告为准。\n"
               "待用户转发，尚未送达。\n")
    (HERE / "FORWARD_TO_M2.txt").write_text(message, encoding="utf-8", newline="\n")
    archive_path = HERE / ("M3_FOUR_PACKAGES_GITHUB_HANDOFF_" + commit[:7] + ".zip")
    with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED) as archive:
        for relative, blob in blobs.items():
            archive.writestr(relative, blob)
        for name in ("PUBLICATION_RECEIPT.json", "FORWARD_TO_M2.txt"):
            archive.write(HERE / name, name)
        for run in ("R01", "R02"):
            path = HERE / ("REPOSITORY_GATE_" + run + ".zip")
            if path.is_file():
                archive.write(path, path.name)
        archive.write(Path(__file__), "finalize_forward_package.py")
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        for relative, blob in blobs.items():
            assert archive.read(relative) == blob
    result = {"archive": str(archive_path), "bytes": archive_path.stat().st_size,
              "sha256": sha(archive_path.read_bytes()), "commit": commit, "published_files": len(actual)}
    (HERE / "FORWARD_PACKAGE_SHA.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
