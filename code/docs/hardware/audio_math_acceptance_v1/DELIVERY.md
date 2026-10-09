# T060 开工进展：组件自检通过，真实 A1 未完成

2026-10-09；遵循 D043 新路径以及 D044 当前冻结版本／成果优先范围。
当前是局部离线 Python 自检证据，不是完整 A1、A2 或 T060 通过；T061 尚未开始。

已新增严格 JSONL／16-tag F 解析、原序 RESET／REQUEST／COMMIT 及 D-STATE 运输核对，
整数 note FCW／PitchMod 和有状态 DDS 参考。DDS 独立维护相位、亮度窗、pending 换表；
没有把 ADSR 状态拿来替代亮度窗，也没有默认使用观测 FCW 当 expected。

正式组件运行：`code/output/m3_audio_math_prereq_20261009_01/receipt.json`，
退出 0，177.420 秒，状态 `COMPONENT_SELFTEST_ONLY`。
26 项 unittest 通过，46 个带指定诊断的错误输入拒收；所有生成测试数据均明确为 SYNTHETIC。
覆盖合法全静音、16 tags、pre-NBA/retrigger、复位取消、480/960/1440 窗口与 wrap，
及完整 END 的末条 FCW／table／phase 语义错误。
九项仓库门禁 PASS，退出 0；56 份只读输入与任务 Git blob 的 LF 身份一致。
其中七份为 ROM；此 56 是本轮源／模板／证据输入清单，不是“56 原反例已通过”。
原 stdout/stderr、完整命令、退出码、Python 路径版本、源／输入／日志 SHA 均在收据及邻接日志中。

另一次默认验收入口运行保存在
`code/output/m3_audio_math_missing_capture_20261009_01/receipt.json`：
2.484 秒，runner 退出 2，`BLOCKED_MISSING_ORIGINAL_CAPTURE`，没有误报通过。

尚缺原 capture2 双文件、同次生成 TB／observer 的清单及原 56 反例封存输入。
准确名称、SHA 及可用 ZIP 标识见 `M2_INPUT_REQUEST.md`。
即使收到双文件，仍要接通独立事件／控制快照／LFO 时间线后才能完成 A1；
包络／同步 ROM／增益／混音到 PCM 数学属于后续 A2，当前不能声称已覆盖。

新文件仅在任务 A 三处；未改生产源码、原 M1 文件、RTL／ROM、工程、公共包或共享登记。
没有新音频 RTL 仿真、Gowin 构建、设备安装、Flash、串口或接线操作。
本轮新增文件尚未 Git 提交或推送。旧测试与全部旧证据保持。
