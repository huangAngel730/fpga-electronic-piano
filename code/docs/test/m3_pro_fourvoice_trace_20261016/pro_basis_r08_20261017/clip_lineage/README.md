# R8-15 clip_lineage

当前L0源码/用例READY前静态准备，功能NOT_RUN；统一由夜间任务1冻结T组执行，本窗口功能消费0。result握手→commit→pending→held→实际TX的ID/PCM/双clip原行谱系。

生产CLI（此处未执行）：

```powershell
python -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/clip_lineage/r08c15_lineage.py --input <input.json> --output <new-result.json>
```

输入：origin，rows[{cycle,epoch,source_line,rst_n,metadata_error,frame_id_overflow,result{valid,ready,req_id,left,right,clip_mask},commit{valid,req_id,left,right,clip_any,clip_mask可选},tx{valid,metadata_valid,id_valid,req_id,startup,hold,left,right,clip_mask,clip_any}}]；也可机械读取R7-A原行。

独立机器输出：ledger逐转换含result_line/commit_line/tx_line及双clip/原单bit。pending/held是根据公开握手推演的期望状态，明确不是读取私有内部寄存器。

边界：控制位None/XZ返回PENDING，非法bit拒；同PCM/同OR不掩盖ID或双clip变化。metadata/overflow/reset不丢，缺实际M1字段不填0。

新用例共20项，见对应tb/board/.../pro_basis_r08_20261017/clip_lineage/CASES.json。selftest.py导入仅定义，run_case(case_id, output_dir)独占创建未存在的目录，构造输入先落INPUT_BEFORE_CALL.json，实际输出在断言前落ACTUAL_BEFORE_ASSERT.json；失败保留原件并抛异常。夹具真实返回PENDING/UNKNOWN/UNRESOLVED时，CASE_EXPECTATION_MATCHED仅表示预期符合，不冒称实义通过。所有读入对象完整保留，不以row_count摘要代替原件。

HDL/EDA/设备/外部EXE/子进程0；旧R6-6的28/20、B19、D22不重跑，旧摄取器/runner只读。board_release_allowed=false，真实Pro/M1/来源/物理准入仍PENDING。Git与共享状态由总控/M2按原职责处理。
