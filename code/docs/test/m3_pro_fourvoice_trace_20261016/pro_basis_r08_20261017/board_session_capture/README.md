# R8-23 board_session_capture

当前L0源码/用例READY前静态准备，功能NOT_RUN；统一由夜间任务1冻结H组执行，本窗口功能消费0。十类同版板采原文件的离线导入与SHA保全。

生产CLI（此处未执行）：

```powershell
python -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/board_session_capture/r08c23_session.py --input <input.json> --output <new-result.json>
```

输入：session_id/origin/input_root/fs_sha256/source_sha256/board_identity_sha256/timebase_id，files每项含role/path/bytes/sha256及同一五项关联、format=RAW_FILE、original_unmodified=true。role精确MIDI/UART/LA/WAV/SETTINGS/INPUT_PLAN/BITSTREAM/SOURCE_MANIFEST/BOARD_IDENTITY/MEASUREMENT_PROFILE。

独立机器输出：M3_R08_BOARD_SESSION_INDEX_V1，原文件索引、原WAV格式与完整只读复制，副本逐SHA核同；原文件始终只读。

边界：本工具不采集、不连串口/仪器；原音频本体不能由截图代替。即使origin改REAL_UNVERIFIED，仍PENDING_REAL_BOARD_SESSION_ADMISSION，时基和实物未认证。

新用例共8项，见对应tb/board/.../pro_basis_r08_20261017/board_session_capture/CASES.json。selftest.py导入仅定义，run_case(case_id, output_dir)独占创建未存在的目录，构造输入先落INPUT_BEFORE_CALL.json，实际输出在断言前落ACTUAL_BEFORE_ASSERT.json；失败保留原件并抛异常。夹具真实返回PENDING/UNKNOWN/UNRESOLVED时，CASE_EXPECTATION_MATCHED仅表示预期符合，不冒称实义通过。所有读入对象完整保留，不以row_count摘要代替原件。

HDL/EDA/设备/外部EXE/子进程0；旧R6-6的28/20、B19、D22不重跑，旧摄取器/runner只读。board_release_allowed=false，真实Pro/M1/来源/物理准入仍PENDING。Git与共享状态由总控/M2按原职责处理。
