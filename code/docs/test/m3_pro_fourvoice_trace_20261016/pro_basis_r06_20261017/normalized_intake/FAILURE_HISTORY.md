# M3-R6-3 failure history

Status: `CLOSED_AFTER_RUN_03`; historical failures remain preserved below.

## RUN_01 — preserved first failure

- Frozen spec: `RUN_SPEC.json`, SHA-256 `c4c25ca39cc69a876663f1455249ce1902f445452f50054c631f8c7863c18353`.
- Exit code: `1`; timeout: no; elapsed: `0.08192324638366699 s`.
- First failure: `FileNotFoundError` in `selftest.py::base_binding()`. The harness tried to hash the placeholder trace path before `run_case()` created the trace.
- Raw stderr: `RUN_01/stderr.bin`, SHA-256 `8c6a627ef5d2cc82ae1cb9234f3b163d0f049a68083e89829e977f02dde996ca`.
- Receipt: `RUN_01/receipt.json`, SHA-256 `e1c8698ff3323caa73c614958a4cfe8f84e25d04ee6d42e3a8ea78f4de52b780`.
- Frozen identities after failure: all 12 matched.

## One permitted minimal repair

`base_binding()` now uses a syntactically valid zero placeholder SHA. `run_case()` still writes the trace first and replaces the placeholder with the actual trace SHA before invoking the CLI. No production normalization rule changed in this repair.

## RUN_02 — bounded selftest passed

- Frozen spec: `RUN_SPEC_R02.json`, SHA-256 `7b6d9d68fe12e23a003a4da7d9b48aa25e91d127c91ff799df031b43e179ec3d`.
- Exit code: `0`; timeout: no; elapsed: `2.1086859703063965 s`.
- Result: 13 cases, 5 accepted and 8 rejected as expected.
- Receipt: `RUN_02/receipt.json`, SHA-256 `281f6287a774cb3702509d76a3463a40db5a0ad18d109ba1003e8ebb26bc3130`.
- Selftest result: `RUN_02/products/SELFTEST_RESULT.json`, SHA-256 `aec1149b6ced68c0fd8b37ac6a486d043e4120b15c5f881445c727787f52ce0c`.
- All 13 case directories retain `stdout.bin` and `stderr.bin`.
- Old checker/mapper runs: `0`; HDL/EDA/hardware runs: `0`.

## Post-run self-review blocker

The D3 projection currently writes `cancel_reason` into `CANCEL.req_id`. The 61-field contract identifies `cancel_reason` as the cancellation reason, while D3 requires the active transaction request ID. The passing synthetic case contains no cancellation and therefore did not exercise this path.

The original single repair allowance was consumed by RUN_01. The package remained `PARTIAL_BLOCKED` until the controller granted up to three additional evidence-driven software attempts.

## RUN_03 — additional attempt 1 passed

- Frozen spec: `RUN_SPEC_R03.json`, SHA-256 `8af88746d2482017844f2073374ed3f637be3e42ddc33275684716b486942b13`.
- Repair: D3 projection now tracks active `(epoch, req_id)`; CANCEL exports that identity instead of `cancel_reason`. Added one active-cancellation positive case and one cancellation-without-active rejection case.
- Exit code: `0`; timeout: no; elapsed: `2.8781445026397705 s`.
- Result: 15 cases, 6 accepted and 9 rejected as expected.
- Receipt: `RUN_03/receipt.json`, SHA-256 `7a2ec03028b7e9f372742d47bc71b26b9895ed5bee95cec9914c2983fedd56bb`.
- Selftest result: `RUN_03/products/SELFTEST_RESULT.json`, SHA-256 `837830650f94d272769be6ec6a3e714c39f2d1120d38249e31e61ae215e3ae02`.
- Cancellation evidence: canonical line 3 retains `cancel_reason=99`; D3 emits `CANCEL.req_id=7`; cancellation without an active request rejects with `CANCEL_STATE_LINE_3`.
- Frozen identities after execution: all 12 matched. All 15 case raw stdout/stderr pairs are retained.
- Old checker/mapper runs: `0`; HDL/EDA/hardware runs: `0`.

Acceptance was reached on the first additional attempt. RUN_04 and RUN_05 were not created, and the two remaining attempts were not consumed.
