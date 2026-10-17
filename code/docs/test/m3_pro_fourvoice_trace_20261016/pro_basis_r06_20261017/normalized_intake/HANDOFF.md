# M3-R6-3 final software handoff

Disposition: `IMPLEMENTATION_COMPLETE_L1_SYNTHETIC`; the declared normalized-intake software scope is complete.

## Implementation files

- `code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/normalized_intake/normalize_intake.py`
- `code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/normalized_intake/selftest.py`
- `code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/normalized_intake/run_once.py`
- `code/tb/board/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/normalized_intake/cases.json`
- `code/tb/board/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/normalized_intake/README.md`

## Evidence and review files

- `RUN_SPEC.json` and `RUN_01/`: original frozen run and preserved harness failure.
- `RUN_SPEC_R02.json` and `RUN_02/`: original one-repair run and its full case products.
- `RUN_SPEC_R03.json` and `RUN_03/`: newly authorized cancellation repair and final case products.
- `RESULT.md`: implemented behavior and actual verification level.
- `FAILURE_HISTORY.md`: RUN_01 through RUN_03 history without deleting failed originals.
- `SELF_REVIEW.md`: final static review and external pending inputs.
- `KEY_HASHES.json`: final source and key evidence identities.
- `M2_PERMISSION_REQUEST.md`: record of the added authorization and consumed attempt.

## Actual verification

- Static Python compilation: pass for three new Python files.
- RUN_01: exit `1`; first failure preserved.
- RUN_02: exit `0`; 13/13 expected outcomes.
- RUN_03: exit `0`; 15/15 expected outcomes, 6 accepts and 9 rejects, `2.8781445026397705 s`.
- Cancellation positive: canonical `cancel_reason=99`, D3 `CANCEL.req_id=7`.
- Cancellation negative: `CANCEL_STATE_LINE_3`.
- Frozen identity check: 12/12 match after every run.
- Raw case streams: 15/15 stdout/stderr pairs in RUN_03.
- Old checker/mapper: not run.
- RTL simulation, synthesis, place-and-route, timing and board testing: not run.
- Real Pro DUT pass and board release: false.

## Remaining integration boundary

The package still requires authoritative M2 public-capture inputs and pinned upstream source-target/MIDI outputs before a real Pro intake can run. Those are external integration dependencies rather than unfinished work in this implementation package. No Git write or audit-window dispatch was performed.
