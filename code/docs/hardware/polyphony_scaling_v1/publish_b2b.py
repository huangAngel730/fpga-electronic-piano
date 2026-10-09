"""Reuse the previously audited exact staged-tree gate; finalize B2b only."""
import argparse
import json
from pathlib import Path
import zipfile

from publish_b2a import ROOT, digest, runner


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("gate", "finalize"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--delivery", type=Path)
    parser.add_argument("--gate", type=Path)
    args = parser.parse_args()
    if args.mode == "gate":
        import publish_b2a
        publish_b2a.main()
        return
    output = args.output.resolve()
    output.relative_to(ROOT / "code/output")
    output.mkdir(parents=True, exist_ok=False)
    run = runner.Run(output)
    gate, delivery = args.gate.resolve(), args.delivery.resolve()
    gate.relative_to(ROOT / "code/output")
    delivery.relative_to(ROOT / "code/output")
    receipt = json.loads((gate / "receipt.json").read_text(encoding="utf-8"))
    if receipt["status"] != "STAGED_TREE_9_GATES_PASS":
        raise ValueError("NO_STAGED_GATE")
    for item in receipt["inputs_after"]:
        if digest(ROOT / item["path"]) != item:
            raise ValueError("POST_GATE_SOURCE_CHANGED")
    head = run.command("head", ["git", "rev-parse", "HEAD"]).decode().strip()
    tree = run.command("tree", ["git", "rev-parse", "HEAD^{tree}"]).decode().strip()
    branch = run.command("branch", ["git", "branch", "--show-current"]).decode().strip()
    status = run.command("status", ["git", "status", "--porcelain"]).decode().strip()
    remote = run.command("remote_develop", ["git", "ls-remote", "origin", "refs/heads/develop"]).decode().split()[0]
    if head != remote or tree != receipt["staged_tree"] or branch != "develop" or status:
        raise ValueError("NOT_EXACT_GATED_CLEAN_PUSH")
    result = {"commit": head, "remote_develop": remote, "tree": tree, "working_tree_clean": True,
              "task_complete": False, "M2_notification": "待用户转发，尚未送达",
              "gate_receipt": digest(gate / "receipt.json"), "steps": run.steps}
    (delivery / "GIT_DELIVERY.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    notice = (f"M2，T061 B2b四声部事件到PCM接入子阶段已完成并推送develop：{head[:7]}。"
              "沿同一混合候选只读复用冻结统一事件路由/allocator/CC64/control snapshot，"
              "接既有B1完整tag、双bank原子提交及B2a真实数学后端。"
              "N4长程R1和多拍ROM R3通过独立accepted-event到路由/退场/控制/时钟/PCM逐样本复算，"
              "合计10466个完整结果、实测67–77/75–85拍；真实退场身份变化的2帧正确作废。"
              "并复现修复前端cancel同沿丢已接受音符的问题，新增on/off取消后继续PCM复算，旧失败保留。"
              "旧generation误收和gain向零取整两可编译行为反例按指定原因拒收，6种新边界完整capture错误拒收，最终暂存树9门禁PASS。"
              "新源/实际编译carrier/工具/ROM/原stdout-stderr/exit/SHA及旧开发失败记录已封存。"
              "仅N4完整事件链路，不冒称冻结L整个top逐时钟等价；8/16/32事件路由尚未实现，原高N协议/数学子项不能替代整链演奏。"
              "取消只丢token，不回滚DSP；外部长期背压和连续sample优先的无条件事件服务上界仍未签。"
              "只改D043/D044 B五路径，生产/ROM/原L及八共享文件不改，无综合/STA/安装/烧录/接线，单次综合额度仍未用，T061保持未关闭。"
              "请复核附件并统一登记；下一独立阶段推广同一候选N8再按实际稳定结果推进16/32。\n\n待用户转发，尚未送达。\n")
    (delivery / "M2_通知_20261010.txt").write_text(notice, encoding="utf-8")
    target = delivery / "M3_T061_B2b_交M2_20261010.zip"
    with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(delivery.iterdir()):
            if path.is_file() and path != target:
                archive.write(path, path.name)
        for folder, prefix in ((gate, "publish_gate"), (output, "remote_verification")):
            for path in sorted(folder.iterdir()):
                if path.is_file():
                    archive.write(path, prefix + "/" + path.name)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip():
            raise ValueError("ZIP_CRC")
    result["archive"] = digest(target)
    (output / "receipt.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"commit": head, "archive": result["archive"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
