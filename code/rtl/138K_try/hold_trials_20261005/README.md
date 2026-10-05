# 138K Hold 修复交付（2026-10-05）

结论：以 H 的 Setup +1.522 ns 为基线，保持系统/像素/串行时钟 40/25/125 MHz，不改 RTL，只调整两个现有内部寄存器位置，I、L 均实际完成综合、布局布线和 STA，Setup +1.279 ns、Hold 违例端点 0。推荐 L 的加严 Hold guardband 方案，同时完整保留 I 的原约束成功版本。未烧录、未上板，非 L6。

本轮唯一写入范围为 `E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/rtl/138K_try/hold_trials_20261005`。没有修改正式工程、共享文档、旧基线或旧指导文档；没有 Git 提交/推送。状态与交接记录只放在这里，避免违反用户仅允许实验目录修改的要求。

## 实际比较

单位 ns；下表的最差值来自各候选自己的完整 STA，不能把不同布线的路径值直接混用。

| 候选 | 全局 Setup | 全局 Hold | Hold 违例端点 | 系统同域 Hold uncertainty | 原违例短路径 Hold |
| --- | ---: | ---: | ---: | ---: | ---: |
| H 基线（只读） | +1.522 | -0.000（显示精度） | 1 | 0.550 | -0.000 |
| I：仅内部位置修复 | +1.279 | 0.000 | 0 | 0.550 | +0.060 |
| L：同样位置、额外加严 | +1.279 | 0.000 | 0 | 0.650 | +0.018 |

Setup 比 H 减少 0.243 ns，但比用户最低 +0.5 ns 门槛仍多 0.779 ns。H 的 `-0.000` 不能按四舍五入当作通过：其报告明确有 1 个 Hold 违例端点。I/L 的通过依据同时包括全部违例端点为 0、全部时钟 Setup/Hold TNS 为 0，以及完整路径/复位/脉宽检查，而非只看摘要数字。

L 的 0.650 ns 比原 0.550 ns **严格 0.100 ns**，不是放宽约束。它为系统同域施加额外保守要求，但报告在加严要求下的全局 Hold 最差值仍是 0.000 ns；不能写成“实测全局 Hold +0.100 ns”。本轮没有对同一 L 布线再用原 0.550 ns 单独跑 STA，跨域路径也不能据此统一加 0.1。若硬性要求最终报告中全局 Hold 显示正数，本次尚未达到该更高目标。

L 各域最差 Setup/Hold：系统 +1.279/0.000；像素 +10.303/+0.275；串行 +6.884/+0.466。Recovery +0.706、Removal +0.331、最小脉宽余量 +1.825；7 条 CDC 第二级各自保留并检查，不切掉整个 CDC 总线。

## 修改内容与原理

每个候选共 56 个冻结输入（47 工程输入、7 ROM、2 头文件）。相对于 H，归一化必要的副本路径后，内容变化仅两份约束：

1. `constraints/audio_visual.cst`：追加两条内部 `INS_LOC`，固定发射寄存器，将捕获寄存器从相邻位置移远。
2. `constraints/audio_visual_hold055.sdc`：追加原短路径的 Setup/Hold 诊断报告。I 不改变任何时序约束；L 另将系统同域 Hold uncertainty 0.550 加严到 0.650。文件名沿用基线，不代表 L 仍采用 0.550。

```tcl
INS_LOC "g_polyphonic.u_audio_core/u_bank/u_pitch_mod/g_lane[2].u_control/base_s1_18_s0" R83C99[1][B];
INS_LOC "g_polyphonic.u_audio_core/u_bank/u_pitch_mod/g_lane[2].u_control/base_s2_18_s0" R87C101[0][A];
```

H 捕获位置是 `R84C99[0][A]`。新位置已从实际时序路径的器件位置列读回确认，不能只凭 CST 文本认定生效。原短路径的数据延迟：H 0.554 ns、I 0.634 ns、L 0.692 ns；I/L 时钟偏斜为 -0.011 ns。这是利用空间和路由修复过短数据路径，不是插入一拍缓冲。更长路径可能消耗 Setup，因此同时执行最低 +0.5 ns 门禁。

所有 RTL、PLL 参数、定点数学、ready/valid、公共 FIFO 满队列旁路、本地 FIFO、水位及同拍计数语义保持 H 原样。引脚、电平、Bank、输出延迟、Setup uncertainty 1.000、CDC 例外、route_option 2、correct_hold 1 均不变。无新增 false path、异步时钟分组或 multicycle。新副本中的工程/ROM/include 路径已重定向，不写旧位置。

实际资源：Logic 18823/138240（H 为 18822，增加 1）；Register 8669/139095、DSP 46/298、BSRAM 20/340，与 H 相同。138K 的空闲空间用于物理分散和布线修复，本轮未扩大功能资源、未增加寄存器级数。原拟定的 XOR 编码 J/K 没有启动，也没有做编码对照验证，不能记为已尝试。

## 执行记录与验证边界

- 工具：Gowin V1.9.11.03 Education；器件 `GW5AST-LV138PG484AC1/I0`，Device Version C；顶层 `audio_visual_coexistence_top`。
- I 实际全流程：2026-10-05 20:37:23.533—20:39:55.944（UTC+8），退出码 0。
- L 实际全流程：2026-10-05 20:46:32.211—20:49:12.784（UTC+8），退出码 0。
- 每份候选顶层功能自检 1855 项 PASS：厂商真实 PLL 模型测得 40/25/125 MHz，4 个 MIDI Note On/4 声部、189 音频帧/189 提交、最长处理 30 拍、underrun 0、I2S 时序、CDC 内部状态、复位及注入 PLL LOCK 丢失恢复。错误 PLL 分频、旧频率 NCO 两个反例均在仿真运行时被拒绝。
- 回归采用仿真专用 DVI 边界桩，不是加密 TMDS IP 全行为仿真；Icarus 的 include 和动态结构数组适配只存在仿真副本，实际综合输入不变。未完整验证视频首帧显示、音频主观质量、所有 PCM 字值或所有长周期定时器。
- 原报告检查器 23 项自检 PASS。新验收器要求 Setup 至少 +0.5 ns，核对全部时钟/约束实际生效、引脚/电平、器件配置、PnR 选项、位置读回、复位路径、脉宽和所有 TNS。L 的固定旧 0.550 检查误拒绝已在新验收器适配为精确 0.650 **实际生效检查**；旧脚本和原始报告均未改。
- 交付审计额外测试 Setup 0.499/0.500/0.501 边界、NaN、失败门禁，以及约束放宽、错误生成时钟等反例；结果以 `verification_receipt.json` 为准。
- 保留哈希核对：1566 份旧实验文件及完整 I 成功快照无变化。原 H、0.025、0.039 方法均保留。继承的 PR1014（`sys_clk_d` 使用 generic routing）警告仍存在，不能写成已消除所有工具警告或已完成硬件验收。

## 文件与复核入口

推荐候选 `L_locations_guard065/`；原约束备选 `I_hold_locations/`。各自包含完整 56 输入、功能日志、`build.log`、`build_receipt.json`、`assessment.json`、`impl/pnr/*_tr_content.html`、资源/引脚报告、`cmd.do`、`device.cfg`。

新脚本 `hold_trial.py` 用于复制/冻结/仿真/构建，`assess_hold.py` 验收，`verify_delivery.py` 交付审计与打包。已存在的成功目录禁止用 prepare/build 命令覆盖；I 已冻结，勿重新 collect I 改写其 assessment。

在本目录可重复执行只写审计回执的检查（Python 使用本机现有环境）：

```powershell
python -B -X utf8 .\verify_delivery.py audit
```

正式导入前由 M2 复核。位置约束针对当前 138K C 冻结工程，不能直接复制到 60K；正式集成、其他模块变化或工具/器件变化后必须重跑全 STA。实验 `.fs` 仅自动生成的研究产物，不授权下载/烧录，不作为整机或双模式音画共存已通过的证据。

`M2交接_待用户转发.md` 为完整交接通知（待用户转发，尚未送达）。证据 ZIP 不含 `.fs`/`.pr`、可执行文件或大型综合数据库；完整工程产物仍保留在本机候选目录。ZIP CRC、成员 SHA 和包 SHA 见 `archive_receipt.json`，若该回执未生成，不能声称打包校验已通过。
