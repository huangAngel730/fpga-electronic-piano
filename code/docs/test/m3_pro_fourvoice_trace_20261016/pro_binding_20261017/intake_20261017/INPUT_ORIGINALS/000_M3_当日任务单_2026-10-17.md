# 给 M3：2026-10-17 当日任务单（Pro 四声基础优先）

**版本与适用顺序**：当机主工作树 `develop=ad2de2169230dc8fd9f4b6f8157d384306c2479a`，本机远端跟踪 `origin/develop=8b9d11e5368b6db45a1d3090d45f9e4f754132f2`；GitHub 实时指针未核实。开工先核真实 HEAD/工作树并安全同步最新已发布内容；不得把本地跟踪引用说成此刻远端已验。`8b9d11e` 实际含新 E2/E3/E4 隔离交付，必须先取该树的源与收据，不能在旧 `ad2de21` 上重做已交付内容。再对照 `M3_完赛任务单_2026-10-15.md`；它在本单以外的实物安全和受控接口规则继续有效。用户要求维持仓库既定顺序：**Pro 四声基础 → M2 双音色 → M3 双滑块上飘/下落 → 固定左波形 → 最小真实传谱 → N32**。M3 可在互不抢写的窗口做后项无板隔离准备，但正式接入、物理工具、上板和评分结论不得越过这个顺序。N32 可以按用户另行授权进行离线准备/隔离代码，不抢四声基础的人员、Pro工具和板卡；不能把旧全面暂停/旧一次性预算当成新的正式 N32 接入许可。本单是任务安排，不是新实测结果。

## 已有成果：只读复用，禁止重跑凑工时

2026-10-17 提交 `ad2de21` 新增的原件在 `code/docs/test/m3_pro_fourvoice_trace_20261016/{C,D}/`、其 D/coordinator、`code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/`。先核每项实际源码/工具/日志/失败/消费 SHA，再据其结果接下游：

| 已交包 | 已有实际范围 | 下一缺口，不能升级的结论 |
| --- | --- | --- |
| C/C2 | L1；19帧，76 lane 请求/75返回发布、5取消、71消费；1正18负例按预期，2/6轮。 | 最低空闲slot、lane=slot、NoteOff立即释放、40MHz/833/833/834是 **toy 输入合同**。缺新 Pro 源/ROM、真实 Release/slot 与声部推进、事件应用/效果接受日历；不能直接当 M1 黄金或真实 Pro 接受账本。 |
| D/D2/D3 | L1；D/D2 38000拍诊断夹具，42完整立体声帧，12串行/期限/复位/PA负例；D3 有来源绑定和拒收入口，修后只跑5项增量。 | C/D 是按 epoch 和消费帧映射的诊断夹具，**没有共同真实执行时轴或音符→PCM 算法**；既有诊断串行不能签 Pro 实际48kHz、逐请求833拍、真实 PT8211、PA 电平或模拟≤10ms。 |
| 双滑块 | L2；隔离640×480/8槽/preview120/FIFO32，487检查/4个真实RTL故障拒收，1/6轮。 | 正式模式生产者、98bit score、frame零点/epoch、新 Pro 七组CDC/完整STA、实屏都缺；旧下落命中闪光 FAIL 仍暂缓，不把连续下落运动写成命中反馈通过。 |
| E2 固定左波形（`8b9d11e`） | L2；旧真实5849采纳输入加隔离40→25MHz观察桥，5黄金快照/8扫描/3998520像素拍及5实际RTL坏例；3/6轮。 | 用历史而非新Pro真实PCM，未完成正式Pro完整raster/HDMI、CDC/STA或实屏，完整E2=PARTIAL；不重跑旧窗口。 |
| E3 最小传谱（`8b9d11e`） | L2；真实300B CC0 Type0 MIDI生成44记录/352B，隔离RTL UART→RAM→完整44项READ；127场景、112应答、11快照，6/6轮。 | 未验新Pro正式码流、实体串口/手机有线或声音；默认5秒会话合同不能由50ms隔离覆盖冒充，完整E3=PARTIAL；原额度不可重置。 |
| E4 N32（`8b9d11e`） | 限定短窗L3，N4/8/16/32同源数学/期限/运输，N32 64接受/60发布/3取消/1复位取消、32运输提交、最大349拍，11个有效RTL负例；尾段4802推进退休仅L2，5/6组。 | 冻结piano并非纯正弦，完整左右串行、非零clip、Pro资源/PnR/完整STA/32独立可闻谱峰及实体均未签，T061=PARTIAL；不能把旧PG484风险或剩1组当作正式准入。 |

这些是 M3 在 `ad2de21` 与本机跟踪 `8b9d11e` 中的封存自测，M2 最终限定复核与新 Pro 同版身份需另核；全部不能因 Git 源码存在就升级为板级。先读各包 RESULT/原件/失败史与使用额度，已签 C/D、E1–E4 的正常/负例均不得复制到新目录或无变化全量重跑。`board_release_allowed=false`。

## 今日可连续推进的任务队列（按优先级接力，做不完下次续做）

1. **B0：Pro 板型、电气和四声实物入口**。若有板，按官方4072/4071原理图与实物核完整FPGA料号、Bank电压、MIDI适配器FPGA侧电平/共地、复位/PLL/高有效 `PA_EN`、PT8211线路，记录原件；不凭旧PG484 R17/.fs/STA或静态CST上板。下载只在 M2 给**新 Pro 同版**完整源/ROM/目标/PnR/完整STA/.fs/恢复SHA及本次精确SRAM许可后执行；任何不符先停，绝不写Flash。没板或没新码流即转 B1，不为等许可停止所有软件工作。
2. **B1：真实 Pro 四声独立事件/交易日历（M3 主责）**。只读复用 C/C2，列现有 toy 假设对新 Pro 公开端口的逐字段差异：MIDI/source/channel/note/generation、slot真正释放/Release、四 lane_tick、frame_tick、ready/accept/取消、背压、reset epoch、实际公开结果ID/左右PCM/clip、效果输入接受。M2 提供可核的新 top/source/ROM/trace SHA 时，冻结独立输入计划并自输入推导日历，做四独奏＋四音同发＋逐放及背压/取消/复位，负例须拒收漏第四声、取消后发布、重复发布与跨epoch。没有同版源/真实公开捕获，只能交 `PENDING_PRO_SOURCE_OR_TRACE` 和最小观察接口表；不得把已有 C 日历套上新 DUT。**独占新后继** `code/software/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/`、`code/tb/board/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/`、`code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/`；旧 C、D 和封存包只读。
3. **B2：同版PCM→PT8211数字出口（M3主责）**。以 B1 冻结事件/请求和 M1 黄金为只读输入，另在 `code/software/m3_pro_fourvoice_trace_20261016/pro_serial_successor_20261017/`、`code/tb/board/m3_pro_fourvoice_trace_20261016/pro_serial_successor_20261017/`、对应 `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_serial_successor_20261017/` 实现独立摄取和公开口检查；同一输入/epoch/ID 核逐帧PCM24/clip到 PT8211 LSBJ16左右槽、真实833拍期限及复位静音。M1保留DDS/ADSR/音色/混音/效果数学黄金，M3不从 DUT 私有 wave/env/phase 反填期望。缺实迹只做缺字段/错SHA/错ID/错声道/超期拒收入口，不标真链通过。
4. **E1：双滑块正式接入差异（基础及双音色正式出口以后接入）**。复用已签隔离候选，仅把 `INTEGRATION_DIFF.md` 的真实Pro mode producer、score producer及frame epoch、事件accepted复制点、25/125MHz视频时钟/唯一TMDS、七组CDC与64/98bit bundled路径逐项填“有源SHA/UNKNOWN/冲突”。独立新变更写在 `code/rtl/input/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/`、`code/tb/input/visualizer/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/`、`code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/`；不改原 L2 源或正式top。M2受控接入/完整CDC STA/精确码流，M3保留同版实屏上飘与下落原始动作记录；闪光失败暂不修。
5. **E2：固定左声道波形的 Pro 同版接入**。从本机跟踪 `8b9d11e` 读 `code/docs/test/m3_pro_waveform_successor_20261017/README.md`、`RESULT.json`、`PRO_INTEGRATION_DELTA.md` 与原件，隔离桥/core 的旧真实输入、5快照/坏例均**只读复用**。交 M2 正式 Pro source/PCM公开采纳点、40→25MHz观察、唯一显示/TMDS、完整CDC/STA 的可逆接线差异；若正式工程/码流尚缺，只交UNKNOWN和所需字段。E1 已按顺序同版验收后再采固定左声道一版实屏证据；不重新造旧已签 L2，亦不加缩放/频谱/李萨如。
6. **E3：一份真实文件传谱的实体闭环**。先核 `8b9d11e` 中 `code/docs/test/m3_pro_min_transfer_successor_20261017/RESULT.md`、真实300B MIDI原件与 44 条 RTL READ/缓存ACK/错误COMMIT修复原件，**不重跑已耗尽6/6轮**。把新 Pro 正式UART引脚/Bank/复位与默认5秒会话需验证的差异交 M2；只有其新同版码流准入、电平与一次实体许可齐备后，以一份真实文件完成实体ACK/全部READ与错误拒收。存储读回不代表自动演奏或PCM；BLE后台/多设备/续传后置。
7. **E4：N32最后一项完整拓展**。先核本机跟踪 `8b9d11e` 中 `code/docs/test/m3_n32_pro_candidate_20261017/HANDOFF_CURRENT.md`、`FINAL_RECEIPT.json`、原源码/失败史/5/6轮身份；N4/8/16/32短窗数学及11个RTL坏例**已做，禁止无变化再跑**。当前独立关键增量是请 M1 冻结“32路不同频率纯正弦测试模式”的phase→sine ROM、增益/混音/clip数学，M2核精确新Pro源/约束/商业工具及是否具备候选物理额度；M3准备同源32路时钟/PCM/完整左右串行账本和Pro候选资源闭包。缺签收保持NOT_RUN/PARTIAL，不把冻结piano波表当纯正弦或已有349拍短窗当完整833拍/32可闻谱峰。正式 Pro物理/码流/板测仍在E3后按M2准入，不能复用旧PG484资源/PnR。

## 协作、试错与交接

- 多窗口可拆 B1/B2/E1–E4，但一个任务包只对应一个独占写集/输出/消费台账；主窗口先固源SHA、核原件及最后交付，不能同写共享 Git index、正式顶层或原封存。新隔离软件/模块每包最多六轮有具体缺陷的定向试错（首轮加至多五轮），成功即停；该轮数**不授权**新ModelSim/Gowin/PnR/STA/码流下载。具体运行额度与工具版本按当轮有效任务单核，不借旧已消费额度。
- 必需公共接口、复位时钟、正式CST/SDC/`electronic_piano_top.sv`改动只交差异和可逆提案给 M2，接口组按仓库流程先说明；M2负责最终复核和状态/看板。M1数学确认与M2真实物理/码流签收未到时，保持相应 `PARTIAL/UNKNOWN`，不为持续运行重复旧303/99/487专项。
- 每项交输入/输出/ROM/工具和代码SHA、argv/cwd/原双流/退出码、正负例与首失败、已消费额度、实际L等级、剩余责任人。各任务在自身目标确实完成或需 M2 许可/受控变更时才集中交接；用户确认转发前标 **“待用户转发，尚未送达”**。今天做不完标 `PARTIAL` 和下一可执行动作；没有有意义且已授权的下一包则 `NO_ACTIONABLE_WORK`。