> **【本仓库入库说明 — 非原文，2026-09-13 追加】**
>
> 本文件是**外部整理稿**，不是本仓库编写的文档。原始文件由用户提供，
> SHA-256 `EB24C3A069F1B31FF27E89DC5563F260ADD176C98FB1F4303E6AD24C53A06B0F`（111107 字节）。
> 除本说明块与下方标注的 3 处“封装写法”措辞降级外，**正文未作任何改动**。
>
> - 它与 `code/docs/板级硬件事实.md` 是**两个独立来源**，后者才是本项目的板级事实单一来源。
>   两者冲突时以后者与 `技术决策记录.md` 的已冻结决策为准。详见本目录 `README.md`。
> - 本文件**不作为约束依据**。写 `IO_LOC`/`IO_PORT` 时以
>   `code/constraints/electronic_piano.cst` 与官方参考 CST 为准。
> - **已核对一致**：音频 4 脚（Y17/AB17/AA16/AB16）、`sys_clk`=V22、
>   `sys_rst_n`=AA13、`uart_tx`=U15 与本仓库记录完全一致；
>   复位一节与 D018 更正完全吻合。
> - **已核对差异**：① `LEDs[0..7]` 实为 PMOD0 别名而非板载 LED（本文件正确，
>   本仓库旧记录已据此更正）；② 封装写法按用户指示保持**待定**（见下方 3 处标注）；
>   ③ 本文件提到的 2 个原理图 PDF **未入本仓库**。
> - 本文件第 12 节“待用户确认”的 12 条**不等于本项目待办**，
>   实际跟踪状态见 `风险登记表.md` 与 `任务看板.md`。

# Tang Mega 60K 开发板硬件上下文

## 文档范围与证据规则

本文档面向后续 Verilog RTL、顶层端口、约束选择、Testbench 接口建模和 Gowin FPGA 工程创建。本文不包含 RTL 或工程文件。

- 实物组合已由用户确认：30354 核心板 + 31005 Rev 1.4 NEO Dock 底板。
- FPGA 工程器件已由用户确认：`GW5AT-LV60PG484AC1/I0`，IDE 显示封装 `PBG484A`、Device Version B。**〔入库注：`PBG484A` 的写法按 D018 第 2 项保持待定，待首次上板读器件 ID 确认。〕**
- 两个 PDF 不直接解析。原理图相关结论来自 `Tang_Mega_60K_30354_NEO_31005_引脚事实表.xlsx` 的转录内容；表内“证据页”保留原始 PDF 页码。
- 官方 `tang_mega_60K_pins.cst` 是工程球位和端口电气属性的首选来源。Excel 用于解释实际网络、BTB 针号、终点和复用关系。
- Excel 中的 Bank 字段不是本项目的主要决策依据。除明确的 1.5 V 安全限制外，不据此扩展或反推未给出的 Bank/IO 电气属性。
- `未给出`、`待确认`、`冲突` 均保持原状，不使用其他 Tang 板卡经验补全。
- 引用格式示例：`Excel 引脚事实表 r18；核心板 p1；底板 p7、p9；CST SYS 段`。其中页码来自 Excel 的“证据页”字段。

# 1. 开发板基本信息

| 项目 | 已确认内容 | 来源 |
| --- | --- | --- |
| 开发板完整名称 | Sipeed Tang Mega 60K 开发板 | 用户确认；Excel `资料与版本!B6` |
| 套装名称 | Sipeed Tang Mega 60K 基础套装 | 用户确认 |
| 核心板型号 | Tang Mega 60K SOM 30354 | 用户确认；Excel `资料与版本!B6` |
| 核心板硬件版本 | 30354；未发现独立 Rev 字段 | 用户确认；Excel `资料与版本!B6`、`B9:C9` |
| 底板型号 | Tang Mega NEO Dock 31005 | 用户确认；Excel `资料与版本!B6` |
| 底板硬件版本 | Rev 1.4，资料日期 2025-02-08 | 用户确认；Excel `资料与版本!B10:C10` |
| FPGA 厂商 | Gowin Semiconductor（高云半导体） | 器件型号及 Gowin 工程确认 |
| FPGA 系列 | GW5AT（Arora V 系列） | 已确认器件型号 `GW5AT-LV60PG484AC1/I0` |
| FPGA 完整器件型号 | `GW5AT-LV60PG484AC1/I0` | 用户确认；Excel `资料与版本!B7:C7` |
| 原理图器件符号 | `GW5AT-60K-PG484A` | Excel `资料与版本!C7`，转录自核心板原理/器件符号 |
| IDE 封装 | `PBG484A`**（待定）** | 用户确认；Excel `资料与版本!B8:C8`。**入库注：按 D018 第 2 项待定，非已核实结论** |
| 速度/温度后缀 | `C1/I0` 是已确认完整 Device 的组成部分；其精确速度、温度等级含义未由现有本地数据手册解释 | 用户确认；Excel `资料与版本!B7` |
| 推荐开发工具 | Gowin EDA/YunYuan；下载配置通常配合 Gowin Programmer | `.cst` 的 Gowin `IO_LOC`/`IO_PORT` 语法；下载器具体型号待确认 |
| 创建工程选择 | Device/Part：`GW5AT-LV60PG484AC1/I0`；Package：`PBG484A`**（待定）**；Device Version：B | 用户确认；Excel `资料与版本!B7:B8`。**入库注：Package 写法按 D018 第 2 项待定** |

> 注意：原理图符号中的 `PG484A` 与 IDE 显示的 `PBG484A` 写法不同。现阶段按用户已经确认的 IDE 选项建工程，同时把命名差异保留为来源差异，不自行解释为封装冲突或等价关系。

## 资料中仍无法确认的信息

- 核心板是否另有独立于 `30354` 的 PCB Rev。
- `C1/I0` 后缀的官方速度等级和温度等级拆分定义。
- 实物上 DDR3、SDRAM、配置 Flash、下载器/调试器芯片的完整丝印与装配容量。
- 部分底板选配器件是否在当前基础套装上全部焊接。

# 2. 核心板与底板的关系

## 2.1 功能分工

核心板承担 FPGA、本地 50 MHz 有源晶振、配置/状态网络、CPU_RESET、JTAG 引出、DDR3 接口以及向底板导出的高速和普通 I/O。底板承担用户按键、拨码、风扇、音频、UART、摄像头、PMOD、microSD、以太网、Joy-Con、USB-A、HDMI/DVI、PCIe、ADC、CH569/RGB LCD、FPC10P/麦克风阵列等外设或连接器。

来源：Excel `引脚事实表!A6:R154`；`电气与复用规则!A6:B26`；证据页覆盖核心板 p1-p5、底板 p6-p21。

## 2.2 板间连接器与编号

已确认的板间连接器名称为 `J0`、`J1`、`J2`。Excel 使用 `J0-61`、`J1-48`、`J2-60` 等“连接器名称-针号”格式记录针位。现有资料没有给出可安全概括的俯视/底视方向、奇偶排方向或 1 脚外观规则，因此装配和测量时必须按实物丝印或原连接器图确认方向，不能仅凭数字顺序推断。

## 2.3 60K 球位回查规则

正确链路为：

`底板实际网络 → 31005 的 J0/J1/J2 针号 → 30354 同名连接器针号 → 60K FPGA 球位`

31005 底板原图连接器旁的 `BANKx_球位` 是 138K 版本标注，仅供审计。它与 60K 的 Bank/球位不具有可直接复制关系。来源：Excel `电气与复用规则!A7:B10`。

## 2.4 网络名和别名

- Excel“板级网络名”是硬件网络事实，例如 `EX_KEY.0`、`FPGA_UART.TX`。
- CST 端口名是官方示例顶层名，例如 AA13 被命名为 `sys_rst_n`，但其硬件网络仍是 `EX_KEY.0`/`USER_BUTTON0`。
- CST 顶层端口名可以在自己的 RTL 中重命名；必须同步修改 `IO_LOC`/`IO_PORT` 中的名字，球位和电气属性不能随意更改。
- 同名网络只有在 Excel 明确给出相同 BTB 针号或物理链路时才视为相连。
- `USR_CLK_IN` 的辅助资料 V10 与两份原理图链路 V13 存在冲突；本文保留冲突，不把它静默改写为同一网络。

## 2.5 直连与中间器件

| 资源 | 连接性质 | 中间器件/说明 | 来源 |
| --- | --- | --- | --- |
| 用户按键、拨码、PMOD、DVP 控制/数据、FPC10P | FPGA 经 BTB 到底板网络 | 具体上拉和复用按逐行表；不统一假设 3.3 V | Excel 引脚事实表 r18-r24、r32-r77 |
| UART | FPGA 经 0 Ω 到 BL616 | FPGA TX→BL616 GPIO27_RX；FPGA RX←BL616 GPIO28_TX | Excel r30-r31；底板 p7、p8 |
| 千兆以太网 | FPGA RGMII/管理信号到 RTL8211F-CG | 通过 PHY，不是 FPGA 直接驱动网线差分对 | Excel r78-r93；底板 p6、p14 |
| Joy-Con | FPGA 3.3 V 侧经 TXS0108E 到 1.8 V 接口侧 | `RST=0` 启用，`RST=1` 禁用 | Excel r94-r101；底板 p6、p20 |
| WS2812/aRGB | FPGA 到外部转换电路后进入 5 V 侧 | 板载 WS2812 与 aRGB 共用同一数据脚 | Excel r25；底板 p7、p9 |
| 音频 | FPGA I2S 到 PT8211-S，再由 NS4263 功放驱动输出 | `PA_EN=0` 打开功放 | Excel r26-r29；底板 p7、p10 |
| microSD | FPGA 与 BL616 共享 SD/SPI 网络 | 模式切换时必须保证非主控端高阻 | Excel r64-r69；底板 p7、p16 |
| HDMI/DVI | FPGA 差分线及 DDC/控制到 HDMI/DVI 电路 | `DVI_DIR_SEL=1` 为 TX、`0` 为 RX；60K RX 能力待确认 | Excel r106-r117；底板 p7、p11 |
| CH569/RGB LCD | 共享 16 位数据总线和控制线 | 不能把共享信号当成互相独立资源 | Excel r124-r154；底板 p6、p7、p12、p21 |

# 3. FPGA 电源与 I/O Bank

## 3.1 使用原则

本项目不把 Excel 中的 Bank 编号当作 Verilog 接口设计的主要依据。编写约束时以官方 CST 对具体端口给出的球位、`IO_TYPE`、`PULL_MODE`、`DRIVE`、`BANK_VCCIO` 为准；CST 未给出的属性保持待确认。

不能因为某一接口通常使用 3.3 V，就覆盖 CST 或 Excel 明确给出的 1.5 V 条目。特别是 Bank 9 相关资源存在硬件安全风险。

| Bank/资源 | 可确认供电 | 主要连接资源 | 可确认 IO 标准 | 资料来源 |
| --- | --- | --- | --- | --- |
| Bank 9 | 1.5 V | `EX_KEY`、`DIP_Switch_0`、`CAM_TWI.SDA`、`FAN_EN`、`PCIE.RST`、FPC10P/麦克风阵列 | CST 已覆盖者为 `LVCMOS15`；未覆盖者不得反推 | Excel `电气与复用规则!B10`、引脚事实表对应行；官方 CST |
| Bank 10/11 | 1.5 V | 核心板 DDR3 | `SSTL15_I`/差分 `SSTL15D_I` 由 CST/IP 管理 | Excel `电气与复用规则!B11`；CST DDR3 段 |
| 其他普通 I/O Bank | 不建立全局结论 | 逐端口见第 8、9 节 | 逐端口采用 CST；没有 CST 属性时写“待确认” | 官方 CST；Excel 引脚事实表 |
| SerDes Q0 | 专用资源，普通 VCCIO 结论不适用 | `Q0_REFCLK1.N/P`、PCIe/SerDes | 专用差分标准待器件/IP资料确认 | Excel r8-r9；核心板 p1、p5；底板 p7、p18 |
| ADC 专用输入 | 普通 GPIO 标准不适用 | `ADC0/1_INP/INN` | 专用差分 ADC | Excel r120-r123 |

## 3.2 约束一致性结论

- 官方 CST 的 180 个启用 `IO_PORT` 中，`BANK_VCCIO=3.3` 有 121 项，`BANK_VCCIO=1.5` 有 59 项。
- 已启用的 `IO_TYPE` 包括 96 项 `LVCMOS33`、12 项 `LVCMOS15`、44 项 `SSTL15_I`、3 项 `SSTL15D_I`，另有 25 项未写 `IO_TYPE`。
- UART RX 的注释示例 `V14` 同时写 `LVCMOS15` 与 `BANK_VCCIO=3.3`，内部不一致，不应直接启用。
- HDMI/TMDS、DDR CK/DQS、SerDes 参考时钟和 ADC 输入包含差分或专用引脚；不作为普通 GPIO 使用。
- JTAG、配置、DDR3、SerDes、ADC 等专用或半专用资源不建议作为普通 GPIO 使用。

# 4. 系统时钟

| 时钟名称 | 频率 | FPGA 引脚 | Bank/资源 | IO 标准 | 时钟来源 | 核心板/底板 | 资料来源 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BANK7_V22_EMCCLK_50MHz` / CST `sys_clk` | 50 MHz | V22 | Excel：Bank 7 | `LVCMOS33`，`PULL_MODE=NONE`，`BANK_VCCIO=3.3` | Y1100 50 MHz 有源晶振 | 核心板 | Excel r6；核心板 p2；底板 p18；CST SYS 段 |
| `USR_CLK_IN` | 未给出 | V13 | Excel：Bank 7 | 未给出 | MS5351 CKO2，经 R40/C158 | 底板→J2-88→核心板 | Excel r7；核心板 p1、p5；底板 p7、p18 |
| `Q0_REFCLK1.N` | 未给出 | E10 | SerDes Q0 | 专用，未给出 | MS5351 CKO0，经 C39 | 底板→J1-71→核心板 | Excel r8；核心板 p1、p5；底板 p7、p18 |
| `Q0_REFCLK1.P` | 未给出 | F10 | SerDes Q0 | 专用，未给出 | MS5351 CKO1，经 C42 | 底板→J1-73→核心板 | Excel r9；核心板 p1、p5；底板 p7、p18 |
| `CAM0_XCLK` / CST `cmos_xclk` | 未给出 | AA21 | Excel：Bank 8 | `LVCMOS33` | FPGA 输出给摄像头 J15 | 底板 | Excel r35；CST OV5640 段 |
| `CAM0_PCLK` / CST `cmos_pclk` | 未给出 | AB20 | Excel：Bank 8 | `LVCMOS33` | 摄像头像素时钟输入 FPGA | 底板 | Excel r39；CST OV5640 段 |
| `RGMII_GTXCLK` | 未给出 | F20 | 逐端口采用 CST | `LVCMOS33` | FPGA→RTL8211F-CG | 底板 | Excel 以太网组；CST ETHERNET 段 |
| `PHY_CLK` | 未给出 | V19 | 逐端口采用 CST | `LVCMOS33` | RTL8211F-CG/板级时钟网络 | 底板 | Excel 以太网组；CST ETHERNET 段 |
| `RGMII_RXCLK` | 未给出 | E20 | Excel：Bank 4 | Excel/CST 未完整给出 | RTL8211F-CG→FPGA | 底板 | Excel 以太网组；底板 p14 |
| `I2S_BCLK` / `HP_BCK` | 未给出 | Y17 | 逐端口采用 CST | `LVCMOS33` | FPGA→PT8211-S | 底板 | Excel r26；底板 p7、p10；CST AUDIO 段 |
| `I2S_LRCK` / `HP_WS` | 未给出 | AB17 | 逐端口采用 CST | `LVCMOS33` | FPGA→PT8211-S | 底板 | Excel r27；底板 p7、p10；CST AUDIO 段 |
| HDMI/TMDS clock pair | 由视频模式决定 | G15/G16 | 差分对 | CST 未写 `IO_TYPE`，写 `DRIVE=3.5`、3.3 V | FPGA TX 示例 | 底板 | Excel r112-r113；底板 p7、p11；CST HDMI 段 |
| `sdram_clk` | 工程/IP 决定 | B17 | 逐端口采用 CST | `LVCMOS33` | FPGA 输出 | 归属待确认 | CST SDRAM 段 |
| `ddr_ck` | DDR IP 决定 | L3/K3 | DDR 专用差分 | `SSTL15D_I`，1.5 V | FPGA DDR PHY | 核心板 | CST DDR3 段；Excel电气规则 DDR3条目 |

只有 V22 主时钟的 50 MHz 得到明确确认。CST 包含物理 `CLOCK_LOC`，但没有 `create_clock`、周期或频率约束；工程仍需在 Gowin 时序约束中为实际使用的时钟建立频率/周期要求。MS5351 的 25 MHz 晶体频率不能直接当作 CKO0/1/2 输出频率。

# 5. 复位、按键、拨码开关和 LED

## 5.1 复位信号

| 名称 | FPGA 引脚 | 有效电平 | 功能 | 是否可由普通 RTL 使用 | 资料来源 |
| --- | --- | --- | --- | --- | --- |
| `RECONFIG` | N12 | 低有效；按键接地并上拉 | FPGA 配置复位/重新配置 | 否，配置专用；不要当普通 `sys_rst_n` | Excel r10；核心板 p1、p2、p5；底板 p6、p9 |
| `CPU_RESET` | F4 | 低有效；按键接地 | CPU 专用相关复位 | 不作为普通用户复位 | Excel r13；核心板 p2、p4 |
| `EX_KEY.0` / CST `sys_rst_n` | AA13 | 低有效，内部上拉 | USER_BUTTON0；官方示例把它作为用户逻辑复位 | 可以，作为普通 FPGA 输入 | Excel r18；核心板 p1；底板 p7、p9；CST SYS 段 |
| `CAM0_RST` / `cmos_rst_n` | Y22 | 低有效 | DVP 摄像头复位输出 | 可以 | Excel r32；核心板 p1；底板 p7、p17；CST OV5640 段 |
| `RGMII_RST_N` | W20 | 名称指示低有效；实际时序未给出 | 以太网 PHY 复位 | 可以，需查 RTL8211F-CG 资料 | Excel以太网组；CST ETHERNET 段 |
| Joy-Con `RST` | 见第 8 节逐行表 | `0` 启用、`1` 禁用电平转换 | TXS0108E 控制 | 可以，但逻辑语义不是常规低有效复位 | Excel电气规则 Joy-Con条目 |

## 5.2 用户按键和拨码开关

| 板上名称 | FPGA 引脚 | Bank（仅记录） | IO 标准 | 按下/拨动电平 | 上下拉 | 资料来源 |
| --- | --- | --- | --- | --- | --- | --- |
| USER_BUTTON0 / `EX_KEY.0` | AA13 | Excel：Bank 9 | `LVCMOS15` | 按下为低 | `UP` | Excel r18；底板 p7、p9；CST `sys_rst_n` |
| USER_BUTTON1 / `EX_KEY.1` | AB13 | Excel：Bank 9 | `LVCMOS15` | 按下为低 | `UP` | Excel r19；底板 p7、p9；CST `Key_in[0]` |
| USER_BUTTON2 / `EX_KEY.2` | Y12 | Excel：Bank 9 | `LVCMOS15` | 按下为低 | `UP` | Excel r20；底板 p7、p9；CST `Key_in[1]` |
| SW2 相关 `DIP_Switch_0` | AB12 | Excel：Bank 9 | 待确认 | 开关逻辑电平未给出 | 原理图要求内部上拉至 1.5 V | Excel r21；核心板 p1、p5；底板 p7 |

## 5.3 LED

| 板上名称 | 颜色/功能 | FPGA 引脚 | IO 标准 | 点亮电平 | RTL 可控性 | 资料来源 |
| --- | --- | --- | --- | --- | --- | --- |
| 板载 WS2812 / aRGB 数据 | 可编程串行 RGB 灯及外接 aRGB，共用数据脚 | J16 | CST 未写 `IO_TYPE`；`PULL_MODE=NONE`、`DRIVE=8`、`BANK_VCCIO=3.3` | 不是静态高/低点亮；协议时序待器件资料 | 可以 | Excel r25；核心板 p1；底板 p7、p9；CST WS2812 段 |
| DONE 状态 LED | FPGA 配置完成状态 | G11 | 配置专用，未给出 | 未给出 | 不作为普通 RTL LED | Excel r11；核心板 p1、p2、p5；底板 p6 |
| READY 状态 LED | FPGA 配置就绪状态 | U12 | 配置专用，未给出 | 未给出 | 不作为普通 RTL LED | Excel r12；核心板 p1、p2、p5；底板 p6 |
| 电源/下载器状态 LED | 待确认 | 待确认 | 待确认 | 待确认 | 待确认 | Excel 未收录 |

### `LEDs[0..7]` 重要说明

官方 CST 的 `LEDs[0]` 至 `LEDs[7]` 不是底板上的 8 颗板载 LED，而是示例工程为 PMOD0 八根信号使用的顶层别名；相同物理线还复用为 `SDRAM1_D[0..7]`。颜色、限流电阻和静态点亮电平取决于插在 PMOD 上的外部模块，不能从核心板或底板推断。

| CST 别名 | 60K 球位 | 31005 实际网络 | 同时复用 |
| --- | --- | --- | --- |
| `LEDs[0]` | T18 | `PMOD0_IO7` | `SDRAM1_D6` |
| `LEDs[1]` | R18 | `PMOD0_IO6` | `SDRAM1_D7` |
| `LEDs[2]` | R17 | `PMOD0_IO5` | `SDRAM1_D4` |
| `LEDs[3]` | P16 | `PMOD0_IO4` | `SDRAM1_D5` |
| `LEDs[4]` | U21 | `PMOD0_IO3` | `SDRAM1_D2` |
| `LEDs[5]` | T21 | `PMOD0_IO2` | `SDRAM1_D3` |
| `LEDs[6]` | R19 | `PMOD0_IO1` | `SDRAM1_D0` |
| `LEDs[7]` | P19 | `PMOD0_IO0` | `SDRAM1_D1` |

来源：用户提供的核对截图；Excel 引脚事实表 r48-r55 的球位与实际 PMOD0/SDRAM1 网络；CST LEDS 段。

# 6. 下载、配置和调试接口

| 接口/信号 | 使用芯片或连接器 | 与 FPGA 的连接 | 是否需要 RTL | 是否需要普通端口约束 | 工具管理方式 | 来源 |
| --- | --- | --- | --- | --- | --- | --- |
| JTAG：TMS/TDO/TCK/TDI | JTAG 调试连接器/板载调试器；具体调试芯片待确认 | T13/U13/V12/R13，经 J0-3/5/7/9 | 通常不需要 | 通常不作为普通 RTL 端口绑定 | 主要由 Gowin Programmer/调试工具管理 | Excel r14-r17；核心板 p1、p2、p5；底板 p6 |
| USB 下载接口 | 实际 USB 接口及下载器芯片型号待确认 | 现有 Excel 只确认 JTAG 到板载调试器，未给出完整 USB 下载链路 | 不需要 | 不需要额外普通端口 | 下载工具管理 | 待确认 |
| 板载 USB-UART TX | BL616 GPIO27_RX，经 0 Ω | FPGA U15 输出 | 需要 UART TX RTL | 需要；CST 示例 `txp` 已启用 | 串口工具使用 | Excel r30；核心板 p1；底板 p7、p8；CST UART 段 |
| 板载 USB-UART RX | BL616 GPIO28_TX，经 0 Ω | FPGA V14 输入 | 需要 UART RX RTL | 需要，但官方 CST 只有冲突的注释示例 | 串口工具使用 | Excel r31；核心板 p1；底板 p7、p8；CST UART 注释 |
| `RECONFIG` | 核心板/底板 RECONFIG 按键 | N12，配置专用输入 | 不需要 | 不作为普通 RTL 端口 | 配置硬件管理 | Excel r10 |
| `DONE`/`READY` | 核心板状态 LED/BTB | G11/U12，配置状态 | 不需要 | 不作为普通 RTL LED | FPGA 配置逻辑管理 | Excel r11-r12 |
| FPGA 配置 Flash | 型号、容量、网络均未收录 | 待确认 | 通常不需要用户 RTL，但以实际配置模式为准 | 通常由器件配置规则管理 | Gowin Programmer | 待确认 |

# 7. 存储器资源

| 器件型号 | 存储类型 | 容量/位宽 | FPGA 接口 | 相关引脚 | 时钟 | 电压 | 位置 | 资料来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 型号待确认 | DDR3 | 当前 CST 启用 16 位 `DQ[15:0]`；容量待确认 | `ddr_*`，包含地址、Bank、控制、CK、DQS、DM、DQ | 逐项见第 9 节；高 16 位 DQ、DQS2/3、DM2/3 被注释 | `ddr_ck` L3/K3 | 1.5 V，`SSTL15_I/SSTL15D_I` | 核心板 | CST DDR3 段；Excel `电气与复用规则!B11` |
| 型号待确认 | SDRAM | CST 为 16 位数据接口；容量待确认 | `sdram_*` | 逐项见第 9 节 | `sdram_clk` B17 | 3.3 V，`LVCMOS33` | 与 Excel 的 `SDRAM1` 是否为同一实际器件待确认 | CST SDRAM 段 |
| 可移除 microSD 卡 | Flash 卡 | 由插卡决定；支持完整 SDIO 线，但 CST 仅提供 4 线 SPI 示例 | `FPGA_SDIO_*`，与 BL616 共享 | AA15、AB15、Y16、W15、V15、W14 | V15 | 已确认示例为 3.3 V；D1/D2 属性待确认 | 底板 J31，扩展排针 J10 | Excel r64-r69；底板 p7、p16；CST SDCARD 段 |
| 型号待确认 | FPGA 配置 Flash | 容量待确认 | 配置专用 | 待确认 | 待确认 | 待确认 | 待确认 | 当前 Excel/CST 未给出 |

## 7.1 使用建议和限制

- DDR3 必须使用高云 DDR IP、PHY 和由工具生成的配套约束，不适合以普通 GPIO 方式手写控制。
- CST 中的 DDR3 `INS_LOC` 与内部实例路径绑定示例工程层次，复制到新工程前必须与实际 IP 实例名一致。
- SDRAM 在接口层面可以由 RTL 控制，但芯片型号、容量、刷新和时序参数没有现有数据手册支持，不能从 CST 推导。
- microSD 可用普通 Verilog 实现 SPI 模式；若使用完整 SDIO、高速模式或共享切换，需要额外协议、时序和 BL616 协作设计。
- 未查到 HyperRAM、PSRAM 或 SRAM 的可靠本地证据，不列为已存在资源。

# 8. 底板外设和扩展接口

下面的总表由 Excel `引脚事实表!A6:R154` 逐行生成。Bank 仅原样记录，不作为约束选择依据；`IOSTANDARD` 为空或“未给出”时不得从 Bank 反推。

| 接口 | 板级网络名 | FPGA方向 | 60K球位 | Bank（记录） | IO标准 | 差分/专用 | SOM/BTB | 物理终点与复用 | 状态与资料来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 时钟 | `BANK7_V22_EMCCLK_50MHz` | FPGA输入 | `V22` | Bank 7 | `LVCMOS33` | 否/未注明 | `核心板内部` | Y1100 50 MHz有源晶振；CST示例名 sys_clk | 已确认；Excel r6；核心板p2；底板p18；官方CST |
| 时钟 | `USR_CLK_IN` | FPGA输入 | `V13` | Bank 7 | 未给出 | 否/未注明 | `J2-88` | MS5351 CKO2，经R40/C158；31005未给出CKO2频率；辅助资料曾写V10，与两份原理图冲突，见待确认页 | 物理已确认；Excel r7；核心板p1、p5；底板p7、p18 |
| 高速参考时钟 | `Q0_REFCLK1.N` | FPGA输入 | `E10` | SerDes Q0 | 未给出 | SerDes专用差分 | `J1-71` | MS5351 CKO0，经C39；复用：PCIe/SerDes；专用SerDes参考时钟；频率由MS5351配置，原理图未给出 | 物理已确认；Excel r8；核心板p1、p5；底板p7、p18 |
| 高速参考时钟 | `Q0_REFCLK1.P` | FPGA输入 | `F10` | SerDes Q0 | 未给出 | SerDes专用差分 | `J1-73` | MS5351 CKO1，经C42；复用：PCIe/SerDes；专用SerDes参考时钟；频率由MS5351配置，原理图未给出 | 物理已确认；Excel r9；核心板p1、p5；底板p7、p18 |
| 配置 | `RECONFIG` | FPGA配置输入 | `N12` | Bank 3 | 未给出 | 复用 | `J0-61` | 核心板与底板RECONFIG按键；复用：配置专用功能；不要与用户工程的 sys_rst_n 别名混淆 | 已确认；Excel r10；核心板p1；核心板p2、p5；底板p6、p9 |
| 配置 | `DONE` | FPGA配置状态 | `G11` | Bank 3 | 未给出 | 复用 | `J0-77` | 核心板状态LED/BTB；复用：配置专用功能；有效电平未在资料中明确给出 | 物理已确认；Excel r11；核心板p1；核心板p2、p5；底板p6 |
| 配置 | `READY` | FPGA配置状态 | `U12` | Bank 3 | 未给出 | 复用 | `J0-79` | 核心板状态LED/BTB；复用：配置专用功能；有效电平未在资料中明确给出 | 物理已确认；Excel r12；核心板p1；核心板p2、p5；底板p6 |
| 复位 | `CPU_RESET` | CPU复位输入 | `F4` | Bank 1 | 未给出 | 复用 | `核心板内部` | 核心板CPU_RESET按键；复用：CPU专用相关；不是普通用户复位端口 | 物理已确认；Excel r13；核心板p2、p4 |
| JTAG | `JTAG.TMS` | 未给出 | `T13` | Bank 12 | 未给出 | 复用 | `J0-3` | JTAG调试连接器/板载调试器；复用：JTAG | 物理已确认；Excel r14；核心板p1；核心板p2、p5；底板p6 |
| JTAG | `JTAG.TDO` | 未给出 | `U13` | Bank 12 | 未给出 | 复用 | `J0-5` | JTAG调试连接器/板载调试器；复用：JTAG | 物理已确认；Excel r15；核心板p1；核心板p2、p5；底板p6 |
| JTAG | `JTAG.TCK` | 未给出 | `V12` | Bank 12 | 未给出 | 复用 | `J0-7` | JTAG调试连接器/板载调试器；复用：JTAG | 物理已确认；Excel r16；核心板p1；核心板p2、p5；底板p6 |
| JTAG | `JTAG.TDI` | 未给出 | `R13` | Bank 12 | 未给出 | 复用 | `J0-9` | JTAG调试连接器/板载调试器；复用：JTAG | 物理已确认；Excel r17；核心板p1；核心板p2、p5；底板p6 |
| 用户按键 | `EX_KEY.0` | FPGA输入 | `AA13` | Bank 9 | `LVCMOS15` | 复用 | `J2-60` | USER_BUTTON0；复用：与官方CST示例 sys_rst_n 别名相关；官方CST把AA13作为示例 sys_rst_n；硬件事实仍是EX_KEY.0 | 已确认；Excel r18；核心板p1；底板p7、p9；官方CST |
| 用户按键 | `EX_KEY.1` | FPGA输入 | `AB13` | Bank 9 | `LVCMOS15` | 否/未注明 | `J2-62` | USER_BUTTON1；CST示例名 Key_in[0] | 已确认；Excel r19；核心板p1；底板p7、p9；官方CST |
| 用户按键 | `EX_KEY.2` | FPGA输入 | `Y12` | Bank 9 | `LVCMOS15` | 否/未注明 | `J2-64` | USER_BUTTON2；CST示例名 Key_in[1] | 已确认；Excel r20；核心板p1；底板p7、p9；官方CST |
| 拨码 | `DIP_Switch_0` | FPGA输入 | `AB12` | Bank 9 | 未给出 | 否/未注明 | `J2-66` | 底板SW2相关拨码网络；31005未给出IOSTANDARD和开关逻辑含义 | 物理已确认；Excel r21；核心板p1、p5；底板p7 |
| 风扇 | `FAN_EN` | FPGA输出 | `V10` | Bank 9 | 未给出 | 否/未注明 | `J2-68` | 风扇电源控制电路/J23；IOSTANDARD/DRIVE未给出，不能仅由Bank电压反推 | 物理已确认；Excel r22；核心板p1、p5；底板p7、p9 |
| 风扇 | `FAN_PWM0` | FPGA输出 | `W19` | Bank 8 | 未给出 | 否/未注明 | `J2-21` | 4线风扇PWM/J23；IOSTANDARD和PWM频率未给出 | 物理已确认；Excel r23；核心板p1、p5；底板p7、p9 |
| 风扇 | `FAN_TACHO` | FPGA输入 | `T14` | Bank 6 | 未给出 | 否/未注明 | `J2-90` | 风扇测速/J23；测速脉冲电气及时序未给出 | 物理已确认；Excel r24；核心板p1、p5；底板p7、p9 |
| 灯带 | `WS2812` | FPGA输出 | `J16` | Bank 5 | 未给出 | 复用 | `J1-48` | 板载WS2812与aRGB连接器；复用：同一数据脚；CST未写IO_TYPE；外部电路转换到5 V侧 | 已确认；Excel r25；核心板p1；底板p7、p9；官方CST |
| 音频I2S | `I2S_BCLK` | FPGA输出 | `Y17` | Bank 7 | `LVCMOS33` | 否/未注明 | `J2-26` | PT8211-S BCK；CST示例名 HP_BCK；采样率/时序未给出 | 已确认；Excel r26；核心板p1；底板p7、p10；官方CST |
| 音频I2S | `I2S_LRCK` | FPGA输出 | `AB17` | Bank 7 | `LVCMOS33` | 否/未注明 | `J2-28` | PT8211-S WS；CST示例名 HP_WS；采样率/时序未给出 | 已确认；Excel r27；核心板p1；底板p7、p10；官方CST |
| 音频I2S | `I2S_DIN` | FPGA输出 | `AA16` | Bank 7 | `LVCMOS33` | 否/未注明 | `J2-30` | PT8211-S DIN；CST示例名 HP_DIN；数据格式未给出 | 已确认；Excel r28；核心板p1；底板p7、p10；官方CST |
| 音频功放 | `PA_EN` | FPGA输出 | `AB16` | Bank 7 | `LVCMOS33` | 否/未注明 | `J2-36` | NS4263功放使能；上电初始化必须考虑低有效 | 已确认；Excel r29；核心板p1；底板p7、p10；官方CST |
| UART | `FPGA_UART.TX` | FPGA输出 | `U15` | Bank 6 | `LVCMOS33` | 复用 | `J2-50` | BL616 GPIO27_RX，经0Ω；复用：板载USB-UART；CST示例名 txp | 已确认；Excel r30；核心板p1；底板p7、p8；官方CST |
| UART | `FPGA_UART.RX` | FPGA输入 | `V14` | Bank 8 | 未给出 | 复用 | `J2-54` | BL616 GPIO28_TX，经0Ω；复用：板载USB-UART；物理连接确定；官方CST注释写LVCMOS15与BANK_VCCIO=3.3同列，故不采用其IOSTANDARD | 冲突；Excel r31；核心板p1；底板p7、p8；官方CST注释 |
| DVP摄像头 | `CAM0_RST` | FPGA输出 | `Y22` | Bank 8 | `LVCMOS33` | 复用 | `J2-3` | 摄像头J15；复用：PMOD1_IO1/SDRAM1_A9；CST示例名 cmos_rst_n | 已确认；Excel r32；核心板p1；底板p7、p17；官方CST |
| DVP摄像头 | `CAM0_VSYNC` | FPGA输入 | `Y21` | Bank 8 | `LVCMOS33` | 复用 | `J2-5` | 摄像头J15；复用：PMOD1_IO0/SDRAM1_A11；CST示例名 cmos_vsync | 已确认；Excel r33；核心板p1；底板p7、p17；官方CST |
| DVP摄像头 | `CAM0_PWDN` | FPGA输出 | `AB22` | Bank 8 | `LVCMOS33` | 复用 | `J2-7` | 摄像头J15；复用：PMOD1_IO3/SDRAM1_A7；CST示例名 cmos_pwdn | 已确认；Excel r34；核心板p1；底板p7、p17；官方CST |
| DVP摄像头 | `CAM0_HSYNC` | FPGA输入 | `AB21` | Bank 8 | `LVCMOS33` | 复用 | `J2-9` | 摄像头J15；复用：PMOD1_IO2/SDRAM1_A8；CST示例名 cmos_href | 已确认；Excel r35；核心板p1；底板p7、p17；官方CST |
| DVP摄像头 | `CAM0_MCLK` | FPGA输出 | `AA21` | Bank 7 | `LVCMOS33` | 复用 | `J2-11` | 摄像头J15；复用：PMOD1_IO5/SDRAM1_A5；CST示例名 cmos_xclk | 已确认；Excel r36；核心板p1；底板p7、p17；官方CST |
| DVP摄像头 | `CAM0_D7` | FPGA输入 | `AA20` | Bank 7 | `LVCMOS33` | 复用 | `J2-13` | 摄像头J15；复用：PMOD1_IO4/SDRAM1_A6；CST示例名 cmos_db[7] | 已确认；Excel r37；核心板p1；底板p7、p17；官方CST |
| DVP摄像头 | `CAM0_PCLK` | FPGA输入 | `AB20` | Bank 8 | `LVCMOS33` | 复用 | `J2-15` | 摄像头J15；复用：PMOD1_IO7/SDRAM1_WE；CST示例名 cmos_pclk | 已确认；Excel r38；核心板p1；底板p7、p17；官方CST |
| DVP摄像头 | `CAM0_D6` | FPGA输入 | `AA19` | Bank 8 | `LVCMOS33` | 复用 | `J2-17` | 摄像头J15；复用：PMOD1_IO6/SDRAM1_A4；CST示例名 cmos_db[6] | 已确认；Excel r39；核心板p1；底板p7、p17；官方CST |
| DVP摄像头 | `CAM0_D5` | FPGA输入 | `T20` | Bank 7 | `LVCMOS33` | 复用 | `J0-19` | 摄像头J15；复用：SDRAM1_CS；CST示例名 cmos_db[5] | 已确认；Excel r40；核心板p1；底板p7、p17；官方CST |
| DVP摄像头 | `CAM0_D4` | FPGA输入 | `N15` | Bank 6 | `LVCMOS33` | 复用 | `J2-20` | 摄像头J15；复用：SDRAM1_BA0；CST示例名 cmos_db[4] | 已确认；Excel r41；核心板p1；底板p7、p17；官方CST |
| DVP摄像头 | `CAM0_D2` | FPGA输入 | `R16` | Bank 6 | `LVCMOS33` | 复用 | `J2-49` | 摄像头J15；复用：SDRAM1_A0；CST示例名 cmos_db[2] | 已确认；Excel r42；核心板p1；底板p7、p17；官方CST |
| DVP摄像头 | `CAM0_D1` | FPGA输入 | `P15` | Bank 6 | `LVCMOS33` | 复用 | `J2-51` | 摄像头J15；复用：SDRAM1_A1；CST示例名 cmos_db[1] | 已确认；Excel r43；核心板p1；底板p7、p17；官方CST |
| DVP摄像头 | `CAM0_D3` | FPGA输入 | `R14` | Bank 6 | `LVCMOS33` | 复用 | `J2-55` | 摄像头J15；复用：SDRAM1_A2；CST示例名 cmos_db[3] | 已确认；Excel r44；核心板p1；底板p7、p17；官方CST |
| DVP摄像头 | `CAM0_D0` | FPGA输入 | `P14` | Bank 6 | `LVCMOS33` | 复用 | `J2-57` | 摄像头J15；复用：SDRAM1_A3；CST示例名 cmos_db[0] | 已确认；Excel r45；核心板p1；底板p7、p17；官方CST |
| 摄像头I2C | `CAM_TWI.SDA` | 双向 | `Y13` | Bank 9 | `LVCMOS15` | 否/未注明 | `J2-56` | PCA9306 FPGA侧；CST示例名 cmos_sda；与SCL分属不同Bank/电压 | 已确认；Excel r46；核心板p1；底板p7、p17；官方CST |
| 摄像头I2C | `CAM_TWI.SCL` | 双向（I2C总线） | `AA14` | Bank 8 | `LVCMOS33` | 否/未注明 | `J2-58` | PCA9306 FPGA侧；CST示例名 cmos_scl | 已确认；Excel r47；核心板p1；底板p7、p17；官方CST |
| PMOD0 | `PMOD0_IO0` | 由用户设计决定 | `P19` | Bank 7 | `LVCMOS33（官方CST示例别名）` | 复用 | `J0-25` | PMOD J9；复用：SDRAM1；通用方向/驱动强度由实际外设决定；不要同时启用PMOD0与SDRAM1复用功能 | 已确认；Excel r48；核心板p1；底板p6、p19；官方CST |
| PMOD0 | `PMOD0_IO1` | 由用户设计决定 | `R19` | Bank 7 | `LVCMOS33（官方CST示例别名）` | 复用 | `J0-23` | PMOD J9；复用：SDRAM1；通用方向/驱动强度由实际外设决定；不要同时启用PMOD0与SDRAM1复用功能 | 已确认；Excel r49；核心板p1；底板p6、p19；官方CST |
| PMOD0 | `PMOD0_IO2` | 由用户设计决定 | `T21` | Bank 7 | `LVCMOS33（官方CST示例别名）` | 复用 | `J0-15` | PMOD J9；复用：SDRAM1；通用方向/驱动强度由实际外设决定；不要同时启用PMOD0与SDRAM1复用功能 | 已确认；Excel r50；核心板p1；底板p6、p19；官方CST |
| PMOD0 | `PMOD0_IO3` | 由用户设计决定 | `U21` | Bank 7 | `LVCMOS33（官方CST示例别名）` | 复用 | `J0-13` | PMOD J9；复用：SDRAM1；通用方向/驱动强度由实际外设决定；不要同时启用PMOD0与SDRAM1复用功能 | 已确认；Excel r51；核心板p1；底板p6、p19；官方CST |
| PMOD0 | `PMOD0_IO4` | 由用户设计决定 | `P16` | Bank 8 | `LVCMOS33（官方CST示例别名）` | 复用 | `J0-20` | PMOD J9；复用：SDRAM1；通用方向/驱动强度由实际外设决定；不要同时启用PMOD0与SDRAM1复用功能 | 已确认；Excel r52；核心板p1；底板p6、p19；官方CST |
| PMOD0 | `PMOD0_IO5` | 由用户设计决定 | `R17` | Bank 8 | `LVCMOS33（官方CST示例别名）` | 复用 | `J0-18` | PMOD J9；复用：SDRAM1；通用方向/驱动强度由实际外设决定；不要同时启用PMOD0与SDRAM1复用功能 | 已确认；Excel r53；核心板p1；底板p6、p19；官方CST |
| PMOD0 | `PMOD0_IO6` | 由用户设计决定 | `R18` | Bank 8 | `LVCMOS33（官方CST示例别名）` | 复用 | `J0-14` | PMOD J9；复用：SDRAM1；通用方向/驱动强度由实际外设决定；不要同时启用PMOD0与SDRAM1复用功能 | 已确认；Excel r54；核心板p1；底板p6、p19；官方CST |
| PMOD0 | `PMOD0_IO7` | 由用户设计决定 | `T18` | Bank 8 | `LVCMOS33（官方CST示例别名）` | 复用 | `J0-12` | PMOD J9；复用：SDRAM1；通用方向/驱动强度由实际外设决定；不要同时启用PMOD0与SDRAM1复用功能 | 已确认；Excel r55；核心板p1；底板p6、p19；官方CST |
| PMOD1 | `PMOD1_IO0` | 由用户设计决定 | `Y21` | Bank 8 | `LVCMOS33（官方CST的摄像头别名）` | 复用 | `J2-5` | PMOD J8；复用：DVP摄像头/SDRAM1；不要同时启用PMOD1、DVP与SDRAM1复用功能 | 已确认；Excel r56；核心板p1；底板p7、p19；官方CST |
| PMOD1 | `PMOD1_IO1` | 由用户设计决定 | `Y22` | Bank 8 | `LVCMOS33（官方CST的摄像头别名）` | 复用 | `J2-3` | PMOD J8；复用：DVP摄像头/SDRAM1；不要同时启用PMOD1、DVP与SDRAM1复用功能 | 已确认；Excel r57；核心板p1；底板p7、p19；官方CST |
| PMOD1 | `PMOD1_IO2` | 由用户设计决定 | `AB21` | Bank 8 | `LVCMOS33（官方CST的摄像头别名）` | 复用 | `J2-9` | PMOD J8；复用：DVP摄像头/SDRAM1；不要同时启用PMOD1、DVP与SDRAM1复用功能 | 已确认；Excel r58；核心板p1；底板p7、p19；官方CST |
| PMOD1 | `PMOD1_IO3` | 由用户设计决定 | `AB22` | Bank 8 | `LVCMOS33（官方CST的摄像头别名）` | 复用 | `J2-7` | PMOD J8；复用：DVP摄像头/SDRAM1；不要同时启用PMOD1、DVP与SDRAM1复用功能 | 已确认；Excel r59；核心板p1；底板p7、p19；官方CST |
| PMOD1 | `PMOD1_IO4` | 由用户设计决定 | `AA20` | Bank 7 | `LVCMOS33（官方CST的摄像头别名）` | 复用 | `J2-13` | PMOD J8；复用：DVP摄像头/SDRAM1；不要同时启用PMOD1、DVP与SDRAM1复用功能 | 已确认；Excel r60；核心板p1；底板p7、p19；官方CST |
| PMOD1 | `PMOD1_IO5` | 由用户设计决定 | `AA21` | Bank 7 | `LVCMOS33（官方CST的摄像头别名）` | 复用 | `J2-11` | PMOD J8；复用：DVP摄像头/SDRAM1；不要同时启用PMOD1、DVP与SDRAM1复用功能 | 已确认；Excel r61；核心板p1；底板p7、p19；官方CST |
| PMOD1 | `PMOD1_IO6` | 由用户设计决定 | `AA19` | Bank 8 | `LVCMOS33（官方CST的摄像头别名）` | 复用 | `J2-17` | PMOD J8；复用：DVP摄像头/SDRAM1；不要同时启用PMOD1、DVP与SDRAM1复用功能 | 已确认；Excel r62；核心板p1；底板p7、p19；官方CST |
| PMOD1 | `PMOD1_IO7` | 由用户设计决定 | `AB20` | Bank 8 | `LVCMOS33（官方CST的摄像头别名）` | 复用 | `J2-15` | PMOD J8；复用：DVP摄像头/SDRAM1；不要同时启用PMOD1、DVP与SDRAM1复用功能 | 已确认；Excel r63；核心板p1；底板p7、p19；官方CST |
| SD卡 | `FPGA_SDIO_D0\|SPI_MISO` | 双向 | `AA15` | Bank 7 | `LVCMOS33` | 复用 | `J2-38` | microSD卡座J31及扩展排针J10；复用：与BL616 SPI共享；CST示例名 sd_miso | 已确认；Excel r64；核心板p1；底板p7、p16；官方CST |
| SD卡 | `FPGA_SDIO_D1` | 双向 | `AB15` | Bank 8 | 未给出 | 复用 | `J2-40` | microSD卡座J31及扩展排针J10；复用：与BL616 SPI共享；官方CST未给出此位 | 物理已确认；Excel r65；核心板p1；底板p7、p16；官方CST |
| SD卡 | `FPGA_SDIO_CMD\|SPI_MOSI` | 双向 | `Y16` | Bank 7 | `LVCMOS33` | 复用 | `J2-42` | microSD卡座J31及扩展排针J10；复用：与BL616 SPI共享；CST示例名 sd_mosi | 已确认；Excel r66；核心板p1；底板p7、p16；官方CST |
| SD卡 | `FPGA_SDIO_D3\|SPI_CS` | 双向 | `W15` | Bank 7 | `LVCMOS33` | 复用 | `J2-44` | microSD卡座J31及扩展排针J10；复用：与BL616 SPI共享；CST示例名 sd_cs | 已确认；Excel r67；核心板p1；底板p7、p16；官方CST |
| SD卡 | `FPGA_SDIO_CLK\|SPI_SCK` | FPGA输出 | `V15` | Bank 6 | `LVCMOS33` | 复用 | `J2-46` | microSD卡座J31及扩展排针J10；复用：与BL616 SPI共享；CST示例名 sd_clk | 已确认；Excel r68；核心板p1；底板p7、p16；官方CST |
| SD卡 | `FPGA_SDIO_D2` | 双向 | `W14` | Bank 8 | 未给出 | 复用 | `J2-48` | microSD卡座J31及扩展排针J10；复用：与BL616 SPI共享；官方CST未给出此位 | 物理已确认；Excel r69；核心板p1；底板p7、p16；官方CST |
| FPC10P/麦克风阵列 | `FPC10P_IO0` | 由用户设计决定 | `W12` | Bank 9 | `LVCMOS15` | 复用 | `J2-86` | FPC10P J32；复用：麦克风阵列接口；CST示例名 sk9822_ck；J32-9是5V_Peripheral，J32-10是GND | 已确认；Excel r70；核心板p1；底板p7、p19；官方CST |
| FPC10P/麦克风阵列 | `FPC10P_IO1` | 由用户设计决定 | `AA9` | Bank 9 | `LVCMOS15` | 复用 | `J2-84` | FPC10P J32；复用：麦克风阵列接口；CST示例名 sk9822_da；J32-9是5V_Peripheral，J32-10是GND | 已确认；Excel r71；核心板p1；底板p7、p19；官方CST |
| FPC10P/麦克风阵列 | `FPC10P_IO2` | 由用户设计决定 | `AA10` | Bank 9 | `LVCMOS15` | 复用 | `J2-82` | FPC10P J32；复用：麦克风阵列接口；CST示例名 mic_array_d[0]；J32-9是5V_Peripheral，J32-10是GND | 已确认；Excel r72；核心板p1；底板p7、p19；官方CST |
| FPC10P/麦克风阵列 | `FPC10P_IO3` | 由用户设计决定 | `AB10` | Bank 9 | `LVCMOS15` | 复用 | `J2-80` | FPC10P J32；复用：麦克风阵列接口；CST示例名 mic_array_d[1]；J32-9是5V_Peripheral，J32-10是GND | 已确认；Excel r73；核心板p1；底板p7、p19；官方CST |
| FPC10P/麦克风阵列 | `FPC10P_IO4` | 由用户设计决定 | `AA11` | Bank 9 | `LVCMOS15` | 复用 | `J2-78` | FPC10P J32；复用：麦克风阵列接口；CST示例名 mic_array_d[2]；J32-9是5V_Peripheral，J32-10是GND | 已确认；Excel r74；核心板p1；底板p7、p19；官方CST |
| FPC10P/麦克风阵列 | `FPC10P_IO5` | 由用户设计决定 | `AB11` | Bank 9 | `LVCMOS15` | 复用 | `J2-76` | FPC10P J32；复用：麦克风阵列接口；CST示例名 mic_array_d[3]；J32-9是5V_Peripheral，J32-10是GND | 已确认；Excel r75；核心板p1；底板p7、p19；官方CST |
| FPC10P/麦克风阵列 | `FPC10P_IO6` | 由用户设计决定 | `W10` | Bank 9 | `LVCMOS15` | 复用 | `J2-74` | FPC10P J32；复用：麦克风阵列接口；CST示例名 mic_array_ws；J32-9是5V_Peripheral，J32-10是GND | 已确认；Excel r76；核心板p1；底板p7、p19；官方CST |
| FPC10P/麦克风阵列 | `FPC10P_IO7` | 由用户设计决定 | `Y11` | Bank 9 | `LVCMOS15` | 复用 | `J2-72` | FPC10P J32；复用：麦克风阵列接口；CST示例名 mic_array_bck；J32-9是5V_Peripheral，J32-10是GND | 已确认；Excel r77；核心板p1；底板p7、p19；官方CST |
| 千兆以太网 | `EPHY_CLK` | FPGA输入 | `V19` | Bank 8 | `LVCMOS33` | 复用 | `J0-4` | RTL8211F-CG；复用：RGMII；CST示例名 PHY_CLK | 已确认；Excel r78；核心板p1；底板p6、p7、p11；官方CST |
| 千兆以太网 | `RGMII_MDC` | FPGA输出 | `V18` | Bank 8 | 未给出 | 复用 | `J0-6` | RTL8211F-CG；复用：RGMII；IOSTANDARD/时序未在所给约束中给出 | 物理已确认；Excel r79；核心板p1；底板p6、p7、p11；官方CST |
| 千兆以太网 | `RGMII_MDIO` | 双向 | `U22` | Bank 7 | 未给出 | 复用 | `J0-10` | RTL8211F-CG；复用：RGMII；IOSTANDARD/时序未在所给约束中给出 | 物理已确认；Excel r80；核心板p1；底板p6、p7、p11；官方CST |
| 千兆以太网 | `RGMII_RXCK` | FPGA输入 | `G21` | Bank 2 | 未给出 | 复用 | `J0-65` | RTL8211F-CG；复用：RGMII；IOSTANDARD/时序未在所给约束中给出 | 物理已确认；Excel r81；核心板p1；底板p6、p7、p11；官方CST |
| 千兆以太网 | `RGMII_RXDV` | FPGA输入 | `G22` | Bank 2 | 未给出 | 复用 | `J0-67` | RTL8211F-CG；复用：RGMII；IOSTANDARD/时序未在所给约束中给出 | 物理已确认；Excel r82；核心板p1；底板p6、p7、p11；官方CST |
| 千兆以太网 | `RGMII_RX0` | FPGA输入 | `F18` | Bank 2 | 未给出 | 复用 | `J0-69` | RTL8211F-CG；复用：RGMII；IOSTANDARD/时序未在所给约束中给出 | 物理已确认；Excel r83；核心板p1；底板p6、p7、p11；官方CST |
| 千兆以太网 | `RGMII_RX1` | FPGA输入 | `E18` | Bank 2 | 未给出 | 复用 | `J0-71` | RTL8211F-CG；复用：RGMII；IOSTANDARD/时序未在所给约束中给出 | 物理已确认；Excel r84；核心板p1；底板p6、p7、p11；官方CST |
| 千兆以太网 | `RGMII_RX2` | FPGA输入 | `C22` | Bank 2 | 未给出 | 复用 | `J0-73` | RTL8211F-CG；复用：RGMII；IOSTANDARD/时序未在所给约束中给出 | 物理已确认；Excel r85；核心板p1；底板p6、p7、p11；官方CST |
| 千兆以太网 | `RGMII_RX3` | FPGA输入 | `B22` | Bank 2 | 未给出 | 复用 | `J0-75` | RTL8211F-CG；复用：RGMII；IOSTANDARD/时序未在所给约束中给出 | 物理已确认；Excel r86；核心板p1；底板p6、p7、p11；官方CST |
| 千兆以太网 | `RGMII_TXCK` | FPGA输出 | `F20` | Bank 2 | `LVCMOS33` | 复用 | `J0-70` | RTL8211F-CG；复用：RGMII；CST示例名 RGMII_GTXCLK | 已确认；Excel r87；核心板p1；底板p6、p7、p11；官方CST |
| 千兆以太网 | `RGMII_TXEN` | FPGA输出 | `F21` | Bank 2 | `LVCMOS33` | 复用 | `J0-72` | RTL8211F-CG；复用：RGMII；CST示例名 RGMII_TXEN | 已确认；Excel r88；核心板p1；底板p6、p7、p11；官方CST |
| 千兆以太网 | `RGMII_TXD3` | FPGA输出 | `E22` | Bank 2 | `LVCMOS33` | 复用 | `J0-74` | RTL8211F-CG；复用：RGMII；CST示例名 RGMII_TXD[3] | 已确认；Excel r89；核心板p1；底板p6、p7、p11；官方CST |
| 千兆以太网 | `RGMII_TXD2` | FPGA输出 | `D22` | Bank 2 | `LVCMOS33` | 复用 | `J0-76` | RTL8211F-CG；复用：RGMII；CST示例名 RGMII_TXD[2] | 已确认；Excel r90；核心板p1；底板p6、p7、p11；官方CST |
| 千兆以太网 | `RGMII_TXD1` | FPGA输出 | `E21` | Bank 2 | `LVCMOS33` | 复用 | `J0-78` | RTL8211F-CG；复用：RGMII；CST示例名 RGMII_TXD[1] | 已确认；Excel r91；核心板p1；底板p6、p7、p11；官方CST |
| 千兆以太网 | `RGMII_TXD0` | FPGA输出 | `D21` | Bank 2 | `LVCMOS33` | 复用 | `J0-80` | RTL8211F-CG；复用：RGMII；CST示例名 RGMII_TXD[0] | 已确认；Excel r92；核心板p1；底板p6、p7、p11；官方CST |
| 千兆以太网 | `EPHY_RST` | FPGA输出 | `W20` | Bank 8 | `LVCMOS33` | 复用 | `J2-19` | RTL8211F-CG；复用：RGMII；CST示例名 RGMII_RST_N | 已确认；Excel r93；核心板p1；底板p6、p7、p11；官方CST |
| Joy-Con | `JOYB_FC_3V3` | 未给出 | `H17` | Bank 4 | `LVCMOS33` | 复用 | `J0-52` | TXS0108E电平转换后到J19/J21；复用：FPGA侧3.3 V/接口侧1.8 V；CST示例名 Joycon_B[0] | 已确认；Excel r94；核心板p1；底板p6、p7、p14；官方CST |
| Joy-Con | `JOYB_TXD_3V3` | 未给出 | `H18` | Bank 4 | `LVCMOS33` | 复用 | `J0-54` | TXS0108E电平转换后到J19/J21；复用：FPGA侧3.3 V/接口侧1.8 V；CST示例名 Joycon_B[1] | 已确认；Excel r95；核心板p1；底板p6、p7、p14；官方CST |
| Joy-Con | `JOYB_RXD_3V3` | 未给出 | `J19` | Bank 5 | `LVCMOS33` | 复用 | `J0-56` | TXS0108E电平转换后到J19/J21；复用：FPGA侧3.3 V/接口侧1.8 V；CST示例名 Joycon_B[2] | 已确认；Excel r96；核心板p1；底板p6、p7、p14；官方CST |
| Joy-Con | `JOYB_RST_3V3` | 未给出 | `U8` | Bank 3 | `LVCMOS33` | 复用 | `J2-75` | TXS0108E电平转换后到J19/J21；复用：FPGA侧3.3 V/接口侧1.8 V；CST示例名 Joycon_B[3] | 已确认；Excel r97；核心板p1；底板p6、p7、p14；官方CST |
| Joy-Con | `JOYA_FC_3V3` | 未给出 | `H19` | Bank 5 | `LVCMOS33` | 复用 | `J0-58` | TXS0108E电平转换后到J19/J21；复用：FPGA侧3.3 V/接口侧1.8 V；CST示例名 Joycon_A[0] | 已确认；Excel r98；核心板p1；底板p6、p7、p14；官方CST |
| Joy-Con | `JOYA_TXD_3V3` | 未给出 | `H20` | Bank 5 | `LVCMOS33` | 复用 | `J0-62` | TXS0108E电平转换后到J19/J21；复用：FPGA侧3.3 V/接口侧1.8 V；CST示例名 Joycon_A[1] | 已确认；Excel r99；核心板p1；底板p6、p7、p14；官方CST |
| Joy-Con | `JOYA_RXD_3V3` | 未给出 | `G20` | Bank 5 | `LVCMOS33` | 复用 | `J0-64` | TXS0108E电平转换后到J19/J21；复用：FPGA侧3.3 V/接口侧1.8 V；CST示例名 Joycon_A[2] | 已确认；Excel r100；核心板p1；底板p6、p7、p14；官方CST |
| Joy-Con | `JOYA_RST_3V3` | 未给出 | `M17` | Bank 6 | `LVCMOS33` | 复用 | `J2-10` | TXS0108E电平转换后到J19/J21；复用：FPGA侧3.3 V/接口侧1.8 V；CST示例名 Joycon_A[3] | 已确认；Excel r101；核心板p1；底板p6、p7、p14；官方CST |
| USB-A软PHY | `FPGA_USB1_P` | 双向 | `M15` | Bank 5 | `LVCMOS33` | D+/D-成对；CST为LVCMOS33 | `J2-18` | USB-A接口/选择开关；复用：USB-Ax2切换；CST示例名 USB_1_P；原理图要求约束使用USB_A2侧物理脚并正确设置开关 | 已确认；Excel r102；核心板p1；底板p7、p9；官方CST |
| USB-A软PHY | `FPGA_USB1_N` | 双向 | `M16` | Bank 5 | `LVCMOS33` | D+/D-成对；CST为LVCMOS33 | `J2-16` | USB-A接口/选择开关；复用：USB-Ax2切换；CST示例名 USB_1_N；原理图要求约束使用USB_A2侧物理脚并正确设置开关 | 已确认；Excel r103；核心板p1；底板p7、p9；官方CST |
| USB-A软PHY | `FPGA_USB2_P` | 双向 | `H13` | Bank 4 | `LVCMOS33` | D+/D-成对；CST为LVCMOS33 | `J1-68` | USB-A接口/选择开关；复用：USB-Ax2切换；CST示例名 USB_2_P；原理图要求约束使用USB_A2侧物理脚并正确设置开关 | 已确认；Excel r104；核心板p1；底板p7、p9；官方CST |
| USB-A软PHY | `FPGA_USB2_N` | 双向 | `G13` | Bank 4 | `LVCMOS33` | D+/D-成对；CST为LVCMOS33 | `J1-66` | USB-A接口/选择开关；复用：USB-Ax2切换；CST示例名 USB_2_N；原理图要求约束使用USB_A2侧物理脚并正确设置开关 | 已确认；Excel r105；核心板p1；底板p7、p9；官方CST |
| HDMI/DVI差分线 | `DVI-A_D2.N` | 官方CST示例为FPGA输出 | `J17` | Bank 5 | 未给出 | 差分P/N | `J1-50` | 经100 nF串联电容到HDMI连接器J29；复用：DVI_DIR_SEL选择TX/RX通路；CST差分别名 tmds_d_p_0[2] N；31005原理图本身不证明60K接收模式可用 | 物理已确认；Excel r106；核心板p1、p4/5；底板p7、p15；官方CST |
| HDMI/DVI差分线 | `DVI-A_D2.P` | 官方CST示例为FPGA输出 | `K17` | Bank 5 | 未给出 | 差分P/N | `J1-52` | 经100 nF串联电容到HDMI连接器J29；复用：DVI_DIR_SEL选择TX/RX通路；CST差分别名 tmds_d_p_0[2] P；31005原理图本身不证明60K接收模式可用 | 物理已确认；Excel r107；核心板p1、p4/5；底板p7、p15；官方CST |
| HDMI/DVI差分线 | `DVI-A_D1.N` | 官方CST示例为FPGA输出 | `H15` | Bank 4 | 未给出 | 差分P/N | `J1-54` | 经100 nF串联电容到HDMI连接器J29；复用：DVI_DIR_SEL选择TX/RX通路；CST差分别名 tmds_d_p_0[1] N；31005原理图本身不证明60K接收模式可用 | 物理已确认；Excel r108；核心板p1、p4/5；底板p7、p15；官方CST |
| HDMI/DVI差分线 | `DVI-A_D1.P` | 官方CST示例为FPGA输出 | `J15` | Bank 4 | 未给出 | 差分P/N | `J1-56` | 经100 nF串联电容到HDMI连接器J29；复用：DVI_DIR_SEL选择TX/RX通路；CST差分别名 tmds_d_p_0[1] P；31005原理图本身不证明60K接收模式可用 | 物理已确认；Excel r109；核心板p1、p4/5；底板p7、p15；官方CST |
| HDMI/DVI差分线 | `DVI-A_D0.N` | 官方CST示例为FPGA输出 | `H14` | Bank 4 | 未给出 | 差分P/N | `J1-58` | 经100 nF串联电容到HDMI连接器J29；复用：DVI_DIR_SEL选择TX/RX通路；CST差分别名 tmds_d_p_0[0] N；31005原理图本身不证明60K接收模式可用 | 物理已确认；Excel r110；核心板p1、p4/5；底板p7、p15；官方CST |
| HDMI/DVI差分线 | `DVI-A_D0.P` | 官方CST示例为FPGA输出 | `J14` | Bank 4 | 未给出 | 差分P/N | `J1-60` | 经100 nF串联电容到HDMI连接器J29；复用：DVI_DIR_SEL选择TX/RX通路；CST差分别名 tmds_d_p_0[0] P；31005原理图本身不证明60K接收模式可用 | 物理已确认；Excel r111；核心板p1、p4/5；底板p7、p15；官方CST |
| HDMI/DVI差分线 | `DVI-A_CK.N` | 官方CST示例为FPGA输出 | `G16` | Bank 4 | 未给出 | 差分P/N | `J1-62` | 经100 nF串联电容到HDMI连接器J29；复用：DVI_DIR_SEL选择TX/RX通路；CST差分别名 tmds_clk_p_0 N；31005原理图本身不证明60K接收模式可用 | 物理已确认；Excel r112；核心板p1、p4/5；底板p7、p15；官方CST |
| HDMI/DVI差分线 | `DVI-A_CK.P` | 官方CST示例为FPGA输出 | `G15` | Bank 4 | 未给出 | 差分P/N | `J1-64` | 经100 nF串联电容到HDMI连接器J29；复用：DVI_DIR_SEL选择TX/RX通路；CST差分别名 tmds_clk_p_0 P；31005原理图本身不证明60K接收模式可用 | 物理已确认；Excel r113；核心板p1、p4/5；底板p7、p15；官方CST |
| HDMI控制 | `DVI-A_ALT` | FPGA输出 | `K14` | Bank 4 | 未给出 | 复用 | `J1-61` | 经R164(0Ω)到DVI_DIR_SEL；复用：方向选择；不是HDMI CEC；60K RX可用性仍需官方器件/例程确认 | 物理已确认；Excel r114；核心板p1、p4；底板p7、p15 |
| HDMI控制 | `DVI-A_HPD` | FPGA输入 | `K13` | Bank 4 | 未给出 | 否/未注明 | `J1-63` | HDMI J29 HPD，经R169下拉；原理图未用文字定义有效电平，故不作推断 | 物理已确认；Excel r115；核心板p1、p4；底板p7、p15 |
| HDMI DDC | `DVI_TWI1_SCL` | 双向/开漏 | `M13` | Bank 5 | 未给出 | 否/未注明 | `J2-32` | HDMI DDC电平转换 | 物理已确认；Excel r116；核心板p1；底板p7、p15 |
| HDMI DDC | `DVI_TWI1_SDA` | 双向/开漏 | `L13` | Bank 5 | 未给出 | 否/未注明 | `J2-34` | HDMI DDC电平转换 | 物理已确认；Excel r117；核心板p1；底板p7、p15 |
| PCIe控制 | `PCIE.RST` | FPGA输出 | `W11` | Bank 9 | 未给出 | 复用 | `J2-70` | 经Q18/Q15到PCIe插槽PERST#；复用：PCIe控制；逻辑极性和时序不可仅由网络名推断，需PCIe设计规范/例程确认 | 物理已确认；Excel r118；核心板p1、p5；底板p7、p13 |
| 测试点 | `TP24` | 未给出 | `Y14` | Bank 9 | 未给出 | 否/未注明 | `J2-52` | 底板测试点TP24；31005把UART RX放在J2-54；TP24位于J2-52，两者不要混淆 | 物理已确认；Excel r119；核心板p1、p5；底板p7 |
| FPGA ADC | `ADCT_N` | 模拟输入 | `N9` | ADC专用 | `专用ADC，非普通GPIO` | ADC专用差分 | `J2-92` | 差分ADC连接器J11-5；复用：ADCT或ADCV差分对；输入范围、采样率和时序未在原理图给出 | 已确认；Excel r120；核心板p1；核心板p5；底板p7、p19 |
| FPGA ADC | `ADCT_P` | 模拟输入 | `N10` | ADC专用 | `专用ADC，非普通GPIO` | ADC专用差分 | `J2-94` | 差分ADC连接器J11-6；复用：ADCT或ADCV差分对；输入范围、采样率和时序未在原理图给出 | 已确认；Excel r121；核心板p1；核心板p5；底板p7、p19 |
| FPGA ADC | `ADCV_N` | 模拟输入 | `M9` | ADC专用 | `专用ADC，非普通GPIO` | ADC专用差分 | `J2-96` | 差分ADC连接器J11-1；复用：ADCT或ADCV差分对；输入范围、采样率和时序未在原理图给出 | 已确认；Excel r122；核心板p1；核心板p5；底板p7、p19 |
| FPGA ADC | `ADCV_P` | 模拟输入 | `L10` | ADC专用 | `专用ADC，非普通GPIO` | ADC专用差分 | `J2-98` | 差分ADC连接器J11-2；复用：ADCT或ADCV差分对；输入范围、采样率和时序未在原理图给出 | 已确认；Excel r123；核心板p1；核心板p5；底板p7、p19 |
| CH569 HSPI/RGB LCD | `HD0` | 未给出 | `G17` | Bank 5 | 未给出 | 复用 | `J0-57` | CH569与RGB LCD共享数据总线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HD[0]；IO_TYPE未写 | 已确认；Excel r124；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HD1` | 未给出 | `H22` | Bank 5 | 未给出 | 复用 | `J0-51` | CH569与RGB LCD共享数据总线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HD[1]；IO_TYPE未写 | 已确认；Excel r125；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HD2` | 未给出 | `L14` | Bank 5 | 未给出 | 复用 | `J0-24` | CH569与RGB LCD共享数据总线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HD[2]；IO_TYPE未写 | 已确认；Excel r126；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HD3` | 未给出 | `K22` | Bank 5 | 未给出 | 复用 | `J0-47` | CH569与RGB LCD共享数据总线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HD[3]；IO_TYPE未写 | 已确认；Excel r127；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HD4` | 未给出 | `K21` | Bank 5 | 未给出 | 复用 | `J0-45` | CH569与RGB LCD共享数据总线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HD[4]；IO_TYPE未写 | 已确认；Excel r128；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HD5` | 未给出 | `K18` | Bank 5 | 未给出 | 复用 | `J0-48` | CH569与RGB LCD共享数据总线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HD[5]；IO_TYPE未写 | 已确认；Excel r129；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HD6` | 未给出 | `L21` | Bank 5 | 未给出 | 复用 | `J0-39` | CH569与RGB LCD共享数据总线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HD[6]；IO_TYPE未写 | 已确认；Excel r130；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HD7` | 未给出 | `M21` | Bank 5 | 未给出 | 复用 | `J0-37` | CH569与RGB LCD共享数据总线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HD[7]；IO_TYPE未写 | 已确认；Excel r131；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HD8` | 未给出 | `M22` | Bank 5 | 未给出 | 复用 | `J0-33` | CH569与RGB LCD共享数据总线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HD[8]；IO_TYPE未写 | 已确认；Excel r132；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HD9` | 未给出 | `N22` | Bank 5 | 未给出 | 复用 | `J0-31` | CH569与RGB LCD共享数据总线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HD[9]；IO_TYPE未写 | 已确认；Excel r133；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HD10` | 未给出 | `L18` | Bank 5 | 未给出 | 复用 | `J0-46` | CH569与RGB LCD共享数据总线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HD[10]；IO_TYPE未写 | 已确认；Excel r134；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HD11` | 未给出 | `M18` | Bank 5 | 未给出 | 复用 | `J0-44` | CH569与RGB LCD共享数据总线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HD[11]；IO_TYPE未写 | 已确认；Excel r135；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HD12` | 未给出 | `N19` | Bank 5 | 未给出 | 复用 | `J0-42` | CH569与RGB LCD共享数据总线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HD[12]；IO_TYPE未写 | 已确认；Excel r136；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HD13` | 未给出 | `N18` | Bank 5 | 未给出 | 复用 | `J0-40` | CH569与RGB LCD共享数据总线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HD[13]；IO_TYPE未写 | 已确认；Excel r137；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HD14` | 未给出 | `K16` | Bank 4 | 未给出 | 复用 | `J0-34` | CH569与RGB LCD共享数据总线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HD[14]；IO_TYPE未写 | 已确认；Excel r138；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HD15` | 未给出 | `L16` | Bank 4 | 未给出 | 复用 | `J0-32` | CH569与RGB LCD共享数据总线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HD[15]；IO_TYPE未写 | 已确认；Excel r139；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HTVLD` | 未给出 | `L15` | Bank 5 | 未给出 | 复用 | `J0-26` | CH569/RGB LCD控制线；复用：CH569_HSPI\|RGB_LCD；官方CST未覆盖该控制线 | 物理已确认；Excel r140；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HTREQ` | 未给出 | `N20` | Bank 5 | 未给出 | 复用 | `J0-28` | CH569/RGB LCD控制线；复用：CH569_HSPI\|RGB_LCD；官方CST未覆盖该控制线 | 物理已确认；Excel r141；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HCTS` | 未给出 | `M20` | Bank 5 | 未给出 | 复用 | `J0-30` | CH569/RGB LCD控制线；复用：CH569_HSPI\|RGB_LCD；官方CST未覆盖该控制线 | 物理已确认；Excel r142；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HTACK` | 未给出 | `L19` | Bank 5 | 未给出 | 复用 | `J0-41` | CH569/RGB LCD控制线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HTRDY | 已确认；Excel r143；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HTCLK` | 未给出 | `L20` | Bank 5 | 未给出 | 复用 | `J0-43` | CH569/RGB LCD控制线；复用：CH569_HSPI\|RGB_LCD；官方CST未覆盖该控制线 | 物理已确认；Excel r144；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HTRDY` | 未给出 | `J22` | Bank 5 | 未给出 | 复用 | `J0-49` | CH569/RGB LCD控制线；复用：CH569_HSPI\|RGB_LCD；官方CST未覆盖该控制线 | 物理已确认；Excel r145；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HRTS` | 未给出 | `K19` | Bank 5 | 未给出 | 复用 | `J0-50` | CH569/RGB LCD控制线；复用：CH569_HSPI\|RGB_LCD；官方CST未覆盖该控制线 | 物理已确认；Excel r146；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HRCLK` | 未给出 | `J20` | Bank 5 | 未给出 | 复用 | `J0-53` | CH569/RGB LCD控制线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HTCLK | 已确认；Excel r147；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HRACK` | 未给出 | `J21` | Bank 5 | 未给出 | 复用 | `J0-55` | CH569/RGB LCD控制线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HTREQ | 已确认；Excel r148；核心板p1；底板p6、p12、p21；官方CST |
| CH569 HSPI/RGB LCD | `HRVLD` | 未给出 | `G18` | Bank 5 | 未给出 | 复用 | `J0-59` | CH569/RGB LCD控制线；复用：CH569_HSPI\|RGB_LCD；CST示例名 HSPI_HTVLD | 已确认；Excel r149；核心板p1；底板p6、p12、p21；官方CST |
| RGB LCD | `LCD_DPI_BL` | FPGA输出 | `P20` | Bank 7 | `LVCMOS33` | 否/未注明 | `J0-36` | 背光驱动EN；CST示例名 LCD_BL | 已确认；Excel r150；核心板p1；底板p6、p12；官方CST |
| RGB LCD触摸/初始化 | `LCD.INT0` | 未给出 | `W16` | Bank 7 | `LVCMOS33` | 否/未注明 | `J2-39` | LCD/触摸连接器；CST示例名 LCD_CTP[0] | 已确认；Excel r151；核心板p1；底板p7、p12；官方CST |
| RGB LCD触摸/初始化 | `LCD.INT1` | 未给出 | `U16` | Bank 6 | `LVCMOS33` | 否/未注明 | `J2-41` | LCD/触摸连接器；CST示例名 LCD_CTP[1] | 已确认；Excel r152；核心板p1；底板p7、p12；官方CST |
| RGB LCD触摸/初始化 | `LCD.INT2` | 未给出 | `T16` | Bank 2 | `LVCMOS33` | 否/未注明 | `J2-43` | LCD/触摸连接器；CST示例名 LCD_CTP[2] | 已确认；Excel r153；核心板p1；底板p7、p12；官方CST |
| RGB LCD触摸/初始化 | `LCD.INT3` | 未给出 | `T15` | Bank 6 | `LVCMOS33` | 否/未注明 | `J2-45` | LCD/触摸连接器；CST示例名 LCD_CTP[3] | 已确认；Excel r154；核心板p1；底板p7、p12；官方CST |
## 8.1 外设开发方式与附加资料需求

| 外设/接口 | FPGA连接方式 | 中间器件 | 普通 Verilog 可控性 | 额外时钟/IP/数据手册 | CST 覆盖 |
| --- | --- | --- | --- | --- | --- |
| 用户按键/拨码 | 普通输入 | 上拉网络；具体见逐行表 | 可以 | 按键消抖由 RTL 处理；拨码有效电平待确认 | 按键部分覆盖；拨码未覆盖 |
| 风扇 J23 | EN、PWM 输出和 TACHO 输入 | 风扇电源控制电路 | 可以，但电气和频率要求不完整 | 需要风扇规格；PWM/TACHO 时序待确认 | 未覆盖 |
| WS2812/aRGB | 单线数据输出 | 转换到 5 V 侧 | 可以 | 需要 WS2812 时序资料 | 已覆盖，未写 IO_TYPE |
| 音频输出 | I2S 三线及功放使能 | PT8211-S、NS4263 | 可以 | 需 PT8211-S/NS4263 数据手册；采样率和格式待定 | 已覆盖 |
| 板载 UART | TX/RX | BL616，经 0 Ω | 可以 | 波特率由系统选择；RX 电气属性待确认 | TX 启用；RX 只有冲突注释 |
| DVP 摄像头 J15 | 8 位数据、PCLK、同步、控制和 I2C | 摄像头模块，示例名 OV5640 | 可以实现基础接口 | 需实际摄像头数据手册；图像处理可用厂商 IP | 主要信号已覆盖 |
| PMOD0/PMOD1 | 普通扩展 I/O | 无固定外设 | 可以 | 取决于外接模块 | PMOD0 以 LEDs 别名覆盖；PMOD1 未直接以 PMOD 名覆盖 |
| microSD J31/J10 | SDIO 网络；CST 提供 SPI 子集 | 与 BL616 共享 | SPI 模式可以 | 完整 SDIO/高速模式需协议和时序支持 | D0/CMD/D3/CLK 覆盖；D1/D2 未覆盖 |
| FPC10P J32/麦克风阵列 | 8 路 1.5 V I/O | 外接麦克风阵列/灯控器件 | 可以，但不得按 3.3 V 驱动 | 需外接模块数据手册和音频时钟定义 | 以 Mic Array 示例名覆盖 |
| 千兆以太网 | RGMII/MDIO/MDC/复位 | RTL8211F-CG PHY | 可自写 MAC，但复杂 | 需 RTL8211F-CG 数据手册；MAC/时钟可采用厂商 IP或官方例程 | CST 覆盖 8 个示例端口，其余见 Excel |
| Joy-Con | 3.3 V FPGA I/O | TXS0108E 转换到 1.8 V | 可控制接口线 | 需 Joy-Con 协议及 TXS0108E 使用条件 | 已覆盖 8 路示例信号 |
| USB-A 软 PHY | D+/D- 成对普通 I/O | 开关/连接器电路 | 物理层和协议实现复杂 | 需要 USB 协议、时序及官方软 PHY 例程 | 4 路信号已覆盖为 LVCMOS33 |
| HDMI/DVI | 4 组差分线、DDC、HPD、方向控制 | HDMI/DVI 接口电路 | TX 需差分输出、PLL和视频逻辑 | 建议使用高云高速 I/O/视频参考设计；RX 能力待确认 | CST 提供 TX 差分示例 |
| PCIe | SerDes 差分通道及复位 | PCIe 插槽/板级通路 | 不适合普通 GPIO RTL | 必须使用 60K SerDes/PCIe IP、参考时钟和官方例程 | 普通 CST 只覆盖部分控制；高速通道由专用资源管理 |
| FPGA ADC | 专用差分模拟输入 | 模拟输入网络 | 不能作为普通数字 GPIO | 需要高云 ADC IP、输入范围和采样配置资料 | 普通 CST 未覆盖 |
| CH569 HSPI/RGB LCD | 共享 16 位数据和控制线 | CH569、LCD/触摸接口 | 接口逻辑可写，但必须处理共享和协议 | 需 CH569、LCD/触摸器件资料；时钟定义待确认 | 20 个 CH569 示例端口及 LCD 控制部分已覆盖 |
| SDRAM/SDRAM1 | CST SDRAM 与底板复用网络关系待确认 | SDRAM 器件型号待确认 | 接口层可写，时序风险高 | 需要芯片数据手册、容量和时序；可使用控制器 IP | CST 有 38 个启用端口 |
| DDR3 | 专用 DDR PHY 接口 | 核心板 DDR3 芯片 | 不作为普通 GPIO RTL | 必须使用 Gowin DDR IP 和生成约束 | CST 当前启用 16 位数据接口 |

# 9. 约束文件完整整理

## 9.1 文件与语法

- 文件：`tang_mega_60K_pins.cst`。
- 格式：Gowin 物理约束文本，使用 `//` 注释。
- 工具：Gowin EDA/YunYuan。
- `IO_LOC "name" pin;` 绑定逻辑端口/对象与物理球位。
- `IO_PORT "name" IO_TYPE=... PULL_MODE=... DRIVE=... BANK_VCCIO=...;` 设置端口电气属性。
- `INS_LOC` 固定内部实例资源；`CLOCK_LOC` 固定时钟资源类型/位置。
- RTL 顶层端口名必须与所选启用约束中的引号内名称完全一致；若重命名 RTL 端口，约束名也必须同步重命名。

## 9.2 端口约束总表

| 约束端口名 | FPGA引脚 | IO类型 | 其他属性 | 对应硬件 | 核心板/底板 | 是否启用 | 资料来源 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `sys_clk` | `V22` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | 时钟/BANK7_V22_EMCCLK_50MHz | 核心板 | 启用 | CST SYS L3/L4；Excel r6 |
| `sys_rst_n` | `AA13` | `LVCMOS33` | PULL=UP；DRIVE=未设置；VCCIO=3.3 | 用户按键/EX_KEY.0 | 底板或板间接口 | 注释（不生效） | CST SYS L5/L6；Excel r18 |
| `sys_rst_n` | `AA13` | `LVCMOS15` | PULL=UP；DRIVE=未设置；VCCIO=1.5 | 用户按键/EX_KEY.0 | 底板或板间接口 | 启用 | CST SYS L5/L7；Excel r18 |
| `cmos_pwdn` | `AB22` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | DVP摄像头/CAM0_PWDN；PMOD1/PMOD1_IO3 | 底板或板间接口 | 启用 | CST OV5640 L10/L11；Excel r34,r59 |
| `cmos_rst_n` | `Y22` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | DVP摄像头/CAM0_RST；PMOD1/PMOD1_IO1 | 底板或板间接口 | 启用 | CST OV5640 L12/L13；Excel r32,r57 |
| `cmos_xclk` | `AA21` | `LVCMOS33` | PULL=NONE；DRIVE=4；VCCIO=3.3 | DVP摄像头/CAM0_MCLK；PMOD1/PMOD1_IO5 | 底板或板间接口 | 启用 | CST OV5640 L14/L15；Excel r36,r61 |
| `cmos_sda` | `Y13` | `LVCMOS33` | PULL=UP；DRIVE=8；VCCIO=3.3 | 摄像头I2C/CAM_TWI.SDA | 底板或板间接口 | 注释（不生效） | CST OV5640 L17/L18；Excel r46 |
| `cmos_sda` | `Y13` | `LVCMOS15` | PULL=UP；DRIVE=8；VCCIO=1.5 | 摄像头I2C/CAM_TWI.SDA | 底板或板间接口 | 启用 | CST OV5640 L17/L19；Excel r46 |
| `cmos_scl` | `AA14` | `LVCMOS33` | PULL=UP；DRIVE=8；VCCIO=3.3 | 摄像头I2C/CAM_TWI.SCL | 底板或板间接口 | 启用 | CST OV5640 L20/L21；Excel r47 |
| `cmos_db[7]` | `AA20` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | DVP摄像头/CAM0_D7；PMOD1/PMOD1_IO4 | 底板或板间接口 | 启用 | CST OV5640 L23/L24；Excel r37,r60 |
| `cmos_db[6]` | `AA19` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | DVP摄像头/CAM0_D6；PMOD1/PMOD1_IO6 | 底板或板间接口 | 启用 | CST OV5640 L25/L26；Excel r39,r62 |
| `cmos_db[5]` | `T20` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | DVP摄像头/CAM0_D5 | 底板或板间接口 | 启用 | CST OV5640 L27/L28；Excel r40 |
| `cmos_db[4]` | `N15` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | DVP摄像头/CAM0_D4 | 底板或板间接口 | 启用 | CST OV5640 L29/L30；Excel r41 |
| `cmos_db[3]` | `R14` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | DVP摄像头/CAM0_D3 | 底板或板间接口 | 启用 | CST OV5640 L31/L32；Excel r44 |
| `cmos_db[2]` | `R16` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | DVP摄像头/CAM0_D2 | 底板或板间接口 | 启用 | CST OV5640 L33/L34；Excel r42 |
| `cmos_db[1]` | `P15` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | DVP摄像头/CAM0_D1 | 底板或板间接口 | 启用 | CST OV5640 L35/L36；Excel r43 |
| `cmos_db[0]` | `P14` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | DVP摄像头/CAM0_D0 | 底板或板间接口 | 启用 | CST OV5640 L37/L38；Excel r45 |
| `cmos_pclk` | `AB20` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | DVP摄像头/CAM0_PCLK；PMOD1/PMOD1_IO7 | 底板或板间接口 | 启用 | CST OV5640 L39/L40；Excel r38,r63 |
| `cmos_href` | `AB21` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | DVP摄像头/CAM0_HSYNC；PMOD1/PMOD1_IO2 | 底板或板间接口 | 启用 | CST OV5640 L41/L42；Excel r35,r58 |
| `cmos_vsync` | `Y21` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | DVP摄像头/CAM0_VSYNC；PMOD1/PMOD1_IO0 | 底板或板间接口 | 启用 | CST OV5640 L43/L44；Excel r33,r56 |
| `tmds_d_p_0[0]` | `J14,H14` | `未设置` | PULL=NONE；DRIVE=3.5；VCCIO=3.3 | HDMI/DVI差分线/DVI-A_D0.P；HDMI/DVI差分线/DVI-A_D0.N | 底板或板间接口 | 启用 | CST HDMI L47/L48；Excel r111,r110 |
| `tmds_d_p_0[1]` | `J15,H15` | `未设置` | PULL=NONE；DRIVE=3.5；VCCIO=3.3 | HDMI/DVI差分线/DVI-A_D1.P；HDMI/DVI差分线/DVI-A_D1.N | 底板或板间接口 | 启用 | CST HDMI L49/L50；Excel r109,r108 |
| `tmds_d_p_0[2]` | `K17,J17` | `未设置` | PULL=NONE；DRIVE=3.5；VCCIO=3.3 | HDMI/DVI差分线/DVI-A_D2.P；HDMI/DVI差分线/DVI-A_D2.N | 底板或板间接口 | 启用 | CST HDMI L51/L52；Excel r107,r106 |
| `tmds_clk_p_0` | `G15,G16` | `未设置` | PULL=NONE；DRIVE=3.5；VCCIO=3.3 | HDMI/DVI差分线/DVI-A_CK.P；HDMI/DVI差分线/DVI-A_CK.N | 底板或板间接口 | 启用 | CST HDMI L53/L54；Excel r113,r112 |
| `RGMII_GTXCLK` | `F20` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | 千兆以太网/RGMII_TXCK | 底板或板间接口 | 启用 | CST ETHERNET L57/L65；Excel r87 |
| `PHY_CLK` | `V19` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | 千兆以太网/EPHY_CLK | 底板或板间接口 | 启用 | CST ETHERNET L58/L66；Excel r78 |
| `RGMII_TXD[0]` | `D21` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | 千兆以太网/RGMII_TXD0 | 底板或板间接口 | 启用 | CST ETHERNET L59/L67；Excel r92 |
| `RGMII_TXD[1]` | `E21` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | 千兆以太网/RGMII_TXD1 | 底板或板间接口 | 启用 | CST ETHERNET L60/L68；Excel r91 |
| `RGMII_TXD[2]` | `D22` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | 千兆以太网/RGMII_TXD2 | 底板或板间接口 | 启用 | CST ETHERNET L61/L69；Excel r90 |
| `RGMII_TXD[3]` | `E22` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | 千兆以太网/RGMII_TXD3 | 底板或板间接口 | 启用 | CST ETHERNET L62/L70；Excel r89 |
| `RGMII_TXEN` | `F21` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | 千兆以太网/RGMII_TXEN | 底板或板间接口 | 启用 | CST ETHERNET L63/L71；Excel r88 |
| `RGMII_RST_N` | `W20` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | 千兆以太网/EPHY_RST | 底板或板间接口 | 启用 | CST ETHERNET L64/L72；Excel r93 |
| `sd_miso` | `AA15` | `LVCMOS33` | PULL=NONE；DRIVE=OFF；VCCIO=3.3 | SD卡/FPGA_SDIO_D0\|SPI_MISO | 底板或板间接口 | 启用 | CST SDCARD L75/L79；Excel r64 |
| `sd_clk` | `V15` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | SD卡/FPGA_SDIO_CLK\|SPI_SCK | 底板或板间接口 | 启用 | CST SDCARD L76/L80；Excel r68 |
| `sd_cs` | `W15` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | SD卡/FPGA_SDIO_D3\|SPI_CS | 底板或板间接口 | 启用 | CST SDCARD L77/L81；Excel r67 |
| `sd_mosi` | `Y16` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | SD卡/FPGA_SDIO_CMD\|SPI_MOSI | 底板或板间接口 | 启用 | CST SDCARD L78/L82；Excel r66 |
| `HP_BCK` | `Y17` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | 音频I2S/I2S_BCLK | 底板或板间接口 | 启用 | CST AUDIO L85/L89；Excel r26 |
| `HP_WS` | `AB17` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | 音频I2S/I2S_LRCK | 底板或板间接口 | 启用 | CST AUDIO L86/L90；Excel r27 |
| `HP_DIN` | `AA16` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | 音频I2S/I2S_DIN | 底板或板间接口 | 启用 | CST AUDIO L87/L91；Excel r28 |
| `PA_EN` | `AB16` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | 音频功放/PA_EN | 底板或板间接口 | 启用 | CST AUDIO L88/L92；Excel r29 |
| `Key_in[1]` | `Y12` | `LVCMOS33` | PULL=UP；DRIVE=未设置；VCCIO=3.3 | 用户按键/EX_KEY.2 | 底板或板间接口 | 注释（不生效） | CST Keys L95/L96；Excel r20 |
| `Key_in[1]` | `Y12` | `LVCMOS15` | PULL=UP；DRIVE=未设置；VCCIO=1.5 | 用户按键/EX_KEY.2 | 底板或板间接口 | 启用 | CST Keys L95/L97；Excel r20 |
| `Key_in[0]` | `AB13` | `LVCMOS33` | PULL=UP；DRIVE=未设置；VCCIO=3.3 | 用户按键/EX_KEY.1 | 底板或板间接口 | 注释（不生效） | CST Keys L98/L99；Excel r19 |
| `Key_in[0]` | `AB13` | `LVCMOS15` | PULL=UP；DRIVE=未设置；VCCIO=1.5 | 用户按键/EX_KEY.1 | 底板或板间接口 | 启用 | CST Keys L98/L100；Excel r19 |
| `WS2812` | `J16` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | 灯带/WS2812 | 底板或板间接口 | 启用 | CST WS2812 L103/L104；Excel r25 |
| `sk9822_ck` | `W12` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | FPC10P/麦克风阵列/FPC10P_IO0 | 底板或板间接口 | 注释（不生效） | CST Mic Array L107/L108；Excel r70 |
| `sk9822_ck` | `W12` | `LVCMOS15` | PULL=NONE；DRIVE=8；VCCIO=1.5 | FPC10P/麦克风阵列/FPC10P_IO0 | 底板或板间接口 | 启用 | CST Mic Array L107/L109；Excel r70 |
| `sk9822_da` | `AA9` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | FPC10P/麦克风阵列/FPC10P_IO1 | 底板或板间接口 | 注释（不生效） | CST Mic Array L110/L111；Excel r71 |
| `sk9822_da` | `AA9` | `LVCMOS15` | PULL=NONE；DRIVE=8；VCCIO=1.5 | FPC10P/麦克风阵列/FPC10P_IO1 | 底板或板间接口 | 启用 | CST Mic Array L110/L112；Excel r71 |
| `mic_array_bck` | `Y11` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | FPC10P/麦克风阵列/FPC10P_IO7 | 底板或板间接口 | 注释（不生效） | CST Mic Array L113/L114；Excel r77 |
| `mic_array_bck` | `Y11` | `LVCMOS15` | PULL=NONE；DRIVE=8；VCCIO=1.5 | FPC10P/麦克风阵列/FPC10P_IO7 | 底板或板间接口 | 启用 | CST Mic Array L113/L115；Excel r77 |
| `mic_array_ws` | `W10` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | FPC10P/麦克风阵列/FPC10P_IO6 | 底板或板间接口 | 注释（不生效） | CST Mic Array L116/L117；Excel r76 |
| `mic_array_ws` | `W10` | `LVCMOS15` | PULL=NONE；DRIVE=8；VCCIO=1.5 | FPC10P/麦克风阵列/FPC10P_IO6 | 底板或板间接口 | 启用 | CST Mic Array L116/L118；Excel r76 |
| `mic_array_d[3]` | `AB11` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | FPC10P/麦克风阵列/FPC10P_IO5 | 底板或板间接口 | 注释（不生效） | CST Mic Array L119/L120；Excel r75 |
| `mic_array_d[3]` | `AB11` | `LVCMOS15` | PULL=NONE；DRIVE=8；VCCIO=1.5 | FPC10P/麦克风阵列/FPC10P_IO5 | 底板或板间接口 | 启用 | CST Mic Array L119/L121；Excel r75 |
| `mic_array_d[2]` | `AA11` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | FPC10P/麦克风阵列/FPC10P_IO4 | 底板或板间接口 | 注释（不生效） | CST Mic Array L122/L123；Excel r74 |
| `mic_array_d[2]` | `AA11` | `LVCMOS15` | PULL=NONE；DRIVE=8；VCCIO=1.5 | FPC10P/麦克风阵列/FPC10P_IO4 | 底板或板间接口 | 启用 | CST Mic Array L122/L124；Excel r74 |
| `mic_array_d[1]` | `AB10` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | FPC10P/麦克风阵列/FPC10P_IO3 | 底板或板间接口 | 注释（不生效） | CST Mic Array L125/L126；Excel r73 |
| `mic_array_d[1]` | `AB10` | `LVCMOS15` | PULL=NONE；DRIVE=8；VCCIO=1.5 | FPC10P/麦克风阵列/FPC10P_IO3 | 底板或板间接口 | 启用 | CST Mic Array L125/L127；Excel r73 |
| `mic_array_d[0]` | `AA10` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | FPC10P/麦克风阵列/FPC10P_IO2 | 底板或板间接口 | 注释（不生效） | CST Mic Array L128/L129；Excel r72 |
| `mic_array_d[0]` | `AA10` | `LVCMOS15` | PULL=NONE；DRIVE=8；VCCIO=1.5 | FPC10P/麦克风阵列/FPC10P_IO2 | 底板或板间接口 | 启用 | CST Mic Array L128/L130；Excel r72 |
| `LEDs[0]` | `T18` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | PMOD0/PMOD0_IO7 | 底板或板间接口 | 启用 | CST LEDS L133/L142；Excel r55 |
| `LEDs[1]` | `R18` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | PMOD0/PMOD0_IO6 | 底板或板间接口 | 启用 | CST LEDS L134/L143；Excel r54 |
| `LEDs[2]` | `R17` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | PMOD0/PMOD0_IO5 | 底板或板间接口 | 启用 | CST LEDS L135/L144；Excel r53 |
| `LEDs[3]` | `P16` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | PMOD0/PMOD0_IO4 | 底板或板间接口 | 启用 | CST LEDS L136/L145；Excel r52 |
| `LEDs[4]` | `U21` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | PMOD0/PMOD0_IO3 | 底板或板间接口 | 启用 | CST LEDS L137/L146；Excel r51 |
| `LEDs[5]` | `T21` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | PMOD0/PMOD0_IO2 | 底板或板间接口 | 启用 | CST LEDS L138/L147；Excel r50 |
| `LEDs[6]` | `R19` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | PMOD0/PMOD0_IO1 | 底板或板间接口 | 启用 | CST LEDS L139/L148；Excel r49 |
| `LEDs[7]` | `P19` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | PMOD0/PMOD0_IO0 | 底板或板间接口 | 启用 | CST LEDS L140/L149；Excel r48 |
| `USB_1_P` | `M15` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | USB-A软PHY/FPGA_USB1_P | 底板或板间接口 | 启用 | CST USBA L152/L157；Excel r102 |
| `USB_1_N` | `M16` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | USB-A软PHY/FPGA_USB1_N | 底板或板间接口 | 启用 | CST USBA L153/L158；Excel r103 |
| `USB_2_P` | `H13` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | USB-A软PHY/FPGA_USB2_P | 底板或板间接口 | 启用 | CST USBA L154/L159；Excel r104 |
| `USB_2_N` | `G13` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | USB-A软PHY/FPGA_USB2_N | 底板或板间接口 | 启用 | CST USBA L155/L160；Excel r105 |
| `Joycon_A[0]` | `H19` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | Joy-Con/JOYA_FC_3V3 | 底板或板间接口 | 启用 | CST JoyConA L163/L168；Excel r98 |
| `Joycon_A[1]` | `H20` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | Joy-Con/JOYA_TXD_3V3 | 底板或板间接口 | 启用 | CST JoyConA L164/L169；Excel r99 |
| `Joycon_A[2]` | `G20` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | Joy-Con/JOYA_RXD_3V3 | 底板或板间接口 | 启用 | CST JoyConA L165/L170；Excel r100 |
| `Joycon_A[3]` | `M17` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | Joy-Con/JOYA_RST_3V3 | 底板或板间接口 | 启用 | CST JoyConA L166/L171；Excel r101 |
| `Joycon_B[0]` | `H17` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | Joy-Con/JOYB_FC_3V3 | 底板或板间接口 | 启用 | CST JoyConB L174/L179；Excel r94 |
| `Joycon_B[1]` | `H18` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | Joy-Con/JOYB_TXD_3V3 | 底板或板间接口 | 启用 | CST JoyConB L175/L180；Excel r95 |
| `Joycon_B[2]` | `J19` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | Joy-Con/JOYB_RXD_3V3 | 底板或板间接口 | 启用 | CST JoyConB L176/L181；Excel r96 |
| `Joycon_B[3]` | `U8` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | Joy-Con/JOYB_RST_3V3 | 底板或板间接口 | 启用 | CST JoyConB L177/L182；Excel r97 |
| `LCD_CTP[0]` | `W16` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | RGB LCD触摸/初始化/LCD.INT0 | 底板或板间接口 | 启用 | CST LCD L185/L191；Excel r151 |
| `LCD_CTP[1]` | `U16` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | RGB LCD触摸/初始化/LCD.INT1 | 底板或板间接口 | 启用 | CST LCD L186/L192；Excel r152 |
| `LCD_CTP[2]` | `T16` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | RGB LCD触摸/初始化/LCD.INT2 | 底板或板间接口 | 启用 | CST LCD L187/L193；Excel r153 |
| `LCD_CTP[3]` | `T15` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | RGB LCD触摸/初始化/LCD.INT3 | 底板或板间接口 | 启用 | CST LCD L188/L194；Excel r154 |
| `LCD_BL` | `P20` | `LVCMOS33` | PULL=NONE；DRIVE=未设置；VCCIO=3.3 | RGB LCD/LCD_DPI_BL | 底板或板间接口 | 启用 | CST LCD L189/L195；Excel r150 |
| `txp` | `U15` | `LVCMOS33` | PULL=UP；DRIVE=8；VCCIO=3.3 | UART/FPGA_UART.TX | 底板或板间接口 | 启用 | CST UART L198/L199；Excel r30 |
| `rxp` | `Y14` | `LVCMOS15` | PULL=NONE；DRIVE=OFF；VCCIO=1.5 | 测试点/TP24 | 底板或板间接口 | 注释（不生效） | CST UART L201/L202；Excel r119 |
| `rxp` | `V14` | `LVCMOS15` | PULL=NONE；DRIVE=OFF；VCCIO=3.3 | UART/FPGA_UART.RX | 底板或板间接口 | 注释（不生效） | CST UART L204/L205；Excel r31 |
| `HSPI_HTCLK` | `J20` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CH569 HSPI/RGB LCD/HRCLK | 底板或板间接口 | 启用 | CST CH569 L208/L209；Excel r147 |
| `HSPI_HTREQ` | `J21` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CH569 HSPI/RGB LCD/HRACK | 底板或板间接口 | 启用 | CST CH569 L210/L211；Excel r148 |
| `HSPI_HTRDY` | `L19` | `未设置` | PULL=DOWN；DRIVE=OFF；VCCIO=3.3 | CH569 HSPI/RGB LCD/HTACK | 底板或板间接口 | 启用 | CST CH569 L212/L213；Excel r143 |
| `HSPI_HTVLD` | `G18` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CH569 HSPI/RGB LCD/HRVLD | 底板或板间接口 | 启用 | CST CH569 L214/L215；Excel r149 |
| `HSPI_HD[0]` | `G17` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CH569 HSPI/RGB LCD/HD0 | 底板或板间接口 | 启用 | CST CH569 L217/L218；Excel r124 |
| `HSPI_HD[1]` | `H22` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CH569 HSPI/RGB LCD/HD1 | 底板或板间接口 | 启用 | CST CH569 L219/L220；Excel r125 |
| `HSPI_HD[2]` | `L14` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CH569 HSPI/RGB LCD/HD2 | 底板或板间接口 | 启用 | CST CH569 L221/L222；Excel r126 |
| `HSPI_HD[3]` | `K22` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CH569 HSPI/RGB LCD/HD3 | 底板或板间接口 | 启用 | CST CH569 L223/L224；Excel r127 |
| `HSPI_HD[4]` | `K21` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CH569 HSPI/RGB LCD/HD4 | 底板或板间接口 | 启用 | CST CH569 L225/L226；Excel r128 |
| `HSPI_HD[5]` | `K18` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CH569 HSPI/RGB LCD/HD5 | 底板或板间接口 | 启用 | CST CH569 L227/L228；Excel r129 |
| `HSPI_HD[6]` | `L21` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CH569 HSPI/RGB LCD/HD6 | 底板或板间接口 | 启用 | CST CH569 L229/L230；Excel r130 |
| `HSPI_HD[7]` | `M21` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CH569 HSPI/RGB LCD/HD7 | 底板或板间接口 | 启用 | CST CH569 L231/L232；Excel r131 |
| `HSPI_HD[8]` | `M22` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CH569 HSPI/RGB LCD/HD8 | 底板或板间接口 | 启用 | CST CH569 L233/L234；Excel r132 |
| `HSPI_HD[9]` | `N22` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CH569 HSPI/RGB LCD/HD9 | 底板或板间接口 | 启用 | CST CH569 L235/L236；Excel r133 |
| `HSPI_HD[10]` | `L18` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CH569 HSPI/RGB LCD/HD10 | 底板或板间接口 | 启用 | CST CH569 L237/L238；Excel r134 |
| `HSPI_HD[11]` | `M18` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CH569 HSPI/RGB LCD/HD11 | 底板或板间接口 | 启用 | CST CH569 L239/L240；Excel r135 |
| `HSPI_HD[12]` | `N19` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CH569 HSPI/RGB LCD/HD12 | 底板或板间接口 | 启用 | CST CH569 L241/L242；Excel r136 |
| `HSPI_HD[13]` | `N18` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CH569 HSPI/RGB LCD/HD13 | 底板或板间接口 | 启用 | CST CH569 L243/L244；Excel r137 |
| `HSPI_HD[14]` | `K16` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CH569 HSPI/RGB LCD/HD14 | 底板或板间接口 | 启用 | CST CH569 L245/L246；Excel r138 |
| `HSPI_HD[15]` | `L16` | `未设置` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CH569 HSPI/RGB LCD/HD15 | 底板或板间接口 | 启用 | CST CH569 L247/L248；Excel r139 |
| `sdram_dqm[1]` | `F13` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L251/L252；Excel 未逐脚收录 |
| `sdram_dqm[0]` | `F14` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L253/L254；Excel 未逐脚收录 |
| `sdram_clk` | `B17` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L256/L257；Excel 未逐脚收录 |
| `sdram_cas` | `E17` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L258/L259；Excel 未逐脚收录 |
| `sdram_ras` | `F16` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L260/L261；Excel 未逐脚收录 |
| `sdram_we` | `D16` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L262/L263；Excel 未逐脚收录 |
| `sdram_cs` | `F19` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L264/L265；Excel 未逐脚收录 |
| `sdram_ba[1]` | `C20` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L266/L267；Excel 未逐脚收录 |
| `sdram_ba[0]` | `F15` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L268/L269；Excel 未逐脚收录 |
| `sdram_adr[12]` | `B18` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L271/L272；Excel 未逐脚收录 |
| `sdram_adr[11]` | `D17` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L273/L274；Excel 未逐脚收录 |
| `sdram_adr[10]` | `D20` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L275/L276；Excel 未逐脚收录 |
| `sdram_adr[9]` | `C17` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L277/L278；Excel 未逐脚收录 |
| `sdram_adr[8]` | `A18` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L279/L280；Excel 未逐脚收录 |
| `sdram_adr[7]` | `A19` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L281/L282；Excel 未逐脚收录 |
| `sdram_adr[6]` | `D14` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L283/L284；Excel 未逐脚收录 |
| `sdram_adr[5]` | `D15` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L285/L286；Excel 未逐脚收录 |
| `sdram_adr[4]` | `E16` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L287/L288；Excel 未逐脚收录 |
| `sdram_adr[3]` | `C18` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L289/L290；Excel 未逐脚收录 |
| `sdram_adr[2]` | `C19` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L291/L292；Excel 未逐脚收录 |
| `sdram_adr[1]` | `E19` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L293/L294；Excel 未逐脚收录 |
| `sdram_adr[0]` | `D19` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L295/L296；Excel 未逐脚收录 |
| `sdram_dq[15]` | `B16` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L298/L299；Excel 未逐脚收录 |
| `sdram_dq[14]` | `B15` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L300/L301；Excel 未逐脚收录 |
| `sdram_dq[13]` | `A16` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L302/L303；Excel 未逐脚收录 |
| `sdram_dq[12]` | `A15` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L304/L305；Excel 未逐脚收录 |
| `sdram_dq[11]` | `A20` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L306/L307；Excel 未逐脚收录 |
| `sdram_dq[10]` | `B20` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L308/L309；Excel 未逐脚收录 |
| `sdram_dq[9]` | `A21` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L310/L311；Excel 未逐脚收录 |
| `sdram_dq[8]` | `B21` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L312/L313；Excel 未逐脚收录 |
| `sdram_dq[7]` | `A13` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L314/L315；Excel 未逐脚收录 |
| `sdram_dq[6]` | `A14` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L316/L317；Excel 未逐脚收录 |
| `sdram_dq[5]` | `C13` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L318/L319；Excel 未逐脚收录 |
| `sdram_dq[4]` | `B13` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L320/L321；Excel 未逐脚收录 |
| `sdram_dq[3]` | `C14` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L322/L323；Excel 未逐脚收录 |
| `sdram_dq[2]` | `C15` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L324/L325；Excel 未逐脚收录 |
| `sdram_dq[1]` | `E13` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L326/L327；Excel 未逐脚收录 |
| `sdram_dq[0]` | `E14` | `LVCMOS33` | PULL=NONE；DRIVE=8；VCCIO=3.3 | CST 标注 SDRAM；与 Excel 的 SDRAM1 是否同一器件待确认 | 待确认 | 启用 | CST SDRAM L328/L329；Excel 未逐脚收录 |
| `ddr_bank[2]` | `M6` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L332/L333；Excel 未逐脚收录 |
| `ddr_bank[1]` | `P2` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L334/L335；Excel 未逐脚收录 |
| `ddr_bank[0]` | `P5` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L336/L337；Excel 未逐脚收录 |
| `ddr_addr[15]` | `R1` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L339/L340；Excel 未逐脚收录 |
| `ddr_addr[14]` | `D1` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L341/L342；Excel 未逐脚收录 |
| `ddr_addr[13]` | `K1` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L343/L344；Excel 未逐脚收录 |
| `ddr_addr[12]` | `K4` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L345/L346；Excel 未逐脚收录 |
| `ddr_addr[11]` | `H3` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L347/L348；Excel 未逐脚收录 |
| `ddr_addr[10]` | `L1` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L349/L350；Excel 未逐脚收录 |
| `ddr_addr[9]` | `H5` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L351/L352；Excel 未逐脚收录 |
| `ddr_addr[8]` | `J5` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L353/L354；Excel 未逐脚收录 |
| `ddr_addr[7]` | `J1` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L355/L356；Excel 未逐脚收录 |
| `ddr_addr[6]` | `G3` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L357/L358；Excel 未逐脚收录 |
| `ddr_addr[5]` | `H2` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L359/L360；Excel 未逐脚收录 |
| `ddr_addr[4]` | `J2` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L361/L362；Excel 未逐脚收录 |
| `ddr_addr[3]` | `J4` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L363/L364；Excel 未逐脚收录 |
| `ddr_addr[2]` | `G2` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L365/L366；Excel 未逐脚收录 |
| `ddr_addr[1]` | `K2` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L367/L368；Excel 未逐脚收录 |
| `ddr_addr[0]` | `M1` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L369/L370；Excel 未逐脚收录 |
| `ddr_odt` | `M2` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L372/L373；Excel 未逐脚收录 |
| `ddr_cke` | `K6` | `SSTL15_I` | PULL=NONE；DRIVE=8；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L374/L375；Excel 未逐脚收录 |
| `ddr_we` | `M5` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L376/L377；Excel 未逐脚收录 |
| `ddr_cas` | `L4` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L378/L379；Excel 未逐脚收录 |
| `ddr_ras` | `L5` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L380/L381；Excel 未逐脚收录 |
| `ddr_cs` | `P4` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L382/L383；Excel 未逐脚收录 |
| `ddr_reset_n` | `L6` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L384/L385；Excel 未逐脚收录 |
| `ddr_ck` | `L3,K3` | `SSTL15D_I` | PULL=NONE；DRIVE=8；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L386/L387；Excel 未逐脚收录 |
| `ddr_dm[3]` | `W1` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L388/L389；Excel 未逐脚收录 |
| `ddr_dm[2]` | `T6` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L390/L391；Excel 未逐脚收录 |
| `ddr_dm[1]` | `V7` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L392/L393；Excel 未逐脚收录 |
| `ddr_dm[0]` | `AA4` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L394/L395；Excel 未逐脚收录 |
| `ddr_dq[31]` | `Y2` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L397/L398；Excel 未逐脚收录 |
| `ddr_dq[30]` | `U1` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L399/L400；Excel 未逐脚收录 |
| `ddr_dq[29]` | `V2` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L401/L402；Excel 未逐脚收录 |
| `ddr_dq[28]` | `U2` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L403/L404；Excel 未逐脚收录 |
| `ddr_dq[27]` | `U3` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L405/L406；Excel 未逐脚收录 |
| `ddr_dq[26]` | `T1` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L407/L408；Excel 未逐脚收录 |
| `ddr_dq[25]` | `Y1` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L409/L410；Excel 未逐脚收录 |
| `ddr_dq[24]` | `W2` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L411/L412；Excel 未逐脚收录 |
| `ddr_dq[23]` | `T5` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L413/L414；Excel 未逐脚收录 |
| `ddr_dq[22]` | `V5` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L415/L416；Excel 未逐脚收录 |
| `ddr_dq[21]` | `T4` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L417/L418；Excel 未逐脚收录 |
| `ddr_dq[20]` | `Y6` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L419/L420；Excel 未逐脚收录 |
| `ddr_dq[19]` | `R4` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L421/L422；Excel 未逐脚收录 |
| `ddr_dq[18]` | `U6` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L423/L424；Excel 未逐脚收录 |
| `ddr_dq[17]` | `R6` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L425/L426；Excel 未逐脚收录 |
| `ddr_dq[16]` | `U5` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L427/L428；Excel 未逐脚收录 |
| `ddr_dq[15]` | `Y9` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L429/L430；Excel 未逐脚收录 |
| `ddr_dq[14]` | `AB6` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L431/L432；Excel 未逐脚收录 |
| `ddr_dq[13]` | `W9` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L433/L434；Excel 未逐脚收录 |
| `ddr_dq[12]` | `AB8` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L435/L436；Excel 未逐脚收录 |
| `ddr_dq[11]` | `Y7` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L437/L438；Excel 未逐脚收录 |
| `ddr_dq[10]` | `AB7` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L439/L440；Excel 未逐脚收录 |
| `ddr_dq[9]` | `Y8` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L441/L442；Excel 未逐脚收录 |
| `ddr_dq[8]` | `AA8` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L443/L444；Excel 未逐脚收录 |
| `ddr_dq[7]` | `AB1` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L445/L446；Excel 未逐脚收录 |
| `ddr_dq[6]` | `AB5` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L447/L448；Excel 未逐脚收录 |
| `ddr_dq[5]` | `AB2` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L449/L450；Excel 未逐脚收录 |
| `ddr_dq[4]` | `AA1` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L451/L452；Excel 未逐脚收录 |
| `ddr_dq[3]` | `V4` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L453/L454；Excel 未逐脚收录 |
| `ddr_dq[2]` | `AA5` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L455/L456；Excel 未逐脚收录 |
| `ddr_dq[1]` | `AB3` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L457/L458；Excel 未逐脚收录 |
| `ddr_dq[0]` | `Y4` | `SSTL15_I` | PULL=NONE；DRIVE=12；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L459/L460；Excel 未逐脚收录 |
| `ddr_dqs[3]` | `R3,R2` | `SSTL15D_I` | PULL=NONE；DRIVE=8；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L462/L463；Excel 未逐脚收录 |
| `ddr_dqs[2]` | `W6,W5` | `SSTL15D_I` | PULL=NONE；DRIVE=8；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 注释（不生效） | CST DDR3 L464/L465；Excel 未逐脚收录 |
| `ddr_dqs[1]` | `V9,V8` | `SSTL15D_I` | PULL=NONE；DRIVE=8；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L466/L467；Excel 未逐脚收录 |
| `ddr_dqs[0]` | `Y3,AA3` | `SSTL15D_I` | PULL=NONE；DRIVE=8；VCCIO=1.5 | 核心板 DDR3 接口（芯片型号待确认） | 核心板 | 启用 | CST DDR3 L468/L469；Excel 未逐脚收录 |

## 9.3 非端口物理约束

| 状态 | 指令 | 对象 | 位置/属性 | 说明 |
| --- | --- | --- | --- | --- |
| 启用 | `INS_LOC` | `camera_hdmi_inst/u_ddr3/gw3_top/u_ddr_phy_top/u_dll` | `DDRDLLM_BL` | 依赖示例工程层次和 DDR IP 实例名 |
| 启用 | `INS_LOC` | `camera_hdmi_inst/u_ddr3/gw3_top/u_ddr_phy_top/fclkdiv` | `BOTTOMSIDE[3]` | 依赖示例工程层次 |
| 启用 | `INS_LOC` | `camera_hdmi_inst/Gowin_PLL_m0/PLLA_inst` | `PLL_B[1]` | 依赖实例名 |
| 启用 | `INS_LOC` | `camera_hdmi_inst/u_tmds_pll/PLLA_inst` | `PLL_R[0]` | 依赖实例名 |
| 启用 | `INS_LOC` | `eth_inst/GMII_pll_m0/PLLA_inst` | `PLL_R[1]` | 依赖实例名 |
| 启用 | `INS_LOC` | `sdram_inst/SDRAM_PLL/PLLA_inst` | `PLL_T[0]` | 依赖实例名 |
| 启用 | `CLOCK_LOC` | `divclk` | `LOCAL_CLOCK` | 不是频率约束 |
| 启用 | `CLOCK_LOC` | `sdram_inst/clk_133M` | `BUFG = CLK` | 名称包含 133M，但仍应由工程时序/IP确认频率 |
| 启用 | `CLOCK_LOC` | `cmos_vsync_d` | `LOCAL_CLOCK` | 不是频率约束 |
| 注释 | `SET_PARAM` | DDR DLL 实例 | `CLKIN_SEL=CLKIN5` | 当前不生效 |

# 10. 原理图与约束文件交叉检查

| 检查项 | 结果 | 证据/处理 |
| --- | --- | --- |
| FPGA 完整型号 | 用户确认 IDE 为 `GW5AT-LV60PG484AC1/I0`；原理图符号为 `GW5AT-60K-PG484A` | Excel `资料与版本!B7:C8`；保留命名差异 |
| 封装 | IDE 为 `PBG484A`；原理图符号中为 `PG484A` | 不自行判定等价；工程按用户确认值 |
| 主时钟 | V22 一致；Excel明确 50 MHz；CST 端口为 `sys_clk` | Excel r6；CST SYS 段 |
| 用户按键 | AA13/AB13/Y12 与 CST `sys_rst_n`、`Key_in[0]`、`Key_in[1]` 一致 | Excel r18-r20；CST SYS/Keys 段 |
| 离散用户 LED | CST `LEDs[0..7]` 实为 PMOD0/SDRAM1 复用别名，不是板载 LED | 用户截图；Excel r48-r55；CST LEDS 段 |
| UART TX | U15 一致 | Excel r30；CST `txp` |
| UART RX | V14 物理连接明确，但 CST 对应项被注释且 IO 属性冲突 | Excel r31；CST UART 注释 |
| HDMI 差分线 | 8 个 N/P 球位可由 Excel 与 CST 对应 | Excel r106-r113；CST HDMI 段；RX 能力仍待确认 |
| DDR3 差分 CK/DQS | CST 明确差分球位；Excel未逐脚转录 | 以 CST 为物理约束来源；芯片信息待确认 |
| IO 电压 | 端口有 CST 时采用 CST；Bank 9 的 1.5 V 安全规则明确 | 不用 Excel Bank 字段反推其他端口 |
| 原理图有而 CST 无 | JTAG、RECONFIG、DONE、READY、USR_CLK_IN、部分 SDIO、风扇、ADC、PCIe/SerDes 等存在 | 可能是专用资源或未提供示例；见第 8 节 |
| CST 有而 Excel未逐项收录 | DDR3、SDRAM，以及 `LEDs[]` 别名 | DDR/SDRAM见待确认；`LEDs[]` 已按球位映射回 PMOD0 |
| CST 内部实例约束 | 依赖官方示例层次，不可无条件复制 | 第 9.3 节 |

# 11. 资料冲突

## 资料冲突

| 项目 | 来源一 | 来源二 | 处理 |
| --- | --- | --- | --- |
| 底板连接器旁球位 | 31005 底板原图使用 138K 的 `BANKx_球位` 标签 | 30354 核心板按同一 J0/J1/J2 针号给出 60K 球位 | 只用 BTB 针号回查出的 60K 球位；底板球位标签禁止写入 60K CST |
| UART RX IOSTANDARD | 原理图链路/Excel确认 V14 为 `FPGA_UART.RX`，但未确认 IO 标准 | CST 注释把 V14 写成 `LVCMOS15` 且 `BANK_VCCIO=3.3` | 保留 V14 物理连接；IOSTANDARD 待确认，不启用冲突行 |
| `USR_CLK_IN` 球位 | 31005 J2-88 + 30354 J2-88 得到 V13 | 一份辅助说明曾写 31005 以后为 V10 | 本文列为冲突；当前物理链路记录 V13，使用前建议实测或官方例程复核 |
| `sys_rst_n` 含义 | 硬件网络 AA13 是 `EX_KEY.0`/USER_BUTTON0 | 官方 CST 示例端口名写 `sys_rst_n` | 视为 RTL 示例别名，不当作 RECONFIG 或 CPU_RESET |
| DVI 接收模式 | 底板有 `DVI_DIR_SEL`：1=TX，0=RX | 官方 60K CST 只提供 TX 示例，现有资料不能证明 RX 模式可用 | 保留物理线，RX 功能待官方资料/实测确认 |
| FPGA/封装名称 | 核心板符号 `GW5AT-60K-PG484A` | 用户确认 IDE `GW5AT-LV60PG484AC1/I0`、`PBG484A`、Version B | 不覆盖任一来源；工程按已确认 IDE 选择，命名差异保留 |
| `LEDs[0..7]` 名称 | CST 段名和端口名看似 LED | Excel r48-r55 与用户截图表明对应 PMOD0/SDRAM1 复用线 | 明确不是板载 8 LED；不得据名称推断颜色/有效电平 |

# 12. 待用户确认

## 待用户确认

- 核心板是否存在独立 PCB Rev 标识。
- `C1/I0` 的官方速度/温度等级解释。
- DDR3、SDRAM、配置 Flash 的完整芯片型号、容量、位宽和实物焊接状态。
- CST 的 SDRAM 段是否就是底板网络 `SDRAM1`，以及对应器件位置。
- 板载 USB 下载/调试器的具体芯片型号和 USB 接口名称。
- UART RX V14 应采用的最终 `IO_TYPE`、上拉和驱动属性。
- `USR_CLK_IN` 的最终实测球位，以及 MS5351 CKO0/1/2 的实际配置频率。
- HDMI/DVI 的 60K 接收模式是否由官方例程支持。
- I2S 采样率、位宽、左右对齐方式和 PT8211-S 时序。
- ADC 输入范围、采样率、端接和所需 ADC IP 配置。
- FAN_PWM0/FAN_TACHO 的电气和时序要求。
- 底板资料中出现的选配功能是否全部焊接在当前基础套装实物上。

# 13. 后续开发快速查询表

## 常用资源快速查询

| 功能 | RTL 建议端口名 | FPGA 引脚 | IO 标准 | 有效电平/频率 | 来源 |
| --- | --- | --- | --- | --- | --- |
| 主时钟 | `sys_clk` | V22 | `LVCMOS33` | 50 MHz | Excel r6；CST SYS 段 |
| 用户逻辑复位 | `sys_rst_n` 或 `user_btn0_n` | AA13 | `LVCMOS15`，`PULL_MODE=UP` | 低有效 | Excel r18；CST SYS 段 |
| 用户按键 1 | `user_btn1_n` | AB13 | `LVCMOS15`，`PULL_MODE=UP` | 低有效 | Excel r19；CST `Key_in[0]` |
| 用户按键 2 | `user_btn2_n` | Y12 | `LVCMOS15`，`PULL_MODE=UP` | 低有效 | Excel r20；CST `Key_in[1]` |
| 用户 RGB 灯 | `ws2812_dout` | J16 | CST 未写 `IO_TYPE`；3.3 V、DRIVE 8 | WS2812 串行协议；静态有效电平不适用 | Excel r25；CST WS2812 段 |
| 离散用户 LED | 不适用/待外接 PMOD 模块 | 无已确认板载离散 LED | 不适用 | 不适用 | `LEDs[0..7]` 不是板载 LED |
| UART TX | `uart_tx` | U15 | `LVCMOS33`，UP，DRIVE 8 | 空闲高；波特率由 RTL 决定 | Excel r30；CST `txp` |
| UART RX | `uart_rx` | V14 | 待确认 | 资料未给出；波特率由 RTL/系统选择，电气属性不得采用冲突 CST 行 | Excel r31；CST UART 注释 |
| PMOD0 IO0 | `pmod0_io0` | P19 | `LVCMOS33`（CST `LEDs[7]` 示例） | 由外接模块决定 | Excel r48-r55；用户截图；CST LEDS 段 |
| PMOD0 IO1 | `pmod0_io1` | R19 | `LVCMOS33`（CST `LEDs[6]` 示例） | 由外接模块决定 | 同上 |
| PMOD0 IO2 | `pmod0_io2` | T21 | `LVCMOS33`（CST `LEDs[5]` 示例） | 由外接模块决定 | 同上 |
| PMOD0 IO3 | `pmod0_io3` | U21 | `LVCMOS33`（CST `LEDs[4]` 示例） | 由外接模块决定 | 同上 |
| PMOD0 IO4 | `pmod0_io4` | P16 | `LVCMOS33`（CST `LEDs[3]` 示例） | 由外接模块决定 | 同上 |
| PMOD0 IO5 | `pmod0_io5` | R17 | `LVCMOS33`（CST `LEDs[2]` 示例） | 由外接模块决定 | 同上 |
| PMOD0 IO6 | `pmod0_io6` | R18 | `LVCMOS33`（CST `LEDs[1]` 示例） | 由外接模块决定 | 同上 |
| PMOD0 IO7 | `pmod0_io7` | T18 | `LVCMOS33`（CST `LEDs[0]` 示例） | 由外接模块决定 | 同上 |
| FPC10P IO0-7 | `fpc_io[7:0]` | W12, AA9, AA10, AB10, AA11, AB11, W10, Y11 | `LVCMOS15` | 1.5 V I/O；方向由设计决定 | Excel r70-r77；CST Mic Array 段 |

使用快速表前仍应查阅第 8、9 节。快速表中的 RTL 名称是建议名；真正生效的顶层名必须与所用 CST 同步。
