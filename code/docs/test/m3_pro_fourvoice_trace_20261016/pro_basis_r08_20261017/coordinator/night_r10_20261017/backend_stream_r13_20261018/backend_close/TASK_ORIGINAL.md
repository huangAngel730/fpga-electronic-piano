# M3 夜间任务单 R13：Pro 完整窗口软件生产与交付（2026-10-18）

本单按用户“给M3更新任务单并准备夜间任务，多分担M2任务量”的直接指令编制。覆盖R12完成后的下一队列；R12原成果、失败、消费和证据保留，不改写。当前可在本单精确新写集完成阅读、静态设计、实现候选、自审和许可材料；新软件执行、受控worker、九门禁、网络发布整包已由用户明确批准，仍须本单前置和实际时窗齐。不得把任务分派当成新工具额度。

**当前：用户已明确批准同SHA R13整包；实际START未登记；M3尚未确认收件；未启动新Goal或后台触发。** 本单本地未提交／未推送。唯一机器计划SHA：`729cb21bd4b759f7d5738bdc14964bee1eaf5da053eee20b4a278acf651357d3`。

## 基线与开工动作

1. 完整阅读根/code适用AGENTS、夜间通用规范、当前快照及本单。读取[M2 R12限定复核](test/m2_138k_pro_fourvoice_candidate_20261016/r06_public_chain_20261017/night_r10_20261017/intake_resume_20261018/m3_r12_e39b36b9_20261018/M2_REVIEW_AND_NEXT_ACTION.md)和同目录M2_RECEIPT.json，回填按交接ID＋完整SHA＋M3去重的接收回执。
2. 功能基线固定`e39b36b9b7f956659f7fd5e3ca6dd57e5a34735b`，已发布并由M2限定接受R12软件前端；不是完整后段／真实Pro／数学／板卡通过。旧40复用＋新增2证据，不全面重跑。M2主树尚未检出整合。
3. 本轮沿用一个M3主窗口和唯一测试／发布入口。按需把A合同、B原件、C软件候选分别交给目录互斥的协作角色；不得在同一文件同时写。A只写contract_bundle，B只写capture_originals，C只写13源码（静态发现写README／CASE_MATRIX），backend_close总证据由M3主窗口维护；AUTHORIZATION、START_AND_DEADLINE、CONSUMPTION、最终RESULT_RECEIPT／INTEGRATION_HANDOFF／OUTBOX总绑定仅M3主窗口维护。所有目标检查、九门禁和Git发布也仅M3主窗口执行，M3统一汇合后交一次。不默认启用审核制度；本次只规划角色，尚未实际创建或通知这些角色。
4. 先核M3实际电脑、工作树、HEAD、暂存／脏改动归属、冻结源／工具和可用空间；不以M2本机故障替换M3工具，不借M2未发布的入口。新远端只核本轮增量。

## 目标与交付方式

独立负责“完整窗口软件生产与交付”一个板块，下分三个互补大包共12项。尽量把合同拼装、原件追索、格式接缝和软件后段在M3侧收齐；M2负责少量受控决定及最终复核，M1负责数学／黄金与周期定义。三包归一份冻结版本、一个预先定义的完整交接单元R13-SW。全部必要验收齐才签软件交付完成；缺本单必需的来源原件、冻结合同、可取软件原件或验证证据则交PARTIAL；本单软件条件齐可签R13_SW_COMPLETE，真实Pro／数学／板卡继续PENDING，不阻本软件交付自身结项。不得临时拆小未验任务冒称完成。

|顺序|大包|四项内部任务|交给M2的完成条件|
|---|---|---|---|
|A|合同总成|A1字段／schema路由；A2 profile／全产物容量与无损分卷；A3独立plan映射及epoch/reset/finish；A4源码／工具来源及待决表|9份合同对象互引同一版本，逐项指原件／消费路径／责任人；一页决定表只列真实未决及最小选项，不留整份空模板|
|B|业务原件齐套|B1原件及依赖DAG；B2 capture同源／双流／输入身份；B3正负与失败／消费继承；B4 M1/M2直接消费索引与缺件恢复|7份索引齐；每件准确包/成员/字节/SHA/验证等级/可访问入口，PENDING与真实回执分开，缺件指定责任人和恢复条件|
|C|实际后段软件|C1实际可达链与流式接缝；C2机械输入生产／无损分卷；C3 EOF/拒收/最终原子完成及全产物资源；C4真实后段合成全窗证明与真实执行准入申请|前提与新预算齐后，无D4替身的实际后段软件检查、容量实测、自审／封存／最终树门禁和普通发布齐套；真实采集／数学仍另准入|

### A：由M3把合同一次组装齐

CONTRACT_INDEX逐项链接74字段／公开出口、已有schema/profile、数学机械格式和消费者；FIELD_ROUTE_TABLE写源字段、转换、位宽／符号、时基、目标字段及权威依据，未确认留显式槽，不改公共规范。PROFILE_AND_CAPACITY对全部raw43/public/CSV往返/行索引/三类历史/临时文件/分卷计几何上界，不只统计前端raw。

PLAN_IDENTITY_MAP记录独立plan的生产者、生成依据、输入SHA、逐事件ID到accept/apply的映射；不得反向从实际trace造“独立”预期。EPOCH_RESET_FINISH_CONTRACT保留D／D+1候选差额、最后采样／MONITOR_END/唯一终止/行数证据。M1算法与NoteOff/NoteOn周期意见仍由M1确认，M2决定受控接口差额；未决不默认选一边或改TB。

SOURCE_PROVENANCE列真实源码／ROM/include／工具动态依赖闭包、argv/cwd、环境键的允许公开摘要、实际时基／双流及执行收据是否可取。OPEN_DECISIONS与M2_DECISION_SHEET对每个未决写事实、候选、影响和需要谁确认；已有结论直接引用，不重复申请已批事项。

### B：由M3完成本业务原件和消费交接

ORIGINALS_INDEX、DEPENDENCY_DAG、CAPTURE_IDENTITY_BINDING必须引用实际可访问原件，不只给SHA或生成器。七件机械输入的准确名称、schema、生产者及消费入口先从现有M1合同／D4实现提取，无法确定的条目标PENDING，由M1/M2确认；不得在本单凭空补造七个名称。

POSITIVE_NEGATIVE_HISTORY区分旧40、新2、原失败／消费／上游新增权限转录以及当前新结果。CONSUMER_LOAD_MAP让M1/M2从一处能打开所需对象，标单文件／逻辑流／分卷读法、大小、顺序、收齐／拒收条件和验证等级。MISSING_ORIGINALS写缺什么、谁给、如何核同和何时恢复；真实缺件不能用全零、fixture或错误expected覆盖。

原件大于常规Git载荷时留可达无损分卷；记录卷序号、逻辑偏移、decoded长度／SHA、整流长度／SHA、全局行序和可逆组合规则，跨UTF-8和换行边界不丢字节。W启动前冻结跨电脑原件通道：可使用同一已允许仓库路径且EXECUTION_ORIGINALS.zip≤32MiB、所有逻辑原件可无损恢复；超限只能使用已允许且确认M2可取的用户转发原包／分卷通道，写准确位置、卷清单和获取方式。不授权新增外部存储／凭据／上传服务。只有M3本地ignored路径不算可达；通道未核则DELIVERY_CHANNEL_PENDING，阻W及B／整包完成，继续静态备用，不假填M2已收到。原件缺失照实登记，不开发通用附件工具，不修改delivery_tool。

### C：实际D4后段软件后继

从固定R12入口→R11→R10/capture_link→D4实际链出发，只在新后继根做显式注入／最小适配。保留现有raw→public→CSV往返、日历／串行、数学advance（含cancel后保留项）、逐行来源和终末身份复查。先确认实际可达的64MiB／8MiB整缓冲入口和整体控制JSON使用，按真实调用链处置；不能仅凭旧函数存在推断它被当前执行。

新入口绑定冻结来源／当前控制JSON，控制JSON同缓冲核身份和解析；大角色按≤1MiB流式处理。分卷仍是同一逻辑流，不能删字段、裁窗、跳比较、改finish或用私有D4替身代签。EOF后复查总长／SHA、row_count/finish_cycle/MONITOR_END唯一性；任一子阶段失败传播原异常，保全已生成失败原件，不留下“完成”标志。

完整软件窗为明确标记的合成输入，至少1130662行且raw≥1398627657B，实际经过D4后段全产物链。样本几何、行数／字段和值来源先冻结；只证明软件容量和处理链，不是实际HDL采集、M1数学或Pro数字闭环。若真实有效输入、数学定义或受控决定缺失，保持PENDING并转A/B／静态C，不调用真实工具凑输入。

## 精确独占写集

新软件根：`code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/backend_stream_r13_20261018/`，仅以下13文件：

`entry.py、binding.py、stream_bridge.py、volume_io.py、finalize.py、resources.py、selftest.py、run_plan.py、job_bridge.py、DEPENDENCIES.json、CALL_CHAIN_BINDINGS.json、CASE_MATRIX.json、README.md`。

run_plan/job_bridge只能复用M3已有受控Job启动／清理机制并做本业务编排；冻结原始实现、调用账与身份，未知不得凭新代码宣称受控证明通过。不得以此另开通用运行框架。

新证据根：`code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/backend_stream_r13_20261018/`，三包各自只写以下文件：

- `contract_bundle/`：`CONTRACT_INDEX.json、FIELD_ROUTE_TABLE.json、PROFILE_AND_CAPACITY.json、PLAN_IDENTITY_MAP.json、EPOCH_RESET_FINISH_CONTRACT.json、SOURCE_PROVENANCE.json、OPEN_DECISIONS.json、M2_DECISION_SHEET.md、README.md`。
- `capture_originals/`：`ORIGINALS_INDEX.json、DEPENDENCY_DAG.json、CAPTURE_IDENTITY_BINDING.json、POSITIVE_NEGATIVE_HISTORY.json、CONSUMER_LOAD_MAP.json、MISSING_ORIGINALS.json、README_FOR_M1_M2.md`。
- `backend_close/`：`PLAN.json、AUTHORIZATION.json、START_AND_DEADLINE.json、BASELINE.json、SOURCE_MANIFEST.json、RESULT_RECEIPT.json、CASE_RESULTS.json、RESOURCE_RECEIPT.json、CONSUMPTION.json、FAILURE_HISTORY.json、SELF_REVIEW.md、GATE_01.json、GATE_02.json、PUBLISH_ALLOWLIST.json、PUBLICATION_RECEIPT.json、OUTBOX_REFERENCE.json、TASK_ORIGINAL.md、SOURCE_PAYLOAD.zip、EXECUTION_ORIGINALS.zip、INTEGRATION_HANDOFF.json`。

ignored输出仅`code/output/m3_backend_stream_r13_20261018/`，保存运行原件／分卷／双流／独立自然退出、S1/S2和既有outbox引用。原R12/R11/R10/D4、M1源码／黄金、已冻结历史和旧账只读。本单原件与机器计划复制到backend_close/TASK_ORIGINAL、PLAN，不改本单／共享状态索引。

**排除：RTL/TB、正式source list、约束、公共接口／schema／finish行为、M1算法、M2 runtime/runner/catalog/共享PS/check_repo、工具安装和code/scripts/delivery_tool/。** 确需跨出新写集，只保存精确变更请求；先做独立项，不自行扩大。

## 新执行／发布整包（用户已批准同SHA原提案）

[机器计划](test/m2_138k_pro_fourvoice_candidate_20261016/r06_public_chain_20261017/night_r10_20261017/intake_resume_20261018/m3_night_r13_dispatch_20261018/SOFTWARE_PUBLISH_PLAN_R13.json)按以下各槽计费，不按实际快结束返还：

|槽|次数／上限|范围与前置|
|---|---:|---|
|P0|1次≤60秒|来源／工具／Job受控机制／输入空间冻结，缺失仅阻对应链|
|K|1组≤120秒，≤16案|本次合同路由／plan/epoch/finish/来源拒收增量|
|V|1组≤120秒，≤16案|逻辑流分卷／重组、错序／缺卷／截短／UTF-8边界及末尾SHA拒收|
|B|1组≤120秒，≤16案|无D4替身的实际后段小合成正例、拒收传播／终检／完成屏障|
|W|1组≤900秒，1案|合成完整窗实际后段；生成、全链、哈希、盘／内存和清理均在槽内|
|R|至多1组≤120秒，≤16案|仅K/V/B一个已定位软件缺陷的改后继和全部受影响必要回归；不是原样重试|
|P1|条件式1次≤60秒|保存定位／差异／新SHA后先P1重新冻结，成功才R；P1失败停止，不重试失败P0|
|S1/S2|各1次≤60秒|两个预定义用途，失败保全；不互作重试，不新增第三段|
|Gate01/02|各1次≤900秒|完整候选九门禁／精确最终树九门禁，各9/9自然0；第二次不是第一次重试|
|本地Git|累计≤360秒|唯一发布者，直接独立单文件暂存／提交；保存原始回执|
|新网络|≤20操作，累计≤1260秒|query≤30/fetch≤60/push≤300秒，含开工／30分钟／交接／发布及包含核验|

初始矩阵K8／V12／B12／W1共33案，均未运行；R另为条件式≤16案，不以旧42替代。矩阵见同派发目录CASE_MATRIX_PROPOSED.json。

累计软件1380＋准入120＋封存120＋九门禁1800＋网络1260＋本地Git360＝**5040秒（84分钟）**；实现／静态自审另在当夜五小时墙钟内完成。两门禁原生上限合计Yosys/read_slang6、iverilog18、内部ivlpp18/ivl18、VVP18；不含独立C9、其他HDL／EDA／设备。门禁profile必须是M3已验证的同一工具／依赖，发生变化则NO_GO，不切M2未发布入口或自行换工具。

W拟准入：单处理worker峰值≤512MiB、chunk≤1MiB；自有workspace全产物／中间件峰值≤24GiB，启动可用≥32GiB并保留≥8GiB。先由A2推导实际几何，若超上限或无法测量，不启动W、不删产物降标准；保留扩容请求。必须证明处理worker无子进程，否则测并发进程树总量；root峰值不代替树峰值，监督器另记。旧39MB前端峰值不复用为后段容量通过。

网络延时以R12实际246.422秒成功为依据保留300秒push，不能据此认定postBuffer唯一修复。沿用已冻结的成功传输路径和进程级设置；不写仓库配置、不扩散环境。临时故障最多重试一次，结果不明先查成果提交包含；远端tip被队友追加不算本次失败。20次同时受1260秒计费限，先预留发布／包含槽，余额不足不启动新网络操作。

## 时窗、停止、备用与恢复

这是已获批但尚待M3收件／准入的新夜轮，**不替M3填START，也不继承已过期的06:30/16:57/20:09/21:20截止**。整包批准后由M3记录本轮真实START／时区、本人最早结束和用户本夜更早截止；deadline取三者最早，最长START+5h。缺这些只阻对应执行链，静态A/B/C可推进。不得把收卡／换窗口算成旧轮重开；旧6540秒计费、旧失败及原生历史UNKNOWN均原样继承。

主组首失败停组及依赖，R仅上述已定位条件齐可用；W/P0/封存/原生/九门禁失败终止对应链，无修复重试额度。每次启动前按完整本组上限＋尚未消费且必需的准入／两封存／两门禁／本地Git／push及包含操作全部上限＋固定60秒余量核最早截止；不够不开始、不跨截止滚动。修复分支固定为保存故障依据／差异／新SHA→P1冻结通过→R回归；P1失败即停。未定位、权限拒绝、工具变化、资源上限不明直接NO_GO，不盲试。

C缺同源原件或受控决定→立即做A合同和B索引；B缺原件→做A路由／C静态接缝及资源推导；缺数学定义→列M1确认项，做机械来源／分卷静态实现。新件按完整SHA、精确载荷和去重账核验后，在安全检查点重算队列恢复，已通过组不为凑数重跑。全部可执行项完成／受阻或到点，封存PARTIAL与恢复入口。

## 检查入口、冻结与交付

M3沿用一个夜间Goal绑定本队列／精确写集／证据／deadline。开工、每30分钟、交接完成／阻塞／发布前由主代理直接query origin/develop，按需fetch；命令原始回执写既有outbox执行记录及backend_close消费索引，不自动pull/rebase/merge或替换运行源。Goal／轮询触发未实际部署验证前写NOT_DEPLOYED，不声称后台已运行。到期先清理和封存，周期检查不产生新网络额度。

S1在候选门禁通过后冻结所有受跟踪载荷／精确allowlist；未来Gate02／发布字段只能PENDING或引用，不预写PASS。Gate02检查精确最终树，通过后不改受跟踪字节，逐文件直接`git add 路径`，独立提交／普通develop推送／远端包含。最终Git／Gate02／S2回执写ignored输出，S2打最终交接包，receipt_commit可null；不能回填元数据再称旧门禁覆盖新树。

正常原定单文件暂存必须记录实际树、Git路径／版本、argv、起始、工具墙钟、自然码、完整双流／截断标记、文件数／暂存清单；只在宿主能保持直接Git形态且单进程注入时采Trace2，否则内部耗时UNKNOWN，不为测速新增或重复暂存。

最终交M2：三个大包统一索引、精确源码及依赖／工具身份、原件可取、所有新旧结果与消费、首差异／失败原件、资源／EOF终检、完整成果SHA、包含证明及M2决定表。`REMOTE_VERIFIED→RECEIVED→ACCEPTED→INTEGRATED`分别留证，M2限定复核不代替真实执行许可。真实Pro trace、数学、C9、时序、物理身份和实物在新准入前仍NOT_RUN/PENDING，board_release_allowed=false。

## 本轮明确授权与形成时提案的关系

用户已回复“批准 R13 整包，按上述边界执行”。[AUTHORIZATION_R13.json](test/m2_138k_pro_fourvoice_candidate_20261016/r06_public_chain_20261017/night_r10_20261017/intake_resume_20261018/m3_night_r13_dispatch_20261018/AUTHORIZATION_R13.json)绑定本单机读计划完整SHA；机读计划的approved=false保留为获批前原始提案，不覆盖该新授权。批准未替M3回填START、收件、准入、执行结果或发布；M3自行核前置后按原槽执行，无需重复申请同一范围。新授权不恢复M2到期工具链或允许其借用M3预算。
