# M3 task-day2 R07 五窗口执行单（2026-10-17）

当前基线：4fd3366e42fd2356e56eb96eee70b6771afd4bb1，开工 fetch 核同 origin/develop。
输入：用户 task-day2/FORWARD_M1_M3.md；仓库 R07 任务单及未覆盖 R06 合同。最高优先级为 Pro 四声基础；不启动 E/N32。
时间盒：2026-10-17 18:55 至 22:55（最多四小时，准备完成或授权耗尽即提前收口，不为凑时间重跑）。用户未提供本轮实物条件，硬件可用性 UNKNOWN；只执行离线准备。ModelSim 版本可用不等于新仿真许可。

## 独占分工

- 夜间任务1：总控、基线/原件/消费核验、跨包接口只读检查、最终封存和串行 Git；独占本 coordinator 子目录。
- 夜间任务2：R7-A public_capture_tb，先复用已交 R6-2 driver，再实现唯一公开采集 TB/observer、schema与新合成检查。
- 夜间任务3：R7-B public_equivalence_tb 完成后串行继续 R7-D capture_provenance；D 下 coordinator 和 dependency_audit 保留给总控及夜间5。
- 夜间任务4：R7-C oracle_bundle_bridge，复用 R6-2/3/5 原件，保留 unsupported profile 差额，数学不代做。
- 夜间任务5：只读审查 R06 消费/到件差额及 R07 新包关键接口；只写 D/dependency_audit 报告，不写实现、不运行测试。发现具体阻断一次回传，不启用审核员/预审员。

三名实现写者同时最多为夜间2/3/4。每名可使用自己的只读子智能体自审，不增加实现写者。三个允许根为 code/software/m3_pro_fourvoice_trace_20261016、code/tb/board/m3_pro_fourvoice_trace_20261016、code/docs/test/m3_pro_fourvoice_trace_20261016，其下仅 pro_basis_r07_20261017/四个指定目录。R06、M1、M2及正式接口源均只读；共享状态/看板不改。

## 共享消费规则

R6-1至7已在 ffc8b4cc 交付准备成果，现有 RUN/修复消费全部保留，不恢复；R6-8缺实物/新.fs/物理及精确SRAM许可，仍阻断。
R7-A/B/C/D各唯一初组 <=90 秒；新缺陷仅一次 <=60 秒定向增量，不全量复跑。每包写 RUN_SPEC、原输入/源码/依赖 SHA 后消费，独占 RUN_01/RUN_02，所有首失败保留；所有执行写原 argv/cwd/UTC/双流/退出码/耗时。无新断言不消费。全局 HDL/ModelSim/Gowin/设备新轮次为0；仓库九项发布门禁单列。
每个包 RESULT/RECEIPT 须写真实消费、文件清单/身份、正负例、L0/L1、缺件和下一责任。软件测试只签工具夹具，真实 capture/M1语义/M2准入未到仍 PENDING；board_release_allowed=false。不得以旧R02补丁或D3旧组替代新合同。

## 跨包接口与通信

所有包以已发布 M2 CAPTURE_CONTRACT/NORMALIZED_ROW_SCHEMA/OBSERVER_EXPORTS_R06C3/SOURCE_REPLACEMENTS 为合同出处；R6-5唯一生成独立 FRAME_PLAN，R6-6只读核验。A不生成第二份期望帧计划，B不窥读旧top私有层级，C不反填期望/丢弃HOLD或F-A，D不自报approved/authenticated。
派工一次、必要阻断一次、完成一次；可直接回传夜间任务1（01a14050-cd98-7c41-8004-5d3e25765167），这是本轮用户明确授权。若平台仍拒绝回传，保留拒绝回执并以本地 RESULT/RECEIPT 等待总控读取，不换工具绕过。
成员不 fetch/merge/add/commit/push。总控在全部当前可执行工作完成或确需 M2 准入时集中核身份/自审/门禁/普通发布；最终给用户 M2 转发文字及原件包，不能把准备完成写成 G0–G3或整机通过。

## 只读核对后续接（同一写者串行，不增加额度）

夜间5确认 R6-5 公式生成器与 R6-8 Pro 离线准备确实尚缺。夜间4完成 C 后，在 R06 原有独占包目录串行补 R6-5 的新文件式生成器/未执行自检候选（不改旧已签源码或重跑旧组），并补 R6-8 的无设备步骤/格式与禁止下载门槛。R6-5 新软件执行预算已耗尽，因此这一新增源码仅 L0，测试 NOT_RUN，交 M2 绑定后续增量；R6-8 不消费设备/软件组，仅准备文件。其他窗口不得写上述增量，总控封存时显式列入，不借 R07 四包预算跑 R06。

## M2 V0396/C5 到件后的有界返修

发布前 fetch 到 M2 最新回执并快进至 40d78131e8ed50643dd169816f7bfc7149a8ced9。原开工快照保留；另存远端变更及发布基线，不把 M2 的合法新提交误认作本轮改写。

- 夜间2冻结 A 后，在 R6-4 原包新增 r07_fix 候选，修消费端 spec→plan 安全字段重建和执行前限定。先核台账，再用原 R06 尚未消费的一次 <=60 秒定向修复组；不恢复旧七类、不升级真实工具执行器。同时只做 A 对 C5 源清单的静态绑定。
- 夜间3冻结 B/D 后，在 R6-6 原包新增 r07_fix 候选，修 F/A 期限、独立 FRAME_PLAN、C3 profile 和 REAL 来源判定。先核台账，再用原 R06 尚未消费的一次 <=60 秒定向修复组。B 的 C5 绑定仅静态，不恢复 B 已耗尽的额度。
- 夜间4完成 R6-5 生成器和 R6-8 准备后，在 R6-3/R6-5 原包新增 r07_fix 候选，修 null/HOLD/raw cancel/F-A 等，只有 L0 和 NOT_RUN 用例；原额度已尽，不执行功能测试。
- 夜间5和总控继续只读交叉核对；同时仍只有夜间2/3/4三名实现写者。旧源码/旧失败/已消费许可不变，新的受控接口、真实HDL、EDA、设备准入均未获得。

C5 已给出71源/9ROM的限定仿真源闭包，DDS 派生首模块由 M2 定义，不再把源清单决定写成待定；该决定仍不是实际编译或准入。
