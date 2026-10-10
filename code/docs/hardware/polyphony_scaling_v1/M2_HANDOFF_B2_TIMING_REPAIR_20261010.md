# 给 M2：B2 时间 checker 返修

待用户转发，尚未送达。

M2，已按 Callback2 的反馈完成 B2a/B2b 时间 checker 最小返修：由源码 FSM 推导 A、逐槽 L 和首次 valid 日历，B2b 每沿检查首次 F 精确且唯一，P 只作输出握手；B2a O 检查明确限定原 fixture，不外推任意反压。合法取消、身份失效和 DSP 非回滚语义保持。

新软件终验 47 步符合预期退出码：6+2 原完整 capture 和两份短正例通过；你提供的 7 份时间错例、新增 14 份错沿/缺失/重复反例、3 份 deadline 字段反例均指定诊断拒收；F 不变而 P 延迟正例通过。原 9+6 语义诊断保持，原行为日志只读核验，原 gain capture 仍以 MATH_GAIN_PCM 拒收；4+6+40 单测通过。详见新源码 SHA、命令、原 stdout/stderr、退出码、收据和封存 manifest。发布提交号及九门禁结果以附件 GIT_DELIVERY.json / publish_gate 为准，不回填旧收据。

未改 RTL/ROM/原 capture/共享状态或旧封存，未重跑长程 RTL/Gowin，无新增综合或设备操作。完整 T060/T061 及原覆盖限制保持；请复核本包并统一登记。本包不包含另一项已授权 RAM 后台 PnR 的时序结论。后续按授权继续 RAM 候选和同一候选 N8 独立阶段。
