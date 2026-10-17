# 新 CLI 与实际跨包合同

入口软件：`code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/tx_clock_reset_checker/r07_fix/checker.py`。Python3.12.4；执行本示例**需要后续有效额度和许可**，本轮只运行 RUN_SPEC 中28项，不据此例再次运行。

```powershell
python -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/tx_clock_reset_checker/r07_fix/checker.py `
  --binding <frozen_binding.json> --binding-sha <binding_sha256> `
  --trace <R7-A/PUBLIC_ROWS.jsonl> `
  --calendar <R6-5/calendar_r07_fix_candidate_report.json> `
  --frame-plan <R6-5/UNIQUE_FRAME_PLAN.json> `
  --frame-input <same_frozen_generator_input.json> `
  --frame-rules code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/r06_observer_20261017/FRAME_PLAN_RULES.json `
  --oracle <independent_pcm24_oracle.json> `
  --decoder code/software/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/RESUME_R02/consume_capture.py `
  --decoder-sha da91462e8421719e09ffab60d7bbe38d4ee05ac1793ea70e1f09c7a69ccda0cb `
  --output <new_exclusive_result.json>
```

R7-A对应 `assemble.py --raw ... --resets ... --end ... --stdout ... --output ...` 的 PUBLIC_ROWS.jsonl 格式；R6-5对应 `calendar_r07_fix_candidate.py --intake-ledger ... --frame-plan ... --output ...` 的 `M3_R65_R07_CALENDAR_REPORT_V1`。这两个producer本轮只读，未执行或import。必须保留原source.line/cycle/epoch/time_ps，不转换为1基cycle；F/first_valid/A/result/commit/tx_adoption均读原 `{cycle,source_line}`，frame_plan_id绑定同份canonical_plan_id。

binding沿用 `M3_R06_TX_CLOCK_RESET_BINDING_V1`，增加 trace_profile：实际 A用 `M3_R7A_PUBLIC_ROW_V1`；旧flat用 LEGACY_R06_FLAT_V1；新六字段flat用 R06C3_TX_FLAT_V1。inputs_sha256必须包含 calendar/frame_plan/oracle/trace/frame_input/frame_rules 六项原文件SHA。SYNTHETIC_SELFTEST_ONLY只适用明示合成夹具，不能把真实采集改名为合成而通过。REAL_PUBLIC_TRACE目前一律exit3/PENDING_SOURCE_PROVENANCE，包括缺其他输入的情况；没有批准字段可以恢复真实通过。

合成串行后端还沿用trace_authority=SYNTHETIC_FIXTURE、tx_sidecar_authority=SYNTHETIC_EXPLICIT_SIDECAR、pins_authority=SYNTHETIC_PIN_STREAM、timebase_authority=SYNTHETIC_40MHZ_TIMEBASE、finish_authority=SYNTHETIC_EXPLICIT_FINISH、clock_hz=40000000、sample_phase=SYS_POSEDGE_PRE_NBA、serial_format=PT8211_32BIT_SLOT_LSBJ16_WS_LOW_RIGHT_HIGH_LEFT、pcm24_to_pcm16=SATURATE((PCM24+128)//256)。oracle为M3_R06_PCM24_ORACLE_V1，records保留epoch/req_id/left/right/clip，C3另需clip_mask，不能把OR标量当双clip。

退出码：0仅完整合成串行后端通过；3为指定PENDING；2为结构/矛盾证据拒收。机械prepare返回不代表完整串行通过。新增报告始终 real_pro_tx_pass=false、board_release_allowed=false。原生R6-5输出为观察账本，未含独立TX选择期望时，验证可用的F/A/FRAME边界并返回PENDING_TX_SELECTION_PLAN；完整pending_reasons与原对象保留，不造 tx_expectations。其原有M1语义/FRAME准入等PENDING不会被消除。

不支持项：无可信真实生产者入口；未实现的M1字段/语义、null/XZ或reset epoch歧义不能补0；未知profile/schema不能硬投旧D3；raw FRAME cancel不自动推导交易CANCEL；metadata/error/overflow保持原信息。FRAME_PLAN候选身份可核，但不等于M2已批准其物理意义或真实finish。读者不输出期望计划，SOURCE/PID/SHA不是权限。

唯一实际执行命令及输入快照在 RUN_02/LAUNCH.json 与 RUN_SPEC.json；该组已经消费，不重复。R7-A/R6-5生产输入无本轮端到端执行证据，只有同格式手写夹具证明适配机械逻辑。
