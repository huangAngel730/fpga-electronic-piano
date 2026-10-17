# 给 M3：四项完整拓展主责任务单（2026-10-17；待用户转发，尚未送达）

**最新授权与优先级**：用户本轮明确把更多完整拓展任务交给 M3，包含 **N32／32 复音**。这覆盖旧任务单“当前阶段任何人不得启动 N32 增量”的**离线隔离工作禁令**；M3 可现在并行实施 N32 候选，不等前一项全部上板才写代码。基础 Pro 四声仍是主窗口及工具/实物的第一优先，拓展的正式同版签收顺序仍为 **双音色（M2）→ 双滑块（M3）→ 固定左波形（M3）→ 最小传谱（M3）→ N32（M3）**。此单分配完整功能责任，不声称已有 Pro 码流、32 声板测或四项完成；旧阶段的 PASS/FAIL/UNKNOWN 与来源 SHA 原样保留。商业 Pro 许可与设备可用性以开工实核为准。

## 执行组织与边界

- M3 主窗口继续 Pro 四声 C/D 数字证据和实际板型/电气原件；可开独立窗口分别负责下表各**整个功能包**。同一功能只有一个窗口拥有可写目录，主窗口只读核来源、串行处理共享 Git 暂存/九项门禁/普通推送和向 M2 交接。完成当前包即转下一个有实际输入的包，不为凑时间重复旧专项；夜间五小时到点未完成的包记 PARTIAL 和确切续做点，不算失败。
- M3 对每项负责**实现→独立参考/负例→模块仿真→隔离组合→来源封存→待正式接入差异→同版板级原件**的闭环，缺许可/Pro工程/实物的环节保持 PENDING，不把单个离线 PASS 称“完整拓展已达成”。M2 继续拥有正式 top、PLL、公共接口、正式 CST/SDC、整机 CDC/完整 STA、精确 `.fs` 身份与下载准入；M1 只核其冻结音频算法或变化后的数学口径。M3 可在隔离工程实现适配和做授权候选物理试核，但不直接覆盖生产树。
- 所有旧源码/ROM、旧 seal、旧失败/捕获、M1 黄金、M2 正式工程均只读。上表新子目录与 M3 Pro 四声 C/D、M2 双音色候选互不重叠。若必须动公共音频事件/PCM协议、时钟复位、正式顶层/引脚，交精确端口/时序/资源影响与可逆补丁给 M2，按接口组变更流程，不自行写共享文件。

| 完整功能包 | M3 独占新增写集（不存在时按需创建） | 当前可直接做的成果与最终验收门槛 |
| --- | --- | --- |
| E1 双滑块上飘＋下落 | 沿用 `code/docs/M3_并行拓展双滑块窗口_2026-10-16.md` 的三个 `pro_parallel_20261016/` 新目录；不另开一套实现 | 完成默认640×480、八槽、队列32、模式切换/复位/CDC入口、上飘按/松动作、下落连续移动及退出的隔离自检和音频不被显示回压的负例；同版 Pro 实屏/音画共存由M3采原件、M2核完整STA。旧下落命中闪光 FAIL 本轮仍暂缓，不能写下落完整交互通过。 |
| E2 固定左声道真实波形 | `code/rtl/input/pcm_waveform_candidate/m3_pro_waveform_successor_20261017/`、`code/tb/input/pcm_waveform_candidate/m3_pro_waveform_successor_20261017/`、`code/docs/test/m3_pro_waveform_successor_20261017/` | 只读复用既有 `pcm_waveform_candidate.sv`、`reference.py`、`tb_waveform.sv` 与原真实左声道输入；固定一版区域/窗口，核 sample_seq、signed24→像素、2048快照、帧边界不撕裂、reset/丢样拒收及显示不回压音频。再给 Pro 40→25MHz 接入差异与一版实屏原件；不加缩放/双声道/频谱/李萨如。正式 CDC/顶层/STA 由 M2 执行并核同版。 |
| E3 一份真实文件的最小传谱 | `code/rtl/input/score_transfer_candidate/m3_pro_min_transfer_successor_20261017/`、`code/tb/input/score_transfer_candidate/m3_pro_min_transfer_successor_20261017/`、`code/software/score_transfer_trace_candidate_20261015/m3_pro_min_transfer_successor_20261017/`、`code/docs/test/m3_pro_min_transfer_successor_20261017/` | 复用 T057 编码、严格帧/CRC/事务/ACK/完整READ的已签源码和实际真实 `.mid` 限定原件；隔离端到端输入→RAM→READ逐字节同源核对，重放 ACK、丢帧/CRC错/超时等负例。取得真实安全串口或手机有线链路后只用**一份**来源明确的真实文件做实物 ACK/READ 与拒收，不将存储读回写成自动演奏/PCM；BLE后台、多设备、编辑器后置。正式 UART pin/Bank/CST 与码流由 M2 准入。 |
| E4 N32／32 个真实独立声部 | `code/rtl/common/m3_n32_pro_candidate_20261017/`、`code/tb/audio/m3_n32_pro_candidate_20261017/`、`code/software/m3_n32_pro_candidate_20261017/`、`code/build/138k_polyphony_resource/m3_n32_pro_candidate_20261017/`、`code/docs/test/m3_n32_pro_candidate_20261017/` | **立即允许离线实现**：先核 `M3任务表_32复音独立候选实现与收口_2026-10-13.md` 的分配器/压力输入、`prom_candidate_20261013_01/`、历史 N32 输出隔离重放和失败物理报告的精确 SHA；继承有证据的功能，不重造分配器/ROM。补齐 N4→N8→N16→N32 事件到独立相位/频控/包络→逐样本 PCM/clipped/左右运输的同次证据、33音窃取、重触发、CC64、Release ACK、背压、取消/复位的严格负例。以实际48kHz与40MHz核下最短833拍逐请求账本核期限，给出32个同时活跃可闻独立振荡器的证据，不能把单波表谐波或过采样计作复音。再做**新 Pro** 目标资源、完整Setup/Hold与必要端点，最终在同一获准 `.fs` 的测试模式核32路不同频率谱峰及其独奏/混合原件；旧 PG484/pROM 的 Logic72583/Reg42321/BSRAM162与预布局Fmax6.109MHz仅是历史风险，不作Pro通过。 |

## E4 N32 自主推进细则

1. **先取字节而不是重写**：M3读 `code/rtl/common/m3_n32_allocator_candidate_20261013/`、`code/software/t061_n32_stress_plan_candidate_20261013/`、`code/build/138k_polyphony_resource/prom_candidate_20261013_01/`、`code/docs/evidence/m2_n32_output_transport_20261013/`，列原功能、输入/ROM/工具/报告 SHA、真实覆盖和失败史。不同封存冲突时停在差异，不从 DUT 波形反推黄金，也不把已有1300条隔离发布重放冒充生产实时N32。
2. **隔离联接与独立判据**：在 E4 新目录做 Pro 候选分配器＋32槽事件/音频/运输连接，针对四种规模同源向量和32全活跃纯音；显式记录每槽独立相位累加器、FCW、ADSR、source/channel/note/generation、PCM24/clipped和左右声道。独立控制日历得出每个接受/取消/发布的期望；checker要求每笔至多一次、无跨reset epoch、END无未闭事务。新组合负例必须以实际 RTL 行为拒收，不能仅改文本报告。
3. **代码试错与候选物理**：本包 Python/本机已核身份的模块仿真最多六轮有具体缺陷的实现—定向验证，成功即停、首失败永久保留。商用 Gowin Pro许可实际可用、精确FPG676器件版本/源ROM/独立候选CST-SDC/工具SHA冻结后，M3可在 E4 **隔离工程**自主进行至多两轮有界综合→PnR→完整Setup/Hold/Recovery/Removal（首轮及一次具体失败后修复，每轮≤1800s）；两轮共享唯一消费台账，失败不得重置包或换目录获得新额度。没有这些条件则只交构建预检，未运行写 NOT_RUN。结果仅为隔离物理，不是正式整机STA或生产 `.fs` 准入。
4. **板级交付**：只有 M2 完成正式同版音频链、引脚与完整时序并交精确 Pro `.fs`/恢复SHA，且 M3 核电平与本次 SRAM 授权后，才进行32音测试；禁止下载隔离 N32 候选码流到未知板。记录采样率/FFT窗口、32路不同频点逐音与同发、谱峰及对应RTL独立声部、混音/欠载/温升异常。谱峰的谐波/回声不计独立单元。未到这一步 `T061=PARTIAL`、`board_release_allowed=false`。

## 工具、发布与止损

- E1–E4 各自至多六轮新隔离代码/模块软件试错；实际编译/仿真工具版本（M3 的 ModelSim 2020.4 可按其真实身份记录）和次数按每包台账记录，不从旧 T052/R04/N32 一次许可挪用。E4 Pro候选物理的两轮是本单新增**条件授权**，不适用于其他包或正式整机。无板夜间只做离线；不为凑五小时重复已签 N32 小项或运行没有目标来源的工具。
- 每包每次交一页：实际文件、HEAD/输入/源ROM/工具 SHA、argv/cwd/时间上限、stdout/stderr、退出码、首失败、覆盖到的功能/资源/STA/实物等级及仍待字段。M3 可自审隔离成果，按最新 develop 串行跑 `code/scripts/check_repo.ps1` 九项全 PASS、逐文件暂存、末次 fetch 后取号与普通推送；与其他窗口共享 Git index、门禁、输出或同一工具额度时必须排队。当前是否能连远端由执行机当轮验证，未推送明确写出。
- 既定拓展**验收顺序**不因 E4 离线提前开工而改变。E1/E2/E3/E4 任一共享接口、ROM算法、正式时钟/约束或下载条件不符，停止该子项并转其他已授权独立包；没有可行动包则记录 `NO_ACTIONABLE_WORK`。M2 收原件后复核候选差异并决定受控正式接入，M1只在数学口径变化时签算法；用户确认私发前给M1/M2的回执一律标“待用户转发，尚未送达”。