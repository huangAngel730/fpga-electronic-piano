# R8-16 midi_ingress_arrival

当前L0源码/用例READY前静态准备，功能NOT_RUN；统一由夜间任务1冻结T组执行，本窗口功能消费0。外部串行输入边沿独立8N1解码与字节计划到达对齐。

生产CLI（此处未执行）：

```powershell
python -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/midi_ingress_arrival/r08c16_arrival.py --input <input.json> --output <new-result.json>
```

输入：clock_hz=40000000，baud=31250，capture{timebase_known,initial_level=1,start_cycle,finish_cycle,edges[{cycle,level,source_line}],resets[{cycle,rst_n,source_line}]}；byte_plan[{byte_seq,value,start_min_cycle,start_max_cycle,event_seq可选}]，或input_root/r62_byte_plan/r62_byte_plan_sha256只读原bytes.drv三列格式。

独立机器输出：decoded含bit_centers、start_source_line、arrival_cycle、原byte_seq/plan_source_line及application_cycle=null，每bit1280cycle、每byte12800cycle。

边界：四条NoteOn分别串行到达，不推同拍应用；半byte/reset/未知时间轴保持UNKNOWN。event_seq仅来自独立计划元数据，不声称DUT已应用。

新用例共9项，见对应tb/board/.../pro_basis_r08_20261017/midi_ingress_arrival/CASES.json。selftest.py导入仅定义，run_case(case_id, output_dir)独占创建未存在的目录，构造输入先落INPUT_BEFORE_CALL.json，实际输出在断言前落ACTUAL_BEFORE_ASSERT.json；失败保留原件并抛异常。夹具真实返回PENDING/UNKNOWN/UNRESOLVED时，CASE_EXPECTATION_MATCHED仅表示预期符合，不冒称实义通过。所有读入对象完整保留，不以row_count摘要代替原件。

HDL/EDA/设备/外部EXE/子进程0；旧R6-6的28/20、B19、D22不重跑，旧摄取器/runner只读。board_release_allowed=false，真实Pro/M1/来源/物理准入仍PENDING。Git与共享状态由总控/M2按原职责处理。
