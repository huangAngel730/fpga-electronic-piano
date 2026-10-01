# MIDI 输入模块使用说明（含实际例子）

日期：2026-09-18；CC64／Pitch／CC1 更新：2026-10-01
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

### 2026-10-01 Pitch／CC1 输入侧排队合同

本次仅按冻结接口增加 `En LSB MSB` 和 `Bn 01 value`；分别调用公共
`midi_bend_to_12bit({MSB,LSB})` 和 `midi_cc_to_12bit(value)`。
Pitch 为 `EVENT_PITCH_BEND/CTRL_PITCH_BEND` 的 12 位补码，中心为零；
CC1 为 `EVENT_CONTROL_CHANGE/CTRL_MODULATION`，其他未用字段清零。
parser 增加末尾 `CLK_HZ` 参数（默认 50 MHz），wrapper 传入已有 `CLK_HZ`；
原端口、64 位公共事件、原参数位置及编译文件清单不变。

排队与调度规则在实现前确定如下：

1. 每个 parser 的 `SOURCE_ID` 固定；32 个待发送槽仅按 16 通道×Pitch/CC1
   寻址，保存待发最新值，不合并不同来源（不同实例）/通道/控制项。
   这不是 M2 的演奏控制状态表，不提供查询、音符绑定或每帧快照。
2. Note On/Off、CC64 原样进入原深度离散 FIFO，严格保留相互顺序；
   连续控制不占其容量、不替换其内容。连续控制与离散事件之间不承诺原字节顺序：
   未呈现连续值可以被后续 Note/CC64 超越，M2 不应视其为 Note 的原子参数快照。
3. FIFO 非空时优先发送离散事件；仅 FIFO 为空且本拍没有新离散事件时，
   在待发槽中轮询选择一项。持续离散流可能推迟连续控制，停止输入且下游恢复
   ready 后最终值送达；32 项同时待发在无其他阻塞时约需 32 ms。
4. Pitch/CC1 合计每来源不超过 1 kHz，间隔为 `ceil(CLK_HZ/1000)` 个时钟。
   从实际连续事件握手开始计时，不从字节接收计时；背压恢复不会突发排空旧控制。
5. 被选中的连续事件独立锁定，一旦 `event_valid=1` 就不再合并；背压期间
   事件和 valid 不变。更新写入对应待发槽，不能改写这个已呈现事件；同拍收到
   该槽的新值时推迟选择一拍，避免冻结过期值。
6. CC1 按将来发送的有效序列去重：相同值不重复；若未呈现的新值又回到
   已呈现/最后成功发送的值，取消这项待发变化。去重历史只是发送缓存，复位清空，
   首次值（包括0）必须发送。Pitch 原始重复允许重新输出，但仍受限速/合并。
7. 同一拍先出离散 FIFO 再入新离散事件，保留满队列同时读写能力；
   FIFO 水位/峰值只统计离散 FIFO，不包括32个待发控制槽或1个锁定控制事件。
   外部串行输入不可反压，超容量离散突发仍保留旧事件、显式累计丢新溢出，
   不宣称无限背压下绝不丢事件。控制合并不计作溢出。
8. 同步系统复位清解析上下文、离散 FIFO、待发槽、锁定控制、去重历史和限速；
   无CC121/CC123、panic策略、断线看门狗或FCW/LFO算法。

本阶段只证明 MIDI 输入模块输出控制事件，不证明键盘已经变调/颤音，不关闭T036。

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
MIDI Real-Time 字节。2026-10-01 按公共接口 v1.6 支持 CC64 延音踏板，
并补齐 Pitch Bend 和 CC1 Modulation；Aftertouch 和其他 CC 仍完整消费但不输出。

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
| `code/tb/input/tb_midi_controls.sv` | 16384 Pitch 原值/16通道×128 CC1/两个来源，独立64位事件比较 |
| `code/tb/input/tb_midi_control_queue.sv` | 合并、去重、全32待发槽、背压、混合离散FIFO和限速 |
| `code/tb/input/tb_midi_controls_uart.sv` | 真实50MHz/31250串行线→midi_input控制事件 |
| `code/scripts/run_midi_controls_sim.ps1` | 六组Icarus专项/真实限速/UART/Note及CC64回归，保留日志 |

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
| `event_fifo_level` | 输出 | 16 | 本地离散事件 FIFO 当前占用数，不含连续控制槽 |
| `event_fifo_high_watermark` | 输出 | 16 | 复位以来离散 FIFO 的最高占用数 |
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
| `parsed_event_valid` | 1 | 本拍完成了一条支持的 MIDI 消息 |
| `control_pending` / `pending_value` | 32 / 32×12 | 固定来源下16通道×Pitch/CC1待发送槽 |
| `control_locked` / `locked_event` | 1 / 64 | 已呈现、握手前不可变的连续事件 |
| `control_cooldown` | 参数化 | 最近成功控制握手之后的最小间隔计数 |
| `mod_sent_valid` / `mod_sent_value` | 16 / 16×12 | 仅用于CC1发送去重的历史缓存，非M2状态表 |
| `parser_error_pulse` | 1 | 本拍发现非法数据、截断消息或 SysEx 内异常状态 |
| `fifo_overflow_pulse` | 1 | 本拍产生事件但本地 FIFO 没有空位 |

解析器没有使用派生时钟或组合反馈。所有解析和 FIFO 状态都在 `clk` 上升沿
更新；组合逻辑只负责计算下一状态和当前输出。串行输入是唯一异步信号，已经在
公共 `uart_rx` 内经过带 `async_reg` 属性的两级触发器同步，所以解析器内部不再
重复跨时钟域处理。

## 5. MIDI 解析规则

- `8n note velocity`：生成 Note Off。
- `9n note velocity`：Velocity 非零时生成 Note On；为零时生成 Note Off。
- `Bn 40 vv`：调用公共 `make_sustain_event()`，生成 `EVENT_CONTROL_CHANGE`、
  `CTRL_SUSTAIN=6`；7 位值扩为 `{vv,vv[6:2]}`，12 位阈值 2048 对应原始值 64。
- `En LSB MSB`：组合 `{MSB,LSB}` 调公共 `midi_bend_to_12bit()`，
  输出 `EVENT_PITCH_BEND/CTRL_PITCH_BEND=0`，12位补码−2048..2047，8192严格映射0。
- `Bn 01 vv`：调公共 `midi_cc_to_12bit()`，输出
  `EVENT_CONTROL_CHANGE/CTRL_MODULATION=1`，0..4095；相同值不重复发送。
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

### 5.2 CC64 与其他控制消息

例如：

```text
B0 40 7F
```

这是 CC64 踩踏板，现生成 `CTRL_SUSTAIN`、`control_value=4095` 的控制事件；
`B0 40 00` 对应松踏板、值 0。通道和来源保留，其他事件字段清零。
`B0 01 7F` 现在输出 Modulation=4095；`B0 02 7F` 等其他 CC 仍跳过。
新增解析不等于现有正式码流已支持延音；独立控制与接入说明见
`code/rtl/input/sustain_control/README.md`。

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

例如默认 FIFO 深度为 8，而下游一直不接收：前 8 个离散事件可以排队，第 9 个离散事件
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
- Pitch/CC1/CC64 输入解析已实现；Aftertouch和其他CC不扩展。
  Pitch/Mod数学与FCW由M1，accepted控制状态/正式接入/采样快照由M2。
  旧“未取得键盘/引脚待确认”描述为2026-09-18历史阶段，不覆盖最新仓库硬件事实。
- 新增自检入口 `.\code\scripts\run_cc64_input_sim.ps1`，覆盖 16 通道×128 个值、
  Running Status/Realtime/异常/FIFO 边界和真实 UART；实际 UART 回归已从旧版
  42 项扩为 44 项。上文旧环境/42 项记录属于 2026-09-18 的历史结果。

## 9. Pitch／CC1 专项交付与实际日志（2026-10-01）

仓库根目录执行：

```powershell
.\code\scripts\run_midi_controls_sim.ps1
$env:PATH = 'C:\Users\songdongkuan\miniconda3;' + $env:PATH
.\code\scripts\check_repo.ps1
```

专项脚本自动编译真实RTL，比较完整64位输出，仅在退出码0且PASS标记存在、
无ERROR/FAIL/FATAL时成功；任何断言失败都非零退出。
每次创建唯一忽略目录`code/output/midi_controls_<时间>_<随机>/`，保留六组
`*_compile.log` / `*_run.log`，不覆盖旧结果。当前实际日志为
`code/output/midi_controls_20261001_213441_dfee4173/`；仓库门禁日志也在该目录的
`check_repo.log`。

| 实际RTL测试 | 结果 |
| --- | --- |
| 全部16384 Pitch原值、16通道×128 CC1、2来源/异常/复位 | 每来源18445事件、36904检查 PASS |
| 加速排队CLK_HZ=64000、最小间隔64拍 | 1286检查、43次控制握手 PASS |
| 真实50MHz、Pitch/CC1合计最小间隔50000拍 | 51222检查、43次控制握手 PASS |
| 真实50MHz/31250 UART→midi_input | 8完整事件、14检查 PASS |
| 原UART Note/CC64回归 | 44检查 PASS |
| 原CC64全通道/值/FIFO回归 | 2058事件、4134检查 PASS |

`check_repo.ps1`九组全部PASS、退出0。Verilator `--lint-only -Wall -Wno-fatal
--top-module midi_input`（公共包/UART/parser/wrapper）退出0，新增排队逻辑
无警告、无锁存器/多驱动诊断；原FIFO索引/零扩展、公共包timescale/映射位宽及
UART位宽提示保留，不把`-Wno-fatal`解释成全部警告已消除。

加速映射测试仅缩短`CLK_HZ`参数以逐个验证映射，不把该组用于实际1kHz证明；
真实50MHz排队组逐次检查成功握手间隔，背压保持与最终值送达有实际断言。
原“不支持CC”测试字节从CC1改为未支持CC2，原断言和检查数量保持。

本轮最高L2。尚未做新增输入逻辑的Gowin综合/PnR/资源/50MHz时序、真实键盘
Pitch/CC1码流或音频效果验收。离散FIFO无限背压会溢出，持续离散流可能使
连续控制饥饿；控制与Note之间没有原子排序保证，这是上述调度合同的明确边界。
M2接入时只用公共FIFO成功握手tap更新控制状态，按正式采样请求锁存参数，
不得把本模块待发槽或去重历史当作已经被音频接受的通道状态。
