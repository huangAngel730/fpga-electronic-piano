# 138K 从 +0.039 ns 基线开始的真实降频实验

2026-10-05，北京时间。全部工作限于本目录的独立副本，正式仓库只读，无 Git 操作、提交或烧录。原 +0.025 / +0.039 ns 成功版本及旧文档不修改。

## 方案与边界

从 `structural_trials_20261005/E_fixed_slot_next` 出发，把系统逻辑的真实时钟由 50 MHz 改为 PLL 输出的 40 MHz，周期从 20 ns 增至 25 ns。板载输入晶振仍为 50 MHz；视频像素/串行仍为 25/125 MHz。不是仅把 SDC 周期放宽，也不是普通逻辑门控时钟。

PLL 仍为原 138K 迁移候选中的 `PLL` 原语、`PLLA_inst` 层次，IDIV=1、FBDIV=1、MDIV=20；CLKOUT0/1/2 的 ODIV 分别为 8/40/25，对应 125/25/40 MHz。厂商原语仿真实测周期 8/40/25 ns；实际 STA 必须报告这些时钟及 50 MHz 参考时钟。

只有三个寄存器时钟域，STA 中第四个 `ref_clk` 是输入参考。不能认为共同 PLL 就允许直接跨域读多位数据；原 CDC 握手、同步器、总线延迟约束全部保留。视频 25→125 MHz 的 1:5 关系不变，无须让三个域每拍同时到沿。

系统执行能力降低 20%，相同事件拍数的实际时间增长 25%。频率变化会影响时钟量化抖动，不代表音频质量变好。另一个实质区别是音频不再独立于视频 PLL：LOCK 低时系统异步复位、功放静音，LOCK 恢复后同步释放。增加 `pa_en = ~rst_sync_n | ~core_async_rst_n` 保护，避免 PLL 尚无输出时同步寄存器未知导致启动静音不确定。仿真注入 LOCK 丢失检查，不是硬件 LOCK 动态实测。

## 改动与参数

两份候选都只有下列四个综合输入文件相对 E 基线发生非路径变化。公共包、音频算法、parser、FIFO、本地计数、ADSR、视觉算法及 CST 全部不修改。

| 文件 | 变化 |
|---|---|
| `sources/audio_visual_coexistence_top.sv` | 系统逻辑接 core_clk；40 MHz 参数传播；LOCK 复位和直接静音保护；I2S NCO 重新计算 |
| `sources/audio_visual_display_probe.sv` | PLL 参考输入/系统输出连接；按新频率推导诊断定时计数 |
| `sources/TMDS_PLL_800_600_60.v` | 开启实际 CLKOUT2，ODIV2=25，输出 core_clk |
| `constraints/audio_visual_hold055.sdc` | 输入参考50 MHz，系统真实 generated clock=40 MHz；视频 generated clock 改以参考时钟为 master |

| 功能 | 40 MHz 配置 | 保持的目标 |
|---|---|---|
| MIDI UART | DIV=1280 | 31250 baud |
| MIDI 控制合并 | 40000 拍 | 1 kHz |
| I2S NCO | 659706977，替代 527765581 | BCLK 3.072 MHz / 64 BCLK 每立体声帧 / 目标48 kHz |
| 按键去抖 | 120000 拍 | 3 ms |
| STAT UART | DIV=347 | 115200 baud 目标，整数分频存在约 +0.064% 误差 |
| STAT 周期 | 10000000 拍 | 250 ms |
| 诊断模式切换 | 200000000 拍 | 5 s |
| 诊断帧计数 | 672000 拍 | 800×525 / 25 MHz = 16.8 ms |

源文件保留的旧版权、60K 料号和 50 MHz 历史说明不能当作本候选的配置事实；实际目标和配置以本说明、冻结清单及实际报告为准。没有声称本 PLL 是新 GUI 生成或已上板发布。

56 个输入（47 个 GPRJ 项、7 ROM、2 include）逐文件 SHA 固定。sys Setup/Hold uncertainty 仍为 1.000/0.550 ns，输出延迟、七处 CDC 第一级精确切断、10 ns 载荷上限及报告命令均不放宽。无 clock_groups、宽泛 false_path、多周期例外或接口新增一拍。

## 已执行的功能验证及限制

G 和 H 各自运行完整自检，均得到 1855 次检查；189 音频帧、189 次 PCM 提交、四声部处理峰值30拍、underrun=0；实际串行 MIDI 四个 Note On 被接收，经原 CDC 到达视频域内部 live_state。测试时未到第一帧画面发布时刻，不能把该内部状态检查称为完整渲染验证。

测得257个 BCLK 边沿短窗口平均周期325.488281 ns，验证64个 BCLK 上升沿/立体声帧和 DIN 只在 BCLK 低时改变。此窗口不是精确长期采样率、完整 DAC 数据字序或音频质量测量。去抖、STAT、5秒和16.8ms计时参数经过断言检查，未声称完整跑满全部长定时。

真实错误 PLL 分频与遗漏 BCLK 步进重算两个负例均成功编译、运行后被测量断言拒绝，不以编译错误冒充负例通过。检查了外部复位期间静音、注入 LOCK 丢失异步复位/静音、恢复后旧声部清除及新 MIDI 再接收。测试明确保持外部复位直到 PLL 锁定，不能推断所有硬件自动上电场景已经验证。

仿真使用厂商 `gw5a/prim_sim.v` 的真实 PLL 模型。Icarus 不支持加密 DVI IP，顶层仿真用 DVI 边界 stub；不验证 TMDS 编码、串行发送、屏幕识别或出图。两个绝对 include 在仿真副本改为 basename，voice_allocator 的动态结构数组在仿真副本按原位宽/NBA顺序拆字段；这些只是模拟器语法适配，Gowin 综合仍使用实际原版模块。不是所有原版源码无适配直接仿真，也不是后仿真。

## 实际构建

G 的唯一完整构建：19:50:09 至19:52:46，Gowin V1.9.11.03 Education，GW5AST-LV138PG484AC1/I0，C，place=0 / route=1。Setup +3.377 ns，Hold 显示 -0.000 ns，但系统域有3个 Hold 违例端点，严格 FAIL。Logic=18822，Register=8669，DSP=46，BSRAM=20。Recovery +1.176 / Removal +0.324 ns，最小脉宽余量+1.825 ns。最差 Setup 为系统复位同步第二级→公共FIFO载荷寄存器，最差 Hold 为 I2S 移位寄存器相邻级。保留完整失败报告，不作为可下载版本发布。

H 是新副本，综合输入与 G 经路径归一化逐字节一致，仅 `run.tcl` 的 route=1→2。原自动 Hold 修复已开启，两次都保持 `correct_hold_violation=1`。每份候选最多一次完整构建，不扫描种子，不放宽约束，不改 I2S 移位逻辑。

H 的唯一完整构建：19:58:29 至20:00:46，退出码0。Setup +1.522 ns，Hold 显示 -0.000 ns、系统域1个 Hold 违例端点，仍严格 FAIL。Logic/Register/DSP/BSRAM 与 G 相同。Recovery +0.706 / Removal +0.331 ns。最差 Setup 为 MIDI 轮询索引→待处理位图 CE，最差 Hold 为 lane[2] 音高控制 base_s1[18]→base_s2[18]。没有擅自改这个音频流水级来掩盖违例。

| 方案 | 实际系统主频 | Setup余量(ns) | Hold违例端点 | 严格时序门禁 |
|---|---|---|---|---|
| 保留 E 基线 | 50 MHz | +0.039 | 0 | PASS |
| G，route=1 | 40 MHz | +3.377 | 3 | FAIL |
| H，route=2 | 40 MHz | +1.522 | 1 | FAIL |

降频增加 Setup 时间的方法已经实际验证有效，但这两份40 MHz码流都不能作为时序通过版采用。下一阶段重点是独立处理短路径 Hold/时钟偏斜，而不是继续降低频率或放宽 Hold uncertainty。结构优化与降低主频是不同取舍，不能称为相同50 MHz规格下的性能提升。

报告检查包括三域全部 Setup/Hold/TNS、Recovery/Removal、最小脉宽、时钟实际对象/波形、引脚电气和位置、串行复位固定位置、14个 CDC 第二级报告及23/50条存活总线约束路径。存活路径检查不等于原未优化64/98位总线全部覆盖。报告检查器原23项自检通过；新时钟 profile 的实际报告负例验证拒绝把40MHz当50MHz、放宽Hold uncertainty、错误PLL频率比。两次都保留 `sys_clk_d` generic-clock-route PR1014 警告：它是参考输入到PLL的旧警告，但未消除，不声称完整专用时钟布线验证已通过。

## 失败测试历史不删除

G 的 functional/v2/v3 分别因 Icarus absolute include、加密 DVI、动态结构数组不支持而未放行；v4 编译后发现启动静音未知，修正前 top/manifest 保存在 `pre_startup_mute_guard/`。v5 对未到首帧的发布快照错误地要求四个可见音符，失败夹具单独保留；v6 改为检查已经接收事件的内部状态后通过，没有为此改 RTL。

H 全部模拟运行实际通过并写出 review 后，包装脚本因缺少 `functional/` 索引目录退出1；补建索引前逐项验证实际保存的日志 SHA、返回码和 review，不重新运行、不伪造结果、不改 RTL。记录见 `H_functional_index_repair.json`。物理构建只在这个证据核验完成后开始。

## 保留和复查入口

此前1263个文件的 SHA 比对保持不变，见 `preservation_verification.json`；H 实验额外冻结 G 完整172个证据文件，见 `G_preservation_verification.json`。不更新正式仓库看板/状态，原因是用户明确要求仓库不可修改。

```powershell
$python = 'C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
Set-Location 'E:/FPGA/GAOYUNFPGA/138K_try/clock_trials_20261005'
& $python -B -X utf8 .\verify_clock_delivery.py audit
```

prepare/seal/functional/build 为一次性入口，已存在目录和构建证据禁止覆盖重跑。结果以 `results.json`（G）及 `H_results.json`（H）的实际报告判定为准。只有审核、仿真、综合、PnR/STA，不是 L6；没有上板、烧录、60K集成或正式接口变更。交接消息标注待用户转发，尚未送达 M2。

证据一致性审计实际 PASS，见 `verification_receipt.json`；这个 PASS 不覆盖两个候选的 STA FAIL。`hold_path_diagnostics.json` 提取报告中带负号的 Hold 行（不等同于全部违例端点清单）。交付归档 `M3_138K_clock40_evidence_20261005.zip` 包含源码、冻结输入、工程/约束/Tcl、仿真夹具与正负例日志、失败历史、完整实际报告和哈希；排除工具、可执行文件、仿真镜像、码流、临时目录和大型数据库。CRC/逐成员SHA校验记录在归档外的 `archive_receipt.json`。复核脚本依赖本机既有 `reproduction_20261005`、`preparation_20261005` 和 `optimization_followup_20261005` 报告检查模块，归档不是另附一整套 EDA/旧基线的便携安装包。
