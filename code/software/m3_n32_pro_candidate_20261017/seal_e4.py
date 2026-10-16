"""Seal existing E4 originals only; never invoke a functional or EDA tool."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import zipfile

from e4_common import ROOT, DOC, SOFT, identity, write_new

BUILD = ROOT / "code/build/138k_polyphony_resource/m3_n32_pro_candidate_20261017"
TREES = [ROOT / name for name in (
    "code/rtl/common/m3_n32_pro_candidate_20261017",
    "code/tb/audio/m3_n32_pro_candidate_20261017",
    "code/software/m3_n32_pro_candidate_20261017",
    "code/build/138k_polyphony_resource/m3_n32_pro_candidate_20261017",
    "code/docs/test/m3_n32_pro_candidate_20261017",
)]
COORD = ROOT / "code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/task2_coordinator"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify(item):
    assert identity(item["path"]) == item, item["path"]


def main():
    rounds = [read(DOC / f"ROUND_{i:02d}/RUN_RECEIPT.json") for i in range(1, 6)]
    assert len(list(DOC.glob("ROUND_*_CONSUMED.json"))) == 5
    assert rounds[-1]["status"] == "E4_SCOPED_COMPOSITION_AND_NEGATIVES_PASS"
    calls = []
    for r in rounds:
        assert r["functional_attempt_consumed"] and r["physical_calls"] == 0
        assert r["source_before"] == r["source_after"]
        assert r["tool_before"] == r["tool_after"]
        assert r["stage_before"] == r["stage_after"]
        assert r["elapsed_s"] < 900
        assert sum(c["elapsed_s"] for c in r["calls"]
                   if Path(c["argv"][0]).name.lower().startswith("python")) < 90
        for key, info in r["source_snapshots"].items():
            verify(info)
            assert info["sha256"] == r["source_before"][key]["sha256"]
        for c in r["calls"]:
            verify(c["stdout"])
            verify(c["stderr"])
            assert not c["timeout"] and not c["error"] and not c["log_limit_exceeded"]
            assert c["elapsed_s"] < c["step_budget_s"]
            calls.append({"round": r["round"], **c})

    normal = []
    for n in (4, 8, 16, 32):
        r = rounds[3 if n == 32 else 2]
        case = next(c for c in r["cases"] if c["case"]["name"] == f"normal_n{n}")
        verify(case["check_result"])
        report = read(case["check_result"]["path"])
        assert report["status"] == "PASS_ISOLATED_FROZEN_PIANO_E4_PARTIAL"
        assert report["all_nonzero_lanes"] == list(range(n))
        assert report["max_request_commit_cycles"] < 833
        assert report["transport"]["committed"] == 32
        verify(case["sim_stdout"])
        binding = case.get("reuse_binding")
        if binding:
            verify(binding["receipt"])
        normal.append({"n": n, "receipt": identity(DOC / f"ROUND_{r['round']:02d}/RUN_RECEIPT.json"),
                       "case": case, "summary": report})

    bad = [c for r in rounds[3:] for c in r["cases"]
           if c["case"]["name"].startswith("bad_")]
    assert len(bad) == len({c["case"]["name"] for c in bad}) == 11
    for c in bad:
        verify(c["sim_stdout"])
        raw = Path(c["sim_stdout"]["path"]).read_text(encoding="utf-8")
        failures = re.findall(r"(?m)^\s*(?:#\s*)?\*\*\s*(Fatal|Error|Failure):\s*(.*)$", raw)
        if c["status"] == "ACTUAL_RTL_TARGET_REJECTED":
            assert len(failures) == 1 and failures[0] == ("Fatal", c["diagnostic"])
        else:
            assert c["status"] == "ACTUAL_RTL_MUTANT_INDEPENDENTLY_REJECTED"
            assert not failures
            verify(c["check_result"])
            assert read(c["check_result"]["path"])["reason"] == c["diagnostic"]

    latest = rounds[-1]["source_before"]
    addendum = {
        "status": "SIMULATION_ONLY_NEGATIVE_MONITOR_SUCCESSOR_NOT_PRO",
        "positive_tb_sha256": "38265540a81990ca61bb6e4a4217a4c8d52fc99234f0b4575f12a33b11812bb9",
        "negative_successor_tb_sha256": "65281fdbef1b912ee6194017bc26b93adb349ee0ede47896e3e06bc3ffda9501",
        "only_tb_change": "Immediate result-valid ID monitor before F/K; business RTL and stimulus unchanged",
        "normal_groups_rerun_with_successor_tb": False,
        "round5_sources": latest,
        "round5_receipt": identity(DOC / "ROUND_05/RUN_RECEIPT.json"),
        "physical_calls": 0, "board_release_allowed": False,
    }
    write_new(BUILD / "NEGATIVE_MONITOR_SOURCE_ADDENDUM.json", addendum)

    audit = {
        "scope": "READ_ONLY_SELF_AUDIT_AND_EXISTING_ORIGINALS_IDENTITY_SEAL",
        "functional_tools_invoked_by_sealer": 0,
        "root_review": "Receipt identities, source/tool/stage before-after, actual raw streams, signed normal/negative selection, closure, budgets and package inventory",
        "rtl_subagent": "e4_rtl_integration: no blocker within RTL/TB, ten sole-target Fatals and one actual RTL clip mutant independently rejected; positive/successor TB identities distinguished",
        "math_subagent": "e4_source_audit: no blocker in independent Oracle/transport/buffer/pins chain; quiet retirement L2 only",
        "clip_diagnostic_detail": "Original CHECK_RESULT groups first failure at F line290 cycle629. Actual differing K is original stdout line292: clipped1 for independent sum20224, expected clipped0. Original receipt unchanged.",
        "per_call_wall_start_end": "UNKNOWN_NOT_INDIVIDUALLY_CAPTURED; group ISO8601 timestamps have explicit +08:00 despite original keys named _utc; calls contain elapsed_s and monotonic deadline. No fabricated timestamps.",
        "dynamic_loaded_dependency_inventory": "UNKNOWN_NOT_MEASURED; EXE and enumerated ModelSim DLL files are hashed, not a claim of exhaustive process loaded-module tracing",
        "blockers_found_in_scoped_result": [],
    }
    write_new(DOC / "SELF_AUDIT.json", audit)

    summary = {
        "schema": "M3_E4_FINAL_PARTIAL_RECEIPT_V1",
        "status": "PARTIAL_E4_T061_OFFLINE_SCOPED_PASS_PHYSICAL_AND_BOARD_PENDING",
        "baseline_head": rounds[0]["baseline_head"],
        "sealed_utc": datetime.now(timezone.utc).isoformat(),
        "rounds_consumed": 5, "round_limit": 6, "unused_rounds": 1,
        "round_elapsed_s_total": sum(r["elapsed_s"] for r in rounds),
        "normal_cases": normal, "actual_RTL_negative_cases": bad,
        "rounds": [{"round": r["round"], "status": r["status"], "error": r.get("error"),
                    "elapsed_s": r["elapsed_s"], "started_original_ISO8601": r["started_utc"],
                    "ended_original_ISO8601": r["ended_utc"],
                    "receipt": identity(DOC / f"ROUND_{r['round']:02d}/RUN_RECEIPT.json")}
                   for r in rounds],
        "actual_commands": calls,
        "validation_level": "L3 independent short event/lane/PCM/clipped/request/transport/serial windows; L2 only for 4802-frame retirement tail",
        "limits": [
            "Frozen piano multi-band ROM; no pure sine or 32 audible/spectral peak claim",
            "Backend equal stereo L=R; unequal L/R swap behavior not covered",
            "Normal clip=0 capture plus actual flipped metadata rejection; nonzero positive/negative saturation boundaries not added",
            "Short math windows cover attack and initial release; complete 4800-step release tail is lifecycle only",
            "V release payload is observed but not independently fully checked; release ACK/CC64 targeted RTL assertions and existing Oracle semantics only",
            audit["per_call_wall_start_end"], audit["dynamic_loaded_dependency_inventory"],
            "Positive TB and negative monitor successor have distinct exact identities; no assertion that successor reran normal captures",
        ],
        "physical_rounds_consumed": 0, "Gowin_STA_PnR": "NOT_RUN",
        "hardware_calls": 0, "board_release_allowed": False,
        "pro_precheck": identity(BUILD / "PRO_BUILD_PRECHECK.json"),
        "publication": "UNCOMMITTED_UNPUSHED_NIGHT_TASK1_OWNS_SERIAL_PUBLICATION",
        "human_M1_M2_delivery": "待用户转发，尚未送达",
    }
    write_new(DOC / "FINAL_RECEIPT.json", summary)
    report = """# 夜间任务2：E4 N32 离线交付（PARTIAL）

本轮完成授权内可执行的新隔离联接与定向证据；完整E4/T061仍PARTIAL，board_release_allowed=false。基线ad2de2169230dc8fd9f4b6f8157d384306c2479a。只新增任务单五处目录，未修改旧分配器/ROM/M1数学/正式top、时钟、约束或共享状态。未提交、未推送；夜间任务1串行发布。

## 已得到的结果

N4→N8→N16→N32同源参数化B/pROM后端＋原运输模块，通过真实ModelSim SE-64 2020.4执行及独立Oracle逐lane/PCM/clipped核对。四档各64接受＝60发布＋3取消＋1复位取消；每档32运输提交、21个833拍间隔与10个834拍间隔、独立PT8211解码左32/右31半帧；请求到提交最大分别69/109/189/349拍，均小于833。每档全部槽有真实非零贡献、满槽FCW互异，公开phase/FCW/ADSR/身份由既有独立参考检查。S播放与串行黄金来自已数学核同的T提交，再经独立pending/held模型，未以DUT播放值自供黄金。

11个实际RTL坏例：偷音、重触发、CC64延迟、Release ACK、HOLD、cancel、reset、结果ID、运输左PCM、不退休各命中唯一首Fatal；clipped行为变异仿真正常结束，独立checker退出1、拒收码K_ID_PCM_CLIPPED_INDEPENDENT_MATH。实际差异K位于原stdout292行/cycle629，sum20224应clip0而返回1；原收据定位的是同cycle组首F290行，原件保持不改。

N32另有4802请求/真实推进、65个done观察、真实D累计OR=ffffffff且occupied清零；尾段只签生命周期L2，不签尾段逐样本数学。短窗口独立数学/期限/运输/串行为限定L3。冻结piano波表不证明纯正弦、32可闻独奏或32独立谱峰；左右相等，不覆盖不等左右交换；正常clip0，不新增实际正负饱和边界专项；完整ADSR/长压力使用旧原件范围，不重跑1300/FULL。

## 原件与失败史

实际消耗5/6组（总runner约70.656秒），剩余1组未用，成功后停止。R1编译退出2：quiet_tail声明顺序；R2真仿真0、checker1：合法末尾同cycle R/END；R3前三档通过，N32真仿真0、checker1：TAIL_END至真实reset前生命周期观察；R4 N32复用捕获核同＋7坏例通过，错误ID先触发E4_DEADLINE_OPEN而非预设E4_ID，正确保留为失败；R5只加立即valid核ID断言后重测该坏例及三个未跑坏例，13条调用退出0，唯一clip checker退出1，整组退出0。所有失败与修复原件完整封存，不将错误拒收冒称目标坏例通过。

正常四档精确TB SHA38265540a81990ca61bb6e4a4217a4c8d52fc99234f0b4575f12a33b11812bb9；R5增量坏例TB SHA65281fdbef1b912ee6194017bc26b93adb349ee0ede47896e3e06bc3ffda9501，仅增加ID监视。没有声称后者重新跑过正常四档。N4的R2真捕获在R3换checker复用；N32的R3真捕获在R4换checker复用；绑定均核原receipt/工具/全部编译HDL、ROM、include和独立模型同字节。

FINAL_RECEIPT.json含每条实际argv/cwd、退出码、耗时、双流SHA、每组ISO时间及源码/ROM/工具前后身份入口；原字段虽名_utc，组时间实际带+08:00，以显式时区为准。单条调用未单独记墙钟起止，标UNKNOWN；动态加载DLL未逐进程追踪，只有已枚举ModelSim EXE/DLL身份，不能称全动态依赖已测。SELF_AUDIT.json记父窗口及两个只读子智能体自审边界，未启用审核员制度。封包含原源码/数学/ROM快照、双流和失败记录，不含work/qdb/wlf编译缓存。

## M1/M2续做与集中交接（待用户转发，尚未送达）

M1：若最终验收需要纯正弦32频独奏/混合，请确认与冻结piano模式隔离的测试模式、phase→sine ROM、增益/混音/clipped数学口径；本轮未换ROM。现有V释放批次公开payload未作完整独立逐字段签收，不扩大为全口径覆盖。

M2：收到同版新Pro source/ROM/IP/top、完整FPG676料号/修订、商业许可及独立候选CST/SDC后，决定E4候选物理执行；当前综合/PnR/Setup/Hold/Recovery/Removal均NOT_RUN，条件2轮额度消耗0，不以旧PG484资源或6.109MHz替代Pro结果。正式接入仍遵基础Pro四声→双音色→E1→E2→E3→E4；获准同一.fs、恢复SHA、电气核验和本次SRAM许可齐备后再做实物32路频谱、音频与异常原件。夜间任务1接手统一Git门禁/发布与原件转交，本窗口不动index/编号/共享状态。
"""
    with (DOC / "HANDOFF.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(report)

    # Inventory archived bytes, excluding only regenerable compiled/runtime caches.
    files = {}
    for tree in TREES:
        for p in tree.rglob("*"):
            if not p.is_file() or any(x in p.relative_to(tree).parts for x in ("work", "__pycache__")):
                continue
            if p.suffix.lower() in (".wlf", ".pyc"):
                continue
            files[p.relative_to(ROOT).as_posix()] = p
    for name in ("NIGHT_PLAN_20261017_TASK2.md", "BUDGET_REVISION_E4.json", "USER_TASK_ORIGINAL.md", "TASK_IDENTITY.json"):
        p = COORD / name
        files["INPUT_ORIGINALS/coordinator/" + name] = p
    old = read(DOC / "SOURCE_IDENTITIES.json")
    historical_large_originals = []
    for entry in old["files"]:
        p = ROOT / entry["path"]
        data = p.read_bytes()
        assert len(data) == entry["bytes"] and hashlib.sha256(data).hexdigest() == entry["sha256"]
        if p.suffix.lower() == ".zip" and len(data) > 1_000_000:
            historical_large_originals.append({**entry,
                "availability": "Existing read-only original file at this repository path; retained in place, not duplicated into new ZIP",
                "baseline_head": rounds[0]["baseline_head"]})
        else:
            files["INPUT_ORIGINALS/" + Path(entry["path"]).as_posix()] = p
    manifest = {"schema": "M3_E4_ORIGINALS_ARCHIVE_MANIFEST_V1", "entries": [
        {"archive_member": key, **identity(p)} for key, p in sorted(files.items())],
        "exclusions": ["ModelSim work compiled database", "Python pycache/pyc", "wlf wave databases"],
        "historical_large_originals_not_duplicated": historical_large_originals,
        "functional_invocations_during_seal": 0}
    write_new(DOC / "SEAL_MANIFEST.json", manifest)
    archive = DOC / "M3_E4_N32_OFFLINE_PARTIAL_20261017.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for key, p in sorted(files.items()):
            z.write(p, key)
        z.write(DOC / "SEAL_MANIFEST.json", "SEAL_MANIFEST.json")
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist()) == set(files) | {"SEAL_MANIFEST.json"}
        for entry in manifest["entries"]:
            data = z.read(entry["archive_member"])
            assert len(data) == entry["bytes"] and hashlib.sha256(data).hexdigest() == entry["sha256"]
        assert z.read("SEAL_MANIFEST.json") == (DOC / "SEAL_MANIFEST.json").read_bytes()
    write_new(DOC / "SEAL_RECEIPT.json", {"status": "ALL_ARCHIVE_MEMBERS_BYTES_SHA_VERIFIED",
        "archive": identity(archive), "manifest": identity(DOC / "SEAL_MANIFEST.json"),
        "original_members_verified": len(files), "board_release_allowed": False,
        "functional_groups_consumed": 5, "physical_calls": 0})
    # Coordinator publishes sources plus concise metadata and sealed originals,
    # preserving local raw directories but omitting duplicated expanded captures.
    publish = []
    for tree in TREES:
        candidates = tree.glob("*") if tree == DOC else tree.rglob("*")
        for p in candidates:
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
                publish.append(p.relative_to(ROOT).as_posix())
    publish.append((DOC / "PUBLICATION_FILES.json").relative_to(ROOT).as_posix())
    write_new(DOC / "PUBLICATION_FILES.json", {"status": "PROPOSED_EXACT_E4_WRITESET_ONLY_NIGHT_TASK1_TO_PUBLISH",
        "files": sorted(publish), "unrelated_dirty_files_included": False,
        "local_expanded_round_originals_preserved": True, "committed": False, "pushed": False})
    print(json.dumps({"status": summary["status"], "archive": identity(archive),
                      "original_members": len(files), "publication_files": len(publish)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
