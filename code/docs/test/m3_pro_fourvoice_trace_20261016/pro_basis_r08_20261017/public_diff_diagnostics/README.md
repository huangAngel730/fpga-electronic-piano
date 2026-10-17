# R8-18 public_diff_diagnostics

当前L0源码/用例READY前静态准备，功能NOT_RUN；统一由夜间任务1冻结T组执行，本窗口功能消费0。复用B最终比较器，对公开采样与沿间事件给出首现场解释。

生产CLI（此处未执行）：

```powershell
python -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/public_diff_diagnostics/r08c18_diagnostics.py --input <input.json> --output <new-result.json>
```

输入：input_root，csv/events/stdout相对路径，inputs_sha256三项，start_cycle/stop_cycle，allowed_differences=[]，source_identities。

独立机器输出：两路B比较结果、最早差异time_ps/csv_line/cycle、公开pin分类与allowance依据；原38obs为NOT_PUBLIC。

边界：M2当前允许差异表为空；任意自报approved白名单均拒，不吞DIN/UART真实差异。无STAT仍PENDING；首现场解释不认证生产者或真实等价，不建第三top。

新用例共6项，见对应tb/board/.../pro_basis_r08_20261017/public_diff_diagnostics/CASES.json。selftest.py导入仅定义，run_case(case_id, output_dir)独占创建未存在的目录，构造输入先落INPUT_BEFORE_CALL.json，实际输出在断言前落ACTUAL_BEFORE_ASSERT.json；失败保留原件并抛异常。夹具真实返回PENDING/UNKNOWN/UNRESOLVED时，CASE_EXPECTATION_MATCHED仅表示预期符合，不冒称实义通过。所有读入对象完整保留，不以row_count摘要代替原件。

HDL/EDA/设备/外部EXE/子进程0；旧R6-6的28/20、B19、D22不重跑，旧摄取器/runner只读。board_release_allowed=false，真实Pro/M1/来源/物理准入仍PENDING。Git与共享状态由总控/M2按原职责处理。
