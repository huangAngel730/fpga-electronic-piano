# M3 晨接任务单 R11（2026-10-18）：同源 capture 生产与机械交接链

本卡按用户本轮“昨日夜间改为今日晨接”生效，覆盖下方R10的当夜时段和当前队列；[晨接总单](Pro基础无实物夜间总任务单_R10_2026-10-17.md)统筹，演练原任务的写集与失败历史继续有效。文件名沿用，旧正文保留。晨接实际START起最长5小时；M3本日START／结束／Goal尚待本人回执，不用昨夜21:52→02:52代填。

## 唯一大板块和晨接主顺序

M3独立负责输入、实际交付机制、公开采集入口、机械bridge／FRAME／TX／serial／provenance和完整原件包；数学预期归M1、系统源与最终准入归M2。

1. **先承接原演练返工和接收回执**：按[演练R01及晨接覆盖](M3_夜间协作双机演练任务单_R01_2026-10-17.md)处理实际transport复用安全outbox、实际HANDOFF与冻结身份精确绑定两项软件缺陷，在原演练写集内做最小源码后继／静态自审。原120／60／60秒三组已消费，不重跑；到需要新软件／worker／网络故障演练许可时封存具体增量，不以未闭演练长期等待，转下面同一大板块的独立准备。
2. **机械输入和容量接缝**：向M1一次提供现有bundle／JSONL索引的实际结构、完整窗口大小／行序、来源图及可达原件；按M1消费端唯一兼容方案协同，不自行定义第二套数学格式，不删行／裁窗或代造黄金。补逐事件独立plan、epoch/reset原始材料的缺件清单和机械映射。
3. **finish与精确整链申请**：对已知双negedge造成的D／D+1差额，仅准备最小可逆变更说明、调度合同和受影响断言，交M2决定。旧TB与1130660／1130661候选原样保留；当前暂缓扩大RTL/TB，批准相位／写集及有效执行范围齐后才形成和验证后继，不猜值产生FRAME。
4. **同源完整route**：保留既有75=72基础单元＋driver／observer／TB的身份，以及LINK／新增6例只证分发／拒收的限定结果；完整route仍NOT_RUN。全部输入、finish、来源、软件／工具精确准入齐后，才从同次raw/pins/reset/END和双流产生唯一FRAME、日历／TX／serial及数学机械包。
5. **一次交完整交接单元**：向M1／M2提交当前INTEGRATION_HANDOFF和本体原件、身份／失败／消费／验证等级。静态、合成例、完整处理、HDL、实际数学分记；没有raw_edges、低样本、PCM或身份时保持PENDING。

## 独立备用与恢复

| 缺件／阻塞 | 本岗独立备用 | 恢复主任务 |
|---|---|---|
| 演练需新验证范围 | 保留两项最小修法与差异，做机械包接口／容量／来源描述 | 精确新许可及当前候选冻结齐后，按影响范围验证；不重开旧三组。 |
| M1合同尚未汇合 | 整理当前真实生产格式／全局行序及无损分卷方案，列唯一待决定差额 | M1数学含义、M2受控合同决定和同版身份齐。 |
| finish／HDL许可未齐 | 调度差异、准入申请、缺失原件和完整route拒收／PENDING路径静态后继 | 相位获批、源／工具／输入／预算和唯一执行者冻结。 |
| 无真实测量输入 | 在原R8-19～24范围准备已知格式／阈值／时基与来源说明 | 实际材料齐且有独立准入；不造照片、WAV、校准或设备结果，不重跑H54。 |

## 精确写集与消费

原三根为 `code/software/m3_pro_fourvoice_trace_20261016/`、`code/tb/board/m3_pro_fourvoice_trace_20261016/`、`code/docs/test/m3_pro_fourvoice_trace_20261016/`，仍逐项限写。R6仅各根下 `pro_basis_r06_20261017/{normalized_intake,tool_plan_adapter,event_calendar,tx_clock_reset_checker}/`；R7仅 `pro_basis_r07_20261017/{public_capture_tb,public_equivalence_tb,oracle_bundle_bridge,capture_provenance}/`；R8仍依原ASSIGNMENTS逐项写集。当前整链软件／docs/test后继限前述对应根的 `pro_basis_r08_20261017/coordinator/night_r10_20261017/`，输出 `code/output/m3_c9_chain_night_r10_20261017/`，不泛化到三根任意文件。RTL/TB新增／改动仍受上面第3项暂停和批准边界。

演练返工仍限原演练卡三处写集，不改八规范、M1/M2源、受控公共接口或共享状态／看板。只在自有可逆后继写入，旧失败／消费／已签源保留。

原R08五组、D4初始／修复、LINK初始7例与新增分发6例、演练三组的已消费事实不因R11重置；原204／114／H54复用原件。任何仍存在的条件增量逐项核原账、具体缺陷和有效时窗，不作为通用自测池。新完整capture处理软件组、worker、HDL／ModelSim/C9／EDA／设备许可为0；M2的Icarus两最小单元批准也不覆盖本链。

## 持久交接、检查与退出

沿用本岗 `coordinator/night_r10_20261017/` 中实际RESULT_RECEIPT／INTEGRATION_HANDOFF、消费／去重及outbox，演练使用原 `night_drill_r01/` 的对应收据与队列，不新建竞争发布者。开工先回读本机实际文件和SHA；若原outbox未生成，登记缺件及计划持久路径，不声称机制已部署。唯一发布者仍本岗主会话，M2只做最终限定复核。

每30分钟及开工／交接／受阻／发布点由主代理直接查origin/develop，变化按需fetch；不自动pull/rebase/merge。GitHub已发布、AI收到、验收、集成及真人通知分开记录；M2本地回执未发布时，不写已拉取取得。完整交接按九门禁和普通develop发布；缺精确准入或到本岗晨接截止即封存PARTIAL与下一责任，不启动三岗整夜机制或冒称完整route已跑通。
---

## 夜间历史分界：原任务、授权来源与失败消费（完整保留）

# M3：2026-10-17夜间Pro无实物收口 R10（最长5小时）

## 2026-10-17 用户新增：由 M3 主执行双机协作演练 R01

M3 在安全检查点先按 `M3_夜间协作双机演练任务单_R01_2026-10-17.md` 接续 M2＋M3 两机演练，M2 配合并最终限定复核；原件与机读收据在 `test/m2_night_drill_r01_20261017/`，直接从已发布仓库核验，不要求转发本地 ZIP。M3 沿用本岗唯一主 Goal／发布者，新增精确写集与有界机制自测预算只适用演练；原实际 START＋5 小时／06:30 较早截止不重置，R10 业务预算与旧失败消费不恢复，HDL／EDA／设备新增许可为零。四类真实双机原件齐并经 M2 核验后才扩展三岗整夜；缺件按新单做独立准备，不代签整体通过。原 Pro R10 任务与优先顺序在未覆盖部分保持。

## 2026-10-17 用户更正：每人从实际开工起最长5小时

本轮用户明确将夜间上限改为每人从实际START起最长5小时，当前R10及后续夜间单均适用；原06:30硬截止仍取较早者，已开工按原START计算剩余，不因换窗口/转轨/本次修订重新计时。5小时覆盖实现、验证、清理和交接，必要结果达到或无可行动项提前结束。三岗独立大板块、依赖、写集、工具次数/秒级预算及已消费记录不变；旧6小时及历史八小时实例不再决定当前可用时长。详见夜间任务通用执行规范与当前R10五小时卡。

> 发布基线更新：M3 e394790b 的432项R06/R07/R08及C9材料现已到库，登记待M2单独限定复核；此前“R7四包未到件”仅为历史。M3自述仍PARTIAL，C9新42例NOT_RUN；本次NoteOn文字签收不代签M3整项。

## 2026-10-17 M1 Note On 勘误已 L0 接受，关闭原待确认项

M1 已确认原 note_on_mask.definition 的 preceding edge 错指 allocation；M2 已核原包与源码锚点，限定接受 L0 文档/源码语义。成功 allocation E 后，H 为首次 CTRL_ON && cmd_ready，reset 不打断时消费 C=H+1，最早 C=E+2，背压可继续推迟。原待 M1 确认的该文字勘误关闭；M1 不另造 R10 中重复的 ERRATA_NOTEON_R10 文件。权威并引见 test/m2_m1_noteon_erratum_20261017/SEMANTICS_BINDING.json：原语义 SHA 与仅改 /fields/4/definition 的后继 SHA 一起使用，原语义、四份 RTL、C9 和 R10 DELIVERY_CONTRACT 原字节保留。

本轮未跑附件脚本、旧十九方法或新软件/HDL/EDA/设备组，不转签真实行为。R10 三岗大板块/5 小时与硬截止/既有预算保持，旧 R09 两次 0xC0000005 及消费不恢复；独立 plan 序号、audio_stable、同版真实数学输入和完整数字/物理/板测仍 PENDING，整体 PARTIAL、board_release_allowed=false。M1 缺 blob 的历史保留，M2 有原件不等于已送达 M1。给 M1/M3 通知待用户转发，尚未送达，审核制度未启用。


| 项目 | 当前执行卡 |
| --- | --- |
| 唯一大板块 | **独立输入→C9公开采集→日历/TX/串行核验→同源capture封存整条工具链**，由M3主窗口交一份成品 |
| 生效/库存 | 基线30d4591；R08的36项保留为内部库存和原独占写集，本夜按这条链路收敛优先级，不按36项逐项交接 |
| 可用条件 | 按无实物；M1/M2源合同已发布，实际M3机器/修改/消费/可达性START实核。R7/R8未见已发布新交付不等于未开工 |
| 时间盒 | START最多5小时且不晚于北京时间2026-10-18 06:30；四阶段；建议第110分钟已有第一份完整机器可读执行申请，缺项明确列出 |

## 独占写集与唯一写者

三根仍为`code/software/m3_pro_fourvoice_trace_20261016/`、`code/tb/board/m3_pro_fourvoice_trace_20261016/`、`code/docs/test/m3_pro_fourvoice_trace_20261016/`。

- 原R6四个返修目录：`pro_basis_r06_20261017/{normalized_intake,tool_plan_adapter,event_calendar,tx_clock_reset_checker}/`，其他原R6输入包依原写集。
- R7四模块：`pro_basis_r07_20261017/{public_capture_tb,public_equivalence_tb,oracle_bundle_bridge,capture_provenance}/`。
- R8各组件仍在原ASSIGNMENTS指定`pro_basis_r08_20261017/<本项directory>/`，不复制/改名重置额度。新增整链入口/台账仅software与docs/test根的`pro_basis_r08_20261017/coordinator/night_r10_20261017/`，不是第二observer/FRAME生成器。
- 输出`code/output/m3_c9_chain_night_r10_20261017/`。M1/M2源、生产top/pkg/CST/公共规范、状态/看板均不写。

成员级主责统一给M3主窗口。内部可按独占目录委派；原写者仍活跃时不抢写，先核认领/原修改并由主窗口串行汇合。接手不得覆盖他人脏成果或并发共用index；窗口数不增加预算。M3内部完成后汇成一个交付，不把子模块逐件请求M2确认。

## 四阶段连续推进

1. **安全、装配和旧缺陷（建议≤60分钟）**：R8-03/04接R6-4由spec重建规范计划、输出独占和一次消费；R8-01/02/05只读核C9 72单元/9ROM/2头、67口/74字段。R6-3/5/6修startup null/合法ID0、HOLD跨事务、raw cancel、F/A期限、REAL来源及唯一FRAME_PLAN。原RUN03十五项/旧D3不重跑；CANCEL reason不再作req_id。来源安全没闭合不启动任何进程。
2. **唯一公开TB及外部输入（建议≤90分钟）**：R7-A复用R6-2 driver，接R8-07/08/16无损codec、异步reset原边沿、外部MIDI实际到达；R7-B只比较同输入公开行为。仅读公开口，不force内部ready，不以私有wave/env补字段；MIDI四条NoteOn不伪装同拍。独立plan序号与router_apply_seq分列，audio_stable未定保留PENDING。第110分钟左右先汇成唯一INTEGRATION_HANDOFF申请供M2判断，依赖缺项完整写出。
3. **日历/TX/串行/机械桥一条管线（建议≤120分钟）**：R6-5唯一生产FRAME_PLAN，R8-09/10/11只读核全窗口至finish、F/A及严格t-F<833/早于下一独立FRAME，实际TX833/834另核。R8-14/15核startup/HOLD和ID/PCM/双clip谱系，R6-6/R8-13复用固定PinDecoder核PT8211 LSBJ16相位/左右/量化。R7-C按C9和M1已发布NEXT_INPUT_CONTRACT包装数学输入，数学期望仍归M1。R8-17/18仅补当前链路必需的新场景/首差异，避免拖延主线。
4. **整链接合与一份封存（余时≤30分钟）**：R7-D汇合R8-06/12/11的source/input/tool/clock/reset/frame/oracle/receipt来源图和正常尾段。复用R08实际未消费五组，另有N10-M3-LINK≤120秒新接缝组及首个具体缺陷一次≤60秒增量；不全量重跑组件组。无准入输出SOFTWARE_READY+HDL_NOT_RUN+PENDING_EXECUTION；M2精确新准入及原件到件才核实际capture，不把批准字符串/合成日历升级REAL。

建议工时最多5小时，工具额度单列。R08旧组先核真实台账；新LINK组只覆盖74字段端到端往返、同包bridge/FRAME/TX/来源接合等旧组没有的新断言。同case不得归两组；运行前固定SHA/argv/cwd/case/独占输出并消费。所有纯软件组禁止子进程、编译器/HDL/EDA/设备；R6-4真实工具启动仍拒绝，生命周期测试先交申请。

## 独立推进、验收与止损

M2编译受阻时仍完成runnable整链入口、实际TB源码、机械桥、软件正负例及精确执行申请；M1未有实际数学输出时按冻结字段机械包装，oracle结果缺失单列PENDING。完成这些后有余力才转R8-19～24测量软件/错配夹具/离线导入，真实照片、电压、仪器校准及模拟延迟不伪造。

最终只交一份INTEGRATION_HANDOFF及本体包（源/TB/driver/observer/checker/输入/FRAME_PLAN/bridge/原件与收据），一份软件与实际候选结果分开的总结果。原始null/X、startup、取消后帧、EOF/finish、同PCM异ID和clip都不可丢。首失败留原件；超写集/额度/执行权限立即停依赖项并转本板块可做项，无可做项NO_ACTIONABLE_WORK。完整链仍缺真实运行就不签DIGITAL_VERIFIED。依R10总单集中自审发布交M2最终复核，通知待用户转发尚未送达。

发布并发补充：门禁期间远端新增M3提交e394790b的432个文件，均在M3三根且与本勘误写集/验证记录无交集；现已到库，单独待M2限定复核，本次NoteOn接收不代签其软件/真实链。原两次本地提交、旧精确树9/9与失败推送已封存bundle；只在干净发布树重放本轮文字勘误，主树未重置/拉取覆盖。新精确树门禁与远端SHA另封。
