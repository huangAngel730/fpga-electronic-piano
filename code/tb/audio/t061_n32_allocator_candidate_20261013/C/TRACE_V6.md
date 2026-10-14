# C v6 独立短后继

保留 v4 源码和实际 R05 C06 死锁证据。死锁条件是上一帧尚未发布就把
result_ready 拉低，随后新 sample 等待上一 held 结果被消费，计划无法前进。
v6 在所有拉低 result_ready 操作前加 wait_idle，确认上一帧真实排空。

`generate_v6.py --segment SHORT_SUFFIX` 从实际 reset、四个公开 NoteOn 输入和
一次正常 sample 开始，独立运行 C05–C09。输入黄金重新从冻结模型生成，不继承
原 C04 capture 的声音状态。原 C00–C04 实际证据只能另行独立审计／绑定，不能
把短后继的 END 冒作完整计划的一次执行。`--segment FULL` 为完整后继输入准备，
本次使用哪个 segment 必须明确记录在 manifest、plan 和执行收据中。

TB 顶层 `tb_c_n32_r1_v6`、include `c_plan_v6.svh`，命令表通过
`+C4_PLAN_MEM=<冻结的 c_plan_v6.mem 绝对路径>` 读取。命令编码沿用
`generate_tb_v4.py` 的固定宽度 mem 编码；trace 的标签和 PRE／POST NBA 口径
沿用 [TRACE_V4.md](TRACE_V4.md)。

每项 OP 从 BEGIN 到 END 最多 5000 个真实时钟沿。未完成即触发
`C6_OPERATION_NO_COMPLETION`，报告 OP 编号、年龄及公开 audio／router 状态。
连续 CPU 活动或重复 stalled-read 日志不能延长这一语义上限。正常最大 sample
节奏为 833 拍，5000 拍留出显著余量且不会等待无界业务进展。

本说明定义后继准备与运行边界，不替代实际编译、RTL capture、独立复算和封存收据。
