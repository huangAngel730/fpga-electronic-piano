# R11 包 B：当前机械输入格式与容量接缝

状态：**静态交接材料齐；完整 capture NOT_CAPTURED，完整 route NOT_RUN，数学仍 PENDING**。本包只描述现有生产格式，未建立第二套数学格式。源文件、原件和分卷的精确 bytes/SHA256 见同目录 MECHANICAL_INPUTS.json。

## 范围与执行边界

依据正文为 R11 的 task-day1/M3 任务单（SHA ca9a530c0298c5a7db71dff10008b1ae49208c775d6490da19a18585f61dee2a）及总控对包 B 的委派。统一 START 2026-10-18 11:57:42、截止16:57:42（+08）。本窗口仅写本 mechanical 目录；Goal、GitHub检查和统一发布归夜间任务1。

本次只读源码/文档、JSON/ZIP元数据，核旧原件字节及哈希，并做只读子智能体自审。候选 import/compile/软件或 worker/完整处理/HDL/EDA/设备执行均为0；未做网络、Git写入、FRAME生成、采集或数学比较。历史消费、失败和已签源保留。当前可静态描述的 SOURCE_APPLICATION_C9 为75=72基础单元+driver/observer/TB，9ROM、2头文件；源身份不证明真实执行。

## 当前入口与历史入口

| 层 | 实际输入/输出 | 当前边界 |
| --- | --- | --- |
| capture_link_r01/entry.py | N10_M3_UNIFIED_PIPELINE_REQUEST_V1；PROCESS_CAPTURE分发至D4 | 绑定CAPTURE_MODULE_BINDINGS；先核finish/窗口/独立FRAME输入；已有6例只证分发或拒收，完整处理NOT_RUN |
| D4 chain.py | M3_C9_CHAIN_REQUEST_V1 PROCESS_CAPTURE | 原application→唯一FRAME producer→stream→codec往返→intake→calendar→serial→ROM manifest→math→provenance；本轮未执行 |
| c9_stream.py | M3_R7A_C9_RAW_CORE_ROW_V1 → M3_R7A_C9_PUBLIC_ROW_V1 | 增量读写、多遍身份核验；派生43口不作采集权威 |
| math_bundle.py | M3_D4_C9_MATH_BUNDLE_REQUEST_V1 → M3_D4_C9_MATH_INPUT_BUNDLE_V1 | 小manifest与逐行JSONL；原件保留descriptor，不自动全量复制进数学包 |
| 旧C9机械索引 | M3_R7C_C9_MECHANICAL_INDEX_V1 | 旧index_records会积累列表，不当作当前大窗流式入口 |
| 旧61字段桥 | M3_R07_ORACLE_MECHANICAL_BUNDLE_V1 / BUNDLE.json | 历史接口，非当前74字段生产格式；不降投影绕过M1旧B0限制 |

M1 NEXT_INPUT_CONTRACT SHA b9cd60d3df2184e318b03e6d973f3ebf319ae73614f6e7deb51f771159a52373 是文字合同，明确旧B0仅支持已签settled四lane同时推进profile。未在本次所读 M1 oracle_adapter 及相关 code/model 范围发现其实际新消费器版本/容量依据，不能虚构M1有16MiB或64MiB总包限制。

## manifest、全量索引与稀疏历史

生产 MATH_INPUT_BUNDLE.json 有 schema/status、next_input_contract、inputs、missing_roles、row_count、all_rows_retained、history_counts、artifacts、expected_math、legacy_b0_status、pending及真实/数学/放板标志。artifacts引用 MATH_ROW_INDEX.jsonl、FX_HISTORY.jsonl、ADVANCE_HISTORY.jsonl、INPUT_AND_APPLY_HISTORY.jsonl。RECEIPT.json另加manifest自身descriptor。MECHANICAL_INPUT_READY_MATH_PENDING **不等于角色齐全或数学验收**，必须联看missing_roles。

17个role为 source_closure/rom_manifest/observer/driver/tb/tool_identity/capture_contract/midi_plan/public_rows/raw_capture/reset_edges/end/stdout/execution_receipt/frame_plan/ledger/tx_report。桥入口硬性要求public_rows；其他缺项原样报告，不生成占位证据。chain装配来源/工具/ROM、原capture、FRAME、ledger和TX引用；execution_receipt需独立有效输入，工具IDENTITY_ONLY不是可信执行回执。双流、pins、来源/生命周期仍属整链交接，虽不全是math_bundle的17角色。

公开行外壳准确为 schema/capture_id/origin/source/fields/raw_ports/missing_reasons/events/semantics；fields是74字段，raw_ports是72原始端口。完整字段名及每个机械记录的键见MECHANICAL_INPUTS.json。origin可为SYNTHETIC_SCHEMA_FIXTURE或HDL_PUBLIC_CAPTURE_UNVERIFIED，都不能自动升级真实来源。

MATH_ROW_INDEX每个公开行恰保留一项：source（加canonical_row_content_sha256）、完整canonical_row、frame_f_raw、actual_accept_a、advance_request_tag、lane_advance、apply_classification、independent_apply_event_seq、expected_pcm、actual_pcm_is_golden、math_status。actual_accept_a由req_valid/ready判为true/false/null；独立事件seq和expected_pcm保持null。

| 文件 | 实际选择条件 | 保留内容/解释 |
| --- | --- | --- |
| FX_HISTORY | effect_input_valid !=0 或 config_take !=0 | actual_effect_input(valid/ready/id/left/right/clipmask)、actual_config、config_components、上游/效果/反馈三种clip mask；expected_fx_input=null |
| ADVANCE_HISTORY | advance_mask !=0 | lane mask、request tag、req_id、同排commit、raw cancel；接受后未发布或取消的推进不丢 |
| INPUT_AND_APPLY_HISTORY | event_valid !=0 或 apply_valid !=0 | 完整64bit输入、apply kind/data/mask/router seq/valid、分类；independent_apply_event_seq=null |

以上 !=0 也保留未知null，不能改成仅==1以“清理”历史。FRAME F、接受A、lane advance、effect接受、commit、TX采纳各自分开。advance_frame_req_id不是FRAME F；router_apply_seq不是独立plan seq，同seq多阶段不得去重，apply_kind=3/4/8不得借陈旧data造输入原因。config仅按实际take解包；原X/Z/null及missing_reasons保留。M1独立黄金必须按真实应用/推进/FX日历计算，实际PCM不作黄金；真实比较为0 LSB。

## 全局行序、整数与哈希

source准确键为 raw_sha256/reset_edges_sha256/line/cycle/epoch/time_ps/sampling_phase。line是整个canonical文件1起序号，cycle=line-1且从0起；reset/epoch变化或运输分卷均不重编号，time_ps严格递增，sampling_phase=POSEDGE_PRE_NBA。整流capture_id/origin/raw SHA/reset SHA必须一致。

三份history是稀疏观察，以共同来源身份和原source.line/cycle关联；不能按history文件位置互相zip、按req_id重新排序或把多个stage拼成独立输入序列。只有独立原始reset证据决定epoch，分卷不是epoch。

文件SHA覆盖全部原字节。RAW_PUBLIC_LINE_INDEX的raw_line_sha256/public_line_sha256覆盖原/输出物理行字节（生产输出含LF）；数学source的canonical_row_content_sha256覆盖Python规范化JSON内容：sort_keys=True、separators=(逗号,冒号)、ensure_ascii=False、allow_nan=False、UTF-8、不含LF。两种行SHA不可替换。

64bit event_data、62bit config_payload和128bit slot_generations可能超过2^53。消费器须保留任意精度整数和原raw bit字符串；普通JavaScript Number解析再序列化会损失精度，也可能破坏内容SHA。本次读取样例仅用于静态键/身份核对，未重写原记录。

## 完整窗口大小与容量

真实完整raw、public、math index、history字节/计数目前均为null / NOT_CAPTURED。finish未冻，保留两个**未批准候选**；下表只是从cycle0完整保留到finish的公式，不是采集结果：

| 候选finish | 完整行数finish+1 | 首core12500ps、周期25000ps时finish_time_ps |
| --- | --- | --- |
| 1130660 | 1130661 | 28266512500 |
| 1130661 | 1130662 | 28266537500 |

D/D+1调度提案归包C/M2，不在本包选择值。现有FRAME_INPUT_DRAFT明确M2_frozen=false、epoch1.stop/finish=null，不是有效generator输入。

当前stream源限制：每JSONL行1MiB、metadata16MiB、RAW64GiB、1亿行、**每个输出文件**512GiB。不是整包512GiB，不是所有下游模块的统一上限，也不是已验证完整窗口容量；单个meta/行、整RAW和所有消费端分别核。当前实现增量读写但会多遍读RAW，不称“单遍”。旧61/C9列表入口不能承接本流的内存承诺。

可达历史R02/cases/054例：7行SYNTHETIC_SCHEMA_FIXTURE，RAW18827B、public32594B、math index37852B；FX1行834B、advance2行1205B、input/apply5行3382B。manifest缺12角色，expected_math=null。其尺寸只说明该小样例，不作为113万行窗口的容量证明。历史>64MiB软件样本也不能替代指定全窗、full math或真实capture。

## 无损运输/消费方案（待M1确认，未实现）

沿用现有D4 ZIP原字节分卷，不更改数学JSON结构。依part001→004拼到**新**ZIP，先核各part及整ZIP SHA，再按成员bytes/SHA核验。其1458载荷成员外另有ORIGINALS_MANIFEST.json，中央目录共1459项；不把数量差误报丢件。

未来大JSONL仍是一条不变的UTF-8/LF逻辑字节流。只在运输层记录原文件bytes/SHA、分卷序号/bytes/SHA/半开byte offset；若选择行边界，再记原全局首末line。不可把分卷当新schema或改写行号。**现有iter_public_rows不能逐卷重启**，否则首行sequence会拒收；先原字节重组，或由M1获准的消费实现向同一个迭代器提供串联逻辑流，末尾核全文件SHA、行数与原源身份。当前没有已部署的新分卷API/恢复执行证明。

从ZIP恢复到独立staging根并保留repo相对member路径，descriptor resolver只添加staging根；不改原manifest中的output路径或原JSON内容。稀疏history可用有界缓冲按global line关联；跨运输边界保持算法状态，reset仅依据真实证据。吞吐/内存/恢复边界需M1给实际消费器版本及预算后验证，不凭本文授予运行许可。

**唯一格式兼容决定 M1-CONSUMER-COMPATIBILITY**：请M1确认唯一入口是否为现有M3_D4_C9_MATH_INPUT_BUNDLE_V1 manifest + 原样全量MATH_ROW_INDEX/三history流，并返回消费器版本/SHA及整数/流式容量能力；如当前消费者不兼容，给同一合同的最小适配接口与预算。M3不另造数学格式、不删行裁窗、不把旧B0升级为支持完整F/A/TX语义。独立plan/黄金等语义缺件另保留PENDING，不用格式决定替代它们。

## 独立plan、epoch/reset和缺件

既有M3_R06_MIDI_STIMULUS_PLAN_V1为63byte、23事件、total_cycles=1122320。每个事件有event_seq、源byte首末序号、到达窗口及expected_event_hex；本包JSON按原23项列机械映射，但actual_public_acceptance/actual_stage_mapping均null。UART字节/运行状态/realtime意味着四条NoteOn不伪装同拍。计划自带旧semantic_status仅保留原件，不覆盖已接受的NoteOn文字勘误；该勘误已L0关闭，不重复索要。

ready_plan中的public_event_backpressure标签仅是原计划标签：C9 TB第13/95行将driver.event_ready接到driver_ready_not_connected，未接入DUT ready，不能据ready.drv证明实际背压；实际背压须另读公开接受记录并由M2确认政策。

reset.drv原计划：0→0、800→1、1000480→0、1002480→1；它是外部驱动计划，**不是实际异步RESET_EDGES**。现有FRAME草稿epoch0为assert0/release802/stop1000479，epoch1为assert1000480/release1002482/stop null；release值来自源推导，仍非M2冻结或实测。真实reset的精确时间/epoch/时基、初始状态、正常尾段要与同次raw/pins/END绑定。

待M1：消费器唯一兼容决定、独立计划到真实前门接受再到应用stage的因果规则、受支持profile与独立PCM24/双clip数学。不得将router seq、计划到达窗或实际PCM冒作独立数学输入。

待M2：finish/epoch窗口、audio_stable与背压政策、精确可信执行者/工具动态依赖/源与输入/执行预算冻结。待M3在新精确准入后：同次全量raw/pins/实际RESET_EDGES/END/双流/退出生命周期原件，唯一FRAME、ledger、TX/serial、ROM与provenance和真实机械bundle。每项缺失清单、角色和可达原件见JSON。

## 可达原件与来源图

M1可从Git文件直接读取生产源码、C9合同/源闭包、原reset及当前INTEGRATION_HANDOFF；精确身份已实际hash。生产来源链为：M2基础72+采集3→application75/ROM/includes；独立plan+准入→同次raw/pins/reset/END/双流/receipt；独立冻结FRAME输入→唯一FRAME；同次canonical+FRAME→ledger/calendar/TX/serial/math机械包/provenance；最后M1独立模型比较。描述来源链不代表后半链已执行。

D4原件入口为同仓库docs/test/.../coordinator/task_day4_completion_20261017/DELIVERY/ARCHIVE_RECEIPT.json和ORIGINALS_MANIFEST.json。四个part总77181102B，整ZIP SHA 5e03d33672552be866633491d9278194fe923e4bbbaff03c77eb7915a67fb237。本次重核四part、整ZIP及所列23成员身份。JSON列出完整可达repo路径、精确member、bytes/SHA；不仅给本机output路径。7行原件在R02/cases/054/，独立plan/driver/reset/ready在R03/cases/000/a/inputs/；均是历史软件/准备材料，不能交叉拼成一次真实capture。

当前capture_link原件ZIP为M3_OCT18_CAPTURE_LINK_AND_INTAKE_ORIGINALS.zip（104292B，SHA6bada8ed6a8241201a9b67337e8ca1c9e3555d38afede17fb94c2fc52e6ffd3f）。RESULT_RECEIPT记录source提交daf171163d889f2f5ddf3c9061813c1da7220ab2、历史REMOTE_VERIFIED；本包没有重新查远端，不能称M1已收到/接受。当前INTEGRATION_HANDOFF为53596B/SHA461e187a795ed9c8206a0c651f32a6d9adc7d73561e4ccade0c8e1cf99f2f452。

本包结项仅限静态描述、缺件映射和原件可达性。完整业务仍PARTIAL；math_verified=false、real_verified=false、board_release_allowed=false。统一发布与M1/M2交接由总控完成，未提交/未推送的本包不冒称已发布。
