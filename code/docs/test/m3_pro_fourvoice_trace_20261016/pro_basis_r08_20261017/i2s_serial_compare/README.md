# R8-13 i2s_serial_compare

当前L0源码/用例READY前静态准备，功能NOT_RUN；统一由夜间任务1冻结T组执行，本窗口功能消费0。复用固定PinDecoder，输出完整左右槽位帧、原行/首位差异与未完尾段。

生产CLI（此处未执行）：

```powershell
python -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/i2s_serial_compare/r08c13_serial.py --input <input.json> --output <new-result.json>
```

输入：protocol=PT8211_32BIT_SLOT_LSBJ16_WS_LOW_RIGHT_HIGH_LEFT，clock_hz=40000000，sample_phase=SYS_POSEDGE_PRE_NBA，first_phase_known，quantization=SATURATE((PCM24+128)//256)，accepted_requests[{epoch,req_id,A_cycle}]，rows[{cycle,epoch,source_line,time_ps,rst_n,frame_tick,bclk,ws,din,tx_sample_valid,...显式TX旁带}]。rows也可为原R7-A PUBLIC_ROW对象，经机械视图保留原对象。

独立机器输出：complete_frames、half_frames、source_index、first_difference或unknown。缺首相位、半帧reset与尾段不完整保持UNKNOWN；I2S非本配置返回PENDING；身份来自显式旁带与A账本，不以相同PCM推身份。

边界：合成6/7半周期夹具只测协议，不是48kHz公式计划；不输出FRAME_PLAN，不验证M1数学。

新用例共9项，见对应tb/board/.../pro_basis_r08_20261017/i2s_serial_compare/CASES.json。selftest.py导入仅定义，run_case(case_id, output_dir)独占创建未存在的目录，构造输入先落INPUT_BEFORE_CALL.json，实际输出在断言前落ACTUAL_BEFORE_ASSERT.json；失败保留原件并抛异常。夹具真实返回PENDING/UNKNOWN/UNRESOLVED时，CASE_EXPECTATION_MATCHED仅表示预期符合，不冒称实义通过。所有读入对象完整保留，不以row_count摘要代替原件。

HDL/EDA/设备/外部EXE/子进程0；旧R6-6的28/20、B19、D22不重跑，旧摄取器/runner只读。board_release_allowed=false，真实Pro/M1/来源/物理准入仍PENDING。Git与共享状态由总控/M2按原职责处理。
