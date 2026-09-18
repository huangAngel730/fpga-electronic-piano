# MIDI 输入模块使用说明（含实际例子）

日期：2026-09-18  
负责人范围：M3 输入接收、解析、统一事件转换及 Testbench

## 0. 初学者先看这一节

这个模块可以理解成一个“翻译员”：

> MIDI 键盘发送的是几个十六进制字节；这个模块把它们翻译成“按下哪个音、
> 力度多大、什么时候松开”，再交给后面的发声模块。

它本身不产生声音。声音仍由后面的声部、DDS、ADSR、混音和 DAC 链路产生。

最简单的工作过程是：

```text
演奏者按下琴键
    ↓
MIDI 键盘发送若干字节
    ↓
uart_rx 把串行高低电平还原成一个个 8 位字节
    ↓
midi_event_parser 判断这是按键、松键还是其他消息
    ↓
本地 FIFO 暂存尚未被下游取走的事件
    ↓
输出统一的 64 位 performance_event_t
    ↓
后面的声部模块开始或停止发声
```

### 例子：按下中央 C

假设 MIDI 键盘使用通道 1，按下中央 C，按键力度为十进制 100。键盘发送：

```text
90 3C 64
```

| 字节 | 含义 |
|---|---|
| `90` | 通道 1 的 Note On，也就是“有琴键按下” |
| `3C` | 十进制 60，即中央 C |
| `64` | 十进制 100，即本次按键力度 |

模块会生成：

```text
event_type  = Note On
channel     = 0
note_number = 60
velocity    = 806
```

这里 `channel=0` 不是错误。人们口中的 MIDI 通道 1，在字节中用数字 0 表示。

力度从 100 变成 806，是因为 MIDI 力度为 7 位，而项目事件使用 10 位。按照
公共接口规定，把原力度的高 3 位复制到末尾：

```text
100 = 7'b1100100
扩展为 10'b1100100110 = 806
```

### 例子：松开中央 C

键盘可能发送正常的 Note Off：

```text
80 3C 40
```

意思是“松开音符 60，松键力度为 64”。模块会生成 Note Off 事件。

有些键盘会用下面这种方式表示松键：

```text
90 3C 00
```

虽然第一个字节是 Note On，但力度为 0。MIDI 规定它等价于 Note Off，本模块会
自动转换，所以后面的声部仍能正确停止，不会因为两种写法不同而挂音。

### 例子：同时按下 C、E、G

键盘可以发送：

```text
90 3C 64 40 50 43 70
```

完整写法原本是：

```text
90 3C 64   // C4，音符 60
90 40 50   // E4，音符 64
90 43 70   // G4，音符 67
```

后两个重复的 `90` 被省略了，这叫 Running Status。解析器会记住前面的 `90`，
最终依次生成三个独立的 Note On 事件。三个音不是塞进同一个事件，而是由后面的
声部模块分别分配三个声部，因此可以同时发声。

四个音的和弦同样会产生四个事件。本模块不会限制 4 复音或 32 复音；真正能同时
发出多少个音，由后面的声部数量和混音模块决定。

## 1. 整体功能

本目录实现标准 MIDI 输入的数字逻辑部分：

```text
隔离/电平转换后的 MIDI RX
        -> 公共 uart_rx（31250 bps、8N1）
        -> midi_event_parser
        -> 本地事件 FIFO
        -> performance_event_t valid/ready 接口
```

简单地说，`uart_rx` 负责“听清每个字节”，`midi_event_parser` 负责“看懂每条
消息”，FIFO 负责“暂时排队”。它支持 Note On、Note Off、Note On 且 Velocity 为 0 时转成 Note Off、
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

下面用几个容易遇到的字节流说明这些规则。

### 5.1 实时字节插在消息中间

键盘可能发送：

```text
90 3C F8 64
```

`F8` 是 MIDI Timing Clock，可以插在一条消息的任意位置。解析器会忽略 `F8`，
其余字节仍按 `90 3C 64` 处理，最后得到中央 C 的 Note On。

### 5.2 暂不支持的控制消息

例如：

```text
B0 40 7F
```

这是 Control Change。当前版本暂时不把它变成统一事件，但会把三个字节完整读完。
如果它后面紧跟 `90 3C 64`，中央 C 仍能正确解析，不会把上一条消息的数据错当成
新的音符。

### 5.3 SysEx 消息

例如：

```text
F0 01 02 03 F7
```

`F0` 表示 SysEx 开始，`F7` 表示结束。当前版本不使用中间内容，因此跳过
`01 02 03`，遇到 `F7` 后恢复正常解析。

### 5.4 三种错误计数分别代表什么

| 输出 | 通俗解释 | 可能场景 |
|---|---|---|
| `uart_frame_error_count` | 串口的一帧没有正确停止 | 接线干扰、电平错误或波特率不匹配 |
| `parser_error_count` | 字节收到了，但 MIDI 消息残缺或顺序非法 | 只收到音符号，却没先收到状态字节 |
| `event_fifo_overflow_count` | 事件已经解析出来，但 FIFO 没位置 | 下游长时间不给 `event_ready` |

例如默认 FIFO 深度为 8，而下游一直不接收：前 8 个事件可以排队，第 9 个事件
无法保存，此时 `event_fifo_overflow_count` 增加 1。正常演奏时该计数应保持为 0。

## 6. valid/ready 与缓存

当 `event_valid && event_ready` 在同一个 `clk` 上升沿为 1 时，事件完成传输。
如果 `event_ready=0`，模块保持 `event_valid=1` 且 `event_data` 不变。

可以把它想象成两个人交接快递：

```text
event_valid=1：发送方说“我这里有一个事件”
event_ready=1：接收方说“我现在可以接收”
两者同时为 1：这个时钟上升沿完成交接
```

如果 `event_valid=1`、`event_ready=0`，说明事件已经准备好，但下游暂时没空。
此时本模块不能偷偷换成下一个事件，必须一直保持当前的 `event_data`。等到
`event_ready` 变成 1，当前事件完成交接后，FIFO 才显示下一个事件。

MIDI 串行发送端不能被 FPGA 反压，所以解析器内带一个小型 FIFO。FIFO 满后新
事件无法保存时，旧事件保持不变，同时增加 `event_fifo_overflow_count`。系统正常
运行时该计数应一直为 0。最终系统仍应把本模块接到公共 32 深度事件 FIFO；本地
FIFO 不是 4 复音或 32 复音的限制，复音数量由声部管理模块决定。

## 7. 仿真方法

打开 PowerShell，先进入仓库根目录，再运行脚本：

```powershell
cd E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano
.\code\scripts\run_midi_input_sim.ps1
```

不需要在 ModelSim 图形界面中手工添加文件。脚本会自动编译公共事件包、公共
`uart_rx`、两个 MIDI 模块和 Testbench，然后自动运行检查。

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
PASS: tb_midi_input completed 42 checks
Errors: 0, Warnings: 0
```

### 7.1 关于旧的 `D:\Gowin\...` 路径提示

工程现有的 Icarus 环境脚本仍指向一个已经不存在的旧 Gowin 安装目录，因此本次
没有运行 Icarus 交叉检查。这不影响这里的 ModelSim 仿真脚本，因为它使用的是：

```text
E:\FPGA\Bpan\modelsim\modelsim1\win64
```

本次已经实际完成 ModelSim 编译与仿真，结果是 0 错误、0 警告、42 项检查通过。
所以“没有运行 Icarus”不等于“没有进行仿真”。

## 8. 尚未验证和后续集成

- 本次可以完成 RTL 仿真，但没有实体 MIDI 键盘和接收模块，未做真实电气联调。
- FPGA 顶层例化、公共 FIFO 接入、正式 `SOURCE_ID`、输入引脚和 CST 均由 M2
  在确认接收模块数据手册与开发板电气条件后完成。
- 当前正式工程的 UART RX 引脚仍有板级电压属性待实物确认，本模块不能作为解除
  该硬件阻塞项的依据。
- 弯音轮、踏板、Aftertouch 和 Control Change 事件生成属于后续扩展，本版本只
  保证跳过这些消息后仍能继续正确解析音符。
