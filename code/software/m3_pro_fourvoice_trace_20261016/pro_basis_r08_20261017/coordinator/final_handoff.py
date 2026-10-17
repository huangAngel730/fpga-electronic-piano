"""After ordinary push, collect original delivery volumes and gate evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[5]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator"


def ident(path):
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    remote = subprocess.check_output(["git", "rev-parse", "origin/develop"], cwd=ROOT).decode().strip()
    assert head == remote
    gate_path = DOC / "GATE_R01/GATE_RECEIPT.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    assert gate["status"] == "PASS" and gate["exit_code"] == 0 and gate["pass_count"] == 9 and gate["input_bytes_unchanged"]
    index = json.loads((DOC / "INDEX_RECEIPT.json").read_text(encoding="utf-8"))
    assert index["status"] == "EXACT_SCOPE_AND_BYTES_PASS"
    for name, expected in index["files"].items():
        assert ident(ROOT / name) == expected, "POST_GATE_FILE_CHANGED:" + name
        blob = subprocess.check_output(["git", "show", head + ":" + name], cwd=ROOT)
        assert {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()} == expected
    result = json.loads((DOC / "PACKAGE_STATUS.json").read_text(encoding="utf-8"))
    out = DOC / "HANDOFF_FINAL"
    out.mkdir(exist_ok=False)
    publication = {"commit": head, "origin_develop": remote, "github": "https://github.com/huangAngel730/fpga-electronic-piano/commit/" + head, "gate": {"path": gate_path.relative_to(ROOT).as_posix(), **ident(gate_path)}, "exact_index_files": index["count"], "commit_bytes_verified": True, "board_release_allowed": False, "M2_delivery": "待用户转发，尚未送达"}
    (out / "PUBLICATION.json").write_text(json.dumps(publication, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    rows = []
    for run in result["runs"]:
        rows.append(f"{run['group']}/{run['phase']}：匹配 {run['assertions_matched']}/{run['cases_completed']}（计划 {run['cases_total']}），{run['elapsed_s']:.3f}s，退出 {run['exit_code']}")
    text = "\n".join([
        "M2你好，请对 M3 task-day2 的 R08 集中成果做限定复核并登记。待用户转发，尚未送达。", "",
        f"已普通推送 develop：{head}；重新 fetch 后本地 HEAD 与 origin/develop 一致。",
        publication["github"], "",
        f"精确待发布树九门禁 9/9 PASS、退出0、前后输入字节不变；提交中的 {index['count']} 份文件已逐字节核对暂存收据。本轮 gate 单列，不是 Pro HDL/EDA 通过。", "",
        "范围：保留原12包及失败/消费，新增24个离线组件；C6头文件/include/ROM与公开TB/observer/driver装配；R6-3/5新修法及此前本任务R6-4/6、R7-A/B/C/D成果一并封存。未改 M1/M2源、正式接口、当前状态或看板。",
        f"新24项中 {result['new_software_ready_components']} 项完成原冻结版本的软件验证；整体仍 PARTIAL，真实分支 PENDING_REAL_INPUT、board_release_allowed=false。", "",
        "发布前又接入16ac2265的M1 R07/C9。R7-A/B、R8-02、R7-C的C9静态后继另见C9_INTEGRATION.md和DELIVERY_C9补包：原软件结果不升级为C9通过，C9没有新增功能组/HDL执行。十九项静态来源已到；note_on文字勘误、独立input-plan映射/audio_stable及真实PCM/trace仍未闭。", "",
        *rows, "",
        "所有首次失败和修复前源码在原快照中，未删除失败或恢复旧消费。完整逐例清单、命令argv/cwd/UTC、原始双流、退出码、源/输入/依赖SHA见随包 RESULT.md、PACKAGE_STATUS.json、CONSUMPTION.json 与 DELIVERY 分卷。MATCHED含正常、预期拒收和预期UNKNOWN，不代表全部实际功能通过。",
        f"R08功能组累计 {result['r08_software_elapsed_s']:.6f}s；此前本任务R07/V0396为22.081234s另列。模型token/金额不可取，未估算。", "",
        "请M2精确决定：",
        "1. 对本次软件限定结果登记，继续保留 R7-C 尚未执行6例和 R08 尚未运行/失败项（见逐例清单）；若继续检查，请对这些精确用例另签组额度。不得以日期/窗口或新组件名恢复旧额度。",
        "2. 首次Pro真实HDL执行仍需按最新 C9 source/include/ROM、唯一TB/observer/driver及两路隔离装配、工具依赖、argv/cwd/输出/超时及可信执行器精确准入；C6只保留为历史冻结证据。生命周期/子孙进程/双流收敛未验证。R08五功能组与两次定向增量内未启动子进程/工具EXE/HDL/EDA/设备；仓库门禁的既有T007/T019仿真单列，不算Pro新执行。",
        "3. M1确认note_on文字勘误并补逐样本真实PCM/ID/clip黄金、独立plan映射与TX选择期望；M2/用户补实物Part/version/Bank、电气与仪器原件、同会话真实捕获、正确新.fs/完整STA/Recovery/Removal/CDC/恢复身份及精确一次SRAM许可。无Flash/SRAM操作，不启动E/N32。", "",
        "R7-B最后<=stop源码仅L0；R8-13完整帧与不完整尾段分开，后者UNKNOWN。文件哈希/结构检查不能认证真实来源或上板通过。M2负责最终复核、状态及看板更新。", ""
    ])
    (out / "FORWARD_TO_M2.txt").write_text(text, encoding="utf-8", newline="\n")
    # Include the actual post-publication metadata helper as well as its
    # earlier sealed version. This wording clarification changes no candidate.
    helper_path = out / "FINAL_HANDOFF_SOURCE.py"
    helper_path.write_bytes(Path(__file__).read_bytes())
    sealed_index = json.loads((DOC / "DELIVERY/ORIGINALS_INDEX.json").read_text(encoding="utf-8"))
    helper_name = Path(__file__).resolve().relative_to(ROOT).as_posix()
    helper_delta = {"scope": "Post-seal metadata delivery composition: C9 static supplement and explicit distinction between legacy repository gate and Pro functional execution", "sealed_original": sealed_index["files"][helper_name], "published_current": ident(helper_path), "candidate_changes": 0, "functional_replay": 0}
    (out / "METADATA_HELPER_DELTA.json").write_text(json.dumps(helper_delta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    files = [DOC / name for name in ("RESULT.md", "PACKAGE_STATUS.json", "CONSUMPTION.json", "INDEX_RECEIPT.json", "PUBLICATION_FILES.json", "SELF_REVIEW.md", "M2_DECISION_REQUESTS.json")]
    files += sorted(p for p in (DOC / "DELIVERY").iterdir() if p.is_file())
    files += sorted(p for p in (DOC / "DELIVERY_C9").iterdir() if p.is_file())
    files += [DOC / "C9_INTEGRATION.md", DOC / "C9_INTAKE_RECEIPT.json"]
    files += sorted(p for p in (DOC / "GATE_R01").iterdir() if p.is_file())
    files += [out / "PUBLICATION.json", out / "FORWARD_TO_M2.txt", helper_path, out / "METADATA_HELPER_DELTA.json"]
    manifest = {p.relative_to(DOC).as_posix(): ident(p) for p in files}
    archive_path = out / "M3_TASK_DAY2_R08_TO_M2.zip"
    with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files:
            archive.write(path, path.relative_to(DOC).as_posix())
        archive.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        for name, expected in manifest.items():
            raw = archive.read(name)
            assert {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} == expected
    receipt = {"status": "FINAL_PACKAGE_CRC_SIZE_SHA_PASS", "archive": {"path": str(archive_path), **ident(archive_path)}, "publication": publication, "M2_delivery": "待用户转发，尚未送达"}
    (out / "HANDOFF_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
