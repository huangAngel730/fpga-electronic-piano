"""Collect actual receipts into a bounded, non-hardware completion report."""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
BASE = Path("m3_pro_fourvoice_trace_20261016")
DOC = ROOT / "code/docs/test" / BASE / "pro_basis_r08_20261017/coordinator"
TB = ROOT / "code/tb/board" / BASE / "pro_basis_r08_20261017"
SW = ROOT / "code/software" / BASE / "pro_basis_r08_20261017"
COMPONENTS = "recursive_include_audit public_port_map plan_consumption_guard output_reservation tool_dependency_identity build_admission_bundle capture_csv_codec async_reset_events frame_coverage_diff frame_accept_provenance finish_protocol_recorder real_authority_graph i2s_serial_compare tx_hold_sequences clip_lineage midi_ingress_arrival midi_recovery_schedule public_diff_diagnostics physical_photo_index io_voltage_budget measurement_profile latency_alignment board_session_capture recovery_manifest".split()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def identity(path):
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    ledger = read(DOC / "CONSUMPTION.json")
    runs = []
    final = {}
    for group in "RSCTH":
        for phase, folder in (("initial", "R01"), ("repair", "R02")):
            path = DOC / "RUNS" / group / folder / "RECEIPT.json"
            if not path.exists():
                continue
            receipt = read(path)
            assert receipt["group"] == group and receipt["phase"] == phase
            assert ledger["groups"][group][phase + "_consumed"] == 1
            assert ledger["groups"][group][phase + "_receipt"]["sha256"] == identity(path)["sha256"]
            runs.append({"group": group, "phase": phase, "status": receipt["status"], "exit_code": receipt["exit_code"], "elapsed_s": receipt["elapsed_s"], "limit_s": receipt["limit_s"], "cases_total": receipt["cases_total"], "cases_completed": receipt["cases_completed"], "assertions_matched": receipt["assertions_matched"], "audit_violations": receipt["audit_violations"], "receipt": identity(path)})
            for case in receipt["results"]:
                key = (case["component"], case["id"])
                if phase == "repair":
                    assert final.get(key, {}).get("assertion") != "MATCHED", "PASSED_CASE_REPLAY"
                final[key] = {**case, "group": group, "phase": phase, "receipt": path.relative_to(ROOT).as_posix()}
    components = []
    for number, component in enumerate(COMPONENTS, 1):
        manifest = TB / component / "CASES.json"
        definition = read(manifest)
        cases = [final.get((component, case["id"]), {"component": component, "id": case["id"], "expected": case["expected"], "assertion": "NOT_RUN"}) for case in definition["cases"]]
        counts = Counter(case["assertion"] for case in cases)
        ready = counts["MATCHED"] == len(cases)
        components.append({"id": f"R8-{number:02d}", "component": component, "group": definition["group"], "status": "SOFTWARE_READY_PENDING_REAL_INPUT" if ready else "PARTIAL_SOFTWARE_PENDING_REAL_INPUT", "level": "L1_LIMITED_SOFTWARE" if ready else "L0_L1_PARTIAL", "counts": dict(counts), "case_manifest": identity(manifest), "source_files": [identity(p) for p in sorted((SW / component).glob("*.py"))], "cases": cases, "real_verified": False, "board_release_allowed": False})
    r_cases = [value for (component, _), value in final.items() if component == "r08_integration"]
    r_definition = read(ROOT / "code/tb/board" / BASE / "pro_basis_r06_20261017/normalized_intake/r08_integration/CASES.json")
    r_ready = len(r_cases) == len(r_definition["cases"]) and all(c["assertion"] == "MATCHED" for c in r_cases)
    previous = read(ROOT / "code/docs/test" / BASE / "pro_basis_r07_20261017/capture_provenance/coordinator/PACKAGE_STATUS.json")
    original = [
        {"id": "R6-1", "status": "C6_STATIC_SOURCE_ASSEMBLY_L0_NOT_COMPILED", "remaining": "M2 exact HDL/tool admission"},
        {"id": "R6-2", "status": "PRIOR_SOFTWARE_REUSED_DRIVER_L0_NOT_COMPILED", "remaining": "actual public capture and first byte evidence"},
        {"id": "R6-3", "status": "NEW_R08_CASES_MATCHED_LIMITED" if r_ready else "NEW_R08_PARTIAL", "remaining": "REAL trace/oracle/authority", "group": "R"},
        {"id": "R6-4", "status": "25_NEW_REJECTION_CONTROL_CHECKS_AND_2_CLI_PASSED_PRE_R08", "remaining": "process tree / live dual streams / post-root cleanup safety NOT_QUALIFIED"},
        {"id": "R6-5", "status": "NEW_R08_CASES_MATCHED_LIMITED" if r_ready else "NEW_R08_PARTIAL", "remaining": "independent TX selection expectations and REAL trace", "group": "R"},
        {"id": "R6-6", "status": "28_NEW_CHECKS_PASSED_PRE_R08", "remaining": "no new full positive serial regression; REAL and TX selection expectations pending"},
        {"id": "R6-7", "status": "PRIOR_17_IDENTITY_CHECKS_REUSED", "remaining": "actual Part/version/board/Bank/electrical evidence"},
        {"id": "R6-8", "status": "OFFLINE_PROCEDURE_AND_IMPORT_PREPARED", "remaining": "physical capture/new fs/recovery/precise SRAM admission"},
    ]
    for key in ("R7-A", "R7-B", "R7-C", "R7-D"):
        original.append({"id": key, **previous["packages"][key]})
    status = {"schema": "M3_TASK_DAY2_R08_FINAL_STATUS_V1", "baseline": ledger["baseline"], "status": "PARTIAL_NEEDS_M2_ADMISSION_AND_REAL_INPUT", "inventory_total": 36, "new_components": components, "original_12": original, "runs": runs, "R_integration_cases": r_cases, "new_software_ready_components": sum(c["status"] == "SOFTWARE_READY_PENDING_REAL_INPUT" for c in components), "R_all_new_assertions_matched": r_ready, "r08_software_elapsed_s": sum(r["elapsed_s"] for r in runs), "prior_task_R07_V0396_elapsed_s": 22.081234317759634, "model_token_or_money_usage": "UNAVAILABLE_NOT_ESTIMATED", "hdl_eda_device_new_runs": 0, "board_release_allowed": False, "M2_delivery": "待用户转发，尚未送达", "old_R7C_unrun_cases": 6, "old_R7C_permission_restored": False}
    with (DOC / "PACKAGE_STATUS.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(status, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    pending_cases = [case for component in components for case in component["cases"] if case["assertion"] != "MATCHED"]
    old_bridge_cases = ROOT / "code/tb/board" / BASE / "pro_basis_r07_20261017/oracle_bundle_bridge/cases.json"
    requests = {"status": "REQUEST_ONLY_NOT_GRANTED", "R08_remaining": {"count": len(pending_cases), "cases": pending_cases, "initial_frozen_spec": identity(DOC / "FREEZE_R01/SPEC_T.json"), "source_identities": {component["component"]: component["source_files"] for component in components if component["status"].startswith("PARTIAL")}, "reason": "Initial T stopped on denied unfrozen pyc; single repair limited to related T13. Unrelated cases never run; no further group available."}, "R7C_remaining": {"count": 6, "manifest": identity(old_bridge_cases), "cases": [case for case in read(old_bridge_cases)["cases"] if case["name"] != "frozen_r6_public_fixture"], "reason": "Original initial and single targeted repair consumed; no old quota restored."}, "execution_authority": "M2 exact additional software group approval required before any remaining case", "no_request_is_permission": True, "real_tool_execution": "Separate exact source/tool/executor admission required", "M2_delivery": "待用户转发，尚未送达"}
    (DOC / "M2_DECISION_REQUESTS.json").write_text(json.dumps(requests, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    lines = ["# M3 task-day2 R08 集中交付", "", "整体 PARTIAL：软件限定结果如下；真实 Pro 链、G0–G3 与板卡放行均未完成。36 是原12包加新24项的库存，不是36项整体通过。", "", f"基线 `{ledger['baseline']}`。新24项中 {status['new_software_ready_components']} 项完成所列必要软件断言；每项真实分支仍 PENDING_REAL_INPUT。原 R7-C 仍有6项未执行，旧额度不恢复。", "", "## 五组实际执行", "", "| 组 | 轮次 | 匹配/已执行/计划 | 秒/上限 | 退出码 | 结果 |", "|---|---|---:|---:|---:|---|"]
    for run in runs:
        lines.append(f"| {run['group']} | {run['phase']} | {run['assertions_matched']}/{run['cases_completed']}/{run['cases_total']} | {run['elapsed_s']:.3f}/{run['limit_s']} | {run['exit_code']} | {run['status']} |")
    lines += ["", "MATCHED 代表与该例冻结期望相符，包含正常、拒收及 PENDING/UNKNOWN；不把负例拒收或未知判据升级为真实功能通过。首失败、原输入/源码快照、双流和各例实际结果保留在 FREEZE_* 与 RUNS；修复只消费对应增量，不复跑已通过例。", "", "## 新24项", "", "| 项 | 组件 | 最终断言计数 | 限定状态 |", "|---|---|---|---|"]
    for component in components:
        lines.append(f"| {component['id']} | {component['component']} | {json.dumps(component['counts'])} | {component['status']} |")
    lines += ["", "## 保留的边界及下一责任", "", f"- 新 R08 尚有 {len(pending_cases)} 例未通过必要执行；具体用例、源SHA与原SPEC见 M2_DECISION_REQUESTS.json。不得把T13增量9/9升级为T整组56/56。", "- S首组9例因 Windows 277–293字符的claim路径失败；仅缩短总控用例目录为三位序号，完整64位身份与候选语义不变，原41例未重跑。T首组20例后因SourceFileLoader尝试未冻结旧pyc停组；T13改从固定SHA源码字节加载后只核对应9例。", "- R7-A 采样器、R7-B 双路框架与新复位边沿 HDL 均未编译。B 最后 <=stop 改动只有静态等级；C6 静态闭包/装配核同不等于可编译或等价。", "- R7-C 首失败及一次定向正例修复保留，余6例 NOT_RUN；需要 M2 对精确新组另给许可。", "- R8-13 只按冻结 PT8211 LSBJ16 协议复用 PinDecoder。完整帧与不完整尾段分开，后者 UNKNOWN；没有新增 DSP 黄金或真实串行捕获。", "- M1：提供缺失的真实语义与逐样本 PCM/ID/双clip 黄金、算法确认和独立 TX 选择期望。", "- M2：决定纯软件结果登记；按 source/include/ROM/TB/工具依赖及安全执行器的精确组合另签首次 HDL 执行。进程树/双流收敛尚未获本轮执行许可，不因纯 guard 或文件哈希通过而放行。", "- M2/用户：实物 Part/version/核心板与 Dock 修订、Bank 与电气原件、仪器配置校准及同会话原始捕获、正确新.fs/完整STA与Recovery/Removal/CDC/恢复身份、精确一次SRAM许可仍待到件。本轮没有板卡/仪器/Flash/SRAM操作，没有 E/N32 新工作。", "", "## 原件、额度和发布", "", "PACKAGE_STATUS.json 列36项、各组件源码SHA、每例原始期望/结果和收据；CONSUMPTION.json 列唯一共享消费。各角色READY是执行前静态就绪原件；执行结果以本报告关联的实际收据为准。SOURCE/EXE/DLL仅文件读取，未启动工具或加载DLL；本机外部文件只交身份，不重分发安装文件。", "", f"R08 五组及修复实际累计 {status['r08_software_elapsed_s']:.6f} 秒；此前本任务 R07/V0396 累计 22.081234 秒另列，未重复计算为R08。模型 token/金额无法从本次执行证据取得，标为未知。", "", "DELIVERY/ORIGINALS_INDEX.json 索引每份原件与分卷 ZIP 的大小/SHA，分卷各自可读取，无需拼接。已签旧源码、首失败与合成/真实来源标记保留。安装工具身份不证明执行安全。", "", "本报告形成时尚未提交/推送；最终精确树九门禁、提交号和远端核验见后续 HANDOFF_FINAL。M2登记/最终复核：待用户转发，尚未送达。", ""]
    (DOC / "RESULT.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(json.dumps({"ready_components": status["new_software_ready_components"], "R_ready": r_ready, "runs": len(runs), "elapsed_s": status["r08_software_elapsed_s"]}))


if __name__ == "__main__":
    main()
