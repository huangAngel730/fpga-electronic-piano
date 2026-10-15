# M3 → M2：T052新长窗精确静态准备与执行范围请求

待用户转发，尚未送达。本文不是许可，不修改共享编号表，也不预占T/V/D编号。

M1确认输入版本`T052_LONG_50M1042_FROZEN_FCW_R01`，确认文档SHA
`56574246ebd7fe75bf59ea7f583ffe2c00f5593b8567230dbb6992cfe857b555`。
冻结v5/DDS/mixer/ROM全部从原归档成员核SHA，原件及旧capture未改。

M3本次仅新增三个原授权树下的长窗子目录：

- `code/software/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015/`
- `code/tb/audio/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015/`
- `code/docs/test/t052_publication_acceptance_20261012/LONG_WINDOW_PREPARATION_20261015/`

## 请决定的精确范围

1. 采用M1固定全部8536336沿、四次1024样本独奏+4096样本合奏，不缩窗、不拆批；A/P/C=8207/8201/6、open=0为静态预期。
2. 接受新紧凑日志表达：170位独立controls.hex，300位逐沿cycle/time/实际控制/公开ready-valid-ID记录，发布JSONL和独立异步reset轨迹；完整布局见软件README。此选择减少JSON重复字段，所有沿仍保留。
3. 约375.6MB输入、648.8～657.3MB全观察；建议750MiB捕获/1200MiB全输出上限、至少2GiB空闲盘。没有实跑吞吐量，300s运行预算是否足够仍未知。
4. 未来在全新ASCII目录一次compile+一次vvp：每步90/300s、离线check300s、总900s的提案；无自动重试，任何失败保留源/原日志/退出码并停止。原旧许可不复用。
5. 精确工具路径、SHA、真实`-V`版本查询原日志和静态依赖库存见封存proposal.json及tool_metadata/receipt.json。实际加载依赖仍UNKNOWN，静态库存不冒充加载记录；最终批准前须落实执行收据/墙钟/日志上限监督机制。
6. 原始capture checker即使逐沿与事务全匹配也只报告`transaction_comparison=PASS / provenance=NOT_VERIFIABLE / exit3`。需要新批准收据绑定源/工具/输入/输出后再签实际RTL等级，不以日志META或自报origin认证来源。

## 当前完成与遗留

独立输入和冻结FSM黄金、公开端口TB/observer、流式事务checker及17项手写软件正负例已实现；完整控制输入SHA和静态账本已生成。当前仅L0/软件自检，实际新HDL编译0、RTL运行0、EDA0、设备0。TB/observer未编译，其语法、调度和运行表现待许可后验证。

已知范围区别无需修改算法：M1的T052 v5为50MHz/固定1042拍/倍频FCW纯DDS隔离源；当前138K基础R04为40MHz、另有ADSR/音色/效果与非倍频合同。两者不可拼成同版整机。旧4207完整性UNKNOWN，已签128沿/T060/旧数学不重跑。

若希望本新长窗也取得PCM数学、active/clip、左右/held数据或音频验收，需另行单列公开声音观测与冻结数学参考范围；本提案不包含这些结论。

本轮无需M1重新决定频点。若改变窗口、分批或频点，先由M1发布新输入版本；若仅追加执行身份/批准监督，不改变输入版本，但新的工具和配置SHA必须重新封存。

交付命令、实际退出码、输入及产物SHA、原始日志、Git提交/推送状态见同目录`RESULT.md`与封存收据。完整T052维持PARTIAL。
