"""Seal the new passive monitor's originals; never execute a DUT or test."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

SOFT = Path(__file__).resolve().parent
ROOT = SOFT.parents[4]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017"
TB = ROOT / "code/tb/board/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017"
BUNDLE = Path("E:/FPGA/GAOYUNFPGA/night_task/10.17/M1_M2_M3_Pro夜间任务与并行窗口_20261016")


def identity(path):
    return {"bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True,
                          capture_output=True).stdout.decode("utf-8").strip()


def main():
    inputs = []
    for path in sorted(BUNDLE.iterdir()):
        if path.is_file():
            inputs.append({"path": str(path), **identity(path)})
    missing = ["code/rtl/board/m2_138k_pro_fourvoice_candidate_20261016",
               "code/model/m1_r05_pcm_oracle_20261016/pro_successor_20261016"]
    save(DOC / "INPUT_IDENTITIES.json", {
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "head": git("rev-parse", "HEAD"), "origin_develop": git("rev-parse", "origin/develop"),
        "bundle": inputs, "candidate_presence": {p: (ROOT/p).exists() for p in missing},
        "scope": "Local checkout only; absence does not assert another member's work status"})
    rounds = [json.loads((DOC/f"ROUND_{i:02d}/RECEIPT.json").read_text(encoding="utf-8")) for i in (1, 2)]
    assert all(r["passed"] and r["identity_stable"] for r in rounds)
    final = rounds[-1]
    files = [*sorted(p for p in TB.rglob("*") if p.is_file()),
             *sorted(p for p in SOFT.iterdir() if p.is_file()),
             *sorted(p for p in DOC.iterdir() if p.is_file())]
    for i in (1, 2):
        files.extend(sorted(p for p in (DOC/f"ROUND_{i:02d}").rglob("*") if p.is_file()))
    entries = {p.relative_to(ROOT).as_posix(): p for p in files}
    payload = {name: identity(path) for name, path in sorted(entries.items())}
    delivery = DOC / "DELIVERY"
    delivery.mkdir(exist_ok=False)
    archive = delivery / "M3_PRO_PASSIVE_MONITOR_ORIGINALS_20261017.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for name, path in sorted(entries.items()):
            bundle.write(path, name)
        bundle.writestr("MANIFEST.json", json.dumps(payload, ensure_ascii=False, indent=2)+"\n")
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        assert set(bundle.namelist()) == set(payload) | {"MANIFEST.json"}
        for name, row in payload.items():
            data = bundle.read(name)
            assert len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"]
    receipt = {
        "status": "DONE_ISOLATED_MONITOR_INCREMENT", "actual_level": "L2_MONITOR_SELFTEST_ONLY",
        "pro_dut_pass": False, "board_release_allowed": False,
        "originals": {"path": archive.relative_to(ROOT).as_posix(), **identity(archive)},
        "payload_files": len(payload), "zip_members": len(payload)+1, "crc_size_sha_verified": True,
        "new_rounds": 2, "round_limit": 3, "seconds": sum(r["seconds"] for r in rounds),
        "old_quota_reset": False, "ModelSim_Gowin_device_calls": 0,
        "final_round": "ROUND_02", "positive_cases": [0, 23, 24],
        "negative_cases": final["negative_targets"],
        "final_sources": final["source_after"], "tool_file_count": final["tool_file_count"],
        "positive": final["positive"],
        "outer_process_exits": {"preflight_wrong_root": 1, "round1": 0,
                                "prelaunch_round2_success_guard": 1, "round2": 0},
        "publication_at_seal": "Not committed or pushed; gate and remote receipt follow separately"}
    save(delivery / "RECEIPT.json", receipt)
    content = f"""# Pro 被动监视器增量结果（2026-10-17）

本增量已完成实现、定向自检、自审和原件封存；只签 **L2_MONITOR_SELFTEST_ONLY**，不签真实 Pro DUT、PCM算法、串行解码或板级。`pro_dut_pass=false`，`board_release_allowed=false`。

- 最终第二轮：3个正例、22个故障反例符合预期，外层退出0；正例vvp退出0，反例均预期退出1且唯一FIRST_REJECT匹配。连续正常观察5062沿、8次接受、6次提交、2次清理、2个epoch；正常最大接受到提交10拍是夹具值。
- 边界：接受+832拍cancel/reset通过，+833拍cancel/reset拒收；22份故障CSV均保留拒收沿，周期连续且末行与首拒收周期相同。
- 新包共2/3轮，编译/仿真及版本调用组计{receipt['seconds']:.3f}秒；ModelSim/Gowin/设备调用0。旧夜间额度未恢复。执行路径、环境、工具版本与SHA、命令、双流、时间、退出码在两轮收据及ZIP内。
- 历史：首个Python路径错误退出1、未启动编译；首轮功能通过；封存检查发现故障沿缺失后保留首轮，第二轮修复。第二轮曾被成功停止保护预启动拒绝（退出1），未消费编译轮数；具体说明见REPAIR_02.md。
- 代码和工具前后身份稳定。范围限D的三个pro_monitor_20261017独占子目录，正式RTL/约束/共享状态未改。

原件：`DELIVERY/{archive.name}`，{receipt['originals']['bytes']}字节，SHA-256 `{receipt['originals']['sha256']}`；{len(payload)}个清单载荷、{len(payload)+1}个ZIP成员，已重开核CRC/大小/SHA。它包含两轮CSV、版本/编译/仿真原始双流、进程/源码/工具身份、冻结源码及失败说明；不含正在生成的RESULT/DELIVERY文件自身，避免自引用。

接入合同见CONTRACT.md，三岗后续安排见PRO_NEXT_STEPS.md。真实Pro源/ROM及公开映射尚未到本机，下一责任为M2固定映射和精确输入，M3再按有效新许可连接，M1独立核PCM数学。稳定后合法PA主动开启未单列正例，串行引脚仅记录未解码，所有物理项未验。

封存时未提交/未推送；最终精确树门禁、提交与远端SHA另在本目录PUBLICATION_STATUS及GATE_R01原件登记。M2最终限定复核及状态登记待用户转发，不把本机自审作为M2签收。
"""
    with (DOC/"RESULT.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
    print(json.dumps({k: receipt[k] for k in ("status", "originals", "payload_files", "seconds")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
