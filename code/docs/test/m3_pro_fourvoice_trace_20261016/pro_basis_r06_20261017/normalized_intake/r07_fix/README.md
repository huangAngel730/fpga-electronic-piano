# R6-3 R07 profile intake additive candidate

This directory documents an additive `r07_fix` candidate. The signed R6-3
source and RUN_01/RUN_02/RUN_03 evidence remain unchanged.

The candidate consumes the actual R7-A wrapper shape and preserves each source
row verbatim inside its report. It requires the exact 61-field, source and TX
extension key sets, PRE_NBA source identity, and the global `line=cycle+1`
axis beginning at cycle 0. It records FRAME origin `F`, first observed
request-valid, and actual acceptance `A` independently. Numeric request ID 0 is
valid. Startup keeps `req_id=null` when `tx_req_id_valid=0`; a new adoption may
close one committed pending transaction, while HOLD remains a TX sample and
does not consume the transaction again.

The frozen R7-A event label `TX_ADOPT` means a reset-released
`tx_sample_valid` sample pulse, so STARTUP and HOLD rows also carry that event.
The candidate validates that public event contract separately from its own
`kind` and `consumes_pending` transaction classification. FRAME, ACCEPT,
RESULT, COMMIT and TX events are all gated by sampled `rst_n==1`; FINISH is
checked independently, matching the R7-A assembler.

The public `cancel` field is retained as `raw_frame_cancels`. It never becomes
a business CANCEL without a separately frozen transaction-cancel rule. The C3
profile cannot be represented losslessly by the old D3 stream, so the candidate
always emits `PENDING_UNSUPPORTED_PROFILE` and no D3 records.

`HDL_PUBLIC_CAPTURE_UNVERIFIED` remains
`PENDING_SOURCE_PROVENANCE`. There is no local trust anchor that can turn a
self-declared string or matching SHA into M2 admission. All outputs force
`real_pro_intake_pass=false` and `board_release_allowed=false`.

Both Python files and every listed case are L0/NOT_RUN. A future execution
requires M2 to bind the exact source, R7-A capture, provenance admission,
case subset, timeout and one new incremental software budget.
