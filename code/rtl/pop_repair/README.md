# 拍频听感修复隔离原型

结论：本目录提供一个**不改音高、不丢相邻音、不降低四声部数量**的候选修复。它保留 32 位 FCW、48 kHz、16 位波形、Q15 包络、32 位混音和 PCM24 输出语义，将每声部原来的 1024×16 单正弦 ROM 改为相同总字数的四组 256 点分音区波表，并利用已有 `note_on`、`velocity` 在起音阶段临时选择更明亮的波表。

这不是“消除物理拍频”。例如 C4 与 C#4 的频差仍是约 15.557 Hz；修复目标是降低纯正弦基频对的支配程度和规则起伏的突兀感，同时增加短促的钢琴化谐波起音。它也不承诺达到真实钢琴采样音色。

## V2 候选（2026-10-01）

用户已经上板确认 V1 相比原纯正弦“好多了”。V2 在**保留 V1 全部文件和位流**的前提下，
进一步加入各声部高次谐波 0/π 相位去相关、10/7/5/1 分音区谱形，以及每声部相差
1 ms 的谐波起音衰减。基频的相位和 FCW 不变，不能把本方案理解为 detune、丢音或把
两个音调成同频。

- V2 详细说明：`output/v2/README.md`
- V2 模型报告：`output/v2/validation_v2.json`
- V2 构建报告：`output/v2/build_validation_v2.json`
- V2 位流：`output/v2/bitstream/electronic_piano_pop_repair_v2_4voice_54774f1_20261001.fs`
- V2 SHA-256：`B12120E53FCEE5A2A48229245F4EA608CE3B7B5B96E0D5935B75FC7446CD1E8D`

V2 相对 V1 的 C4+C#4 块 RMS 包络调制度再下降 19.4%；六组相邻音区的中位下降
19.0%，四声部测试下降 10.6%～11.0%。Gowin V2 完整流程达到 L5：50 MHz 下
Fmax 50.218 MHz，建立/保持最差裕量分别为 +0.087/+0.001 ns，均无违例。

## 隔离边界和来源

- 原仓库：`E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano`
- 本原型：`E:\FPGA\GAOYUNFPGA\pop_repair`
- 读取并留档逻辑副本的源提交：`54774f1016c6314e6af024f44db7a9abc394c3f4`（短名 `54774f1`，也是本次四声部正式配置的源码基线）
- 原仓库在本任务中只读；未修改文件、索引、分支、提交或工作树状态。
- 详细来源、码流路径和 SHA-256 见 `reference/SOURCE_MANIFEST.txt`。

`reference/original_54774f1/` 只保留了直接用于分析和对照的两个源文件：

- `code/rtl/audio/dds_oscillator.sv` → `reference/original_54774f1/dds_oscillator.sv`
- `code/rtl/board/polyphonic_envelope_bank.sv` → `reference/original_54774f1/polyphonic_envelope_bank.sv`

为了实际生成可烧写候选，另用 `git archive 54774f1` 在
`build/source/` 建立了一份隔离构建树；它不属于原仓库工作树。候选只在该构建树内替换
波形振荡器/波表接入，并在隔离 `.gprj` 中加入新源。顶层、器件、CST、SDC、50 MHz、
48 kHz、PT8211/I2S 链路和 MIDI R17 引脚均沿用该提交的正式四声部配置。

根目录的独立 RTL 自检边界是 `piano_dds_oscillator.sv`；实际位流则由
`build/source/code/build/electronic_piano.gprj` 的完整隔离顶层生成。

## 原型改动

### `rtl/audio/piano_dds_oscillator.sv`

- 基频相位仍严格执行 `phase_acc += fcw`，没有 detune。
- ROM 总规模仍为 1024×16：四组 256 点表分别含 8、5、3、1 个整数倍谐波。
- 按 FCW 分区选择允许的最大谐波数；MIDI 21..108 最坏起音谐波约 14.80 kHz，低于 24 kHz Nyquist。
- 轻力度使用柔和 body；中/重力度在 10/20/30 ms 起音窗内选择更亮的一组，之后自动回到 body。
- 起音到 body 的波表切换延迟到 DDS 相位回绕点；所有正弦级数表在该处共同过零，避免在任意相位硬切产生阶跃。
- 没有新增乘法器；新增逻辑主要是每声部一个 11 位计数器、比较器、2 位波表状态和 ROM 地址选择。

### `rtl/board/polyphonic_envelope_bank.sv`

- 基于 `54774f1` 的同名模块复制。
- 外部端口不变；只把内部 `dds_oscillator` 换成 `piano_dds_oscillator`，并接入该槽已有的 `slot_note_on` 与 `slot_velocity`。
- ADSR、事件路由、独立 Release、四路快照和握手状态机不变。

### 模型、表和自检

- `model/generate_wavetable.py`：从明确的谐波系数重建 1024 字 ROM。
- `model/generated/wavetables/piano_band_4x256_8191.mem`：已生成的有符号 16 位十六进制 ROM，峰值限定为 -8192..8191，符合正式 v1.5 波形幅度口径。
- `model/validate_prototype.py`：无第三方依赖的定点近似模型，覆盖复位、音高、四声部、独立释放、力度、相邻音、边界音高和削波/位宽；同时生成前后 WAV 和 JSON。
- `tb/tb_piano_dds_oscillator.sv`：检查复位、力度起音时长、分区选择、FCW 累加无失谐。
- `scripts/run_tests.ps1`：统一运行生成、Python 验收；检测到 `iverilog/vvp` 时再运行 RTL 自检。

## 运行方法

在 PowerShell 中执行：

```powershell
Set-Location E:\FPGA\GAOYUNFPGA\pop_repair
.\scripts\run_tests.ps1
```

也可只运行模型：

```powershell
python .\model\generate_wavetable.py
python .\model\validate_prototype.py --output .\output
```

成功后应得到：

- `output/validation_report.json`
- `output/adjacent_c4_cs4_baseline.wav`
- `output/adjacent_c4_cs4_repaired.wav`
- `output/build_validation.json`
- `output/bitstream/electronic_piano_pop_repair_4voice_54774f1_20261001.fs`
- 若本机有 Icarus Verilog：`PASS: tb_piano_dds_oscillator`

试听时请先降低音量。对比重点是 C4+C#4 的规则涨落是否不再像两路纯正弦那样突兀，以及重力度起音是否更清楚；不要期待拍频完全消失。

## 已执行验证

本次实际执行等级如下，未把上板结果混入工具验证结论：

- Python 波表生成与定点验收模型：实际运行，8 项全部 PASS；WAV 与
  `output/validation_report.json` 已刷新。
- RTL 语法/综合检查：GowinSynthesis 实际运行，完整顶层综合通过；四路候选波表均推断为 pROM。
- RTL 动态仿真：未执行；本机未找到 `iverilog/vvp`。自检 testbench 已保存，但本次不能宣称仿真通过。
- Gowin 布局布线：实际运行，退出码 0；placement、routing、timing analysis、bitstream generation 全部完成。
- 时序：50 MHz 约束下建立/保持违例端点均为 0，TNS 均为 0；实际 Fmax 51.414 MHz。
- 上板：未执行；按任务边界只交付 `.fs`，由主对话进行 SRAM 下载和 A/B 试听。

按项目等级口径，本次厂商流程达到 **L5（布局布线和时序收敛）**；Python 模型证据为
L3。由于缺少 `iverilog/vvp`，独立 RTL 动态自检的 L2 证据为空，不能把 L5 误读为
“所有较低层测试都已执行”。

主要量化结果：

| 检查 | 结果 |
|---|---:|
| MIDI 21..108 最大 FCW 音高误差 | 0.000246 cent |
| 重/轻力度 RMS 比 | 2.332 |
| 最坏起音最高谐波 | 14.800 kHz < 24 kHz |
| 四声部理论最大 PCM24 和 | 8,386,560 < 8,388,607 |
| C4+C#4 基频对支配度 | 0.4908 → 0.3615（下降 26.34%） |
| C4+C#4 块 RMS 包络调制度 | 0.5058 → 0.3323 |
| C4+C#4 物理拍频 | 15.557 Hz，仍保留 |

这里的“支配度”和“包络调制度”是比较指标，不等同于主观听感评分；最终结论必须以上板 A/B 试听为准。

## Gowin 结果与可烧写文件

- 工具：Gowin V1.9.11.03 Education。
- 器件：`GW5AT-LV60PG484AC1/I0`，Device Version B。
- PnR 资源：Logic 5033/59904（9%）、Register 2637/60780（5%）、BSRAM 8/118（7%，8 个 pROM）、DSP 24/118（21%）。
- 最差建立裕量：`+0.550 ns`；最差保持裕量：`+0.001 ns`；TNS 均为 0。
- 可烧写文件：`output/bitstream/electronic_piano_pop_repair_4voice_54774f1_20261001.fs`
- SHA-256：`BB090B3833A057A86F3AFFA4FEE470743BFB1C589187F44BE50394E536D33590`
- 详细报告：`build/source/code/build/impl/pnr/electronic_piano.rpt.txt` 和
  `build/source/code/build/impl/pnr/electronic_piano_tr_content.html`。

回退码流保持不变：
`E:\FPGA\GAOYUNFPGA\T024_T025_4voice_STAT_54774f1_20260930\electronic_piano_4voice_stat_precompute_20260930.fs`，
SHA-256 `DEAD6E1C913F4BFDC807A7945B8654F51BE453D3531E674537AE3A2E89BF4321`。

## 资源、时序和集成限制

- 时序虽然收敛，但最差保持裕量只有 `+0.001 ns`；下载前后都应保留原码流，板测若出现偶发异常立即回退。
- PnR 有一条基线时钟网络警告 `PR1014`：约束指定的 `sys_clk_d` 使用通用布线资源，可能带来额外延迟或偏斜。报告仍显示零违例，但正式合并前应由集成负责人复核该约束。
- 256 点相位地址比原 1024 点更粗；新增谐波会掩蔽一部分量化失真，但仍须测 THD/噪声和试听。
- FCW 比较和表选择位于 ROM 地址前。ROM 仍为单周期同步读，接口延迟未改；STA 已通过，但动态 RTL 仿真尚未执行。
- 当前模型用单调平方根近似复刻力度增益趋势，不代替正式 `velocity_gain_rom.mem` 的逐样本金标准；合并前必须接正式 ROM 重跑逐样本比较。
- WAV 是模型输出，不等同于 FPGA 上 PT8211 的模拟输出；最终判断仍需低音量、分阶段的上板 A/B 试听。

## 若后续合回正式仓库

预计会涉及：

- 新增 `code/rtl/audio/piano_dds_oscillator.sv`
- 修改 `code/rtl/board/polyphonic_envelope_bank.sv`
- 新增 `code/model/generated/wavetables/piano_band_4x256_8191.mem` 及生成脚本/黄金模型
- 新增对应 `code/tb/` 与 `code/scripts/` 回归
- 将新源和 ROM加入实际 Gowin 工程文件（具体文件需先从当前工程核对，不能猜）

`polyphonic_envelope_bank.sv` 位于 M2 的板级/集成责任域。虽然本原型不改变正式公共端口，正式合并前仍应先向 M2 说明：ROM 组织、每声部新增状态、ROM 推断风险、地址路径时序、逐样本验收方案和回退到纯正弦的办法。若最终还需改 `electronic_piano_top.sv`、`audio_defs_pkg.sv`、CST 或《模块接口规范》，它们属于接口组共享文件，必须按项目规则提前在群里说明；本原型没有改这些文件，也没有代用户通知 M2。

