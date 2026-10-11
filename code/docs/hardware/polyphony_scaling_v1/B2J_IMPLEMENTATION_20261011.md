# B2j 公开结果握手与排空周期

2026-10-11，M3 按 D043/D044 在唯一独立混合候选内补齐 B2i 尚未知的局部完成围栏。
这不是正式架构、整机服务上界或物理时序批准；共享状态/编号表由 M2 统一登记。

## 实现和边界

新 `tb_b2j_completion.sv` 仅从公开端口逐拍记录输入/输出：整个日志连续 PRE-NBA
T 记录，包含实际 reset/cancel、sample valid/ready、result valid/ready、idle、
注入/读请求、publish、backend launch、两种 request ID 及左右 PCM。
不读取层级内部状态，不 force、不改功能源或原 TB。

`b2j_check.py` 独立模拟 wrapper/B1/backend 的旧状态 RHS 耦合转移：

- 空闲且路由静止时，C−J=12+6N；首次 F 来自已固定 `backend_calendar`，不由捕获 F 反填。
- P 当沿后端转 IDLE；P+1 B1 看到后端 empty 转 IDLE；P+2 wrapper 看到 B1 idle 转 IDLE；
  第一个 PRE-NBA 公开可接收沿为 P+3。没有注入、读阻塞、取消时成立。
- HOLD 取消的后端先进入 DRAIN，再看已完成的 pitch/ROM 排空；最后 cancel 沿后第4个观察沿恢复。
  重复 cancel 延长停止，不回滚 DSP/router。没有验证早期取消的通用上界。
- 拒绝的注入仍占 result_empty 围栏，7个后续注入沿使正常 P 后恢复延长到10拍；不删除该保护。
- read_valid 在 IDLE 阻止 sample_ready，但不将 idle 改成 busy；整个域 reset 可打断 HOLD/DRAIN。

无反压且路由静止的 J→首次 F / J→下一可接收分别为 N4/R1 **68/71**、
N32/R1 **348/351**、N32/R8 **572/575** 拍。这只是本精确候选的局部空闲入口合同；
输出反压可以任意长，因此不宣称无条件帧 II，更不宣称 MIDI 最坏服务时间已闭合。

左/右 PCM 仅检查 signed24 范围与 HOLD 期间稳定性，期望不来自捕获输出做数学反推。
本阶段没有重新签 PCM 数学；既有 B2F/G/H 的数学证据独立保留。
输入事件只用于使后端真实活动，测量时路由静止；event_ready 记录但没有在此重算事件调度。

## 验证和反例

三个配置分别13请求、13首次valid、10实际发布、2 HOLD取消、2忙态reset、3公开读阻塞沿。
完整捕获包含正常、8/31拍输出反压、注入围栏、重复cancel及恢复。
新 checker 必须逐沿吻合，不能只匹配周期区间或最终数目；完整 END 与周期连续性必核。
Icarus 正常 $finish 的唯一末行来源脚注按精确格式识别，其他额外行拒收。

8个完整 capture 语义反例：提前/推迟ready、提前/推迟首次valid、HOLD数据改变、
假publish、读阻塞错误接收、END计数错误。都保留完整结束，不以截断/超时凑拒收。
两个实际可编译副本变异只写本轮 output：wrapper 排空忽略 B1 busy、sample_ready 忽略读阻塞。
二者 compile0/sim0 完整结束，独立 checker1，分别指定 COMPLETION_IDLE/COMPLETION_SR。

10项新增软件自检包含正常P+3、HOLD取消+4、重复cancel、注入延长、提前ready拒收、
公开读阻塞、HOLD/DRAIN reset、数据稳定、严格整数配置、未知/不完整记录拒收。
源码/ROM pin 与新运行前后 SHA、原命令/工具身份/stdout/stderr/真实退出码/时限齐套。

## 未验

全域最坏事件服务、早期在途取消界、任意注入持续时间的可用性（128拍故障围栏未改）、
全部N配置、冻结L整个top逐时钟等价、映射资源、综合、PnR/STA、正式接入、设备均未新验。
完整T060/T061不关闭；正式档位/资源/代表综合配置和新整机STA由M2决定。
