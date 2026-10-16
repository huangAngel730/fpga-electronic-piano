# R06 MIDI Program 0/1 → M1TD voice router（40 MHz 隔离回归）

仅复用已封存 R06 中原样的 MIDI UART/parser、本地FIFO、共享事件FIFO、M1TD事件路由/分配器。没有新音色、按键 RTL、顶层端口、PLL 或板级码流。音色 Program Change 值 0/1 的消息由 testbench 在 `midi_rx_async` 以 31250 baud 发送；FPGA 时钟 40 MHz。按钮侧维持 idle，`sample_owner_ready=1`，所以本测试**不证明**完整帧服务期限、PCM24、I2S、实际键盘控件或实体声音。

从仓库根目录运行（本机 OSS CAD 工具缺失时可用 `--cad` 指定该工具目录）：

```powershell
python code/tb/board/m2_m1td_program_select_20261016/run.py --output code/output/m2_m1td_program_select_20261016_03
```

`--output` 必须是 `code/output/` 内全新目录。runner 先核 R06 ZIP SHA `4be2b4c185691a3e493827a3a95303fa90f49ba6336eb4a8e0183942c8f05483`，从其单一输入组提取精确源码；用 Yosys Slang 降低原 M1TD 分配器再用 Icarus 编译其余原模块和本 TB。这与旧 T027 的 50MHz 工程不同，不做旧专项复跑。Yosys 对分配器的转换字节保存在输出；测试日志、退出码、每一步 argv、输入 SHA 在 `RUN_RECEIPT.json` 和三个步骤原 stdout/stderr 文件。可复制到另一台机器用不同的全新 output 名运行；工具版本与二进制身份须另按本机记录。

本例验证：复位默认钢琴、Program1 后的下一 NoteOn 为三角、Program0 后的下一 NoteOn 为钢琴，已经发声的槽不随选择改变，不同通道各自独立，Program127 不改变选择，同身份重触发保持当前程序，复位清除占用和程序。逐槽用 note+channel 身份查找而非猜固定分配槽。预期输出 `PASS R06_MIDI_PROGRAM_40M programs=4 notes=6 checks=29`。真实 60K 代码已实现演奏键和 Program Change，本回归无须另写板载音色键。

第一次运行 `_01` 的 TB 把 SystemVerilog 保留字 `program` 当 task 名，Yosys exit0、Icarus编译exit47，未启动仿真；第二次 `_02` 更正命名后只连 UART→router，三步exit0；最终 `_03` 再加入冻结共享事件 FIFO（真实板级路径）重新执行，Yosys/Icarus/VVP 全exit0，29项断言通过。三轮原始双流、首次修前及第二轮TB字节、最终TB/runner和清单封存于 `code/docs/evidence/m2_m1td_program_select_20261016/R06_MIDI_PROGRAM_SELECT_HISTORY_20261016.zip`，SHA-256 `fbf6fa768c5db8be4daf067b4e8bdacb299a78ba7de945b9f7f3663c5937bcd7`。输出 `code/output/` 保持忽略；禁止将仿真产物当成生产码流或板级证据。
