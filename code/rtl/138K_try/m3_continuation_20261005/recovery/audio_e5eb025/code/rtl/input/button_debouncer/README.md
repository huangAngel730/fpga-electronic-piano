# 按键去抖模块使用说明

`button_debouncer.sv` 用于把低有效的异步机械按键转换为稳定状态和单周期事件脉冲。模块先对每一路输入进行两级同步，再要求新状态连续保持指定时间，避免触点抖动产生重复按键事件。

## 接口

| 端口 | 方向 | 宽度 | 含义 |
|---|---|---|---|
| `clk` | 输入 | 1 | 输入域系统时钟 |
| `rst_n` | 输入 | 1 | 低有效同步复位 |
| `button_n_async` | 输入 | `BUTTON_COUNT` | 物理按键输入，低电平表示按下 |
| `button_down` | 输出 | `BUTTON_COUNT` | 去抖后的稳定状态，高电平表示按下 |
| `button_press_pulse` | 输出 | `BUTTON_COUNT` | 确认按下时输出一个 `clk` 周期的高脉冲 |
| `button_release_pulse` | 输出 | `BUTTON_COUNT` | 确认释放时输出一个 `clk` 周期的高脉冲 |

复位期间所有输出为 0，按键按住不放不会重复产生 `button_press_pulse`。

## 参数

| 参数 | 默认值 | 含义 |
|---|---:|---|
| `BUTTON_COUNT` | 2 | 同时处理的按键数量 |
| `CLK_FREQ_HZ` | 50,000,000 | `clk` 的频率 |
| `DEBOUNCE_TIME_MS` | 20 | 按下和释放共同使用的去抖时间 |

修改 `BUTTON_COUNT` 会同时改变输入、状态和两个事件脉冲总线的宽度。综合时 `for` 循环会展开成多套并行硬件，每路按键拥有独立计数器，不是由软件逐个轮询。

## 两路按键例化

当前板级计划保留 `USER_BUTTON0` 作为系统复位，`USER_BUTTON1` 和 `USER_BUTTON2` 作为两路临时演奏按键。物理按键均为低有效。

```systemverilog
logic [1:0] user_button_n;
logic [1:0] button_down;
logic [1:0] button_press_pulse;
logic [1:0] button_release_pulse;

button_debouncer #(
    .BUTTON_COUNT     (2),
    .CLK_FREQ_HZ      (50_000_000),
    .DEBOUNCE_TIME_MS (20)
) u_button_debouncer (
    .button_n_async      (user_button_n),
    .clk                 (sys_clk),
    .rst_n               (rst_n),
    .button_down         (button_down),
    .button_press_pulse  (button_press_pulse),
    .button_release_pulse(button_release_pulse)
);
```

建议保持以下索引关系：

| 总线位 | 板级按键 | FPGA 引脚 | 电气属性 |
|---:|---|---|---|
| 0 | `USER_BUTTON1` / `EX_KEY.1` | AB13 | Bank 9，LVCMOS15，1.5 V 上拉，低有效 |
| 1 | `USER_BUTTON2` / `EX_KEY.2` | Y12 | Bank 9，LVCMOS15，1.5 V 上拉，低有效 |

本模块不直接修改顶层或 CST。顶层例化和引脚约束由 M2 集成，端口名必须与最终 CST 保持一致。

## 扩展到更多按键

例如处理 8 路同类型低有效按键：

```systemverilog
button_debouncer #(
    .BUTTON_COUNT     (8),
    .CLK_FREQ_HZ      (50_000_000),
    .DEBOUNCE_TIME_MS (20)
) u_button_debouncer_8 (
    .button_n_async      (button_n_async[7:0]),
    .clk                 (sys_clk),
    .rst_n               (rst_n),
    .button_down         (button_down[7:0]),
    .button_press_pulse  (button_press_pulse[7:0]),
    .button_release_pulse(button_release_pulse[7:0])
);
```

扩展物理按键前必须另外确认每一路的 FPGA 引脚、Bank 电压、上拉方式和有效电平；不能只修改 `BUTTON_COUNT` 就直接接线。

## 仿真验证

自检 testbench 位于 `code/tb/input/tb_button_debouncer.sv`。它使用缩短后的 10 kHz 时钟和 1 ms 去抖参数加快仿真，但状态机和边界逻辑与默认参数相同。

为避免旧版 ModelSim 处理中文路径时出现问题，先把 RTL 和 testbench 复制到纯 ASCII 临时目录，然后执行：

```text
vlib work
vlog -sv button_debouncer.sv tb_button_debouncer.sv
vsim -c -l vsim.log tb_button_debouncer -do "run -all; quit -f"
```

成功时控制台应出现：

```text
PASS: tb_button_debouncer completed all checks
```

当前验证覆盖复位、短抖动、去抖边界、长按不重复、释放边界、短毛刺、两路同时按下和按下期间复位，共 8 组场景、27 项自动检查。

**2026-09-15 状态更新**：本模块已由 `code/rtl/board/electronic_piano_top.sv` 例化（实例名 `u_button_debouncer`），并纳入 `code/scripts/run_t007_sim.ps1` 的 iverilog 全量回归；综合、布局布线与时序收敛已通过（见 `code/docs/验证记录.md` V0040），**替换后的码流尚未重新上板**。本文件原位于 `code/rtl/input/README.md`，2026-09-15 目录改为"每模块一子目录"后随模块下移至本目录；同级 `button_event_converter/` 是 T022 的按键转统一演奏事件模块，用法见其自身 README。
