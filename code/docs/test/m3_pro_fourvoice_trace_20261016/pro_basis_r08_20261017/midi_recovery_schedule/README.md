# R8-17 midi_recovery_schedule

当前L0源码/用例READY前静态准备，功能NOT_RUN；统一由夜间任务1冻结T组执行，本窗口功能消费0。按冻结C6实际解析器规范生成新的异常/恢复外部字节与时间计划。

生产CLI（此处未执行）：

```powershell
python -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/midi_recovery_schedule/r08c17_schedule.py --input <input.json> --output <new-result.json>
```

输入：scenario=running_realtime_zero_velocity/half_message_reset_new_status/sysex_illegal_status_resync/malformed_uart_stop_policy，parser_sha256=336d867856a7b3956d524105137c035ec2637fea936538979182669987212071，first_cycle，byte_spacing>=14000。

独立机器输出：M3_R08_EXTERNAL_MIDI_RECOVERY_PLAN_V1，byte_plan/resets/规范原行引用/expected_message_semantics；应用拍、slot/retire和未知UART错误策略保持UNRESOLVED。

边界：SPEC_ORIGINALS保存C6 parser/pkg本体；本组件不仿真解析器，不复跑R6-2旧23event，不驱内部ready，不复制DSP规则。

新用例共6项，见对应tb/board/.../pro_basis_r08_20261017/midi_recovery_schedule/CASES.json。selftest.py导入仅定义，run_case(case_id, output_dir)独占创建未存在的目录，构造输入先落INPUT_BEFORE_CALL.json，实际输出在断言前落ACTUAL_BEFORE_ASSERT.json；失败保留原件并抛异常。夹具真实返回PENDING/UNKNOWN/UNRESOLVED时，CASE_EXPECTATION_MATCHED仅表示预期符合，不冒称实义通过。所有读入对象完整保留，不以row_count摘要代替原件。

HDL/EDA/设备/外部EXE/子进程0；旧R6-6的28/20、B19、D22不重跑，旧摄取器/runner只读。board_release_allowed=false，真实Pro/M1/来源/物理准入仍PENDING。Git与共享状态由总控/M2按原职责处理。
