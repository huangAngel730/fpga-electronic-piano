"""Read-only source refresh and final amendment; no functional verification."""
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/C"


def ident(path):
    p = Path(path).resolve()
    b = p.read_bytes()
    return {"path":str(p),"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest()}


def write(path,obj):
    with Path(path).open("x",encoding="utf-8",newline="\n") as f:
        json.dump(obj,f,ensure_ascii=False,indent=2)
        f.write("\n")


def main():
    out = DOC/"SOURCE_REFRESH_01"
    out.mkdir(exist_ok=False)
    inputs = [ROOT/"code/docs/M3_完赛任务单_2026-10-15.md",ROOT/"code/docs/138K四声部后续集成任务总览_2026-10-15.md",ROOT/"code/docs/test/m1_r05_pcm_oracle_20261016/REFERENCE_CONTRACT.json",ROOT/"code/model/m1_r05_pcm_oracle_20261016/DEPENDENCIES.json"]
    authorization = {"source_thread_id":"01a14050-cd98-7c41-8004-5d3e25765167","human_turn_id":"01a1457e-3395-7b81-89a1-687c4e782360","human_message_id":"01a1457e-394a-7941-a0bb-05c55d131d83","verified_via":"read_thread original userMessage, rechecked after auto-review rejection","human_quote":"你是总控  你来给他们发消息 授权夜间任务1 2 3 4 之间的发送对话 主要是1控制2 3 4，2 3 4返回结果给1 因为对话 夜间任务1是总控","scope":"Return this C/C2 night-task result to night-task1 coordinator only; private project paths/results/SHA are necessary result identities; no unrelated data or other recipient."}
    write(out/"COMMUNICATION_AUTHORIZATION.json",authorization)
    write(out/"COMMUNICATION_REJECTION_01.json",{"action":"send_message_to_thread final C/C2 result to coordinator","sent":False,"auto_review_reason":"该操作会向线程发送包含内部项目路径、测试结果、源码/产物哈希及状态的敏感信息；当前可信用户消息未明确授权向此目标发送该具体回执。","response":"Rechecked original human message and exact recipient authorization through read_thread; no workaround/indirect send. One normal tool reconsideration may use this new evidence."})
    info = {"status":"STATIC_SOURCE_REFRESH_NO_RERUN","old_test_baseline":"ca4859abc28e3a5f7fdd0250e9f2cd43de39a8c0","current_head_observed":"b6f289110a0b7341f1f9234c945bcb8d31d95aff","old_evidence_unchanged":True,"new_test_calls":0,"M1_old_R05_five_directories":"NOW_PUBLISHED_PRESENT_AFTER_COORDINATOR_FAST_FORWARD","M1_Pro_successor_present":(ROOT/"code/model/m1_r05_pcm_oracle_20261016/pro_successor_20261016").exists(),"M2_Pro_source_present":(ROOT/"code/rtl/board/m2_138k_pro_fourvoice_candidate_20261016").exists(),"read_only_inputs":[ident(x) for x in inputs],"required_mapping_gaps":["actual Pro allocation/Release lifetime and lane_tick sampling phase","all effect postprocessor acceptance/cancellation and config acceptance; fixture only has abstract per-lane publication/consumption","M1 old reference model has lane_tick+5/pre-NBA snapshot assumptions requiring real Pro adapter","exact new Pro source/ROM/top/clock/trace manifest"],"conclusion":"M1 old R05 model and contract are available; not missing publication. Pro same-version trace/source/golden adapter still pending. Fixture calendar remains independent; no PCM recomputation or old303 rerun.","board_release_allowed":False}
    assert not info["M2_Pro_source_present"]
    write(out/"SOURCE_REFRESH.json",info)
    text = '''# 来源刷新补充，优先于原封包中的缺件表述

总控已快进至b6f289110a0b7341f1f9234c945bcb8d31d95aff。M1旧R05五目录现已发布并在本机可读，旧REFERENCE_CONTRACT及DEPENDENCIES现场SHA见SOURCE_REFRESH.json；不能再笼统称M1五目录未发布。原包和原测试基线仍保留ca4859abc…，不回填。

本包只读核新合同，不运行旧303数学/串行或重复已通过19例，新增功能轮0。M2新Pro候选source目录仍不存在；M1旧R05模型可作为只读数学来源，但真正Pro映射仍缺slot/Release生命周期、全部lane_tick采样相位、效果接受/取消/配置和新Pro同版source/ROM/top/trace。尤其本包NoteOff立即释放是toy fixture，不能直接接真实ADSR Release或称M1数学输入已经闭合。

当前交付：C/C2夹具DONE、Pro对照PENDING；Python软件L1，2/6轮，墙钟4.140秒（子工具2.265秒），1正18负，实际拒收码及首差异位置全部匹配。未提交/未推送，board_release_allowed=false。

CALENDAR.json、CALENDAR.jsonl、CALENDAR_CONTRACT.json和原始两轮均保持原SHA。LATEST_RECEIPT.json为当前入口，同时引用原封包本体和本来源补件；给D/M1只读使用。通信首次被自动审批拒绝，尚未送达；授权原文已再次通过read_thread核实，COMMUNICATION_AUTHORIZATION.json给出精确用户消息ID与目标。
'''
    with (out/"RESULT.md").open("x",encoding="utf-8",newline="\n") as f:
        f.write(text)
    old_package = DOC/"SEAL_20261017/M3_C_C2_INDEPENDENT_CALENDAR_20261017.zip"
    paths = list(out.glob("*")) + [HERE/"source_addendum.py",old_package] + inputs
    members = {}
    for p in paths:
        name = p.relative_to(ROOT).as_posix()
        members[name] = ident(p)
    write(out/"MANIFEST.json",{"members":members})
    target = out/"M3_C_C2_FINAL_WITH_SOURCE_REFRESH_20261017.zip"
    with zipfile.ZipFile(target,"x",zipfile.ZIP_DEFLATED) as z:
        for name,item in members.items():
            z.write(item["path"],name)
        z.write(out/"MANIFEST.json","MANIFEST.json")
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for name,item in members.items():
            b=z.read(name)
            assert len(b)==item["bytes"] and hashlib.sha256(b).hexdigest()==item["sha256"]
    current = {"status":"DONE_C_C2_FIXTURE__PRO_MAPPING_PENDING","source_refresh":ident(out/"SOURCE_REFRESH.json"),"current_result":ident(out/"RESULT.md"),"original_receipt":ident(DOC/"NIGHT_RUN_RECEIPT.json"),"final_package":ident(target),"original_package":ident(old_package),"calendar_json":ident(DOC/"CALENDAR.json"),"calendar_jsonl":ident(DOC/"CALENDAR.jsonl"),"contract":ident(DOC/"CALENDAR_CONTRACT.json"),"final_package_members_verified":len(members),"rounds_consumed":2,"new_refresh_functional_calls":0,"board_release_allowed":False}
    write(DOC/"LATEST_RECEIPT.json",current)
    print(json.dumps(current,ensure_ascii=False))


if __name__ == "__main__":
    main()
