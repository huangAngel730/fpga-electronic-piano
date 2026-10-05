# 138K 无新增周期结构实验（2026-10-05）

当前目录是新的隔离实验，不覆盖 `optimization_20261005/C_reset_route1`（Setup +0.025 ns 成功基线）或任何旧文档。正式仓库完全只读，不提交、不烧录。

## 新方法与依据

成功基线最差 Setup 路径是 `control_pending_28/Q → control_pending_4/CE`，约 25 个逻辑/ALU 单元，报告中 tINS 合计 10.145 ns、tNET 合计 8.107 ns、tC2Q 0.382 ns。原始路径表见 `baseline_path_analysis.json`。不能从寄存器余量推定加流水一定更快，也没有得到全芯片布线占用百分比。

- E：保持原有轮询优先树和载荷选择，只把动态索引的逐位回写改成 32 个固定槽位的并行 next-state。区别于此前 B：不加入优先树 one-hot 掩码、反向旋转或任何新寄存器。
- F：用绝对槽位的后半段 `[RR,31]` / 前半段 `[0,RR-1]` 两组优先树取得第一、第二候选，免去位图桶形旋转和 `RR + rank` 加法反馈；没有快照缓存或前馈流水寄存器。

两者各自从成功基线开始，不互相叠加，也不继承 A/B/C/D 失败结构。公共接口、解码、FIFO、计数块不变；事件、ready/valid、水位、计数均不延后一拍。FIFO 满队列同拍出入旁路保留。

## 测试覆盖修复（如实保留）

E 首轮 `functional/` 的随机逐拍正例通过，但“取消失效”负例也错误地通过，说明测试不够强。此轮停止在仿真阶段，未运行综合/PnR，未写通过的功能验收结论。

第一次补测 `functional_v2_directed/` 也保留为未放行记录：定向序列发完最后字节后在下降沿立刻复位，取消字节尚未被上升沿采样，仍没有检出取消失效负例。这是测试激励问题，不是 RTL 负例被允许通过，更不是物理构建失败。

正式补测在 `functional_v3_directed/` 独立保存，加入 CC1 已锁定 20 → 暂存 70 → 回到锁定 20 的定向序列，显式等待最后字节的上升沿和状态更新，再复位执行原随机压力测试；各配置还断言至少实际执行了一次锁定值取消。验收必须同时通过完整逐拍状态对照、故意错误版本检测、独立指令式参考模型和空/截断向量拒绝检查；不能只用随机正例放行。F 使用最终增强夹具。

`functional/functional_review.json` 在 E 仅是通过最终补测后的索引，记录 `actual_evidence_directory`，并不把前两轮未检出负例的运行伪称通过。

## 冻结与验收

47 项 GPRJ 输入 + 7 ROM + 2 include 共 56 个文件，非路径变更只能是 `sources/midi_event_parser.sv`。CST、SDC、布局/布线参数、器件配置与成功基线一致：Gowin V1.9.11.03 Education，GW5AST-LV138PG484AC1/I0，C，place=0，route=1，sys/pixel/serial=50/25/125 MHz，sys Setup/Hold uncertainty=1.000/0.550 ns。

每方法最多一次完整物理构建，1800 秒封顶。严格检查全部时钟域 Setup/Hold/TNS、Recovery/Removal、时钟/引脚、固定串行复位位置、14 个 CDC 第二级报告及存活总线约束路径；不能用退出码 0 代替时序收敛，不能把显示 `-0.000` 或非零违例端点当成 PASS。

旧工程、旧证据和 60K 指导文档共 992 个文件在 `preservation_before.json` 冻结，最终用 `preservation_verification.json` 对照。当前不更新正式仓库的看板/状态，因为用户明确禁止修改仓库。

## 实际结果

| 工程 | Setup / Hold（ns） | Setup / Hold 违例端点 | Logic / Register | 严格报告门禁 |
|---|---|---|---|---|
| 保留基线 C_reset_route1 | +0.025 / 0.000 | 0 / 0 | 19531 / 8674 | PASS |
| E_fixed_slot_next | +0.039 / 0.000 | 0 / 0 | 19183 / 8675 | PASS，小幅改善 |
| F_absolute_rr | +0.054 / -0.000 | 0 / 1 | 19013 / 8673 | FAIL，不采用 |

E 完整构建时间为北京时间 18:55:57 至 18:59:07，退出码 0。三个时钟域的 Setup/Hold TNS 均为 0；Recovery +1.138 ns，Removal +0.008 ns。SDC/CST/器件配置/PnR 参数及固定复位位置全一致。最差 Setup 已转到 `round_robin_index_1/Q → locked_event.control_value_7/D`；原来的待处理位图 CE 回写不再是全局最差路径。

E 的 Setup 改善只有 0.014 ns；逻辑减少 348，映射寄存器多 1。源代码没有新状态寄存器，逐拍验证证实没有事件延后一拍；不能把映射 FF 数变化等同于接口延迟变化。这个结果只是新的隔离候选，尚未达到 +0.5 ns 工程余量，不覆盖原成功工程，也不代表正式集成或上板通过。

F 完整构建时间为北京时间 18:59:37 至 19:02:45，退出码 0。Setup 虽提高到 +0.054 ns，但 sys_clk 有 1 个 Hold 违例端点，Hold 和 TNS 在报告精度下显示 `-0.000`，必须 FAIL，不能四舍五入为通过。违例为音高控制 LFO 的 `lfo_phase_5/Q → lfo_phase_6/D`。最差 Setup 已转移到 `slot_generation[0]_1/Q → lane[3] ADSR`，Recovery/Removal 为 +0.137/+0.017 ns。没有因候选造成的全局映射变化擅自修改音频模块。

结论：E 是本轮可保留的实测小幅改善候选，F 不采用。原 +0.025 成功基线及所有旧文档保持原样。两个候选各只有一次完整物理构建，未做参数/种子扫描；本轮通过证据审计不表示 F 时序通过。

E 最终增强正例四组各 256,205 拍通过；固定槽位指令式参考共 303,104 例通过；两个编译可运行错误版本在完整 miter 和提取结构探针中均被检出。F 增强正例也通过，独立线性轮询参考共 274,560 例通过，两种错误版本的探针被检出。两者均拒绝空/截断测试向量。报告检查器 23 项自检 PASS。

## 命令与当前阶段

运行环境使用已有独立 Python、Icarus、Gowin 副本，脚本不写仓库，不安装工具，不改系统 PATH。只对进程设置 TMP/TEMP。

```powershell
$python = 'C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$script = 'E:\FPGA\GAOYUNFPGA\138K_try\structural_trials_20261005\structural_trials.py'
# init 已执行，禁止重跑覆盖快照。
# E 首轮已留下记录，禁止再次 run E 覆盖实验目录。
# repair-E-coverage-v3 是最终一次性补测入口；已经完成，不能重跑覆盖证据。
& $python -B -X utf8 $script collect
& $python -B -X utf8 'E:\FPGA\GAOYUNFPGA\138K_try\structural_trials_20261005\verify_delivery.py' audit
```

最终结论以 `results.json` 及完整实际报告为准，两个物理实验均已完成。`verification_receipt.json` 是证据一致性审计；不覆盖 F 的 STA FAIL。本目录不提供任何 L6 或上板通过结论。`M2_无新增周期结构优化交接_待用户转发.md` 是待转发交接，没有直接通知 M2。

交付 ZIP 排除比特流、工具/可执行文件、仿真可执行镜像、大型 `.pr` 数据库和临时目录；保留候选源码、完整冻结输入、约束/工程/Tcl、功能日志与夹具/向量、实际 PnR 报告、哈希和失败夹具历史。归档 CRC 及逐成员 SHA 校验见 `archive_receipt.json`。
