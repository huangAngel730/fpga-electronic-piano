# 138K 后续优化实测记录（2026-10-05）

结论：本轮实际执行了两种内部结构优化，均通过功能验证并完成整机综合、布局布线，但均未通过严格物理验收。因此不替换原成功工程，当前保留的通过方案仍是 `optimization_20261005/C_reset_route1`（Setup +0.025 ns）。本文件是新增独立实验记录，不修改原成功工程、旧文档或正式仓库。

## 基线与边界

- 两个试验分别从原成功 `C_reset_route1` 复制，B 不继承 A 的 RTL 或生成结果。
- 完整 V0171 四音复音音频＋HDMI 工程，47 个 GPRJ 项、56 个实体输入。
- 器件 GW5AST-LV138PG484AC1/I0、版本 C；Gowin V1.9.11.03 Education。
- 保留此前 138K PLL 适配、电气迁移及串行复位 FF 固定位置 R44C168[1][A/B]。
- 每轮仅替换隔离副本的 `sources/midi_event_parser.sv`。其余 55 个输入归一化工程绝对路径后与成功基线一致。没有改 top、公共包、ADSR、可视化、STAT、公共 FIFO、约束或电压。
- CST、SDC 原字节不变；place=0、route=1、correct_hold=1 等实际 PnR 选项全部与成功基线相同。维持 50/25/125 MHz、sys Setup uncertainty 1.000 ns / Hold uncertainty 0.550 ns，不加宽泛 false path。
- 没有延后 ready/valid、事件、计数、水位；没有取消 FIFO 满队列同拍出队旁路。
- 正式仓库只读：没有更新 Git、提交、推送或运行会向正式仓库写输出的 check_repo.ps1。没有下载 SRAM 或写 Flash。
- `preservation_before.json` 与最终复核对旧实验及旧 60K 指导文档共 385 个文件进行 SHA-256 比较：没有改动、新增或删除旧目录文件。

## 实际整机结果

| 工程 | Setup ns | Hold ns | Hold 违例端点 | Recovery ns | Removal ns | Logic | Register | 严格验收 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 保留的成功基线 | +0.025 | 0.000 | 0 | +0.873 | +0.008 | 19531 | 8674 | PASS |
| A 提前计算／寄存候选并当拍修正 | +0.026 | −0.000 | 1 | +1.132 | 0.000 | 19299 | 8707 | FAIL，不采用 |
| B 并行 one-hot 掩码更新 pending | +0.005 | −0.093 | 4 | +1.306 | +0.039 | 19655 | 8672 | FAIL，不采用 |

三者 DSP=46、BSRAM=20。A 比基线少 232 Logic、多 33 个物理 Register；B 多 124 Logic、少 2 个物理 Register。Setup 违例端点三者均为 0。

A 的 Hold TNS 原报告显示 −0.000，但仍有 1 个真实违例端点。不能把舍入后的负零当作 PASS。B 的 sys Hold TNS=−0.105 ns，有 4 个违例端点。两次 Gowin CLI 返回均为 0，均实际完成综合、PnR、STA、码流生成和功耗报告；CLI 成功不代表时序通过。

实际构建时间（Asia/Shanghai）：

- A：16:12:01.819 → 16:15:00.568。
- B：16:17:30.145 → 16:21:50.847。

## 为什么试这些方法

成功基线使用 8674/139095 个 Register（约 6.2%，报告向上显示 7%）和 19531/138240 个 Logic（约 14.1%，报告显示 15%）。这是试内部寄存器／组合结构优化的依据，但报告没有给出整体 wire routing utilization，不能声称“布线利用率很低”。

A 使用仓库已有的隔离 `midi_prepared_candidate`，不是在正式 parser 上落地。其源 SHA-256：`c57b1a9866365527369ee415a3d96ed1929124c8a4e38b0d998b1a3418f17cdb`。增加 40 个声明状态位，综合后净增 33 个物理 FF：提前保存前三个 RR 候选，通过上一拍变更修正及当前 MIDI 字节的当拍修正保持公开接口逐拍一致。它不是直接在输出链插一拍。此候选以前在 60K 上没有采用；本轮是独立的 138K 实际验证，不能沿用 60K 的成绩。

B 使用已有隔离 `midi_pending_mask_candidate`，源 SHA-256：`5bc457af0ba0750be3a062eedc6cfb24e82e29212e24872bf810336f34391798`。保持原 RR 排名和 payload，增加组合 one-hot 掩码，逐 bit 并行计算 pending next-state，无新增流水拍。

两者基线 parser SHA-256 均为 `834887a990a4866d54669c5f18588a0b799aa4c08ccb27c91a2f9e5609f331c6`。所有原始源、路径迁移和散列见各工程的 `input_manifest.json`。

## 实际功能验证

A：

- 全 parser 四配置逐拍 miter，各 256193 拍；FIFO 深度 1/8/16/3，离散 burst 包含 1/8/16。
- 对照全部公开输出，包括 ready/valid 下的事件稳定性、FIFO 水位、高水位、溢出与解析错误计数；同时比较原有 scheduler 寄存状态。
- reset、错误字节、随机 MIDI、反压、控制合并、仲裁及复位后运行覆盖；通过非空事件／控制事件／反压计数防止假绿。
- 33 项定向检查覆盖连续撤销、第三候选回退、插入优先级和复位清空。
- 两个全 parser 错误变体及一个定向错误变体均先编译成功、再被行为检查拒绝，不能用语法错误冒充负例。

B：

- 相同四配置逐拍 miter，各 256193 拍，公开输出及原有 scheduler 状态一致。
- 实际组合逻辑切片对独立线性 Python 参考：399360 组 mask/grant/pending_next 场景通过。
- 错同拍清除、错旋转均编译成功后被行为比较拒绝；空向量和截断向量均被覆盖数检查拒绝。

日志位于各工程的 `functional/`，source/runner provenance 和实际退出码已保留。Icarus 的 constant-select 全敏感集提示保留在日志中；没有忽略运行 FAIL。

## 物理验证与局限

离线报告门禁自检共 23 项全部通过。门禁从真实 HTML 解析全局与分时钟 Setup/Hold、违例数、TNS、Recovery/Removal、最小脉宽、14 条 CDC 第二级 Setup/Hold、冻结后存活 payload 路径 23/50、端口及电气引脚、器件、tool、实际 cmd.do 和 device.cfg。这不等于原始 CDC 总线每一个 bit 都被报告覆盖。

A 的最差 Setup 已从原 pending→CE 转移到：

`u_events/slot_generation[0]_5_s0/Q` → `g_lane[0].u_envelope/n711_s0/B[20]`。

A 的最差 Hold 在 lane0 DDS phase accumulator → ROM address。B 的最差 Setup 在 parser RR → locked event payload，最差 Hold 在 visual diag_frame_cycles。说明缩短一个模块的链后，整机瓶颈可能转移，且布局扰动可能破坏其他模块的 Hold；不能只看寄存器数量或单个 Setup 数字。本轮没有改这些其他模块来掩盖问题。

PR1014 的 sys_clk_d 通用布线告警仍存在。原成功版也只有 +0.025 ns Setup、0.000 ns Hold，并未取得 +0.5 ns Setup 工程余量。138K PLL 并非本轮 GUI 新生成，实际锁定、启动、电气、音频和显示均没有上板验证。

本轮等级：功能验证通过、综合通过、PnR 完成，但 A/B 严格时序失败，不得记为新 L5 PASS，更不是 L6。保留原基线的既有离线 L5 结论，不扩大为硬件验收。

## 查看／复核

Python：`C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`。

已执行的独立入口：`experiment.py start`（A）、`parallel_mask.py start`（B）、`assess.py --selftest`、`assess.py A_prepared_selector B_parallel_pending_mask`。构建入口禁止覆盖已有试验目录，不要直接重复 start。

可只读重查 STA：在本目录运行 `python -B -X utf8 assess.py A_prepared_selector B_parallel_pending_mask`（只更新本独立目录的汇总，不修改旧成功证据）。`experiment.py preserve-check` 重查旧文件 SHA。交付校验和压缩包 CRC／成员 SHA 见 `verification_receipt.json`、`archive_receipt.json`。

下一步优先根据真实新关键路径设计能保持逐拍行为的局部优化；不要为“有余量”盲目延迟输出，不要混入 M2 未冻结的新 ADSR／新闪光工程。这两种候选保持不采用，后续另开目录。
