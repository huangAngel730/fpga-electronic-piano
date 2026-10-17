"""Seal existing B1 originals; no functional tests, EDA or hardware execution."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from check_observation_binding import DOC, HERE, ROOT, strict_json
from run_binding_selftest import identity
from metadata_cases import save


def main():
    r = strict_json((DOC / "B1_ROUND_01/RUN_RECEIPT.json").read_bytes())
    assert r["status"] == "PASS_METADATA_GATE_ONLY_REAL_PRO_PENDING" and len(r["cases"]) == 41
    for a, b in (("source_before", "source_after"), ("tool_before", "tool_after"),
                 ("input_before", "input_after"), ("referenced_input_before", "referenced_input_after")):
        assert r[a] == r[b]
    for call in r["calls"]:
        for stream in ("stdout", "stderr"):
            assert identity(call[stream]["path"]) == call[stream]
    intake = DOC / "intake_20261017"
    intake_copy = DOC / "INTAKE_READONLY_ORIGINALS"
    intake_copy.mkdir(exist_ok=False)
    consumed = []
    for name in ("INTAKE.json", "RECEIPT.json", "MISSING_ITEMS.json", "SOURCE_LOCATIONS.json",
                 "SUPPLEMENT_SOURCE_LOCATIONS.json", "RESULT.md", "SELF_CHECKS.json"):
        p = intake / name
        dst = intake_copy / name
        shutil.copyfile(p, dst)
        assert identity(p)["sha256"] == identity(dst)["sha256"]
        consumed.append({"original": identity(p), "snapshot": identity(dst)})
    fifth = strict_json((intake / "RECEIPT.json").read_bytes())
    assert fifth["status"] == "DONE_INTAKE_AUDIT__PENDING_PRO_SOURCE_OR_TRACE"
    assert fifth["rounds"]["this_window_consumed"] == 1
    save(DOC / "INTAKE_CONSUMPTION.json", {"status": "READ_ONLY_CONSUMED_AFTER_B1_SELFTEST_NO_RERUN",
        "files": consumed, "night5_reported_consumption": 1, "night2_consumption": 1,
        "shared_B1_consumed": 2, "shared_limit": 6,
        "actual_Pro_arrival": "NOT_RECEIVED_AT_NAMED_LOCAL_LOCATIONS",
        "night5_checks_reexecuted": False, "board_release_allowed": False})
    save(DOC / "SELF_REVIEW.json", {"status": "NO_BLOCKER_IN_METADATA_PREPARATION_SCOPE",
        "root_review": "Contract candidate/authority boundary, common tick mask and frame/lane/voice identity distinction, TX independent adoption, gate CLI outputs, source/tool/input before-after and archived raw bytes",
        "readonly_source_subagent": "e4_source_audit: old event apply/Release/retire/private identity, common tick and effect input gaps; no execution or edits",
        "readonly_gate_subagent": "e4_rtl_integration: whitespace placeholders and missing referenced-input freeze found before first functional round; minimal fixes and precise cases added; incremental readback no blocker",
        "first_functional_attempt_after_static_repairs": True,
        "original_failure_tool_rounds": 0,
        "software_selftest_level": "L1_METADATA_BINDING_GATE_ONLY",
        "static_source_difference_level": "L0",
        "new_Pro_DUT_calendar": "NOT_RUN_PENDING_SOURCE_OR_TRACE",
        "loaded_module_inventory": "UNKNOWN_NOT_DYNAMICALLY_TRACED; recorded Python EXE, enumerated runtime DLL/pyd and relevant stdlib identities only",
        "locator_semantics_monitor_END_contents": "DECLARATIONS_ONLY_NOT_VALIDATED_AGAINST_HDLS_OR_RAW_TRACE",
        "authority_verified": False, "pro_dut_pass": False, "board_release_allowed": False})
    result = {
        "task": "TASK_DAY_B1_OBSERVATION_BINDING_PREPARATION",
        "status": "DONE_LIMITED_PREPARATION__PENDING_PRO_SOURCE_OR_TRACE",
        "baseline_head": "414e1a9d3ee0617c5e8ba72dd4b22c36122c9926",
        "actual_level": "L0 source differences + L1 metadata gate; no RTL or real Pro calendar",
        "own_rounds_consumed": 1, "own_round_limit": 4,
        "night5_reported_rounds_consumed": 1, "B1_shared_consumed": 2, "B1_shared_limit": 6,
        "functional_group_seconds": r["elapsed_s"], "functional_group_exit": r["exit_code"],
        "metadata_structure_positive": 1, "metadata_rejections": 39, "actual_missing_arrival_pending": 1,
        "actual_child_exits": {"0": 2, "2": 40},
        "raw_command_count_including_version": len(r["calls"]),
        "round_receipt": identity(DOC / "B1_ROUND_01/RUN_RECEIPT.json"),
        "actual_pending_receipt": identity(DOC / "B1_ROUND_01/case_40.json"),
        "observation_contract": identity(DOC / "OBSERVATION_CONTRACT.json"),
        "input_identity": identity(DOC / "INPUT_IDENTITIES.json"),
        "intake_consumption": identity(DOC / "INTAKE_CONSUMPTION.json"),
        "Icarus_ModelSim_Gowin_device_calls": 0,
        "old_C_D_monitor_tests_reexecuted": 0, "M1_models_modified": False, "M2_formal_files_modified": False,
        "missing": ["M2 exact new Pro source/ROM/top identity and public event/apply/Release/retire/advance/request/result/effect mapping",
                    "Frozen independent same-input plan and actual complete same-axis public trace",
                    "Independent TX-adoption sidecar and success/finish/END/MONITOR_END originals",
                    "M1 same-source Pro golden adaptation; old R05/R06 references are present, not missing publication"],
        "next_owner": "M2 provides source and controlled observation binding; M3 B1 then derives independent real calendar in new effective budget; M1 PCM mathematics; M3 B2 serial",
        "authority_verified": False, "real_trace_calendar_checked": False,
        "pro_dut_pass": False, "board_release_allowed": False,
        "Git": "UNCOMMITTED_UNPUSHED_NIGHT_TASK1_SERIAL_PUBLICATION_OWNER",
        "M2_final_review": "待用户转发，尚未送达",
    }
    save(DOC / "RECEIPT.json", result)
    report = """# task-day B1：限定准备完成，真实Pro待件

夜间任务2完成本轮授权的最小观察合同、toy→真实源差异与metadata拒收入口，状态DONE_LIMITED_PREPARATION__PENDING_PRO_SOURCE_OR_TRACE。等级L0静态差异＋L1软件门禁；未签真实Pro日历、RTL、PCM、期限、串行、物理或板级，board_release_allowed=false。

OBSERVATION_CONTRACT.json共61字段，含事件接受/应用、真实slot Release/retire/generation、advance mask及帧级ID、请求/返回/commit/取消、配置与effect音频接受、独立TX实际采纳和B2原pins/收尾。旧源共同tick一次同沿推进四路，不能套旧toy四个错开lane交易；上午scalar lane监视器不是直接适配入口。commit不能反填TX sample，缺finish/END或唯一MONITOR_END原日志也不能签完整捕获。具体路径/行号和最小M2到件见TOY_TO_PRO_DIFF.md和OBSERVATION_CONTRACT.md。

check_observation_binding.py核调用方独立冻结的binding SHA、十份原件path/bytes/SHA、固定合同本体SHA、61字段/位宽/符号/公开性声明、语义与完成声明。拒收穿越/别名、错SHA、缺字段、私有量当公开黄金、toy scope/ID域、缺TX sidecar、漏收尾等metadata问题。成功仍authority_verified=false、real_trace_calendar_checked=false、Pro/板级false：不验证HDL出口、M2真实性/签名、原日志内容或逐沿日历，不能把marker原件说成真实Pro捕获。

真实工具只用已核Python3.12.4。命令 `C:/Users/songdongkuan/miniconda3/python.exe -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/run_binding_selftest.py --round 1`，外层exit0，3.609秒，1/4本窗口额度；夜间5报告1/2，B1共享2/6，总新功能秒数本窗3.609＋夜间5报告0.781=4.390秒。42子调用含version：2条exit0、40条预期exit2；41项＝1结构正例＋39拒收例＋1真实缺到件PENDING。每例预期拒收码与首差异在首进程前冻结，全部匹配。原命令/UTC起止/PID/双流/依赖/源码前后SHA在B1_ROUND_01。没有Icarus/ModelSim/Gowin/设备、旧C/D/monitor组或303/487重跑。

静态自审在执行前发现并修正空白/带空格占位词漏拒，以及引用原件manifest未纳入轮前后冻结；已补四个精确拒收与22份引用原件前后身份。新增空合同替换拒收。两个只读子智能体复核限定增量无新阻断，未代跑验证或启用审核员制度。功能轮没有失败；未使用剩余轮凑次数。动态加载依赖未追踪，只有枚举EXE/DLL/pyd/stdlib SHA，保持UNKNOWN。

只读消费夜间5最终INTAKE/RECEIPT/MISSING及源位置原件，没有重复其9项审计；本机新Pro指定目录与同执行trace仍缺，旧M1参考/ROM已存在但缺Pro同源适配，不能写成M1未发布。引用入口/本体快照在INTAKE_READONLY_ORIGINALS和INTAKE_CONSUMPTION.json。它们在本窗功能自检之后到件，仅作为静态来源补充，不回填本轮原收据或冒称再测真实输入。

下一责任：M2提供新Pro精确源/ROM/top、同版公开映射、身份/生命周期/采样相位及真实完整捕获；M3 B1在后续有效许可内以冻结独立输入推日历，再做四独奏/同发/逐放及取消后发布、重复/跨epoch/漏第四路的真实反例；M1负责同源PCM/clip数学；B2接独立TX采纳与原pins。若必须增公开观察出口，M2受控变更，不由本窗口写正式工程。Pro基础及拓展顺序保留。

本窗口只写三处pro_binding_20261017，排除intake/coordinator；tb/board仅README说明缺源不造toy，无RTL声称。未动Git/index/门禁/编号/共享状态，未提交、未推送。总控统一汇合、门禁与发布；M2最终限定复核及共享状态登记待用户转发，尚未送达。原件ZIP、清单与交付SHA见DELIVERY_RECEIPT.json。
"""
    with (DOC / "RESULT.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(report)
    roots = [HERE, DOC, ROOT / "code/tb/board/m3_pro_fourvoice_trace_20261016/pro_binding_20261017"]
    files = []
    for tree in roots:
        for p in tree.rglob("*"):
            if p.is_file() and not p.name.startswith("SEAL_EXECUTION") and not any(part in ("intake_20261017", "coordinator_20261017", "__pycache__") for part in p.relative_to(tree).parts):
                files.append(p)
    files = sorted(set(files))
    manifest = {"entries": [{"member": p.relative_to(ROOT).as_posix(), **identity(p)} for p in files],
                "scope": "B1_OWN_WRITESET_PLUS_READONLY_INPUT_SNAPSHOTS", "real_Pro": False}
    save(DOC / "DELIVERY_MANIFEST.json", manifest)
    archive = DOC / "M3_B1_OBSERVATION_BINDING_PREPARATION_20261017.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in files:
            z.write(p, p.relative_to(ROOT).as_posix())
        z.write(DOC / "DELIVERY_MANIFEST.json", "DELIVERY_MANIFEST.json")
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist()) == len(files) + 1
        for entry in manifest["entries"]:
            raw = z.read(entry["member"])
            assert len(raw) == entry["bytes"] and hashlib.sha256(raw).hexdigest() == entry["sha256"]
    for entry in consumed:
        assert identity(entry["original"]["path"]) == entry["original"]
    delivery = {"status": result["status"], "created_utc": datetime.now(timezone.utc).isoformat(),
        "archive": identity(archive), "manifest": identity(DOC / "DELIVERY_MANIFEST.json"),
        "members_verified": len(files) + 1, "receipt": identity(DOC / "RECEIPT.json"),
        "communication": "NOT_YET_SENT", "board_release_allowed": False}
    save(DOC / "DELIVERY_RECEIPT.json", delivery)
    publish = [p.relative_to(ROOT).as_posix() for p in HERE.glob("*.py")]
    publish += [p.relative_to(ROOT).as_posix() for p in DOC.glob("*") if p.is_file()]
    publish += [p.relative_to(ROOT).as_posix() for p in (roots[-1]).glob("*") if p.is_file()]
    publish.append((DOC / "PUBLICATION_FILES.json").relative_to(ROOT).as_posix())
    publish.append((DOC / "SEAL_EXECUTION_RECEIPT.json").relative_to(ROOT).as_posix())
    save(DOC / "PUBLICATION_FILES.json", {"files": sorted(publish), "only_own_write_set": True,
         "expanded_originals_inside_ZIP_not_duplicated_for_publication": True,
         "intake_and_coordinator_not_modified_or_published_by_this_list": True,
         "Git": "NOT_SUBMITTED_COORDINATOR_OWNS_SERIAL_PUBLISH"})
    print(json.dumps(delivery, ensure_ascii=False))


if __name__ == "__main__":
    main()
