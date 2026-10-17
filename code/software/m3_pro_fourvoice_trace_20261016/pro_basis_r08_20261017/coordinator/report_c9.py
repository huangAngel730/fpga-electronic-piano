"""Record static C9 successors without changing frozen software results."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator"
BASELINE = "16ac226552f6fb65347b229b8fad42146ed45644"


def identity(path):
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ready", nargs=3)
    args = parser.parse_args()
    assert not (DOC / "C9_INTEGRATION.md").exists()
    ready = []
    for name in args.ready:
        path = ROOT / name
        value = json.loads(path.read_text(encoding="utf-8"))
        ready.append({"document": identity(path), "status": value.get("status"),
                      "level": "L0_STATIC_ONLY_NOT_RUN"})
    collections = []
    for path in sorted(DOC.glob("COLLECT_C9*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        assert value["functional_executions"] == 0
        # A prior immutable collection can precede a narrowly reviewed correction;
        # preserve it, while the final collections identify the final bytes.
        collections.append(identity(path))
    assert len(collections) >= 3
    review = DOC / "dependency_audit/C9_FINAL_REVIEW.md"
    assert review.is_file()
    source_ids = {}
    for base in (ROOT / "code/software/m3_pro_fourvoice_trace_20261016",
                 ROOT / "code/tb/board/m3_pro_fourvoice_trace_20261016"):
        for path in base.rglob("*"):
            if path.is_file() and "c9_binding" in path.parts and path.suffix in {".py", ".sv", ".json"}:
                source_ids[path.relative_to(ROOT).as_posix()] = identity(path)
    successor = {"baseline": BASELINE, "status": "L0_STATIC_SUCCESSORS_NOT_RUN",
                 "tasks": ["R7-A", "R7-B", "R8-02", "R7-C"],
                 "normalized_fields": 74, "public_observation_ports": 67,
                 "ready": ready, "collections": collections,
                 "source_files": source_ids, "readonly_increment_review": identity(review),
                 "functional_runs": 0, "HDL_EDA_device_runs": 0,
                 "previous_software_results_apply_to_C9": False,
                 "board_release_allowed": False}
    package_path = DOC / "PACKAGE_STATUS.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    assert "c9_static_successors" not in package
    package["c9_static_successors"] = successor
    write_json(package_path, package)
    request_path = DOC / "M2_DECISION_REQUESTS.json"
    requests = json.loads(request_path.read_text(encoding="utf-8"))
    requests["C9_successors"] = {**successor,
        "decision": "Review exact final C9 files and grant any new software/HDL group explicitly; old consumed groups do not restart",
        "remaining_semantics": ["M1 NoteOn wording erratum", "independent input-plan apply_event_seq mapping",
                                "audio_stable policy", "real trace and independent PCM/ID/clip oracle"],
        "physical_and_executor_requirements": "Unchanged; no board release or transfer of M2 R09 admission"}
    write_json(request_path, requests)
    text = """# C9 同版接入与限定交付

整体仍 PARTIAL。本节是发布前新到 C9 的 L0 静态后继，不把原 R08 已测20项/204个匹配用例升级为 C9 功能通过；原 R08 27例、旧 R7-C 6例 NOT_RUN 和全部消费不变。

发布父基线 16ac226552f6fb65347b229b8fad42146ed45644。M2 C9 源包182685字节，SHA d458ab16277bd46751318ac368b22df1b21b35c4867c47942e7bff7d27fc3aa2；M1原包166433字节，SHA 019d50298c171b4359c7882a092f11f5b582033a8d81cb318f22b817a6c3e287。总控分别核86/60个载荷大小、SHA及ZIP CRC；76份新发布文件与Git blob核同。原件见 C9_INTAKE_RECEIPT.json 与 DELIVERY_C9 补包。

- 夜间2：R7-A 唯一公开采样 TB/passive observer及codec接入67观察口、5外部pins；74字段逐项来源矩阵与R8-02精确接线后继。原R6-2 driver复用；无私有层级。64MiB批处理限制明确，不能据此签大规模完整采集能力。
- 夜间3：R7-B 新旧同名M1源分成独立装配，两路同输入公开行为流及伴随字段；合并入口供既有B比较器，未执行比较。A的唯一74字段采集依赖另列；B伴随流不冒充完整A采样。
- 夜间4：R7-C 74字段机械桥，保留kind/mask/router序号有效位、config_take和三类clip；A封装适配按原始身份保留，未运行候选。
- 夜间5与各写者子智能体：只读具体增量自审；总控核文件身份、原始包与封包边界。未启动审核员/预审员制度，不替代M2最终复核。

kind3/4/8的零data/seq且valid0是无效原因哨兵；kind1/2同seq多阶段不去重，合法seq0保留。内部router_apply_seq不替代独立input-plan apply_event_seq。advance_frame_req_id仅请求tag，FRAME F来自frame_tick；四路同时推进只接受advance_mask=1111，部分/X/null保留。配置仅依实际config_take解释62位拼接，upstream/effect/feedback三clip独立保留。M1“分配前一沿”文字待勘误，不生成固定延迟期望。

所有42个C9新增用例（A/R8-02共12、B13、C17）和SYNTHETIC原件均为待运行输入，不是日志或测试结果。没有为C9启动功能组、导入候选、HDL、EDA或设备；纯文件读取/哈希/CRC/封包属于元数据核验。独立plan映射、audio_stable、真实trace/PCM及可信执行器、物理/板测仍待。

DELIVERY十卷保持原字节；DELIVERY_C9/M3_TASK_DAY2_C9_STATIC_SUPPLEMENT.zip按仓库相对路径封存所有c9_binding原件，含SOURCE_STORE和INPUT_ORIGINALS。需要完整原件时先在独立资料目录按归档路径解包，读取各包README；源码装配ZIP可独立展开。解包/静态装配不构成候选或HDL执行许可。Git直接文件保留小入口/合同及源码，生成的原始闭包在ZIP中。

最终READY、源码SHA和静态收集收据见 PACKAGE_STATUS.json.c9_static_successors。各旧报告中的“尚未收到M1十九项”属于历史状态：现在静态来源已到，但M1勘误/独立映射/真实输入并未闭合。最新准入目标应为C9精确装配；C5/C6仅保留历史证据。M2最终登记及许可决定待用户转发，尚未送达。
"""
    (DOC / "C9_INTEGRATION.md").write_text(text, encoding="utf-8", newline="\n")
    with (DOC / "RESULT.md").open("a", encoding="utf-8", newline="\n") as stream:
        stream.write("\n## C9 到件后的最终边界\n\n已接入16ac226的M1 R07/C9；R7-A/B、R8-02及R7-C新增c9_binding静态后继，详见C9_INTEGRATION.md。上述R08实际测试绑定原冻结字节，C9功能执行0、仅L0；原T27和R7-C旧6未运行仍保留。M1十九项静态来源现已到件，原文缺件清单相应收窄为勘误、独立映射/audio_stable/真实黄金与采集；首次新HDL准入改以最新C9精确组合为目标。\n")
    with (DOC / "SELF_REVIEW.md").open("a", encoding="utf-8", newline="\n") as stream:
        stream.write("\n## C9 增量自审\n\n核67公开口到74字段的完整来源、两路同名源隔离、四lane判断及独立plan边界。总控指出READY中clip名称/动作mask混写和A/C封装衔接，交唯一写者修正；最终静态阅读范围及源码SHA见dependency_audit/C9_FINAL_REVIEW，未执行候选。总控子智能体发现补包changed规则过宽可能把旧DELIVERY变动放行；已收紧为5份报告和final_handoff.py精确白名单，旧十卷任何字节变化均拒绝。收集与封包仅核SHA/CRC，不算功能通过。\n")
    print(json.dumps({"status": successor["status"], "ready_documents": len(ready),
                      "source_files": len(source_ids), "functional_runs": 0}))


if __name__ == "__main__":
    main()
