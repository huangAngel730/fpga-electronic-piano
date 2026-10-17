# R8-24 recovery_manifest

当前L0源码/用例READY前静态准备，功能NOT_RUN；统一由夜间任务1冻结H组执行，本窗口功能消费0。正确Part/version、完整物理报告、新.fs、恢复身份与一次SRAM范围的离线预检。

生产CLI（此处未执行）：

```powershell
python -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/recovery_manifest/r08c24_recovery.py --input <input.json> --output <new-result.json>
```

输入：physical_identity/build/input_root/artifacts{sources,rom,constraints,pll,fs,pnr,sta,cdc,recovery}，每原件path/bytes/SHA/part/version/source_sha；STA/CDC仅支持M3_R08_NORMALIZED_PHYSICAL_REPORT_V1原文件，其他格式显式PENDING；timing_coverage与原报告一致，permission仅作待核材料。

独立机器输出：缺件/错版/错.fs/PG484/Flash/复用许可原因及原件身份；即使合成机械齐套也PENDING_TRUSTED_M2_ADMISSION，download_authorized=false。

边界：没有可信M2签收器和实物证据认证，不生成/修改/消费许可，不开设备。完整STA须含setup/hold/recovery/removal/generated_clocks/io_timing/cdc及unconstrained_paths=0。

新用例共9项，见对应tb/board/.../pro_basis_r08_20261017/recovery_manifest/CASES.json。selftest.py导入仅定义，run_case(case_id, output_dir)独占创建未存在的目录，构造输入先落INPUT_BEFORE_CALL.json，实际输出在断言前落ACTUAL_BEFORE_ASSERT.json；失败保留原件并抛异常。夹具真实返回PENDING/UNKNOWN/UNRESOLVED时，CASE_EXPECTATION_MATCHED仅表示预期符合，不冒称实义通过。所有读入对象完整保留，不以row_count摘要代替原件。

HDL/EDA/设备/外部EXE/子进程0；旧R6-6的28/20、B19、D22不重跑，旧摄取器/runner只读。board_release_allowed=false，真实Pro/M1/来源/物理准入仍PENDING。Git与共享状态由总控/M2按原职责处理。
