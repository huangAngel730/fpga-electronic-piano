"""Collect the five windows' completed bounded evidence without rerunning tests."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

SOFT = Path(__file__).resolve().parent
ROOT = SOFT.parents[4]
TRACE_DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016"
B1 = TRACE_DOC / "pro_binding_20261017"
B2 = TRACE_DOC / "pro_serial_successor_20261017"
INTAKE = B1 / "intake_20261017"
COORD = B1 / "coordinator_20261017"
E1 = ROOT / "code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017"
B0 = ROOT / "code/docs/hardware/pro_fourvoice_board_intake_20261017"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def identity(path):
    return {"bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def relative(path):
    return path.relative_to(ROOT).as_posix()


def verify_package(label, path, expected):
    actual = identity(path)
    assert actual["bytes"] == expected["bytes"] and actual["sha256"] == expected["sha256"], label
    with zipfile.ZipFile(path) as bundle:
        names = bundle.namelist()
        assert len(names) == len(set(names)) and bundle.testzip() is None, label
        for name in names:
            parsed = PurePosixPath(name)
            assert not parsed.is_absolute() and ".." not in parsed.parts and "\\" not in name, name
        candidates = [name for name in names if PurePosixPath(name).name.lower()
                      in ("manifest.json", "delivery_manifest.json")]
        manifest_name = min(candidates, key=len)
        manifest = json.loads(bundle.read(manifest_name))
        rows = next(manifest[key] for key in ("entries", "payloads", "members") if key in manifest)
        expected_names = set()
        for row in rows:
            name = row["member"] if "member" in row else row["path"]
            assert name not in expected_names, name
            expected_names.add(name)
            data = bundle.read(name)
            assert len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"], name
        assert set(names) == expected_names | {manifest_name}, label
    return {"label": label, "path": relative(path), **actual, "payloads": len(rows),
            "members": len(names), "manifest": manifest_name, "crc_size_sha_verified": True}


def main():
    b1 = read(B1 / "RECEIPT.json")
    b2 = read(B2 / "NIGHT_RUN_RECEIPT.json")
    e1 = read(E1 / "FINAL_RECEIPT.json")
    intake = read(INTAKE / "RECEIPT.json")
    assert b1["functional_group_exit"] == 0 and e1["passed"]
    assert b2["pro_dut_pass"] is False and not intake["board_release_allowed"]
    b1_archive = read(B1 / "DELIVERY_RECEIPT.json")["archive"]
    b2_archive = read(B2 / "LATEST_RECEIPT.json")["archive"]
    e1_archive = read(E1 / "PACKAGE_STATUS.json")
    intake_archive = read(INTAKE / "LIGHTWEIGHT/RECEIPT.json")
    package_specs = [
        ("B1", Path(b1_archive["path"]), b1_archive),
        ("B2", Path(b2_archive["path"]), b2_archive),
        ("E1_STATIC", Path(e1_archive["package"]), e1_archive),
        ("INTAKE_LIGHTWEIGHT", Path(intake_archive["archive"]), intake_archive),
    ]
    verified = [verify_package(*spec) for spec in package_specs]
    save(COORD / "PACKAGES_VERIFICATION.json", verified)
    static_seconds = read(E1 / "RUN_01/FINAL_RECEIPT.json")["elapsed_seconds"] + e1["elapsed_seconds"]
    counts = {"B1_night2": {"used": 1, "allocated": 4, "checks": 41, "seconds": b1["functional_group_seconds"]},
              "B1_night5": {"used": 1, "allocated": 2, "checks": 9, "seconds": intake["audit"]["seconds"]},
              "B1_shared": {"used": 2, "limit": 6},
              "B2": {"used": b2["rounds_consumed"], "limit": 6, "checks_by_version": [19, 3], "seconds": b2["seconds"]},
              "E1_static": {"used": 2, "allocated": 2, "first_exit": 1, "final_exit": 0, "seconds": static_seconds},
              "B0_static": {"used": 1, "functional_rounds": 0, "seconds": read(B0 / "CALL_R01.receipt.json")["seconds"]},
              "ModelSim_Gowin_devices_new": 0, "new_E4_runs": 0, "old_quotas_restored": False}
    save(COORD / "CONSUMPTION_SUMMARY.json", counts)
    lines = """# M3 task-day 五窗口收口（2026-10-17）

本轮可执行的隔离准备已收齐，自审与原件封存完成；Pro完整当日任务仍PARTIAL。B0缺实物，B1/B2缺新Pro同版源和真实捕获，E1正式接入及E2/E3/E4后续按原顺序待准入。board_release_allowed=false。没有修改M1模型、M2正式顶层/PLL/CST/SDC或共享状态，也没有恢复旧工具额度。

| 窗口/包 | 实际结果 | 真实边界 |
| --- | --- | --- |
| 总控/B0 | 三份板级原件现场SHA/大小与旧声明核同，参考CST缺P15/N16/H17，复位域差异登记；L0。 | 实物修订/完整Part/Bank电压/MIDI侧电平/PLL/PA/音频及新.fs/许可均未知。 |
| 夜间2/B1 | 61字段候选合同、toy差异、来源metadata门禁；1结构正例+39拒收+1实际缺件PENDING，1/4轮；L0+L1。 | 元数据通过不认证M2权威/HDL映射或真实逐沿日历，authority_verified=false。 |
| 夜间3/B2 | 原CSV行号/cycle/epoch/ID保留，独立TX采纳sidecar与PCM对照，只读复用旧PinDecoder；首版19项，cancel修复版3项增量，2/6轮；L1。 | 未把两版22项写成最终源码全量通过；29列测试视图尚未与61字段生产trace连通，真实HOLD/启动/clip归并/finish仍待映射。 |
| 夜间4/E1 | 源/时钟/生产者/七组CDC与64/98bit差异及可逆接线提案；2/2静态组，首个行锚失败保留，修正34→35后通过；L0。 | 当前50MHz/双PLL壳与封存40/25/125MHz副本分开；payload定向hold不能由同步器二级hold报告代签。旧L2/L5原范围保持。 |
| 夜间5/到件与E2/E3依赖 | 52项文件、89个收据链接身份匹配，7旧包只读CRC核验、9项新审计通过，1/2轮；L0+L1。正式采用45成员轻量后继。 | M2新Pro工程与M1同源适配未到本机；旧黄金已发布。E2历史PCM不替新Pro，E3隔离50ms不签默认5秒/实体。 |

B1两窗口合计2/6；B2两轮11.187秒，B1两窗4.390秒；E1静态两组及B0摄取单列在CONSUMPTION_SUMMARY.json。发布门禁另计，不当作新Pro功能测试。单包模型token消费未提供，UNKNOWN，不拿账号共享比例替代。所有源/工具身份、argv/cwd/UTC/PID、原始双流/退出码与失败史见四个内包及B0收据。

汇合核查：共同四lane推进应表示advance mask，不能把旧toy lane=slot/立即释放或上午scalar lane交易套上真实源。commit不能反填TX实际采纳。B1结构门禁成功不代表真实来源；B2不另造D3或算法黄金。两侧当前只有明确的候选字段差额，未冒称同次真实链已经联通。B2已从独立账本先检查清理<833，再逐沿核实际清理和ID；cancel修复原件保留。

首版夜间5审计封包含历史输入副本，保留本地不删除、不发布；正式轻量后继只含本轮新增内容，旧已签案例/旧包按原Git/文件位置引用。夜间4也排除冻结的历史输入副本。原始task-day两文件以用户交付字节封在总包，不在Git文本规范化时改写它们。

夜间2/5主动回传被自动审批拒绝：理由是本窗口缺可信直接授权，未接受从总控读取的跨对话授权。用户已在总控明确授权，故总控用已授权的本地只读领取收齐，不反复请求用户授权、不绕过发送审批；夜间3/4直接采用只读领取，没有冒称发送成功。AI成果领取与真人M2签收分开。

最低解除条件：M2固定新Pro完整source/ROM/top/目标身份、时钟/复位和必要公开映射（61项是trace字段，不是61个物理IO），含帧ID/advance mask/slot生命周期、返回/效果接受、独立TX采纳与真实结束收据；M1确认同源既有黄金/ROM复用或适配。M3再在有效新许可内接B1/B2并推真实独立日历/串行。B0实物数据由现场负责人提供，新码流、完整时序和精确SRAM许可仍归M2准入。

N32只读核旧HANDOFF/FINAL_RECEIPT与8b9d11e Git blob，旧5/6不重置。本轮E4新代码/测试/EDA/设备0；后继需要M1纯正弦独立测试定义、完整左右串行与新Pro同版/物理准入，正式顺序仍在E3后。未代M1写模型或把piano当纯正弦。

当前成果供M2最终限定复核/受控映射决定和登记；当日正式任务未完成不能写DONE。M2及M1交接均待用户转发，尚未送达。封存时未提交/未推送，最终精确树九项门禁、提交与远端SHA另见PUBLICATION_STATUS/HANDOFF_FINAL；本总包不自签Pro或板级。
"""
    with (COORD / "DAY_RESULT.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(lines)
    # This program's running stdout/receipt are outer evidence, avoiding self-reference.
    files = [path for path in COORD.iterdir() if path.is_file() and not path.name.startswith("SEAL_DAY.")]
    files.extend(path for path in (COORD / "INPUT_ORIGINALS").iterdir() if path.is_file())
    files.extend(path for path in SOFT.iterdir() if path.is_file())
    files.extend(path for path in B0.rglob("*") if path.is_file())
    leaf_names = [(B1, ["RESULT.md", "RECEIPT.json", "OBSERVATION_CONTRACT.json", "OBSERVATION_CONTRACT.md", "TOY_TO_PRO_DIFF.md"]),
                  (B2, ["RESULT.md", "NIGHT_RUN_RECEIPT.json", "BRIDGE_CONTRACT.md", "B1_READONLY_LINK.md"]),
                  (E1, ["RESULT.json", "FINAL_RECEIPT.json", "INTEGRATION_DIFF.md", "CDC_PATHS.md", "WIRING_PROPOSAL.md", "FAILURE_HISTORY.md"]),
                  (INTAKE, ["RESULT.md", "RECEIPT.json", "MISSING_ITEMS.json"]),
                  (INTAKE / "LIGHTWEIGHT", ["README.md", "RECEIPT.json", "OLD_REFERENCE_LEDGER.json"])]
    for base, names in leaf_names:
        files.extend(base/name for name in names)
    files.extend(spec[1] for spec in package_specs)
    entries = {relative(path): path for path in files}
    manifest = {name: identity(path) for name, path in sorted(entries.items())}
    delivery = COORD / "DELIVERY"
    delivery.mkdir(exist_ok=False)
    archive = delivery / "M3_TASK_DAY_FIVE_WINDOWS_OFFLINE_PREPARATION_20261017.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for name, path in sorted(entries.items()):
            bundle.write(path, name)
        bundle.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None and set(bundle.namelist()) == set(manifest) | {"MANIFEST.json"}
        for name, row in manifest.items():
            data = bundle.read(name)
            assert len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"], name
    save(delivery / "RECEIPT.json", {"status": "OFFLINE_PREPARATION_COLLECTED_REAL_PRO_PARTIAL",
         "archive": {"path": relative(archive), **identity(archive)}, "payloads": len(manifest),
         "members": len(manifest)+1, "crc_size_sha_verified": True, "inner_packages": verified,
         "consumption": counts, "pro_dut_pass": False, "board_release_allowed": False,
         "Git_at_seal": "Not committed/pushed; gate and final remote receipt follow separately",
         "M2_M1_received": False})
    publish = set()
    b1_soft = ROOT / "code/software/m3_pro_fourvoice_trace_20261016/pro_binding_20261017"
    for path in b1_soft.glob("*.py"):
        publish.add(relative(path))
    for base in (SOFT, ROOT/"code/software/m3_pro_fourvoice_trace_20261016/pro_serial_successor_20261017",
                 b1_soft/"intake_20261017"):
        publish.update(relative(path) for path in base.rglob("*.py"))
    publish.add(relative(SOFT / "publication_gate.ps1"))
    for base, names in leaf_names:
        publish.update(relative(base/name) for name in names)
    publish.update(relative(E1/name) for name in ("audit_static.py", "run_static.py", "seal_static.py", "freeze.ps1",
                   "README.md", "INPUT_IDENTITIES.json", "READ_ONLY_REFERENCES.json", "FINAL_SOURCE_INDEX.md", "PACKAGE_STATUS.json"))
    publish.update(relative(B2/name) for name in ("REQUIRED_PUBLIC_OBSERVATIONS.md", "SOURCE_LINK.json", "LATEST_RECEIPT.json"))
    publish.update(relative(INTAKE/name) for name in ("INTAKE.json", "SOURCE_LOCATIONS.json", "SUPPLEMENT_SOURCE_LOCATIONS.json"))
    publish.update(relative(B1/name) for name in ("DELIVERY_RECEIPT.json", "INTAKE_CONSUMPTION.json", "COMMUNICATION_RESULT.json"))
    publish.update(relative(path) for path in COORD.iterdir() if path.suffix in (".md", ".json")
                   and not path.name.startswith("SEAL_DAY."))
    publish.update(relative(B0/name) for name in ("README.md", "RESULT.md", "AUDIT_R01/B0_INPUT_RECEIPT.json"))
    publish.update(relative(spec[1]) for spec in package_specs)
    publish.update((relative(archive), relative(delivery/"RECEIPT.json"), relative(COORD/"PUBLICATION_FILES.json")))
    allowed = ("code/software/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/",
               "code/software/m3_pro_fourvoice_trace_20261016/pro_serial_successor_20261017/",
               "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/",
               "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_serial_successor_20261017/",
               "code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/",
               "code/docs/hardware/pro_fourvoice_board_intake_20261017/")
    assert all(path.startswith(allowed) and "INPUT_ORIGINALS" not in path for path in publish)
    absent = [path for path in publish if not (ROOT/path).is_file() and path != relative(COORD/"PUBLICATION_FILES.json")]
    assert not absent, absent
    save(COORD / "PUBLICATION_FILES.json", {"paths": sorted(publish), "policy": "Only authorized new code/summary/packets; raw evidence archived; legacy copies excluded"})
    print(json.dumps({"archive": relative(archive), **identity(archive), "payloads": len(manifest),
                      "inner_payloads": [row["payloads"] for row in verified], "publication_files": len(publish)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
