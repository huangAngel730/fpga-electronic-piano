# T052 P0-1 driver／observer 静态后继

岗位 M3；主代理实施 P0-1，子智能体负责 P0-2。复核和实际执行放行统一归 M2。

## 驱动日历

新模块 `tb_t052_control_128_v2`、`t052_public_observer_v2` 保留旧 9998438 原文件。只读固定计划 SHA `b2d0cb1ba0bf3cd4b2d636f3d4cb7ac286558238ae2b52c3e9e43ba54ee5ef02` 和原 170-bit memory。

驱动索引 `driver_index` 与观察编号 `observer_cycle` 分开：time0 驱动 row0；每个下降沿先阻塞递增驱动索引，再驱动相应 row。上升沿先观察当前 cycle，观察编号随后 NBA 加一。128 个上升沿为整数 ns `10+20*cycle`；第 127 沿为 2550ns，2551ns 结束。下降沿输入稳定时间为 `20*cycle`。原问题 `0,2,...127,127` 在新源调度重算中必须拒收。

`schedule_check.py` 独立按 170-bit 字段从低位解包原 memory，与固定 JSON 计划的每个字段比较；从新 TB 有界过程语法提取初值／步长／索引／时钟延迟，按 posedge active → NBA → negedge 顺序求全部128沿。它仅支持本文的新调度子集，遇到其他源结构直接拒收，不是通用 SystemVerilog 解释器，也不代替 elaboration。

## 观察及复位

公开端口在 posedge active 区读取，DUT 的 NBA 更新随后发生。观察源不使用 `$strobe`、采样延迟或 DUT 内部层级。四份 META 均绑定 DUT／ROM／plan／TB／observer／runtime SHA 和时间合同；前三份 origin 为 `RTL_SIM_PUBLIC_PORTS_V1`，reset 为 `RTL_SIM_RESET_SIGNAL_V1`。

时间单位明确 `1ns`、precision `1ps`，并设置 `$timeformat(-9,0,"",0)`；记录使用 `%0d` 的 `$time` 整数 ns，时钟周期20ns。time0 在 inactive 区记稳定 reset 初值，此后 `always @(rst_n)` 记录每次异步转移，包括两个观察沿之间的脉冲。四态未知值触发失败。

固定计划应有复位记录 `(time,cycle_visible_next,rst_n)`：`(0,0,0)`、`(40,2,1)`、`(1280,64,0)`、`(1320,66,1)`。reset 事务归宿在首个低电平观察沿记 CANCEL，异步实际时间由独立 reset 轨迹保留。多余脉冲、漏失转移、窗口不足不得签 PASS；P0-2 比较整份轨迹。现有源码和软件推演不能证明模拟器实际完整捕获。

## 阶段边界

仅静态／软件 L0/L1准备，未执行 lower、compile、VVP、Gowin 或设备操作。`combination_manifest.json` 的 `execution_authorized=false`；拟议命令只供 M2 预检，不能执行。未验真实128沿、声音数学、物理时序及旧4207完整性；完整 T052/T060/T061 保持 PARTIAL。

本次不改共享表；M2 收到精确组合和原日志后统一登记。交接待用户转发，尚未送达。
