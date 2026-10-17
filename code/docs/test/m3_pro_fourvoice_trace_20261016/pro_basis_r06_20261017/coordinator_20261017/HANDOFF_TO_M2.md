# M3 R06 Pro 四声基础软件准备汇合交接

## 结论

- 实现冻结基线：`42d28c4ad8250b9064099da4742fbde12a254444`。
- 发布前已快进到 `8b92d9cfa07e69d5bb2ce1eefef9d3355ceac1f0` 并复核新到件。
- M3-R6-1 至 M3-R6-7 已完成各自授权范围内的软件、静态或资料准备，并完成实现窗口自审。
- 实际等级最高为软件 L1；没有运行新的 HDL 编译、RTL 仿真、Gowin、ModelSim、下载或板卡操作。
- M3-R6-8 未开始。它仍依赖真实硬件身份、M2 的正式 Pro 物理放行、唯一 `.fs` 及精确一次 SRAM 准入。
- 因此 Pro 四声基础整体仍为 `PARTIAL`，`board_release_allowed=false`，不能据本交付下载或放行码流。

## 七包结果

| 包 | 本轮结果 | 实际等级 | 仍缺内容 |
| --- | --- | --- | --- |
| M3-R6-1 `source_target_audit` | 软件工具自测通过；冻结包实审仍拒收：`polyphonic_envelope_bank.sv` 实例化 `dds_oscillator`，但原 `compile.f` 未列 `dds_oscillator.sv` | L1 工具；实际冻结闭包 L0/REJECTED | M2 决定精确 source list；补真实 Part/version/板修订/Bank/PLL |
| M3-R6-2 `midi_stimulus` | 13 个正例、4 个负例通过；63 字节、23 事件；覆盖四独奏、四音保持/逐放、重触发、第五键边界、running status、reset、背压 | L1 软件/纯文件；SV driver 仅 L0 未编译 | M1 slot/释放/generation/第五声语义与真实公开端口 |
| M3-R6-3 `normalized_intake` | 用户批准新增修复额度后，RUN_03 15/15；D3 `CANCEL` 正确使用活动 `req_id`，不再把 `cancel_reason` 当请求号；旧失败与旧轮保留 | L1 合成软件 | 真实 Pro canonical61 输入 |
| M3-R6-4 `tool_plan_adapter` | 7/7 软件夹具通过；覆盖绑定、错误输入、越权工具、输出冲突、并发原子消费、首失败/原始流/Windows job | L1 软件夹具 | M2 精确真实执行准入；本包不授权真实工具 |
| M3-R6-5 `event_calendar` | RUN_02 14/14 符合冻结预期：1 合成正例、3 PENDING、10 负例拒收 | L1 合成软件 | M1 事件语义、M2 同沿优先级/完整 frame plan、真实公开 trace |
| M3-R6-6 `tx_clock_reset_checker` | RUN_01 20/20：1 合成正例、7 PENDING、12 负例拒收；覆盖 startup/HOLD/TX adoption/833边界/串行/复位/finish | L1 合成软件 | M2 同版 TX sidecar、公开 pins、真实时基和 finish/frame plan；M3-R6-5 真实 ledger；M1 PCM24/clip oracle |
| M3-R6-7 `hardware_identity` | validator 17/17；保留首轮 wrapper 路径失败；生产记录仅 `VALID_PENDING` | L1 软件 validator；真实物理 L0/PENDING | 实物完整料号、板修订、Bank/MIDI/PA/PT8211/PLL 原件 |

## 关键身份与原件

- R6-1 完整包：`M3_R6_1_SOURCE_TARGET_AUDIT_20261017.zip`，SHA-256 `2616fe325821ad5e9ca6762d8c32177abaab15f0c887d01f6c0cce90a9296697`。
- R6-4 完整包：`M3_R6_4_TOOL_PLAN_ADAPTER_L1_20261017.zip`，SHA-256 `1a501d76271f1751722de464b7c0eedd223d76d4595f7fe98290a5b8182b3d7c`。
- R6-7 完整包：`M3_R6_7_HARDWARE_IDENTITY_20261017.zip`，SHA-256 `da4238bfafa39efa8c562285d3cf9d3657207e335175a399a350cb3403f15d6b`。
- R6-3 最终收据 SHA-256：`7a2ec030...fedd56bb`；完整值见包内 `RUN_03` 与 `KEY_HASHES.json`。
- R6-5 最终收据 SHA-256：`9456645c...6112af`；完整值见包内结果文件。
- R6-6 收据 SHA-256：`14ebadc4d24e1bcd1f6cd855df0c9fb8ed20e048315930bff027b2c9d8228904`。
- 本目录的 `M3_R06_EVIDENCE_BUNDLE_20261017.zip` 保存七包展开原始证据；其完整 SHA 写入同目录 `PACKAGE_STATUS.json`。
- 发布门禁前对 14 个文本文件仅删除了一个多余末尾 LF；修改前后 SHA、字节数及“不重跑”边界见 `POST_SEAL_WHITESPACE_NORMALIZATION.json`。压缩原件保持原字节不变。

## 请求 M2 决定/提供

1. 决定 `dds_oscillator.sv` 是否应加入正式 `compile.f`，或给出替代的精确源闭包；M3 不擅自改正式工程。
2. 冻结 M1/M2 权威语义与公开观察合同：事件应用沿、slot/generation/释放、同沿优先级、完整 frame plan、真实 finish、TX adoption sidecar、公开 pins 和时基。
3. 在上述输入齐套后，决定是否签发一次精确真实工具/完整链执行准入；软件适配器通过不等于真实执行获准。
4. 提供并复核真实 Pro 器件/板修订/Bank/PLL/电气身份；之后再决定 M2-R6-4 物理放行。
5. 只有正式 `.fs`、SHA、恢复版本与一次 SRAM 准入齐套后，M3 才开始 R6-8 同会话板测。

## 发布前新到件复核

- `8b92d9cf` 新增的 M2 `r06_observer_20261017` 明确是 `PARTIAL_CANDIDATE_PENDING_M1_AND_PUBLIC_EXPORT`：61 字段中仍有 13 项未实现、19 项待 M1 语义、9 项待 M2 受控路由；没有真实公开端口或 TX 旁带。
- 同次新增的 M1 `pro_successor_20261016` 是合成向量和比较入口准备，`FINAL_RECEIPT.json` 仍列真实 Pro/M3 原件、真实同跑 PCM/ID/clip 与真实日历缺失。
- 因此这些新材料没有把 R6-5/R6-6 的真实输入 PENDING 改为 PASS，也不产生额外软件、HDL、EDA 或板卡运行许可；本轮不消耗新的执行轮次。

## 边界

- 所有成功结论均限制在对应合成软件夹具或静态资料范围。
- 没有把缺件 `PENDING` 写成通过；没有用历史工具身份或历史码流替代本轮真实结果。
- 没有修改正式顶层、CST、SDC、公共接口、任务看板或当前状态。
- 审核制度本轮未启用；当前只有实现窗口自审，仍待 M2 最终复核。

状态：**待用户转发，尚未送达**。
