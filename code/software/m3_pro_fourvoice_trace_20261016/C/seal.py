"""Static final evidence audit/package only; never run tests or EDA here."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/C"


def identity(path):
    p = Path(path).resolve()
    b = p.read_bytes()
    return {"path":str(p),"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest()}


def write(path, obj):
    with Path(path).open("x",encoding="utf-8",newline="\n") as f:
        json.dump(obj,f,ensure_ascii=False,indent=2)
        f.write("\n")


def main():
    rounds = []
    elapsed = 0
    audit = []
    for number in (1,2):
        base = DOC/f"ROUND_{number:02d}"
        r = json.loads((base/"RUN_RECEIPT.json").read_text(encoding="utf-8"))
        assert r["source_before"] == r["source_after"]
        for info in r["source_before"].values():
            copied = identity(base/"source"/Path(info["path"]).name)
            assert (copied["bytes"],copied["sha256"]) == (info["bytes"],info["sha256"])
        for call in r["calls"]:
            assert not call["timeout"] and call["elapsed_s"] <= 90
            for stream in ("stdout","stderr"):
                assert identity(call[stream]["path"]) == call[stream]
        for case in r["results"]:
            assert identity(case["input"]["path"]) == case["input"]
        assert r["elapsed_s"] <= 90
        if number == 2:
            assert r["source_after"] == {k:identity(v["path"]) for k,v in r["source_before"].items()}
            assert r["runtime_dependencies"] == r["runtime_dependencies_after"]
            assert r["contract_before"] == r["contract_after"] == identity(DOC/"CALENDAR_CONTRACT.json")
            assert r["status"] == "FIXTURE_SOFTWARE_PASS" and len(r["results"]) == 19 and all(x["matched"] for x in r["results"])
        else:
            assert r["status"] == "FAILED_STOP_ORIGINALS_PRESERVED"
            assert r["first_unexpected_failure"]["name"] == "backpressure_data_change"
        elapsed += r["elapsed_s"]
        rounds.append(r)
        audit.append({"round":number,"receipt":identity(base/"RUN_RECEIPT.json"),"source_snapshots_verified":len(r["source_before"]),"raw_streams_verified":2*len(r["calls"]),"source_unchanged":True,"status":r["status"],"elapsed_s":r["elapsed_s"],"calls_elapsed_s":sum(c["elapsed_s"] for c in r["calls"])})
    assert len(list(DOC.glob("ROUND_*_CONSUMED.json"))) == 2 and elapsed < 2000
    last = rounds[-1]
    for target,source in ((DOC/"STIMULUS.json",Path(last["fixed_plan"]["path"])),(DOC/"CALENDAR.jsonl",Path(last["frozen_calendar"]["path"]))):
        with target.open("xb") as f:
            f.write(source.read_bytes())
        assert identity(target)["sha256"] == identity(source)["sha256"]
    calendar_rows = [json.loads(x) for x in (DOC/"CALENDAR.jsonl").read_text(encoding="utf-8").splitlines()]
    write(DOC/"CALENDAR.json",{"schema":"M3_C_FOUR_LANE_CALENDAR_JSON_V1","scope":"SYNTHETIC_FIXTURE_NOT_PRO_DUT","records":calendar_rows,"jsonl_source":identity(DOC/"CALENDAR.jsonl"),"board_release_allowed":False})
    write(DOC/"HAND_ANCHORS.json",last["hand_anchors"])
    for name in ("cases.py","check_calendar.py","run.py"):
        a = (DOC/"ROUND_01/source"/name).read_text(encoding="utf-8")
        b = (DOC/"ROUND_02/source"/name).read_text(encoding="utf-8")
        with (DOC/(name+".repair.diff")).open("x",encoding="utf-8",newline="\n") as f:
            f.write("".join(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile="round01",tofile="round02")))
    input_root = ROOT.parent.parent / "night_task/10.17/M1_M2_M3_Pro夜间任务与并行窗口_20261016"
    inputs = [ROOT/"AGENTS.md",ROOT/"code/AGENTS.md",ROOT/"code/rtl/input/AGENTS.md",ROOT/"code/docs/协作入口.md",ROOT/"code/docs/模块接口规范.md",ROOT/"code/docs/M3_完赛任务单_2026-10-15.md",ROOT/"code/docs/138K四声部后续集成任务总览_2026-10-15.md",ROOT/"code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/NIGHT_PLAN_20261017.md"]
    inputs += [input_root/x for x in ("M3_夜间五小时_Pro四声基础_2026-10-16.md","M3_并行拓展双滑块窗口_2026-10-16.md","夜间任务通用执行规范.md")]
    write(DOC/"INPUT_IDENTITIES.json",{"baseline_head":"ca4859abc28e3a5f7fdd0250e9f2cd43de39a8c0","local_origin_develop":"ca4859abc28e3a5f7fdd0250e9f2cd43de39a8c0","sources":[identity(x) for x in inputs],"used_old_R05_trace":False,"pro_source_rom_top_trace":"NOT_RECEIVED","M1_published_golden":"NOT_RECEIVED","allocator_and_lane_wiring":"FIXTURE_ASSUMPTIONS_ONLY"})
    write(DOC/"FINAL_AUDIT.json",{"status":"RAW_STREAMS_INPUTS_EXECUTED_SOURCE_AND_FINAL_IDENTITY_VERIFIED","rounds":audit,"rounds_consumed":2,"round_limit":6,"python_elapsed_s":elapsed,"actual_tool_elapsed_s":sum(x["calls_elapsed_s"] for x in audit),"Icarus_calls":0,"ModelSim_calls":0,"Gowin_calls":0,"stop_on_success":True})
    write(DOC/"SELF_AUDIT.json",{"role":"IMPLEMENTER_WITH_READ_ONLY_CHILD_SELF_AUDIT_NO_REVIEWER_REGIME","child":"/root/calendar_selfaudit_1017","read_only_no_commands":True,"findings":[{"issue":"Shared generator/oracle requires independent four-lane anchors","resolution":"19 frames, each ACCEPT and LANE_TICK lanes0..3, totals and handwritten solo/chord/release/reset identity anchors added before final round"},{"issue":"null transaction raises non-machine AttributeError","resolution":"explicit RECORD_STRUCTURE refusal plus actual null negative case"}],"final_child_result":"NO_CONCRETE_BLOCKER_IN_SCOPED_FIXTURE_SOFTWARE","implementer_boundary":"Known public NoteOff enters ADSR Release. Frozen fixture deliberately abstracts immediate slot release; this is NOT real allocator/Release completion semantics. M2/M1 real voice lifetime and lane mapping remain missing; no Pro comparison is possible."})
    receipt = {"status":"DONE_C_C2_FIXTURE__PARTIAL_PRO_MAPPING","level":"L1_ISOLATED_PYTHON_SOFTWARE_SELFTEST_ONLY","scope":"SYNTHETIC_FIXTURE_NOT_PRO_DUT","baseline_head":"ca4859abc28e3a5f7fdd0250e9f2cd43de39a8c0","calendar_json":identity(DOC/"CALENDAR.json"),"calendar_jsonl":identity(DOC/"CALENDAR.jsonl"),"stimulus":identity(DOC/"STIMULUS.json"),"contract":identity(DOC/"CALENDAR_CONTRACT.json"),"hand_anchors":identity(DOC/"HAND_ANCHORS.json"),"successful_run":identity(DOC/"ROUND_02/RUN_RECEIPT.json"),"first_failed_run":identity(DOC/"ROUND_01/RUN_RECEIPT.json"),"audit":identity(DOC/"FINAL_AUDIT.json"),"input_identities":identity(DOC/"INPUT_IDENTITIES.json"),"python":last["python_executable"],"python_version":last["python_version"],"runtime_dependencies":last["runtime_dependencies"],"machine":last["machine"],"positive_cases":1,"negative_cases_actually_rejected":18,"checks":"actual exit, exact refusal code and predeclared first record index","rounds_consumed":2,"round_limit":6,"python_elapsed_s":elapsed,"Icarus_ModelSim_Gowin_calls":0,"PCM_math_computed":False,"git_commit":None,"pushed":False,"pro_dut":"PENDING_PRO_SOURCE_OR_TRACE","missing":["M2 exact Pro source/ROM/top manifest and clock/public-port identity","M2 allocation/voice Release and all lane_tick interface","real event applied/effect config/accept/cancel/reset epoch trace","M1 published golden and schedule adapter"],"next_owner":"coordinator -> M2 identity/wiring; M1 read-only input/calendar mapping; D fixture identity read-only","board_release_allowed":False}
    write(DOC/"NIGHT_RUN_RECEIPT.json",receipt)
    report = '''# C/C2 独立日历与交易边界：限定完成

2026-10-17夜间任务2，已完成本轮授权的C/C2独立软件夹具并自审。结果DONE_C_C2_FIXTURE；真实Pro映射PARTIAL/PENDING_PRO_SOURCE_OR_TRACE。实际L1（Python软件自检），无RTL仿真、PCM黄金、真实期限或实物结论。未提交、未推送；总控负责发布。board_release_allowed=false。

## 已交内容

- STIMULUS.json：60/64/67/72四独奏，再同帧四音和逐放；另有69音、接受后取消、三周期背压、reset epoch与ID重启。
- CALENDAR.json/CALENDAR.jsonl：同一冻结夹具的两种编码。19帧、76个请求及lane_tick、75次返回/发布、5个取消、71次消费，共496记录。四lane每帧含inactive及后续取消的工作；不从DUT的phase/env/wave反推。
- CALENDAR_CONTRACT.json：字段、时基、同周期顺序和所有假设。时基40MHz及833/833/834是输入夹具假设，不是观测Pro时钟。slot最低空闲、lane=slot和立即释放均为toy fixture；真实公开NoteOff进入Release，本夹具不计算Release长度/ADSR或证明真实slot释放，禁止直接当Pro黄金。
- calendar.py推导独立输入计划，check_calendar.py检查请求身份/背压/代际/生命周期并精确比较日历；cases.py含独立手算表，约束每帧四lane、四独奏/四音、逐放和reset。checker当前V1只接精确冻结计划，不能自动摄取其他Pro轨迹；正式适配需M2合同。

## 实际验证与失败史

只用现场预检的C:/Users/songdongkuan/miniconda3/python.exe；每条checker命令的argv/cwd/机器、Python版本、EXE/运行依赖SHA、源码前后SHA、输入/双流/退出/耗时在ROUND_*/RUN_RECEIPT.json。原始双流空流也保留。

执行命令（仓库根cwd）：`C:/Users/songdongkuan/miniconda3/python.exe -X utf8 code/software/m3_pro_fourvoice_trace_20261016/C/run.py --round 1`退出1；`--round 2`退出0。第1轮9例中前8符合预设，背压data攻击因共享字典把前拍也改动，实际仍拒收却得到CALENDAR_FIRST_DIFFERENCE而非BACKPRESSURE_DATA，首失败未覆盖。修复仅替换单拍data字典；同期自审补null机器化拒收、独立每帧四lane锚、预设首差异位置与身份复核，repair.diff保留。

第2轮1正例+18反例全部匹配预设退出码、拒收码及首差异位置：重复lane_tick、错lane、旧epoch返回/复位串入、接受后取消仍消费、漏请求、错重试ID、背压valid撤回/data改变/丢拍、重复发布、缺第4lane、未发布收尾、缺END、布尔cycle、缺reset取消、伪称observed及null交易。正例exit0，所有18反例真实exit2。两轮合计墙钟4.140秒，每轮小于90秒，消费2/6，首过后停止。没有Icarus/ModelSim/Gowin/硬件运行。

## 接手与未验

总交付入口NIGHT_RUN_RECEIPT.json，来源INPUT_IDENTITIES.json，逐例原件ROUND_02/inputs与logs，首失败ROUND_01，全部源码快照保留。封包MANIFEST逐成员SHA可复核。

交D只读：按calendar_json/jsonl及contract SHA取epoch/frame/slot/lane/req_id、offer/accept/return/publish/cancel/consume，不从本包取PCM。交M1只读：输入EVENT的input_cycle/accepted_cycle/cycle与64位data、所有LANE_TICK和取消/reset；需核真实slot、Release推进、效果配置合同后才能建立数学适配。给M1/M2真人的材料均待用户转发，尚未送达；本窗口只回总控一次。

缺M2精确Pro source/ROM/top/时钟和公开端口、真实分配/Release规则及真实trace，M1已发布黄金亦未到。不能把软件夹具改称Pro DUT或实际48k/服务期限、PCM/clip、模拟≤10ms、板级通过；剩余四轮不为凑额度运行。无任务内待做自测，下一动作由总控衔接D、M1/M2输入身份与映射。
'''
    with (DOC/"RESULT.md").open("x",encoding="utf-8",newline="\n") as f:
        f.write(report)
    seal = DOC/"SEAL_20261017"
    seal.mkdir(exist_ok=False)
    files = [x for folder in (HERE,DOC) for x in folder.rglob("*") if x.is_file() and "__pycache__" not in x.parts and seal not in x.parents]
    # Task originals supplied outside the repo are included by exact bytes.
    members = {x.relative_to(ROOT).as_posix():identity(x) for x in sorted(files)}
    for x in inputs:
        members["read_only_inputs/"+x.name] = identity(x)
    write(seal/"MANIFEST.json",{"schema":"M3_C_C2_SEAL_V1","members":members})
    target = seal/"M3_C_C2_INDEPENDENT_CALENDAR_20261017.zip"
    with zipfile.ZipFile(target,"x",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,info in members.items():
            z.write(info["path"],name)
        z.write(seal/"MANIFEST.json","MANIFEST.json")
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for name,info in members.items():
            raw = z.read(name)
            assert len(raw) == info["bytes"] and hashlib.sha256(raw).hexdigest() == info["sha256"]
    final = {"status":"DONE_SCOPED_FIXTURE_L1_PRO_PENDING","package":identity(target),"manifest":identity(seal/"MANIFEST.json"),"members_verified":len(members),"receipt":identity(DOC/"NIGHT_RUN_RECEIPT.json"),"calendar_json":identity(DOC/"CALENDAR.json"),"calendar_jsonl":identity(DOC/"CALENDAR.jsonl"),"contract":identity(DOC/"CALENDAR_CONTRACT.json"),"rounds":2,"elapsed_s":elapsed,"board_release_allowed":False}
    write(seal/"SEAL_RECEIPT.json",final)
    print(json.dumps(final,ensure_ascii=False))


if __name__ == "__main__":
    main()
