# M3-R6-5 static self-review

## Scope

Reviewed only the new isolated `event_calendar` software and evidence
directories. No existing source, shared status file, HDL, constraint, or
frozen evidence was modified.

## Findings

- The checker reads only the independent R6-2 plan, binding metadata,
  independent frame plan, and canonical public-port rows.
- Application identity requires explicit `apply_valid`, `apply_event_seq`, and
  `apply_data`; there is no `accept + 1` inference.
- Four-lane progress is accepted only on an observed `frame_tick` request with
  `advance_mask == 0xF` and matching request identity.
- Requests are keyed by `(epoch, req_id)`. Cross-epoch commit and
  commit-after-cancel are deterministic failures.
- Same-edge ordering is an explicit dependency. The synthetic fixture uses
  `CANCEL > RESULT > COMMIT > REQUEST`; real mode cannot pass without the
  controlled authority declaring its ordering.
- The finish row and every planned frame are exact, independently supplied
  checks. Missing or extra frames cannot be hidden by the observed trace.
- Missing real authority returns `PENDING_*`, not PASS.
- There are no DUT hierarchy references or private wave/envelope/phase reads.
- The single RUN_01 failure and minimal writer repair are preserved; no
  repeated or unbounded execution was performed.

## Static checks

Final static checks parse all JSON files, recompute the selected SHA manifest,
verify LF/final-newline/trailing-whitespace rules for source and hand-written
documents, and run `git diff --check` for the two authorized directories.
The exact result is recorded in the delivery message; no additional functional
test group is consumed by these checks.

## Limitations

- Synthetic lifecycle masks and transactions prove checker behavior only.
- No authoritative Pro public-port rows currently exist in this package.
- No inference about real audio quality, four-sine implementation, RTL timing,
  or hardware behavior is permitted from this result.
