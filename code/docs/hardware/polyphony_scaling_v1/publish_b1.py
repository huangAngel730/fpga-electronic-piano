"""Bounded staged-tree gate and post-push handoff packaging; never commits/pushes."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location("b1_runner", ROOT / "code/scripts/run_m3_polyphony_scaling_acceptance.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def digest(path):
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("gate", "finalize"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--delivery", type=Path, required=True)
    parser.add_argument("--gate", type=Path)
    args = parser.parse_args()
    output, delivery = args.output.resolve(), args.delivery.resolve()
    output.relative_to(ROOT / "code/output")
    delivery.relative_to(ROOT / "code/output")
    output.mkdir(parents=True, exist_ok=False)
    run = module.Run(output)
    if args.mode == "gate":
        paths = run.command("tracked_paths", ["git", "ls-files", "-z"]).decode("utf-8").strip("\0").split("\0")
        before = [digest(ROOT / path) for path in paths]
        run.command("repo_gates", [shutil.which("pwsh") or shutil.which("powershell"), "-NoProfile",
                                   "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "code/scripts/check_repo.ps1")])
        after = [digest(ROOT / path) for path in paths]
        if before != after:
            raise ValueError("STAGED_GATE_INPUT_CHANGED")
        result = {"status": "STAGED_TREE_9_GATES_PASS", "exit_code": 0,
                  "inputs_before": before, "inputs_after": after, "steps": run.steps}
        (output / "receipt.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": result["status"], "inputs": len(paths), "gate_seconds": run.steps[-1]["elapsed_seconds"]}))
        return
    gate = args.gate.resolve()
    gate.relative_to(ROOT / "code/output")
    gate_receipt = json.loads((gate / "receipt.json").read_text(encoding="utf-8"))
    if gate_receipt["status"] != "STAGED_TREE_9_GATES_PASS":
        raise ValueError("NO_GATE")
    # A commit changes Git metadata, not the staged-tree content verified above.
    for item in gate_receipt["inputs_after"]:
        if digest(ROOT / item["path"]) != item:
            raise ValueError("POST_GATE_SOURCE_CHANGED:" + item["path"])
    head = run.command("head", ["git", "rev-parse", "HEAD"]).decode().strip()
    branch = run.command("branch", ["git", "branch", "--show-current"]).decode().strip()
    status = run.command("status", ["git", "status", "--porcelain"]).decode().strip()
    remote = run.command("remote_develop", ["git", "ls-remote", "origin", "refs/heads/develop"]).decode().split()[0]
    if branch != "develop" or status or head != remote:
        raise ValueError("NOT_CLEAN_PUSHED_DEVELOP")
    metadata = {"branch": branch, "commit": head, "verified_remote_develop": remote,
                "working_tree_clean": True, "gate_receipt": digest(gate / "receipt.json"), "steps": run.steps,
                "M2_notification": "待用户转发，尚未送达", "task_complete": False}
    (delivery / "GIT_DELIVERY.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    message = (f"M2，T061 B1 调度／状态存储／tagged ROM 传输隔离子阶段已完成并推送 develop：{head[:7]}。"
               "4/8/16/32槽×ROM1/3及慢算子共9配置，141次完整提交、970次无效/旧结果拒收；"
               "两份可编译RTL行为变异按指定检查非零拒收，40个既有软件自检、6个新单测及7个定向capture反例通过，"
               "最终暂存树9项门禁全PASS。源码、原stdout/stderr、退出码、工具/输入/产物SHA及开发期失败记录已封存。"
               "只改D043/D044 B范围，原冻结L56/7ROM、生产及共享表未改。"
               "本次仅独立L2/限定传输L3，ROM/算子为明确fixture，不含PCM/声学等价，不能称32声部已实现；"
               "CC64扫描/ACK服务和真实DSP排空仍待B2。唯一Gowin额度未用，无综合/STA/设备操作，T061不关闭。"
               "请复核附件并统一登记；下一步先做N4真实声音上下文适配与冻结L逐样本等价。\n\n待用户转发，尚未送达。\n")
    (delivery / "M2_通知_20261010.txt").write_text(message, encoding="utf-8")
    archive_path = delivery / "M3_T061_B1_交M2_20261010.zip"
    with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(delivery.iterdir()):
            if path.is_file() and path != archive_path:
                archive.write(path, path.name)
        for path in sorted(gate.iterdir()):
            if path.is_file():
                archive.write(path, "publish_gate/" + path.name)
        for path in sorted(output.iterdir()):
            if path.is_file():
                archive.write(path, "remote_verification/" + path.name)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip():
            raise ValueError("FINAL_ZIP_CRC")
    result = {"commit": head, "archive": digest(archive_path)}
    (output / "receipt.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
