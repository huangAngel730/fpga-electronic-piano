# C/C2 独立日历与交易边界：限定完成

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
