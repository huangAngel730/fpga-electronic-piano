"""Produce final forwarding packet after ordinary push and fetch verification."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", choices=("R01", "R02"), required=True)
    args = parser.parse_args()
    commit = git("rev-parse", "HEAD").decode().strip()
    assert git("rev-parse", "origin/develop").decode().strip() == commit
    assert not git("diff", "--name-only") and not git("diff", "--cached", "--name-only")
    plan = json.loads((HERE / "PUBLICATION_PLAN.json").read_text(encoding="utf-8"))
    actual = sorted(git("diff-tree", "--no-commit-id", "--name-only", "-r", commit).decode().splitlines())
    assert actual == plan["files"], "unexpected publication tree"
    gate = json.loads((HERE / ("gate_" + args.gate) / "GATE_RECEIPT.json").read_text(encoding="utf-8"))
    assert gate["status"] == "PASS" and gate["pass_count"] == 9 and gate["exit_code"] == 0
    assert gate["exact_inputs_unchanged"] and gate["before"]["head"] == git("rev-parse", "HEAD^").decode().strip()
    identities = {}
    for relative in actual:
        raw = (REPO / relative).read_bytes()
        published = git("show", commit + ":" + relative)
        assert raw == published or (not relative.endswith(".zip") and raw.replace(b"\r\n", b"\n") == published), relative
        identities[relative] = {"bytes": len(published), "git_blob_sha256": sha(published),
                                "working_sha256": sha(raw), "LF_normalization_only": raw != published}
    receipt = {"status": "PUBLISHED_REMOTE_TRACKING_SHA_VERIFIED_AFTER_FETCH", "commit": commit,
               "github": "https://github.com/huangAngel730/fpga-electronic-piano/commit/" + commit,
               "files": identities, "gate": {k: gate[k] for k in ("status", "exit_code", "pass_count", "elapsed_seconds")},
               "board_release_allowed": False, "human_delivery": "WAITING_FOR_USER_FORWARD"}
    (HERE / "PUBLISHED_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    message = ("M2，M3 chat8回执处理及chat9增量已由白天总控核查并发布develop，提交 " + commit + "。\n"
               "M1第11原包已核，原缺包阻断解除。冻结模型独立重算303次发布的PCM/ID/时刻/clip一致，"
               "10项新软件负例通过，申请固定正常窗口的限定数学复核，不是通用取消/HOLD/Release或板级通过。\n"
               "T052现机源/工具/显式环境及Job正负例材料已齐；真实执行仍未批准。"
               "请先决定唯一code/output合成拒收探针写集，再审精确一次执行组合，原proposal保持false。\n"
               "B旧五pair STA复用；D新静态差异列明事件队列32/8、640x480八槽覆盖、98bit谱面CDC与单RGB/TMDS链。"
               "请定后续复制接入选择与范围。\n"
               "最新A→C原件来源一致；纯软件等级已纠正。测试临时路径越界也已修正并记录，旧空目录保留，原日志不改。\n"
               "附件含177项源/原始命令双流/退出码/SHA/失败史及详细HANDOFF_TO_M2.txt；发布九门禁全通过。"
               "没有新业务RTL/EDA/设备，board_release_allowed=false。请限定复核并更新任务状态。\n"
               "待用户转发，尚未送达。\n")
    (HERE / "FORWARD_TO_M2.txt").write_text(message, encoding="utf-8", newline="\n")
    packet = HERE / ("M3_CHAT8_CHAT9_GITHUB_HANDOFF_" + commit[:7] + ".zip")
    with zipfile.ZipFile(packet, "x", zipfile.ZIP_DEFLATED) as archive:
        for name in ("M3_CHAT8_CHAT9_LIMITED_DELIVERY_20261016.zip", "HANDOFF_TO_M2.txt", "DELIVERY_RECEIPT.json", "PUBLISHED_RECEIPT.json", "FORWARD_TO_M2.txt", "finalize_publication.py"):
            archive.write(HERE / name, name)
        for run in ("R01", "R02"):
            path = HERE / ("REPOSITORY_GATE_" + run + ".zip")
            if path.exists():
                archive.write(path, path.name)
    with zipfile.ZipFile(packet) as archive:
        assert archive.testzip() is None
    result = {"packet": str(packet), "bytes": packet.stat().st_size, "sha256": sha(packet.read_bytes()), "commit": commit}
    (HERE / "FORWARD_PACKET_SHA.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
