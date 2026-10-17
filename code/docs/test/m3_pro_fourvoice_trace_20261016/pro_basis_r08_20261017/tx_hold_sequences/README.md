# R8-14 tx_hold_sequences

当前L0源码/用例READY前静态准备，功能NOT_RUN；统一由夜间任务1冻结T组执行，本窗口功能消费0。从独立事务/采纳动作计划生成startup/null、ID0、重复HOLD及reset失效旁带场景。

生产CLI（此处未执行）：

```powershell
python -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/tx_hold_sequences/r08c14_sequences.py --input <input.json> --output <new-result.json>
```

输入：plan{schema,origin=SYNTHETIC_INDEPENDENT_PLAN,actions[{cycle,kind=RESET/COMMIT/CLOSE_TRANSACTION/STARTUP/NEW/HOLD,req_id,left,right,clip_mask}]}；可带observed逐行核对。不得带observed_rows反推期望。

独立机器输出：M3_R08_TX_SCENARIO_V1 rows/history或SCENARIO_MATCH_SYNTHETIC。输出仅TX侧场景，按epoch/cycle加入完整公开capture时缺字段保持null，不冒充完整61列或FRAME计划。

边界：不调用旧摄取器或旧checker；不新增内部请求、DSP或权威帧计划。

新用例共6项，见对应tb/board/.../pro_basis_r08_20261017/tx_hold_sequences/CASES.json。selftest.py导入仅定义，run_case(case_id, output_dir)独占创建未存在的目录，构造输入先落INPUT_BEFORE_CALL.json，实际输出在断言前落ACTUAL_BEFORE_ASSERT.json；失败保留原件并抛异常。夹具真实返回PENDING/UNKNOWN/UNRESOLVED时，CASE_EXPECTATION_MATCHED仅表示预期符合，不冒称实义通过。所有读入对象完整保留，不以row_count摘要代替原件。

HDL/EDA/设备/外部EXE/子进程0；旧R6-6的28/20、B19、D22不重跑，旧摄取器/runner只读。board_release_allowed=false，真实Pro/M1/来源/物理准入仍PENDING。Git与共享状态由总控/M2按原职责处理。
