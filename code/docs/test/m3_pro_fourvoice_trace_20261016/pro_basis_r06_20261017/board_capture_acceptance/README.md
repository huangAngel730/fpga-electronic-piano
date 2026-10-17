# M3-R6-8 Tang Mega 138K Pro 同版采集准备

结论：离线步骤和原件格式已准备，所有设备操作均为 **NOT_RUN**，当前状态为 `BLOCKED_PREFLIGHT`，`board_release_allowed=false`。

本包只服务 Tang Mega 138K Pro 的未来同版采集。旧 GW5AST-LV138PG484AC1/I0、NEO Dock 31005、PG484 引脚、旧 `.fs` 和旧下载许可均不得带入。本文也不批准 Flash、追加下载、替换码流或修约束/ROM/PLL。

三个目录的职责如下：

- `code/software/.../board_capture_acceptance/session_schema.json`：机器可读的会话字段；
- `code/tb/board/.../board_capture_acceptance/CAPTURE_SCENARIOS.json`：静态场景清单，不是 TB 或设备执行器；
- 本目录：人工预检、采集、止损、封存步骤和未执行会话模板。

开始真实会话前，必须同时取得完整 Pro 料号/封装、Core 与 Dock 实物版本、相关 Bank 电压、供电/共地/MIDI电平/安全音频负载、商业工具版本与有效许可、同版 top/源码/ROM/约束/PLL 身份、完整 PnR 与 STA、唯一 `.fs` 原字节和 SHA、恢复身份，以及对该精确 `.fs` 的一次 SRAM-only 明文许可。缺一项就停在 `BLOCKED_PREFLIGHT`。
