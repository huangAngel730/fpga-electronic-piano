# MIDI 输入模块说明

日期：2026-09-18  
负责人范围：M3 输入接收、解析、统一事件转换及 Testbench

## 1. 整体功能

本目录实现标准 MIDI 输入的数字逻辑部分：

```text
隔离/电平转换后的 MIDI RX
        -> 公共 uart_rx（31250 bps、8N1）
        -> midi_event_parser
        -> 本地事件 FIFO
        -> performance_event_t valid/ready 接口
```

它支持 Note On、Note Off、Note On 且 Velocity 为 0 时转成 Note Off、
多条音符消息连续接收、基本 Running Status，以及插在消息任意位置的
MIDI Real-Time 字节。暂不生成弯音、踏板、Aftertouch 和 Control Change
事件，但解析器会按这些消息规定的数据长度将其完整吃掉，避免后续音符错位。

标准 5 针 MIDI 是电流环接口，外部必须使用符合要求的隔离接收电路；如果
接入模块输出为 5 V UART，还必须电平转换。不得把 5 V 信号或标准 MIDI 插座
直接连接 FPGA。具体器件接线、供电、电平、引脚与 CST 由拿到硬件和数据手册
后另行确认，本次 RTL 不绑定任何实体引脚。

## 2. 新增文件

| 文件 | 作用 |
|---|---|
| `code/rtl/input/midi_input/midi_input.sv` | 串接公共 UART 接收器、MIDI 解析器和错误计数器 |
| `code/rtl/input/midi_input/midi_event_parser.sv` | 解析 MIDI 字节并生成统一 64 位事件，带本地 FIFO |
| `code/tb/input/tb_midi_input.sv` | 从异步串行线发送真实 8N1 波形的自检 Testbench |
| `code/scripts/run_midi_input_sim.ps1` | 一键调用 ModelSim 编译并运行 Testbench |

未修改顶层模块、公共包、公共 UART、约束文件和引脚资料。

## 3. `midi_input` 端口

| 端口 | 方向 | 位宽 | 作用 |
|---|---:|---:|---|
| `clk` | 输入 | 1 | 系统时钟；默认参数按 50 MHz 计算 |
| `rst_n` | 输入 | 1 | 低有效的系统域同步复位 |
| `midi_rx_async` | 输入 | 1 | 隔离并完成电平转换后的异步 MIDI 串行线 |
| `event_ready` | 输入 | 1 | 下游可以接收事件 |
| `event_valid` | 输出 | 1 | 当前有有效事件 |
| `event_data` | 输出 | 64 | 公共 `performance_event_t` 事件 |
| `event_fifo_level` | 输出 | 16 | 本地事件 FIFO 当前占用数 |
| `event_fifo_high_watermark` | 输出 | 16 | 复位以来 FIFO 的最高占用数 |
| `uart_frame_error_count` | 输出 | 32 | UART 停止位错误累计值，饱和不回绕 |
| `parser_error_count` | 输出 | 32 | 非法或截断 MIDI 消息累计值，饱和不回绕 |
| `event_fifo_overflow_count` | 输出 | 32 | 本地 FIFO 满时丢弃新事件的累计值，饱和不回绕 |
| `midi_rx_busy` | 输出 | 1 | UART 正在接收一帧 |

参数：

| 参数 | 默认值 | 含义 |
|---|---:|---|
| `CLK_HZ` | 50000000 | `clk` 频率 |
| `MIDI_BAUD` | 31250 | 标准 MIDI 波特率 |
| `LOCAL_FIFO_DEPTH` | 8 | 无法反压串行输入时使用的本地事件缓存深度 |
| `SOURCE_ID` | 0 | 事件来源编号；系统集成时由 M2 显式分配，不能靠默认值猜测 |

50 MHz 下每个 MIDI 位占：

```text
50000000 / 31250 = 1600 个 clk
```

8N1 每字节 10 位，约 320 us；一条三字节 Note 消息约 960 us。

## 4. `midi_event_parser` 的主要内部变量

| 变量 | 位宽 | 作用 |
|---|---:|---|
| `running_status` | 8 | 保存最近一条 80 至 EF 的通道状态字节 |
| `first_data_byte` | 7 | 保存两数据字节消息中的第一个数据字节，例如 Note Number |
| `channel_data_pending` | 1 | 表示已经收到第一个通道数据字节，正在等待第二个 |
| `system_data_remaining` | 2 | 尚需跳过的 System Common 数据字节数 |
| `sysex_active` | 1 | 位于 F0 至 F7 的 SysEx 区间内 |
| `fifo_mem` | 64 x 深度 | 保存尚未被下游接收的统一事件 |
| `fifo_count` | 参数化 | 当前 FIFO 中的事件数量 |
| `parsed_event_valid` | 1 | 本拍完成了一条 Note 消息 |
| `parser_error_pulse` | 1 | 本拍发现非法数据、截断消息或 SysEx 内异常状态 |
| `fifo_overflow_pulse` | 1 | 本拍产生事件但本地 FIFO 没有空位 |

解析器没有使用派生时钟或组合反馈。所有解析和 FIFO 状态都在 `clk` 上升沿
更新；组合逻辑只负责计算下一状态和当前输出。串行输入是唯一异步信号，已经在
公共 `uart_rx` 内经过带 `async_reg` 属性的两级触发器同步，所以解析器内部不再
重复跨时钟域处理。

## 5. MIDI 解析规则

- `8n note velocity`：生成 Note Off。
- `9n note velocity`：Velocity 非零时生成 Note On；为零时生成 Note Off。
- `n` 直接写入统一事件的 4 位 `channel`，所以线缆上的 MIDI 通道 1 对应字段 0。
- Note Number 直接使用 MIDI 的 7 位值，不再用固定 `NOTE_STEP` 推算。
- 7 位 Velocity 按接口规范扩为 `{velocity[6:0], velocity[6:4]}`，范围 0 至 1023。
- Running Status 保留最近的通道状态；每收齐规定数量的数据字节就完成一条消息。
- F8 至 FF 是 Real-Time 字节，可以插入任意位置，不清除 Running Status。
- F0 至 F7 的 SysEx 内容被跳过；F1/F2/F3 的规定数据字节也会被跳过。
- 坏 UART 帧不会进入事件生成；同时清除未完成的解析上下文，以便后续状态字节恢复。
- 计数器达到 `32'hFFFF_FFFF` 后保持最大值，不回绕掩盖历史错误。

## 6. valid/ready 与缓存

当 `event_valid && event_ready` 在同一个 `clk` 上升沿为 1 时，事件完成传输。
如果 `event_ready=0`，模块保持 `event_valid=1` 且 `event_data` 不变。

MIDI 串行发送端不能被 FPGA 反压，所以解析器内带一个小型 FIFO。FIFO 满后新
事件无法保存时，旧事件保持不变，同时增加 `event_fifo_overflow_count`。系统正常
运行时该计数应一直为 0。最终系统仍应把本模块接到公共 32 深度事件 FIFO；本地
FIFO 不是 4 复音或 32 复音的限制，复音数量由声部管理模块决定。

## 7. 仿真方法

在仓库根目录打开 PowerShell，运行：

```powershell
.\code\scripts\run_midi_input_sim.ps1
```

脚本默认使用：

```text
E:\FPGA\Bpan\modelsim\modelsim1\win64
```

如果 ModelSim 安装在别处，可先设置 `MODELSIM_BIN` 为包含 `vlib.exe`、
`vlog.exe` 和 `vsim.exe` 的目录。

Testbench 覆盖：

1. 复位和运行中复位；
2. Note On、Note Off 和 Velocity=0；
3. 7 位到 10 位 Velocity 映射；
4. 多音符连续消息和 Running Status；
5. 消息中穿插 F8 Real-Time；
6. 不支持的通道消息、System Common 和 SysEx 跳过；
7. 非法数据和截断消息计数；
8. `valid/ready` 反压期间数据保持；
9. 本地 FIFO 满载、最高水位和溢出计数；
10. UART 坏停止位计数及后续恢复。

成功时最后应显示：

```text
PASS: tb_midi_input completed ... checks
```

## 8. 尚未验证和后续集成

- 本次可以完成 RTL 仿真，但没有实体 MIDI 键盘和接收模块，未做真实电气联调。
- FPGA 顶层例化、公共 FIFO 接入、正式 `SOURCE_ID`、输入引脚和 CST 均由 M2
  在确认接收模块数据手册与开发板电气条件后完成。
- 当前正式工程的 UART RX 引脚仍有板级电压属性待实物确认，本模块不能作为解除
  该硬件阻塞项的依据。
- 弯音轮、踏板、Aftertouch 和 Control Change 事件生成属于后续扩展，本版本只
  保证跳过这些消息后仍能继续正确解析音符。
