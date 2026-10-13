# P0-2 checker 合同

## 固定输入和顺序

1. 固定计划 SHA：
   `b2d0cb1ba0bf3cd4b2d636f3d4cb7ac286558238ae2b52c3e9e43ba54ee5ef02`。
2. 冻结日历 SHA：
   `0fdf4bb1530453cbbce14136bcae082ca1ff28e04d96402065f4c916ecf36058`。
3. 先从输入和冻结 FSM 算 expected，再打开 controls、observations、
   publications、resets 四轨迹；实际 ready/valid 不能反填黄金。
4. 时钟为 20 ns，首个上升沿 10 ns；正常沿时间为 `10 + 20*cycle`。
   异步复位时间为 0、40、1280、1320 ns，采用 pre-NBA 口径。

## META 与 END

四轨迹 META 精确包含 `type/origin/sampling/time_unit/time_precision/`
`clock_period_ns/first_posedge_ns/dut_sha256/rom_sha256/plan_sha256/`
`tb_sha256/observer_sha256/tool_sha256`。controls、observations、publications
的真实 origin 只能是 `RTL_SIM_PUBLIC_PORTS_V1`，resets 只能是
`RTL_SIM_RESET_SIGNAL_V1`；软件 fixture 只能是
`HANDWRITTEN_SOFTWARE_FIXTURE`。

END 字段集合必须精确；`accepted/published/cancelled/open/last_cycle/rows`
按所在轨迹要求必须为 JSON integer，布尔和浮点数均拒收。`open>0` 保持
UNKNOWN，不从结果缺失反推取消。

## actual 模式来源

actual 模式不相信 META 自报身份。它还必须验证外部钉住的组合 manifest、
approval 和 run receipt，并逐项核对：

- 源与工具 before/after 身份；
- 每个冻结源快照；
- compile/run argv、绝对 cwd、退出码、timeout、可执行文件；
- stdout/stderr 身份；
- 四轨迹 artifact 的路径、字节和 SHA。

单测中的结构化 receipt 只存在于临时目录，用于逐个命中 validator seam
的拒收分支；从未用它执行成功的 actual CLI，也不声明 RTL 已验证。
