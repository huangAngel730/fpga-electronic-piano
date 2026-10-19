# 实物测量2 商业版烧录与138K Pro C持久记录

更新时间：2026-10-20，北京时间。适用窗口：实物测量2，以及接续本项目板卡识别、构建和烧录的会话。

本机当前使用 Tang Mega 138K Pro，C 步进由用户明确确认。指定 Gowin 商业版 V1.9.12.04 已完成最小 LED 工程构建和 SRAM 下载，用户确认 LED1 每约 0.5 秒交替亮灭。四复音、音频整机及全资源实测不在这次通过范围内。

用户要求将“实物测量”对话中的工具使用、板卡身份、识别和烧录方法、故障处理保存为后续会话可重新加载的记录。本记录不扩大任务写集、下载次数或技术准入；历史单次许可已消费，后续设备操作仍核对最新任务单及当前明确授权。文件持久保存依赖仓库与备份，不能保证模型脱离这些文件后自动记忆。

## 一 开工时重新加载

1. 阅读根 AGENTS.md、code/AGENTS.md、code/docs/协作入口.md 及当轮有效任务单，确认正在处理的任务。
2. 阅读本记录；把下列历史成功条件与当前连接、工具、码流逐项核对，不直接重复历史下载。
3. 对话为“实物测量”，ID 为 `01a14355-14d3-7012-9766-7353ade0e70c`；本窗口“实物测量2”，ID 为 `01a15512-5c55-7003-8395-ce0c2c6fa1d9`。需要追溯时使用对话读取工具，只读并核对相关原件。
4. 若后续正式决策改变工具或硬件，以用户新指令及已发布有效文件为准，保留本次历史事实，不以旧记录覆盖新任务。

## 二 指定商业版工具

安装根目录：

```text
D:\program\Gowin_work\Gowin\Gowin_V1.9.12.04_x64
```

| 完整程序路径 | 用途 |
|---|---|
| `D:\program\Gowin_work\Gowin\Gowin_V1.9.12.04_x64\Programmer\bin\programmer_cli.exe` | 优先使用的后台识别与烧录工具 |
| `D:\program\Gowin_work\Gowin\Gowin_V1.9.12.04_x64\Programmer\bin\programmer.exe` | 确实需要时使用的图形 Programmer |
| `D:\program\Gowin_work\Gowin\Gowin_V1.9.12.04_x64\IDE\bin\gw_ide.exe` | 设计 IDE，不能把它当作下载程序 |
| `D:\program\Gowin_work\Gowin\Gowin_V1.9.12.04_x64\IDE\bin\gw_sh.exe` | 后台执行 Tcl，综合、布局布线及生成码流 |

历史实际版本为 V1.9.12.04 build 2743。最近成功下载所用 CLI SHA-256：

```text
ca28fe178b04fd99780267787f61b0e0ec3729d579fe237ff454c1a0353e8ef6
```

用户明确禁止使用或回退到 `D:\program\gaoyunFPGA\Gowin\Gowin_V1.9.11.03_Education_x64`，也禁止混用教育版可执行文件、DLL、配置或驱动。旧脚本写死教育版时不能直接执行，先指出调用路径问题。商业版识别或下载失败时立即停止、保留原件，不擅自换教育版。

用户偏好后台命令行操作，不通过控制鼠标打开 FPGA 软件烧录。不因烧录修改源码、约束、系统环境变量、注册表或重装驱动；若另有获准的工程开发任务，按其独立写集执行。

### 商业版授权

原对话使用 Help → Manage License 配置授权。同一个商业版 IDE 可选 Use Floating License Server 或 Use Local License File，不需通过重装切换。

- Sipeed 浮动授权的历史配置为服务器 `106.55.34.119`、端口 `10559`，Check 成功后 Save；当前可用性和有效期以实际 Check 为准，不把历史地址写成持续有效保证。
- 本地单机 License 应与申请电脑 MAC 对应，收到高云文件后选择本地授权并 Check、Save。多人各机独立使用与通过服务器共享授权是不同部署方式。
- 曾出现“License 将在 6 天后到期”的提醒。该提醒不等于安装失败；服务后续是否续期不能由历史记录保证。

## 三 板卡与芯片身份

| 项目 | 记录及证据边界 |
|---|---|
| 当前板卡 | 用户明确确认 Tang Mega 138K Pro，实物照片可见 138K PRO DOCK |
| 底板修订 | 用户报告 v4071f3；对应资料为 4071f3 底板原理图 |
| 核心板资料 | 4072 Pro 核心板原理图 |
| 供电和连接历史 | 适配器供电，数据线经扩展坞连接电脑；每次操作仍核当前状态 |
| 完整工程目标 | `GW5AST-LV138FPG676AC1/I0`，来自 Pro 资料和实际构建报告 |
| IDE 封装名 | `FCPBG676A` |
| Device Version | C，用户明确确认；2026 年 10 月购买仅为辅助依据 |
| Programmer 目标名称 | `GW5AST-138C` |
| 实物可见料号 | 芯片被散热器遮挡，不能冒称已直接读出完整料号 |

Pro 原理图与原始 CST 的指定来源为 [code/rtl/138K_Pro](../rtl/138K_Pro/)。原始资料保持原样。旧 AIRead 的 60K 资料和 PG484 普通版＋NEO Dock 31005 的映射不能补作 Pro 引脚依据。

最近最小 LED 工程使用：

| 信号 | FPGA 球位 | 条件 |
|---|---|---|
| 板载时钟 | P16 | 50 MHz |
| 核心板 SW5 复位 | U4 | 高有效；资料核对为 1.5 V Bank，不外接 3.3 V 信号 |
| 底板 LED1 | R26 | 低有效，约每 0.5 秒翻转 |

Pro 音频资料核对结果：PT8211 为 U6，BCLK/WS/DIN 分别为 E22/F24/G24；耳机口为 J29；UART TX/RX 为 P15/N16；XPT4809 功放控制为 H17，高电平工作、低电平关闭。旧 NEO 的 U16、J25、低有效功放控制不能沿用到 Pro。这里是历史静态核对，具体接线仍按当轮原理图、Bank 电压和正式约束确认。

PMOD0_IO1 在资料中出现 N26/L22 矛盾，新增 CST 支持 N26，但原矛盾保留。R17 在 Pro 对应 J22 第 5 脚、PMOD0_IO3，不能沿用旧 NEO 的接口编号。CST 的 key/led 数组下标不一定等于板上丝印编号。

## 四 识别与SRAM下载方法

数据线接 JTAG/UART USB 口；SOFT-USB 用于 FPGA 内实现的 USB 功能。执行下载时目标 FPGA 必须已供电。旧 NEO 的电源键位置与长按步骤不能直接当作 Pro 操作说明。

先核待用 .fs 绝对路径、大小、SHA-256 和工程目标，再枚举下载器、扫描 JTAG。默认只做 SRAM Program；Flash 写入必须有用户明确授权。按任务单核对 M2 技术准入、精确 SHA 放行、当前次数及时限；任一条件不足不下载。

下面是 2026-10-20 的成功调用参数，属于历史实例，不能当作本轮执行授权：

```text
programmer_cli.exe --scan-cables F
programmer_cli.exe --scan --cable-index 4 --location 289
programmer_cli.exe --device GW5AST-138C --operation_index 2 --cable-index 4 --location 289 --frequency 2.5MHz --fsFile "<已经核验的.fs绝对路径>"
```

实际执行时须使用第二节商业版完整路径。这版 CLI 的 `operation_index 2` 对应 SRAM Program；工具升级后先核帮助，不能猜操作编号。`289` 是当次 USB location，重新连接后需重新枚举，不写死。后台执行记录采用 ProcessStartInfo 的 UseShellExecute=false、CreateNoWindow=true，保存 stdout、stderr、退出码和超时收尾结果；受控入口及时限遵守当前有效任务单。

当次枚举得到两个通道：

```text
USB Debugger A/0/289/null
USB Debugger A/1/290/null
```

对通道 0 的真实 JTAG 结果为：

```text
Target Cable: USB Debugger A/0/289/null@2.5MHz
Family: GW5AS
Name: GW5AST-138B GW5AST-138C GW5AS-138B GW5AS-138C (One of them)
ID: 0x0001081B
1 device(s) found!
```

`0x0001081B` 对应上述候选集合。扫描不必唯一显示 GW5AST-138C，不能仅凭这个 ID 区分 B/C、AST/AS、676 封装、速度温度后缀或所有资源健康。手工选择器件也不构成实物身份识别证据。

SRAM 下载后保持供电。断电会失去 SRAM 配置；RECONFIG 可能从 Flash 加载其他程序。是否发生过断电应以用户最新更正和实物记录为准，不沿用已撤回的推断。

## 五 最近成功结果与原件

北京时间 2026-10-20 00:45:35 至 00:45:56，商业版对正确 Pro C 最小 LED 工程执行一次 SRAM Program，耗时 21.1793486 秒，进度 100%，显示 Finished，进程退出码 0，Flash 操作 0。未运行读回校验。

下载后用户在原对话明确回复：LED1“按约 0.5 秒交替亮灭”。原始下载 result.json 中的 PENDING_USER 是形成时状态，应与后继 USER_LED_OBSERVATION.json、FINAL_STATUS.json 和对话回复一起阅读，不回写历史原件。

码流绝对路径：

```text
E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano\code\output\m3_pro_board_smoke_r16_20261019\SESSION_01\LED_IMPLEMENTATION_04\GOWIN_C_BUILD_02\pro_board_smoke\impl\pnr\pro_board_smoke.fs
```

大小为 34,690,868 字节，SHA-256 为：

```text
a6cfeb36715b88bd4cdd23577e91a3edcc07efec4d883324d488c2aee4f35489
```

本机原件入口：

- [下载、识别、授权及后继观察原件](../output/m3_pro_board_smoke_r16_20261019/SESSION_01/LED_IMPLEMENTATION_04/SRAM_DOWNLOAD_06/)
- [构建与交接包目录](../output/m3_pro_board_smoke_r16_20261019/SESSION_01/LED_IMPLEMENTATION_04/DELIVERY_05/)
- [商业版识别粗测](../output/m3_pro_board_smoke_r16_20261019/SESSION_01/RESUME_COMMERCIAL_02/TEST_RESULT.md)

code/output 下的原件仅在该机器保存，不随本记忆文档自动上传；其他机器访问不到时应索取原件，不能只凭本表代签。LED 的仿真、构建、时序及实物观察分别成立，不升级为四复音、MIDI、UART、音频、DDR、Flash 或全资源测试通过。

## 六 历史问题与有效处理

| 问题 | 有效处理和实际结论 |
|---|---|
| 最初把实物当作普通版 PG484＋NEO Dock，用教育版下载旧四复音码流 | 后来确认实物是 Pro FPG676。旧日志的 100%/Finished/exit 0 仅证明下载器报告完成，不能证明封装、引脚或功能匹配。暂停沿用旧 .fs，为正确 Pro 目标重新构建。早期无声根因未最终实测确认。 |
| 本机教育版找不到 Pro 676 封装 | 当时库中仅找到普通版 PG484；使用指定商业版检查 Pro 器件与封装，并实际构建。不得把缺封装的问题用手改器件库绕过。 |
| Tcl 不接受 `GowinSynthesis` | 改为 `set_option -synthesis_tool gowinsynthesis`，后续同版实际构建成功。官方 SUG918 §4.2 的小写示例是当时依据。 |
| 最小自检编译出现 0xC0000005 | 保留首失败；按用户指定的编译崩溃处理资料，在获准条件下以同源、同工具做沙盒外核验，编译成功，随后 LED 自检 101 项通过。不能把同一错误码的其他事故直接判作相同根因，也不能恢复已消费的测试许可。 |
| 商业版访问自身安装目录被拒 | 核对为执行环境目录访问限制；经批准在沙盒外执行同一个商业版命令，枚举和 JTAG 扫描成功。没有切换教育版或重装驱动。明确审批拒绝时停止，不换入口绕过。 |
| setup refresh had errors | 发生在创建命令进程前，是执行环境启动失败，不是 RTL 编译、综合或烧录结果。保留原错误，临时故障重试受仓库规则约束。 |
| PR1014 时钟普通布线警告 | P16 输入到时钟网络有一段使用普通布线。报告仍使用一个 PRIMARY；LED 工程 50 MHz 下 setup 最差余量 16.755 ns、hold 0.247 ns，已分析违例均为 0。警告保留，经当次许可做 LED 粗测；不能声称警告消除或代签音频工程时序。 |
| COM13/COM18 均采到 0 字节且没有声音 | 0 字节不能当成有效全零 STAT。之后发现板型误配；旧测点指引撤回。串口号随设备变化，重新枚举；音频根因仍需正确 Pro 同版工程与现场测量确认。 |
| 曾误以为用户烧录后断电 | 用户后来明确更正“烧录后没有再断电”，旧断电推断已撤回，不作为当前无声的已确认原因。 |

LED 构建脚本原件为 `code/output/m3_pro_board_smoke_r16_20261019/SESSION_01/LED_IMPLEMENTATION_04/GOWIN_C_BUILD_02/run_build.tcl`。相关官方历史引用为 [Sipeed Pro 说明](https://wiki.sipeed.com/hardware/zh/tang/tang-mega-138k/mega-138k-pro.html)、[Gowin SUG918](https://cdn.gowinsemi.com.cn/SUG918.pdf)、[Gowin SUG937E](https://cdn.gowinsemi.com.cn/SUG937E.pdf)。本次保存不重新核验在线服务和新版文档。

## 七 后续操作边界

每次烧录记录工具绝对路径和身份、实际命令、目标器件、模式、.fs 路径/大小/SHA、下载器与 JTAG 结果、退出码、耗时、首失败及当前板卡状态。只有工具成功且现场观察相符，才分别登记该项结果。

本次持久化只保存知识与开工索引。M2 技术准入、用户精确 SHA 放行、任务写集、受控次数、时限及硬件条件继续按当前任务执行；不恢复历史已消费许可，不自动启用审核制度，不修改共享状态表或替 M2 签收。
