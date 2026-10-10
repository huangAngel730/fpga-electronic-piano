"""Final staged-source gate and post-push packaging, no commit/push/device action."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location("b2a_runner", ROOT / "code/scripts/run_m3_polyphony_scaling_acceptance.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def digest(path):
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("gate", "finalize"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--delivery", type=Path)
    parser.add_argument("--gate", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(ROOT / "code/output")
    output.mkdir(parents=True, exist_ok=False)
    run = runner.Run(output)
    if args.mode == "gate":
        paths = run.command("tracked_paths", ["git", "ls-files", "-z"]).decode("utf-8").strip("\0").split("\0")
        before = [digest(ROOT / path) for path in paths]
        # Freeze staged content as well as working-tree inputs. A later change
        # to the index may not quietly reuse this gate.
        staged_tree = run.command("staged_tree", ["git", "write-tree"]).decode().strip()
        run.command("repo_gates", [shutil.which("pwsh") or shutil.which("powershell"), "-NoProfile",
                                   "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "code/scripts/check_repo.ps1")])
        after = [digest(ROOT / path) for path in paths]
        if before != after:
            raise ValueError("STAGED_GATE_INPUT_CHANGED")
        result = {"status": "STAGED_TREE_9_GATES_PASS", "exit_code": 0, "staged_tree": staged_tree,
                  "inputs_before": before, "inputs_after": after, "steps": run.steps}
        (output / "receipt.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": result["status"], "inputs": len(paths), "gate_seconds": run.steps[-1]["elapsed_seconds"]}))
        return
    gate = args.gate.resolve()
    gate.relative_to(ROOT / "code/output")
    delivery = args.delivery.resolve()
    delivery.relative_to(ROOT / "code/output")
    receipt = json.loads((gate / "receipt.json").read_text(encoding="utf-8"))
    if receipt["status"] != "STAGED_TREE_9_GATES_PASS":
        raise ValueError("NO_PUBLISH_GATE")
    for item in receipt["inputs_after"]:
        if digest(ROOT / item["path"]) != item:
            raise ValueError("POST_GATE_INPUT_CHANGED:" + item["path"])
    head = run.command("head", ["git", "rev-parse", "HEAD"]).decode().strip()
    tree = run.command("tree", ["git", "rev-parse", "HEAD^{tree}"]).decode().strip()
    branch = run.command("branch", ["git", "branch", "--show-current"]).decode().strip()
    status = run.command("status", ["git", "status", "--porcelain"]).decode().strip()
    remote = run.command("remote_develop", ["git", "ls-remote", "origin", "refs/heads/develop"]).decode().split()[0]
    if head != remote or branch != "develop" or status or tree != receipt["staged_tree"]:
        raise ValueError("NOT_EXACT_GATED_CLEAN_PUSHED_TREE")
    result = {"commit": head, "remote_develop": remote, "tree": tree, "branch": branch,
              "working_tree_clean": True, "M2_notification": "待用户转发，尚未送达", "task_complete": False,
              "gate_receipt": digest(gate / "receipt.json"), "steps": run.steps}
    (delivery / "GIT_DELIVERY.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    notice = (f"M2，T061 B2a真实声音后端子阶段已完成并推送develop：{head[:7]}。"
              "同一混合候选保留冻结ADSR/Pitch逐时钟流水，共享实际钢琴波表、定点gain与混音；"
              "先N4长程逐样本数学复算通过，再跑8/16/32及慢后端。详细数量、周期与覆盖见DELIVERY和原receipt。"
              "两份可编译行为反例及9种完整capture错误均按指定原因拒收，6项新单测和最终暂存树9门禁PASS。"
              "源/ROM/工具/配置/产物SHA、原stdout-stderr/exit/开发失败记录齐套。"
              "只改D043/D044 B五路径，冻结L56/7ROM、原T060/B0/B1及共享文件不改。"
              "本次限定后端L2/L3，不是完整冻结L事件到PCM等价或已实现32声部演奏；"
              "MIDI分配、CC64/Release ACK、B1持久状态接线及端到端服务边界仍待下一独立阶段。"
              "无Gowin/STA/production接入/设备操作，一次独立综合额度未用，T061不关闭。"
              "请复核附件并统一登记；本阶段不申请安装/烧录/接线。\n\n待用户转发，尚未送达。\n")
    (delivery / "M2_通知_20261010.txt").write_text(notice, encoding="utf-8")
    target = delivery / "M3_T061_B2a_交M2_20261010.zip"
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
            raise ValueError("FINAL_FORWARD_ZIP_CRC")
    result["archive"] = digest(target)
    (output / "receipt.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"commit": head, "archive": result["archive"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
