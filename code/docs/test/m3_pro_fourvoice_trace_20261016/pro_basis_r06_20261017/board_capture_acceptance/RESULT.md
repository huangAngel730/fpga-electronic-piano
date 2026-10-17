# M3-R6-8 board capture acceptance result

状态为 **OFFLINE_PREPARATION_COMPLETE / DEVICE_NOT_RUN / BLOCKED_PREFLIGHT**。

已形成 Pro 同版采集的人工步骤、机器可读 session schema、未执行会话模板和七个核心场景：静音/锁定、固定音、四个独奏、四音保持、逐个释放、Velocity、演奏中复位及恢复。原件格式覆盖 MIDI 字节与时间、UART/状态、PT8211 BCLK/WS/DIN、PA/reset/pll、模拟音频、统一触发/时基/校准、工具命令双流与退出码。

当前没有完整实物身份、Bank 电压、商业工具有效许可、同版 source/ROM/constraints/PLL/top、完整 PnR/STA、唯一 Pro `.fs`、恢复身份和针对该精确 SHA 的一次 SRAM-only 许可，因此所有设备操作均未运行。没有 programmer、EDA、逻辑分析仪、示波器、串口、音频或板卡调用；没有下载，也没有消费 SRAM 次数。

旧 PG484 引脚、旧 `.fs` 和旧下载权限没有继承。Flash 和追加下载不在范围内。准备文件不构成 G0–G3、生产码流、赛题整机或硬件通过，`board_release_allowed=false`。
