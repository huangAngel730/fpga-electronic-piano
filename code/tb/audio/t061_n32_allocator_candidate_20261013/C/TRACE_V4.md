# C v4 公开端口驾驶与观察

`tb_c_n32_r1_v4.sv` 直接实例化冻结的 `b_n32_r1_wrapper`，参数固定
N=32、RESPONSE=1、40 MHz。业务输入只来自独立生成的 `plan_v4.jsonl`；
`generate_tb_v4.py` 将计划转换为 `c_plan_v4.svh`，输出必须为新文件。
同目录生成 `c_plan_v4.mem`，128-bit 每项命令格式为 opcode[127:120]、
保留零[119:96]、等待拍数[95:64]、参数[63:0]。include 仅加载表并循环派发，
不按约一万项计划展开自动 task 调用，避免 Icarus 的 elaboration 栈溢出。
运行 VVP 必须传 `+C4_PLAN_MEM=<冻结快照中的绝对 mem 路径>`，收据同时绑定
include 和 mem 两个 SHA。业务计划及独立 expected 不因编码变化而改变。
驱动任务均为静态任务且只从顺序主进程调用，无递归／并发重入；操作名称和
mem 路径使用固定 packed 缓冲，避开本机 Icarus 动态 string／automatic task
清理路径。此兼容调整保持输入计划和观察标签语义，编译结果另由实际收据确认。

```powershell
python generate_tb_v4.py --plan <plan_v4.jsonl> --output <include-dir>/c_plan_v4.svh
```

生成工具不运行 HDL。编译源与工具由外层冻结 runner 从 B 精确封存绑定。
TB 中 sample 接受沿相距至少 833 拍；输入全部在下降沿修改。事件真实握手后
等待公开 event_ready 恢复，避免把 release 扫描前的短暂 router IDLE 当作稳定槽状态。
`await_retirement` 同时要求累计实际 done mask 和公开 occupied/releasing 清零。

保持 B 独立数学审计原格式的 `I/J/U/G/W/C/A/L/F/P/X/Z/Y/R/END`。
输入、接受、控制快照、结果及 read 资格在上升沿 PRE_NBA 观察；`L` 为既有
数学日志 POST_NBA 逐槽观察，`Y` 保持原格式的 POST_NBA read 响应。
新 `RY` 给出该响应下一 PRE_NBA 可见沿，供公开接口 R1 检查。解析器需按标签
明确相位，不能把 Y 与 RY 计为两次响应。

新增稀疏行字段如下。除标记为 hex 的字段外均为十进制；省略沿表示值保持，
不能解释为零。驾驶与公开 ready 状态变化必有 D／AS，实际握手必有对应记录。

| 标签 | 字段（不含标签） | 观察意义 |
|---|---|---|
| C4 | 固定描述文字 | 格式／采样相位说明，不是测试结论 |
| OP | cycle index BEGIN kind／cycle index END | 独立计划操作边界 |
| D | cycle rst_n cancel event_valid event_data(hex) sample_valid sample_id(hex) result_ready read_valid read_slot | 实际驾驶变化 |
| AS | cycle audio_state router_state idle event_ready sample_ready read_ready | 状态或 ready 变化 |
| RA | cycle audio_state router_state | 下降沿、异步复位拉低前的公开状态；用于检查 cancel 后 DRAIN 中复位 |
| CS | cycle id(hex) occupied(hex) sources(hex) channels(hex) generations(hex) value(hex) | 控制快照真实 valid/ready 握手 |
| CR | cycle mask(hex) generations(hex) | 控制释放批次真实握手 |
| RD | cycle lowest_slot generation(hex) mask(hex) | 后端 done 有效 mask；多槽可同沿出现 |
| RT | cycle slot occupied(hex) releasing(hex) | 计划要求槽的退休完成边界 |
| RQ | cycle slot | 公开 read 请求握手 |
| RY | cycle slot context(hex) | 公开 read 输出 PRE_NBA 可见沿 |
| RS | cycle slot audio_state | read_valid=1 且 read_ready=0 的真实沿 |
| K | cycle id(hex) left right late clipped publish | 每个有效、未取消结果沿，含 HOLD |

所有槽 packed 字段均 slot0 在低位。CS.value 直接保持原公开端口打包：
整体 `{all_range, all_modulation, all_bend}`，不是交错的每槽29位；各子域
分别按5／12／12位槽宽展开。RD.lowest_slot 只是 mask 中最低有效槽的便利字段，
完整 mask 是并行 done 观察，实际退休仍以 RT／U 的 occupied 清除证明。

v3 原计划、checker 和证据保持。v4 此说明只定义 TB／观察格式，实际执行及验收
结果以对应 runner、源码 SHA、原始日志和独立 checker 收据为准。
