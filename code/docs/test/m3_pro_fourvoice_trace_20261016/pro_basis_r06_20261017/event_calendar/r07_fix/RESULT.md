# R6-5 r07_fix result

Status: `L0_STATIC_CANDIDATE_NOT_RUN`.

The additive source removes the old F=A assumption, retains F/first-valid/A
and actual advance separately, and consumes the unique canonical FRAME_PLAN
with formula and full-window checks. It supports contiguous reset segments and
a reset-only tail, does not derive business cancellation from raw frame cancel,
and fails closed to provenance/profile/admission PENDING states.
The exact frozen rule identity and zero-based global cycle axis are checked;
the last frame of each epoch is bounded by reset/stop rather than an absent
next-F observation.

No Python import, compilation, functional test, HDL, EDA or hardware action was
performed. Existing R6-5 runs and exhausted permissions were not reused.
`real_pro_calendar_pass=false`; `board_release_allowed=false`.
