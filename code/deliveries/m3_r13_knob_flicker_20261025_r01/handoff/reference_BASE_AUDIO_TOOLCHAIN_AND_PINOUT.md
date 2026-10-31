# 当前音频工程的工具、引脚与构建

Gowin 商业版固定为 `D:/program/Gowin_work/Gowin/Gowin_V1.9.12.04_x64`，版本 V1.9.12.04，器件 `GW5AST-LV138FPG676AC1/I0`、C，顶层 `pro_audio_minimal_top`，音频 SOURCE_MODE=0。不混用教育版或其他封装/IP。软件安装、驱动及 License 使用本机现有安装，本备份不包含它们。

| 当前端口 | 球位 | 当前定义 |
|---|---|---|
| sys_clk_50m | P16 | 50 MHz 输入 |
| sys_rst_n | K16 | Dock S0，低有效复位 |
| key_n[0] / key_n[1] | F15 / G15 | 低有效演奏键 |
| midi_rx | R17 | J22 第5脚、PMOD0_IO3；CPU/SSPI 复用已在工程选项启用 |
| i2s_bclk / i2s_lrck / i2s_din | E22 / F24 / G24 | PT8211 BCLK / WS / DIN |
| pa_en | H17 | 高电平使能功放，复位时关闭 |
| uart_tx | P15 | UART 输出 |

当前实际音频 CST 声明上述端口为 LVCMOS33 / Bank 3.3 V；以 `project/pro_audio.cst` 为工程输入。`docs/hardware/tang_mega_138k-pro_pins.cst` 是全板原始参考，不能直接替换音频 CST。历史核心板 U4 是高有效、1.5 V 复位，与本工程 K16 低有效不能混用。上板前核当时 Bank 配置、外接 MIDI 的隔离/电平及精确码流身份，不将 5 V 直接接 FPGA。

PLL 的输出0/1在本最小音频工程未使用，输出2为40 MHz。复位保留两级同步器的异步断言/同步释放；SDC仅豁免两级同步器的异步 CLEAR 引脚，下游复位恢复/移除和数据路径仍分析，hold不确定度0.750 ns。没有设置整个时钟域互相忽略。

命令行重建（实际运行时会启动新的综合/布局布线，备份过程没有执行）：

```powershell
& 'D:/program/Gowin_work/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe' 'E:/FPGA/GAOYUNFPGA/extra _life/basic/rebuild.tcl'
```

可直接在 Gowin IDE 打开 `project/pro_audio.gprj`；也可用上面命令生成 `REBUILD/pro_audio/pro_audio.gprj`。原 A08 完整成功工程的绝对路径原件在 baseline/A08/provenance，作为来源证据保留；日常拓展使用本目录 project 入口。

原始码流 `baseline/A08/bitstream/pro_audio.fs`：37262764 字节，SHA-256 `55f102b1972deaff774844e125693648ceac1b982ac0d5567d223c3b9c2c21e5`。这是已构建原件身份，不等于已下载、可直接恢复历史下载次数或板上验收通过。
