# M3 完整 V0171 复现与 138K B/C 离线比较

2026-10-05。**M2 原件已齐，60K 控制组成功复现；138K B/C 最小适配后均完成 PnR，但 STA 失败。** 本次不是前一阶段的 8 位计数器工具探针。

全部新增工作在 `E:/FPGA/GAOYUNFPGA/138K_try/reproduction_20261005`。原正式仓库、旧审计/准备目录、M2 封存原件没有修改；没有 Git 提交/推送、Programmer 操作或上板。下列 `.fs` 仅为工具自动生成的研究证据，**全部禁止下载/烧录**，60K 控制组也不作新硬件发布。

## 输入、基线和运行条件

- M2 的 31 个原件逐项核对 FILE_LIST、FILES_SHA256 与 PACKAGE_INVENTORY，大小和 SHA 全部一致；根目录两份 sidecar 与包内对应文件字节相同。用户只交付了解压文件，没有原 ZIP，因此未声称核对 ZIP 哈希。
- 原最终 manifest SHA：`1e29e550b129176e06fe609631229ae7c03a22ed3ad9ac4652f0705c7a234a36`。
- 原 GUI DVI CRLF SHA：`b378c6a41d06a14215dc9ec54ed20bfc91309a0bb1543c589246717da3aee2ab`；实际 LF SHA：`162f68cab4262f8a3acae17f2fc66b6d9ef403815fd5ebeeecf30b59d88e203c`；证实两者只有 CRLF→LF 差异。
- 47/47 工程输入、7 ROM、2 头文件齐套，共 56 物理文件。逐件与原 V0171 actual SHA 或已证明头文件 SHA 核对，副本仅替换 20 处 ROM/include 路径。GPRJ 顺序、60K 器件和 Tcl 非路径选项保留。详细见 `input_audit.json`。
- 完整四声部音频/V1/CC64/PitchMod 与严格视觉/DVI组合；没有换成 audio-only、T028、32 声部或提前寄存拒收候选；没有改 parser、ADSR、公共 FIFO、top 或音频语义。
- 实际工具 **Gowin V1.9.11.03 Education**；PN：60K `GW5AT-LV60PG484AC1/I0`、138K `GW5AST-LV138PG484AC1/I0`，分别使用 B/C 正确 device ID。
- 冻结 SDC 三个时钟 50/25/125 MHz、sys Setup uncertainty 1.000 ns、Hold uncertainty 0.550 ns，所有副本 SDC 逐字节相同。未删例外、未加宽泛 false path、未放宽约束。

## 实际执行结果

单位为 ns；数值是原始导出的最差 slack，不是由 Fmax 推算。

| 本机完整工程 | CLI / 实际阶段 | Setup | Hold | Recovery | Removal | 最小脉宽 |
|---|---|---:|---:|---:|---:|---:|
| 60K_control | exit 0；综合/PnR/STA完成，离线报告门禁 PASS | +0.017 | 0.000 | +1.113 | +0.869 | +2.327 |
| 138K_B_electrical_migration | exit 0；综合/PnR/STA完成，离线报告门禁 **FAIL** | -1.412 | -0.342 | -1.421 | -0.158 | +1.779 |
| 138K_C_electrical_migration | exit 0；综合/PnR/STA完成，离线报告门禁 **FAIL** | -1.356 | -0.348 | -1.411 | -0.152 | +1.779 |

60K 的关键 slack、Fmax、资源、TNS、CDC路径数量及关键路径端点与 M2 原报告一致；60K 原始 PnR 公共选项和 device.cfg 也一致。**这仅证明基线复现，Hold 0.000 和 Setup +0.017 不能宣称达到 +0.5 ns 工程余量或系统稳定。**

| 本机完整工程 | Logic / Register | DSP / BSRAM | sys Fmax MHz | Setup / Hold 违例端点（STA summary） |
|---|---:|---:|---:|---:|
| 60K | 19534 / 8674 | 46 / 20 | 50.043 | 0 / 0 |
| 138K B | 19978 / 10098 | 46 / 20 | 46.703 | 615 / 2410 |
| 138K C | 19528 / 8674 | 46 / 20 | 46.826 | 196 / 2355 |

sys Setup/Hold TNS：B 为 -312.615/-319.875，C 为 -121.294/-306.558。video_serial Setup TNS B=-4.986（4端点）、C=-5.301（4端点），不能仅看串行域 Fmax 高于125 MHz而忽略复位相关违例。video_pixel 的 Setup/Hold TNS 均为0。

以上是**一次已列出必要器件差异的最小迁移比较**，不是参数扫描，也不能外推138K所有实现都失败。但本次实测不支持“只换大器件即可改善时序”的判断；资源占用下降不等于关键路径变短。

## 迁移过程和必要差异

所有阶段独立目录，失败过程不覆盖：

1. `138K_B_frozen_constraints`、`138K_C_frozen_constraints`：只改器件与路径，均在综合技术映射时报 **RP0008：没有 PLLA 资源**，exit 1，没有PnR/STA结果。
2. `138K_B_pll_migration`：依据隔离官方 gw5a 数字模型，将 PLLA 原语接口适配为 PLL，保持模块四端口、`PLLA_inst` 层次、所有原静态参数和125/25 MHz目标。综合完成，但冻结1.5V输入与同Bank5的3.3V音频/UART输出冲突，**CT1136**，exit 1。C的对应目录仅准备，没有运行；不把它记成已测。
3. `138K_B/C_electrical_migration`：只把 `sys_rst_n`、`key_n[0]`、`key_n[1]` 的 IO_TYPE/BANK_VCCIO 声明由 LVCMOS15/1.5改为LVCMOS33/3.3。依据已完整查看的138K核心板原理图：Bank5=3.3V。所有球位、PLL_R[0]和两级复位 R49C101[1][A/B]固定位置均保留；没有试移位置或取消约束。

PLL候选是**工具库原语接口适配，不是伪称GUI重新生成的官方IP**；原DVI源码未改。IDIV=1、FBDIV=1、MDIV=20、ODIV0=8、ODIV1=40、零相位及两个输出使能保留，动态控制关闭。厂商数字模型自检：500个串行周期=8ns、100个像素周期=40ns、100次相位关系检查，compile/run exit0、PASS。数字模型不证明实物锁定、启动校准、抖动或无需厂商初始化逻辑；上板前仍须正式GUI/官方配置复核。

显式设置公共 PnR 选项与60K一致：place0/route0、I/O寄存器打包允许、correct_hold1、clock_route_order0、route_maxfan23；以实际 `cmd.do`核对。B另外由工具产生 `-enable_dsrm 0`，C没有这项新增开关，均明确记录，没有静默忽略任意选项变化。

138K工具 device.cfg 的 `vccx` 自动为1.8V，60K为3.3V；原理图第一页明确注记 **“VCCX in 138K is 1V8”**，因此这是已核对的器件供电差异，没有强制改回3.3V。除这一项允许差异外，配置逐字节比较。VCCX不是Bank5的VCCIO，不能混为同一电源。

参考核心板PDF SHA：`326c45a7ae05e990d5f885fba6ec9b589d966941aa3c00f7d43122d99c068af7`。本轮PDF技能使用既有完整本地供电页渲染，未外传资料、重导出或安装工具。核心板证据不等于目标底板/实物输入已验收，仍禁止烧录。

## 失败路径供 M2 排查

- B最差Setup：parser `control_pending_7_s1/Q → control_pending_18_s1/CE`，-1.412。
- C最差Setup：parser `control_pending_17_s1/Q → control_pending_19_s1/CE`，-1.356。
- B最差Hold：lane1 ADSR `rom_addr_9_s0/Q → gain_rom_gain_rom_0_0_s/AD[13]`，-0.342。
- C最差Hold：parser `locked_index_4_s0/Q → mod_sent_value_mod_sent_value_0_0_s/WAD[3]`，-0.348。
- 两版最差Recovery：`u_visual/u_serial_reset/sync_chain_1_s0/Q → rgb2dvi_inst/u_OSER10_b/RESET`，B=-1.421、C=-1.411。
- Removal在事件桥内部复位到计数/载荷CLEAR路径，B=-0.158、C=-0.152。
- CDC两条存活载荷路径数量仍为23/50，并非完整未优化总线所有位覆盖；但事件桥、score mailbox、mode mailbox三个ack二级同步Hold路径失败。不能把“命令Actived”或载荷数量正确替代逐路径验收。
- B比C多1424个Register，并有工具自动DSRM关闭项；需要M2复核目标库/内存映射，不能仅由此推定具体根因或擅改RTL。
- 三组都保留PR1014（sys_clk_d使用generic routing）的警告；这是本轮记录的已有现象，不在本任务自行改时钟结构。

## 检查器和证据可信边界

`full_report_checks.py`对原始报告进行额外的脉宽、非有限值、CDC独立编号表、14个引脚语义字段、完整运行选项及器件配置差异核对，**21项自检全部PASS**。初次B报告解析出现引脚误报：138K表头没有60K的Slew Rate列，BankVccio索引不同。已改为按真实表头取语义字段，并增加缺列/实际138K格式负例；保留初次 `collect_full_runs_B.log`，以最终JSON和收口日志为准。这个解析修正没有改变负时序结论或原始工具报告。

`collect_full_runs.py` exit0只表示完成结果收集，**不代表三组STA全PASS**；JSON中B/C门禁为false且保留错误。`verify_delivery.py`验证证据身份和“60K成功、B/C失败”的真实状态，也不是将失败项目变成通过。

主要清单：`input_audit.json`、`138k_diagnostic_manifest.json`、`pll_migration_manifest.json`、`electrical_migration_manifest.json`、`full_run_results.json`、各运行目录`build.log/build_receipt.json`及`impl/pnr`原报告；另有`pll_model_test/result.json`和完整报告自检日志。最终新增脚本和清单/报告哈希见`delivery_receipt.json`。

复核命令（本目录，全部隔离输出；收集JSON会更新，因此需先保留旧证据）：

```powershell
$comparisonPython = 'C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $comparisonPython .\test_full_report_checks.py
& $comparisonPython .\collect_full_runs.py
& $comparisonPython .\verify_delivery.py
```

EDA实际命令均为隔离`gw_sh.exe run.tcl`，真实起止时间和exit记录在每目录`build_receipt.json`。`run_build.py`拒绝覆盖已存在的运行日志；若要再次运行，需另建明确尝试目录，不能覆盖本次失败证据。

## 下一步及完成边界

M2补件、冻结基线复现和本次B/C最小迁移对比已经完成到实际PnR/STA；失败也如实交付。**138K B/C不能记为L5时序通过，三组都没有L6。** 当前没有可上板的新发布码流。

`M2_完整对比交接.md`是可转发交接，**待用户转发，尚未送达**。由M2复核本次结果并决定是否另立138K时钟/复位物理适配和关键RTL优化任务；未经交接不继续代改parser、ADSR或公共接口。本轮不改正式仓库状态文档、不提交、不烧录。
