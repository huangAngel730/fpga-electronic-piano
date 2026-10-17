# R7-B 开工

基线4fd3366e42fd2356e56eb96eee70b6771afd4bb1；task-day2，时间盒北京时间18:55–22:55。仅三条M3根下pro_basis_r07_20261017/public_equivalence_tb；完成后串行做R7-D，旧R06及M1/M2源只读。原R06七包已消费，不重跑。

交外部输入双顶层等价TB、精确原包/四候选替换装配、原外部13位输出及UART STAT首差异检查器。38obs在旧top为NOT_PUBLIC。时钟沿/复位/窗口先固定；clock_plan_sim只签模拟模型，不签Pro PLL。已知原compile.f漏dds_oscillator，只记录并拒编译准入，不加未授权源。

新软件唯一初组≤90秒；若该组发现新缺陷，仅一次≤60秒定向修复。先RUN_SPEC冻结源码/输入/工具SHA，再执行。HDL/EDA/设备0。TB为L0待编译，软件仅L1合成检查，真实等价PENDING；board_release_allowed=false。无Git写入。
