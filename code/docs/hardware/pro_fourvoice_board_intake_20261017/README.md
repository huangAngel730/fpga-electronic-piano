# B0：Pro板型与电气入口的当日资料核查

依据用户task-day两单及总控DAY_PLAN。B0整体仍为PARTIAL/PENDING_PHYSICAL_INPUT：当前没有可控实体/仪器会话、实物全料号照片、Bank测量或新Pro码流准入。本次只完成现有原件的L0身份摄取，不重做已发布110行引脚报告，也未重新阅读PDF图形或执行任何接线/下载。

只读入口是已发布 `code/rtl/138K_Pro/Pro_引脚核对_CST_R02_20261016/pin_relationships.json`、两份4072/4071f3 PDF和用户提供参考CST。新脚本在software/pro_binding_20261017/coordinator_20261017/capture_b0.py，保存它们的现场SHA/大小及与旧报告声明的一致性、关键端口的实际CST行号、原报告已有候选注记。它不是新的构建/电气判据，不替M2 P4或复跑原报告自测。

关键差异及待到件：

| 项目 | 当前已存在的静态依据 | 仍缺什么／下一责任 |
| --- | --- | --- |
| 板与器件 | 资料针对4072 Rev1.10、4071f Rev1.5；原报告保留GW5AT/GW5AST符号差异。 | 实物PCB修订、FPGA全料号/步进照片及M2目标确认；UNKNOWN。 |
| 时钟 | 原报告P16/Bank3/50MHz U8；参考CST L3–4。 | 实际时钟、M2新PLL锁定/复位出口与同版源；UNKNOWN。 |
| 复位 | 参考rst=U4，L7–8写LVCMOS15/1.5V；原报告核心SW5高有效。底板S0=K16，参考key[0] L14/18，原报告低有效。 | M2选择公开复位来源/极性并固定接口；M3实物核电平。不得据端口名rst套用低有效假设。 |
| MIDI | 原报告R17→PMOD0_IO3→J22/5；参考pmod_0[1] L50/58。 | 实物针向、配置功能复用、隔离适配器FPGA侧电平/共地；UNKNOWN，不沿旧NEO针号接线。 |
| PT8211 | BCLK=E22、WS=F24、DIN=G24，参考L229–234；仅显式BANK_VCCIO=3.3，未显式IO_TYPE。原合同LSBJ16。 | 实际Bank4/5供电、M2明确IO类型/复位与发送器公开采纳字段；波形/音频未测。 |
| UART与PA | 原报告P15 TX/N16 RX、H17 PA_EN高有效；三个球位均未列入用户参考CST。 | M2新UART双向端口、复位/PA安全默认及约束；原理图静态极性不等于电平实测。 |
| 耳机 | 原报告J29是耳机口，J25为DC电源口。 | 实物修订/低音量采集条件；NOT_RUN。 |
| 电压与资料矛盾 | Bank2/4/5存在1.8V选装可能；N26仅是CST+p5静态候选，p16 L22及SDRAM_DM跨页矛盾保留。 | 实际焊接与VCCIO、必要断电通断核验；原报告未解决项继续UNKNOWN。 |
| 工程身份 | 当前正式electronic_piano.cst正文明确是Tang Mega60K+NEO/GW5AT-LV60PG484，属于另一版本。原110行报告对照的历史audio_visual.cst也不等同本文件。 | M2独立Pro新source/ROM/目标/PnR/完整STA/.fs/恢复SHA及精确SRAM许可；本次均未获得。 |

物理入口需M3实物负责人提供实际身份、电压和接线原件；M2固定同版工程/码流与许可后才到现场下载步骤。没有新精确许可不执行SRAM/Flash。当前board_release_allowed=false。

自审：已有只读子智能体核参考CST与R02表的复位、电压域、串口/PA缺列及历史CST区别，无新增资料内部矛盾；没有重审PDF、运行测试或修改源。实际摄取命令、双流、退出码和SHA见AUDIT_R01。资料身份核同只签L0，不升级任何板级结论。
