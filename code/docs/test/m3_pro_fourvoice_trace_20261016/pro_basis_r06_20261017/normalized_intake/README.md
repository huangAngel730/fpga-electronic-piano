# M3-R6-3 normalized intake

This package is a software-only R06 preparation. `normalize_intake.py` reads a
source-bound JSONL observation, emits a canonical 61-field JSONL with original
line number, same-cycle order, cycle/epoch, input/source identities and
missing-value reasons, then independently derives a B2 29-column view and a
repaired-D3 JSONL view.

The 29-column view is never used to reconstruct the canonical form. The
projection loses event/apply, voice lifecycle, advance, cancel reason,
config/effect, TX sidecar and finish information; result clip reduction is
also lossy. `req_payload`, `lane_tick`, `lane` and `lane_req_id` must arrive as
separate monitor projection inputs.

X, Z and null values are preserved with a reason. Unknown active controls or
used data reject the intake. Idle unknowns remain in `B2_VIEW.jsonl`; because
the current B2 adapter requires every CSV column to be known, no
`B2_PUBLIC.csv` is emitted and the receipt contains
`PENDING_B2_COMPATIBILITY`. Values are never replaced with zero.

The current real dependencies remain pending until M3-R6-1 supplies the
source/ROM/target provenance, M3-R6-2 supplies a frozen independent MIDI plan,
and M2-R6-1 freezes sampling phase, same-edge priority, frame plan and finish
semantics. EOF is not finish. A missing expected frame rejects only after the
independent plan is frozen; before that the status is `PENDING_FRAME_PLAN`.

All results have `pro_dut_pass=false` and `board_release_allowed=false`. The
software does not call the old B1/B2/D3 tools, a mapper, HDL compiler,
simulator, Gowin tool or hardware.
