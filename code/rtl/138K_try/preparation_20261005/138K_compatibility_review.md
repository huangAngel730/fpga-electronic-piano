# 138K B/C适配准备：差异清单，不是最终CST

2026-10-05。仅离线准备；全部结果在138K_try，无正式约束/IP修改或烧录。

## 来源与可信边界

已人工查看核心板原理图全部7页的完整本地渲染；第1至4页提取文本存在字体编码乱码，因此没有用乱码猜引脚/供电。未上传外部MinerU服务，也未再次转换PDF。来源为../comparison_20261005_dab75308/board_138k_schematic.pdf（SHA326c45a7ae05e990d5f885fba6ec9b589d966941aa3c00f7d43122d99c068af7），另有board_138k_reference.cst。核心板原理图不单独证明目标底板端到端接线或实物板版本。

冻结60K来源为relocated_bundle/sources/audio_visual.cst、TMDS_PLL_800_600_60.v和audio_visual_hold055.sdc；其约束字节未改。

| 项目 | 冻结60K设置 | 138K已有证据与下一步 |
|---|---|---|
| 器件 | gw5at60b-002 / GW5AT-LV60PG484AC1/I0 | B=gw5ast138b-011，C=gw5ast138c-007，均GW5AST-LV138PG484AC1/I0；三个独立计数器已实际完成PnR，但不证明完整IP兼容 |
| 时钟 | V22，50MHz，LVCMOS33/3.3V | 原理图第5页Y1100=50MHz，R973连BANK4_V22；第1页Bank4供电3.3V。可作为候选依据，仍保留固定50MHz |
| 复位/用户键 | AA13、AB13、Y12，LVCMOS15/1.5V | 第7页三脚在Bank5，第1页Bank5供电3.3V；参考CST同三脚写LVCMOS33/3.3V。不能原样沿用60K的1.5V声明；需正式适配核验底板/上拉后单列差异 |
| 音频 | Y17/AB17/AA16/AB16，3.3V | 第7页均Bank5，参考CST HP_BCK/HP_WS/HP_DIN/PA_EN同球位，Bank5电源依据第1页。核心板没有证明DAC/功放底板全部线路 |
| UART | U15，3.3V | 第7页Bank5，参考txp同球位；核对实际底板串口版本与复用，不新增RX |
| MIDI | R17，3.3V | 第7页Bank4，参考CST LEDs[2]也占R17；这是参考工程端口别名，不能断言有实体LED冲突，也不能整份搬入。需核对实际PMOD/底板连接，冻结功能不扩展 |
| TMDS对 | J14/H14、J15/H15、K17/J17、G15/G16 | 第4页Bank3，参考CST差分对同球位，第1页Bank3供电3.3V。仍待DVI TLVDS/OSER10物理兼容及底板TX线路核验，不能仅凭球位相同判定通过 |
| 视频PLL | PLLA，IDIV1/MDIV20/ODIV0=8/ODIV1=40，125/25MHz | 来源为60K配置；需138K B/C官方模型/实际工具确认参数和专用位置。当前仅计数器PnR，没有验证PLLA/DVI组合 |
| PLL固定位置 | u_visual/u_video_pll/PLLA_inst=PLL_R[0] | 不因同名器件自动继承；参考里的PLL_L[0]属于DDR3实例，不是本视频PLL替代依据 |
| 串行复位固定位置 | 两级R49C101[1][A/B] | 60K物理坐标不等于138K合法/相邻位置；不得直接删除约束或随意换位置“制造通过”，待验证后记录必要映射 |
| 时序 | sys/pixel/serial=50/25/125MHz，sys Hold0.550ns | SDC保持字节身份；138K改IP后须检查时钟对象/所有例外有效性，不加宽泛异步false path、不降低uncertainty |

## 已知禁止与待件

- 第5页板上N12=RECONFIG、F4=CPU_RESET，不是AA13用户复位的替代接线。第6页连接器有5V电源针，但GPIO不能据此接5V。
- 该原理图未唯一标出芯片B/C；离线两版分别测试，上板前另核丝印。本轮不准备下载。
- 未生成最终138K CST，也未对冻结IP做器件迁移。DVI原件、原V0171运行元数据和完整目标底板资料到件后，再确定允许的副本适配。
- 本阶段实际级别：资料/静态差异分析 + 独立小工程工具PnR；不是冻结V0171的138K STA或L6。
