# M3 任务单 R12：交付与完整窗口采集软件前端收口（2026-10-18）

本单按用户最新要求生效，只覆盖R11三项已定位缺口的当前续接顺序；旧源码、旧结果、旧失败和消费保持。M3独立实现、自审和封存，M2主窗口最终复核，协作窗口如参与仅分析本次增量，不代替M3实施或M2签收。任务状态仍只在当前状态／看板维护。

**当前权限：用户已一次批准同SHA整包；按本单条件在精确新写集实现／自审，M3先确认收件、完整成果SHA、实际时段和源身份，再运行新增软件、受控worker、标准门禁及发布。旧消费及M2暂停项不恢复。** 完整计划SHA `5dfd47d18a6bc3230437327723b796e145323a703a8aa3af4026a8ab966aba7d`，见[机读整包方案](test/m2_138k_pro_fourvoice_candidate_20261016/r06_public_chain_20261017/night_r10_20261017/intake_resume_20261018/m3_frontend_r12_dispatch_20261018/SOFTWARE_PUBLISH_PLAN_R12.json)。

## 先收件与确认成果归属

1. 从用户转发包读取原样的M3_R11_REVIEW.md（3802B／SHA6425a45c7a7b320119ea84d8aa09a332dac861469790f4a13624c136c7bf4b54）和M3_R11_RECEIPT.json（5368B／SHA3302df82b1bad20c0eaf00808105d8b6acd3633fda00772ba8e2960747462bd0），按清单核同并回填接收确认。
2. 明确“晨间已完成”对应的完整功能SHA。当前已核证的是 `3c5101f19daa85b85d43082d9cadaca37fcbea13`，收据为 `ec833d1955fdf5e9cdd2224fbcbc342ba5c1e07f`；不是仅填分支、短SHA或最新tip。若同一件，确认限定为R11静态交付；若另有成果，附完整SHA、增量路径和可达原件，M2只核增量。
3. 原102／240载荷及已有L0接收不全面重查；原报告中“R05未批／原13:47:59”等是形成时历史，不成为本单权限。M2目前已完成独立ctime软件准入修复，原16案／门禁／发布仍暂停，不借用M2额度。
4. M3回填本人实际START、已结束／暂停状态、截止、唯一写者／发布者及真实既有outbox引用。原自报11:57:42→16:57:42不因收件或本单重计；不默认已经后台运行。

## 一个独立大板块，按三项缺口串行收口

A. **同缓冲JSON身份／解析**：一次有上限raw读取，bytes／SHA核验和JSON解析使用同一缓冲；覆盖spec、HANDOFF、contract、provenance、result、admission、fetch／ancestry／tree以及归档JSON与原件关联。保留MAX_JSON、重复键／非有限数、路径及scope拒收。末尾重核不能代替同缓冲绑定。

B. **Git前置cwd与双流绑定**：fetch、ancestry及每项show的规范化cwd必须为同一ROOT；fetch stdout／stderr描述符均绑定实际本体。保留稳定key、operation_id、原Store尝试账、network.run、UNKNOWN／拒绝禁止重发、RECEIVED与advance分离。所有软件组用固定网络替身，不制造真实失败push。

C. **实际capture调用链的流式身份后继**：新入口声明校验和真实处理都经后继身份路径；逐点记录 entry.process→legacy processing→helper.checked/ref。大raw／双流等以≤1MiB块流式SHA／计数，小JSON仍有界同缓冲。不能只改declared_binding／外层封套，不能生产全局monkeypatch，不改冻结common。允许在新capture_link_successor内做必要的显式依赖注入或最小编排后继；不复制改写整套算法，不改原schema、finish时相或黄金定义。

## 精确独占写集

新源码根：`code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/frontend_close_r12_20261018/`，只允许下列9文件：

- `json_identity.py`
- `delivery_binding.py`
- `delivery_transport.py`
- `capture_identity.py`
- `capture_link_successor.py`
- `capture_entry.py`
- `selftest.py`
- `DEPENDENCIES.json`
- `CALL_CHAIN_BINDINGS.json`

新证据根：`code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/frontend_close_r12_20261018/`，允许机读计划列出的23个文件；其中TASK_ORIGINAL为本单原样副本，ACK是接收回执，OUTBOX_REFERENCE只引用既有发布队列，不另建竞争发布者。新输出只用 `code/output/m3_frontend_close_r12_20261018/`。原R11/R10实现、冻结common、旧账与失败只读；不改RTL/TB、M1模型／其他岗位源、受控接口、八规范、共享状态／看板、两共享PS、check_repo、delivery_tool或repo_gate_candidate。跨出写集才列精确影响，不自行扩大。

## 一次已批的验证与发布预算

|组|上限|固定范围|
|---|---:|---|
|P0准入|60秒／一次|源、工具、输入、写者／发布入口冻结及既有受控机制核验|
|J同缓冲|60秒／≤12案|实际receive_frozen正例、A→B→A及各控制JSON拒收|
|G交付前置|60秒／≤12案|实际send_once、三类cwd、fetch双流、尝试账／禁重发|
|C实际调用链|120秒／≤12案|旧归档合成正例经新实际入口处理、禁大对象整读探针、身份／END失败传播|
|W完整窗口前端|240秒／≤4案|≥1398627657B合成大角色的真实前端身份／绑定／分发、后段篡改／截短／整读探针|
|R有据修复增量|240秒／≤16案／最多一组|只针对本轮J/G/C/W一个已定位软件缺陷；先存原因、差异和新SHA，不原样重跑失败组|
|封存|S1／S2各≤60秒，累计120秒|两个预定义用途，各一次；原件、失败、消费、双流／退出、ZIP CRC／成员SHA，不互作重试|
|两轮标准九门禁|各900秒／各一次|候选全门禁及精确最终待发布树全门禁，第二轮不是第一轮重试|
|新网络|≤15次，各≤60秒，累计≤900秒|开工／30分钟／交接／发布观察、必要fetch、普通push、包含性；临时故障仅一次重试|

软件最多780秒＋封存120＝900秒；两轮门禁1800秒；加网络900秒，**全包最多3600秒**。两轮门禁的既有调用上限合计Yosys/read_slang6、iverilog driver18、内部ivlpp18／ivl18、VVP18；只在本包明确批准后随标准门禁使用，不授权独立HDL/C9／额外EDA／设备。门禁脚本或工具身份与已冻结profile不同则对应阶段NO_GO，不换工具或借M2未发布入口绕过。

原所有已消费组不重开。主组首失败停该组和依赖链；只可在一次预先批准R组条件齐后验证已改后继，失败原件／原槽不返还。R组失败、未定位、任何原生／门禁失败即封存停止；R不能用于修门禁或网络。若修复影响已通过多组且无法在≤16案内完整覆盖全部必需回归，则R条件不成立，不裁剪验收或另开组。两轮九门禁均必须9/9、自然退出及明确PASS／无真实失败，原门禁标准不变；没有第三轮。

## 完整窗口与验收等级

C组使用已有归档合成正例的冻结期望，验证实际后继处理调用链；不重跑旧签组来制造新通过。W组的大角色为明确标记的合成原件，过实际软件前端后在已记录处理边界接固定私有软件替身；它只验流式身份／绑定／分发。单worker Windows PeakWorkingSet64拟上限512MiB、最大读块1MiB、临时盘≤4GiB，按本次整包批准生效；Python heap或chunk大小不能代替整进程峰值。实测不可得就不签容量。

大合成原件保留并提供可访问原件／无损压缩分卷，分卷decoded≤64MiB、全局顺序／总大小／分块及整体SHA齐套；不直接Git add巨型raw、不只交生成器+SHA冒充原件送达。封存预算不足则完整交付未完成，不临时拆小发布。

三项修法、实际入口软件组及前端容量边界、自审和封存齐套才可标 `SOFTWARE_FRONTEND_READY_FOR_M2_REVIEW`；真实完整capture处理、HDL、M1数学、RESET/END/raw/FRAME/PCM/ID/clip和实物仍NOT_RUN/PENDING。不得把软件替身或合成大对象写成真实Pro完整窗口通过。

## 精确最终树与两段封存的固定顺序

软件及候选Gate01完成后，S1最多60秒封存当前证据／失败，并冻结全部受跟踪载荷和精确清单。GATE_02.json、PUBLICATION_RECEIPT.json及其他涉及未来结果的元数据，只能冻结真实PENDING条件／引用，不提前写PASS或REMOTE_VERIFIED。

随后Gate02验精确待发布树；通过才独立逐文件暂存、提交、普通develop推送及核远端包含。Gate02之后任何受跟踪字节均不再改动。实际Gate02双流／自然退出、暂存／提交／push及完整成果SHA／包含回执，只写授权ignored输出；S2最多60秒将这些实际结果或停止／失败原件封成输出FINAL_HANDOFF.zip，随可用授权路径／用户转发交M2。不能再追加metadata提交并声称旧最终树门禁仍覆盖它；receipt_commit可为null并明示实际回执仅在输出包。

S1／S2各一次、分别记录启动／结束并按整槽消费，累计120秒；等待／门禁／网络时长不算封存执行，两段不能相互充当重试。先前阶段失败则在适用未消费封存段内记录，依赖发布停止；任一封存失败保留原件、不新增第三段。分卷只作既有两ZIP的内部成员或ignored原件，不增加第24个受跟踪证据路径。

## 时限、发布与交接

沿用本人已确认的原晨接最早截止，默认参考16:57:42；本单不重开五小时。若原时限核实成立，容纳全包3600秒＋60秒余量的最晚执行START为15:56:42。每组启动须容纳完整本组及尚未用封存／必需后续预算；不够不启动、不拆组滚动到下轮。若本人实际结束更早、旧Goal暂停或START不符，先如实NO_GO，静态材料继续保留。

M3唯一主窗口实现／自审／封存，按标准完整门禁后普通develop发布，保留单文件独立Git写命令和原始暂存观测，不夹带他人改动；推送失败保留本地提交和既有outbox引用，结果不明先查远端包含，不能以tip超前判失败。交完整成果SHA、收据SHA、精确清单、原件和消费，M2主窗口只复核本次增量并决定ACCEPTED/INTEGRATED；协作窗口意见不代签。

当前由用户转发本交接包，M3尚未确认收到。仓库发布／AI接收／验收／集成／真人通知分别记录；本单和预算提案在M2本机未提交／未推送。本预算已获用户明确批准；须合读[已批授权](test/m2_138k_pro_fourvoice_candidate_20261016/r06_public_chain_20261017/night_r10_20261017/intake_resume_20261018/m3_frontend_r12_dispatch_20261018/AUTHORIZATION_R12.json)。机读提案approved=false保留形成时原件，不覆盖新授权；收件／SHA／实际时段／源冻结条件未齐仍不运行目标。
