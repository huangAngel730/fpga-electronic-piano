# 按键事件转换模块使用说明

`button_event_converter.sv` 把按键去抖模块产生的单周期按下/释放脉冲，转换成项目统一的 64 位 `performance_event_t` 演奏事件。实现文件与本说明同目录：`code/rtl/input/button_event_converter/button_event_converter.sv`。

推荐连接顺序：

```text
低有效物理按键
    -> button_debouncer
    -> button_press_pulse / button_release_pulse
    -> button_event_converter
    -> event_valid / event_ready / event_data
    -> 公共事件 FIFO 或事件接收模块
```

## 依赖与接口

本模块使用 `audio_defs_pkg::performance_event_t`，编译时必须先编译 `code/rtl/common/audio_defs_pkg.sv`。

事件各字段的拼装由该包提供的构造函数 `make_note_event()` 完成，本模块不再自行赋值（2026-09-15，见 `code/docs/技术决策记录.md` D022）。这样"velocity=0 的 Note On 必须转成 Note Off"这条接口规范 3.4 节的规则由构造入口统一保证。

| 端口 | 方向 | 宽度 | 含义 |
|---|---|---:|---|
| `clk` | 输入 | 1 | 系统时钟；当前项目使用 50 MHz `sys_clk` |
| `rst_n` | 输入 | 1 | 低有效复位；本模块在 `clk` 上升沿采样复位 |
| `button_press_pulse` | 输入 | `BUTTON_COUNT` | 每一位代表对应按键的单周期按下脉冲 |
| `button_release_pulse` | 输入 | `BUTTON_COUNT` | 每一位代表对应按键的单周期释放脉冲 |
| `event_ready` | 输入 | 1 | 下游可以接收事件时拉高 |
| `event_valid` | 输出 | 1 | 当前 `event_data` 有效时拉高 |
| `event_data` | 输出 | 64 | 统一演奏事件结构体 |
| `overflow_count` | 输出 | 32 | 本地 FIFO 满时未能入队的事件数，饱和于 `32'hFFFF_FFFF` |

输入脉冲来自 `button_debouncer`，应只保持一个 `clk` 周期。物理按键的低有效电平、同步和消抖已经在前级处理，本模块不直接连接物理引脚。

## 参数与映射

| 参数 | 默认值 | 含义 |
|---|---:|---|
| `BUTTON_COUNT` | 2 | 按键数量，同时决定两组输入脉冲总线宽度 |
| `LOCAL_FIFO_DEPTH` | 4 | 不可反压的按键脉冲进入统一接口前的本地缓存深度 |
| `BASE_NOTE_NUMBER` | 60 | 按键 0 对应的 MIDI 音符号；60 为中央 C |
| `NOTE_STEP` | 2 | 相邻按键之间的 MIDI 音符号增量 |
| `SOURCE_ID` | 0 | 事件来源编号 |
| `CHANNEL` | 0 | 逻辑演奏通道，合法范围 0 至 15 |
| `NOTE_ON_VELOCITY` | 512 | 按下事件的 10 位固定力度，合法范围 1 至 1023 |

按键 `i` 的音符号为 `BASE_NOTE_NUMBER + i * NOTE_STEP`。默认参数下，按键 0 映射为 Note On/Off 60，按键 1 映射为 Note On/Off 62。扩展按键数量时应保证最大的音符号不超过 127。

**这个等间距公式的适用范围（重要，2026-09-15 补充）**：`BASE_NOTE_NUMBER + i * NOTE_STEP` 只能表示按键编号**等间隔**排列的音符。钢琴白键是 C-D-E-F-G-A-B，相邻音符号差值为 2、2、1、2、2、2、1，**不是等间距**；用本公式直接扫白键会在 E-F 和 B-C 两处产生半个半音的音高错误。电子钢琴顶层只有两个实体按键，A4 与 C5 相差 3 个半音，故顶层实例化时显式传 `.BASE_NOTE_NUMBER(69)` 与 `.NOTE_STEP(3)`，**不改本模块的默认值**。正式键盘（8 键以上）必须改用音符查表法，这一点在本文件末尾仍有说明。

## 一个实际例子

使用默认参数时，用户按下按键 0。消抖模块先产生一个时钟周期的脉冲：

```text
button_press_pulse = 2'b01
```

本模块随后生成一条统一事件，并通过 `event_data` 输出：

```text
event_type  = NOTE_ON
source_id   = 0
channel     = 0
note_number = 60
velocity    = 512
```

它表示“板载按键以中等力度按下中央 C”。当 `event_valid=1` 且下游 `event_ready=1` 时，这条事件完成传输。真正的声音由后面的事件 FIFO、声部管理和音频合成模块产生，本模块只负责生成事件。

用户释放按键 0 后，`button_release_pulse=2'b01`，本模块生成 `NOTE_OFF` 事件，音符号仍为 60，通知后级让中央 C 进入释放阶段。

## 与消抖模块连接

```systemverilog
import audio_defs_pkg::*;

logic [1:0] button_press_pulse;
logic [1:0] button_release_pulse;
logic       event_valid;
logic       event_ready;
performance_event_t event_data;
logic [31:0] event_overflow_count;

button_event_converter #(
    .BUTTON_COUNT        (2),
    .LOCAL_FIFO_DEPTH    (4),
    .BASE_NOTE_NUMBER    (60),
    .NOTE_STEP           (2),
    .SOURCE_ID           (4'd0),
    .CHANNEL             (4'd0),
    .NOTE_ON_VELOCITY    (10'd512)
) u_button_event_converter (
    .clk                  (sys_clk),
    .rst_n                (rst_n),
    .button_press_pulse   (button_press_pulse),
    .button_release_pulse (button_release_pulse),
    .event_ready          (event_ready),
    .event_valid          (event_valid),
    .event_data           (event_data),
    .overflow_count       (event_overflow_count)
);
```

事件只在某个 `sys_clk` 上升沿同时满足 `event_valid && event_ready` 时完成传输。在握手完成前，本模块会保持 `event_valid` 和 `event_data` 不变。

同一拍出现多个脉冲时，模块按按键编号从小到大排队；同一按键若同拍同时出现按下和释放脉冲，则先排 Note On、再排 Note Off。由于输入脉冲无法反压，当本地 FIFO 空间不足时，多出的事件不会发送，并计入 `overflow_count`。系统集成时应监测该计数，正常运行期应保持为 0。

## 扩展到更多按键

例如把 8 个按键映射为连续半音 60 至 67：

```systemverilog
button_event_converter #(
    .BUTTON_COUNT      (8),
    .LOCAL_FIFO_DEPTH  (16),
    .BASE_NOTE_NUMBER  (60),
    .NOTE_STEP         (1)
) u_button_event_converter_8 (
    .clk                  (sys_clk),
    .rst_n                (rst_n),
    .button_press_pulse   (button_press_pulse[7:0]),
    .button_release_pulse (button_release_pulse[7:0]),
    .event_ready          (event_ready),
    .event_valid          (event_valid),
    .event_data           (event_data),
    .overflow_count       (event_overflow_count)
);
```

增加按键数时要同时增加前级 `button_debouncer.BUTTON_COUNT`，并根据“同一拍可能同时变化的最大按键数”和下游最长反压时间选择 `LOCAL_FIFO_DEPTH`。本模块不负责修改顶层、CST 或具体按键引脚，这些内容由 M2 在系统集成时处理。

## 仿真验证

在仓库根目录执行：

```powershell
.\code\scripts\run_t022_sim.ps1
```

成功时输出：

```text
PASS: tb_button_event_converter completed all checks
```

当前自检覆盖复位、两键 Note On/Off 映射、同时按键输出顺序、`valid/ready` 反压保持、本地 FIFO 满载、溢出计数和运行中复位。

**2026-09-15 状态更新（T022 并入 develop）**：本模块已由 `code/rtl/board/electronic_piano_top.sv` 例化（实例名 `u_button_event_converter`），按 A4=69 / C5=72 传参，并纳入 `code/scripts/run_t007_sim.ps1` 的 iverilog 全量回归（测试名 `tb_button_event_converter`）。综合、布局布线与时序收敛结果见 `code/docs/验证记录.md`。

上面这条 ModelSim 命令中的工具路径是 M3 本机路径，在别的机器上需先用环境变量 `MODELSIM_BIN` 覆盖；iverilog 路线不需要 ModelSim。

**注意：本模块仍未使用音符查表法**，按键音符通过 `BASE_NOTE_NUMBER + 按键编号 * NOTE_STEP` 公式生成，因此只能直接表示等间隔音符排列。顶层两键（69、72）恰好可用；正式键盘必须改为查表。

## 并行饱和计数（2026-10-02，M3）

本次只替换内部计数计算结构，正式 RTL 与交接包唯一候选的 LF SHA-256 一致：
`65c7978b2e1ce27fc09606cd87ee43fc1a078898acdd109490ca1909f89c0dd7`。

每拍最多丢弃 `2*BUTTON_COUNT` 个事件，`overflow_increment` 因此使用
`$clog2(2*BUTTON_COUNT+1)` 位。由已寄存的 `overflow_count` 并行预计算
增量 1 至 `2*BUTTON_COUNT` 的 33 位加法结果；最高位为 1 时饱和到
`32'hFFFF_FFFF`，否则取低 32 位。本拍事件处理只选择对应结果，减少
ready→丢弃判定→32 位进位/饱和计算串行路径；**不是增加一拍流水线**。

本拍入队、出队及丢弃判定仍在同一上升沿更新 FIFO 和计数：

- 未丢弃时计数保持，复位时同拍清零，最大值保持饱和、不回绕。
- 按键升序、同键按下先于释放、来源/通道/音高/力度和全部端口参数不变。
- 本地 FIFO、`valid/ready` 保持及公共 FIFO 水位/最高水位时序不变。
- 公共 FIFO 满队列同拍 pop 可接受新事件的旁路保持原样；去掉它会增加真实丢键。

新增正式自检从当前生产 `button_event_converter` 与 `performance_event_fifo`
取 DUT，旧版 `button_reference.sv`/`fifo_reference.sv` 为冻结独立 oracle，
哈希和来源在 `code/tb/input/button_counter_timing/oracle_manifest.json`。
`fifo_no_full_bypass.sv` 仅作应被拒绝的反例，不属于生产 RTL。
没有把两份同源候选互相比对，也没有改 M2 已入库的实验入口。

从仓库根目录执行（Python 3.10+、标准库及已有 Icarus；无需板卡）：

```powershell
python -B code/tb/input/button_counter_timing/run.py --selftest
# 非默认工具路径时追加 --cad <oss-cad-suite目录>
# 可追加 --output code/output/<全新ASCII目录>；已有目录拒绝覆盖
.\code\scripts\check_repo.ps1
```

正式自检包含公共深度3/32、本地深度1/2/4、每组20000随机拍、每拍事件/
ready/水位/最高水位/计数、丢弃增量0..4、八个跨字节进位与32位饱和种子、
满队列pop并发、反压及复位；另用当前模块运行原
`tb_button_event_converter.sv`（Icarus路线，TB未修改）。
`--selftest` 还实际编译并拒绝“计数延后一拍”和“取消满pop旁路”的两个行为反例。
不依赖外部 CallBack 目录，全部新日志留在忽略的 `code/output/`。

本轮实际结果：附件原对照202690项PASS；正式四组405430项PASS、原TB在
Icarus和原T022 ModelSim入口均PASS、两个反例正确非零退出，check_repo九组PASS。
证据为 `code/output/button_counter_packet_20261002/`、
`code/output/button_counter_formal_final_20261002/results.json`、该最终目录的
`check_repo_final.log` 和 `original_t022_modelsim_final.log`。
本次等级 **L2**；未新增整机综合/PnR、未作ADSR或严格闪光组合、未烧录/实物测试。
整机时序与组合复核由M2接手，不能沿用旧隔离报告当作本次整机时序结果。
