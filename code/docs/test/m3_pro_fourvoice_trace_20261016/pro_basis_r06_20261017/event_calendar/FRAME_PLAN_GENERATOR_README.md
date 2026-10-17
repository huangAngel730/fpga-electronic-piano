# R6-5 文件式 FRAME_PLAN 生成器候选

状态：**L0 静态候选，NOT_RUN**。R6-5 的初始组和唯一修复组已经耗尽；本增量源码、自检候选均未执行、导入或编译。后续运行必须由 M2 明确绑定新的 R6-5 定向增量许可、精确输入和时间盒，不能借用 R7-A/B/C/D 的额度。

入口候选为 `frame_plan_generator_candidate.py`。它只接受两个文件：

1. M2 已冻结且 SHA 匹配的 `FRAME_PLAN_RULES.json`；
2. 独立输入文件，包含源文件身份、每个 epoch 的窗口类型、reset 断言周期、`release_cycle`、`stop_cycle` 和唯一 finish。

接口中没有 trace 参数。若输入对象出现 `trace`、`trace_path`、`observed_frames` 或 `observed_frame_rows`，候选会拒收。交易是否存在、是否取消、是否空闲都不会终止帧生成；每个有效窗口均按冻结公式

`cycle_k = release_cycle + ceil(128 * k * 2**32 / 659706977) - 1`

生成至 `stop_cycle`，其中 `release_cycle` 是 PRE_NBA 首次看到同步复位为高的功能沿。相邻 epoch 必须满足 `next.reset_assert_cycle = previous.stop_cycle + 1`，不允许静默省略未声明的全局周期。若复位保持到 finish 且没有功能释放沿，必须使用 `window_kind=RESET_ONLY`、`release_cycle=null`，该 epoch 明确投影为空帧列表；不得伪造 finish 之后的 release。

上述窗口坐标与 R7-A 的全局 `cycle` 完全一致，从 0 开始；因此 reset、release、stop 和 finish 都允许取 0。公式里的 `k>=1` 只表示释放后第几个局部帧事件，不是对全局周期的下界。

输出只有一个规范身份 `M3_R06_UNIQUE_FRAME_PLAN_V1`，另提供两个无损投影：

- `M3_R06_INDEPENDENT_FRAME_PLAN_V1` 使用 `frame_cycles`，供旧 event calendar 读取；
- `M3_R06_TX_FRAME_PLAN_V1` 使用 `cycles`，供旧 TX checker 读取。

两个投影携带完全相同的 `canonical_plan_id` 和 `canonical_identity_sha256`。它们是同一计划的字段名投影，不能作为两份独立期望互相替代或投票。当前 authority 固定为 `CANDIDATE_INDEPENDENT_PLAN_NOT_M2_ADMITTED`，`real_authority_claimed=false`，因此旧真实检查器应保持 PENDING；只有 M2 对精确输入和产物另行准入后才能提升权威状态。

`frame_plan_selftest_candidate.py` 列出首帧、复位重启、reset-only 末 epoch、双投影同身份、禁止观察 trace、窗口空洞/重叠、finish 边界和防覆盖等候选用例。它同样是 NOT_RUN。
