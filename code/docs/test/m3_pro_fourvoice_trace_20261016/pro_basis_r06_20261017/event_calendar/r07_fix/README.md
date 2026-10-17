# R6-5 R07 calendar additive candidate

This additive candidate leaves the signed event calendar and its historical
RUN_01/RUN_02 evidence untouched. It consumes the R6-3 `r07_fix` ledger and
the single canonical plan emitted by the R6-5 file-based FRAME_PLAN generator.

For each planned frame it keeps four independent facts: FRAME origin `F`,
first observed request-valid, actual acceptance `A`, and the actual M1 advance
observation. A request is not required on the F edge. The candidate does not
move A to F, derive A as F+1, or create advance at A+1. A known advance must be
the observed mask `1111` and remain inside that frame window; missing M1
advance semantics stay PENDING.

The candidate recomputes every canonical plan cycle from the frozen NCO
formula, rules SHA and exact parameters, validates contiguous reset segments,
supports a reset-only tail, and compares every observed F against the full
plan through finish. Global reset/release/stop/finish cycles may begin at 0;
the formula's `k>=1` is only the local frame ordinal. The final frame window
ends at `stop_cycle + 1`, so first-valid, A or advance after reset cannot attach
to the preceding epoch. Idle and
raw-cancel frames remain in coverage. Raw frame cancellation never creates a
business CANCEL.

The current plan authority is intentionally
`CANDIDATE_INDEPENDENT_PLAN_NOT_M2_ADMITTED`, so it remains
`PENDING_FRAME_PLAN_ADMISSION`. Any `HDL_PUBLIC_CAPTURE_UNVERIFIED` ledger also
remains `PENDING_SOURCE_PROVENANCE`; matching files and self-declared strings
do not establish trust. The old D3 view remains
`PENDING_UNSUPPORTED_PROFILE`.

Source and self-test cases are L0/NOT_RUN. Functional execution requires an M2
admission naming the exact source, R6-3 ledger, canonical plan, trusted
provenance receipt, case subset, timeout and new incremental budget.
