# R7-C self review

The bridge reads the actual R7-A outer row schema and requires the nested
`fields` object to contain exactly the frozen 61 keys.  `source`,
`extensions`, `missing_reasons`, and `events` remain separate and are copied
into the row index.  Each trace is bound twice: whole-file SHA/length and a
digest over every numbered raw-line SHA.  The internal capture binding must
also match the MIDI plan, independent frame plan, and R7-A schema hashes.

`req_valid/req_ready`, `frame_tick`, and `advance_mask` use three-state
classification.  X/Z/null cannot become false, zero, or an invented request
identity.  TX PCM/ID/clip/HOLD/startup and the raw R7-A envelope remain in the
byte-exact copied input and row index.  FRAME F and request acceptance A are
separate fields.  No DUT wave, envelope, phase, PCM, or current state feeds an
expected value.

The old B0 profile is always `PENDING_UNSUPPORTED_PROFILE`; no lossy B0
calendar/public-PCM projection is written.  M1 must define the successor
profile and perform all arithmetic, rounding, saturation, identity, and PCM
checks.

RUN_01 failed on the first positive fixture because a deliberately
backpressured MIDI event was accepted outside the generator's nominal arrival
window.  The minimal repair labels a unique payload association outside that
window rather than rejecting or treating the window as an acceptance
deadline.  RUN_02 proves that affected 99-row fixture and preserves the
failure originals.

The six RUN_01 cases after the first failure remain `NOT_RUN`, including the
explicit HOLD/startup mutation, three-state mutation, SHA mutation, missing
field, cycle regression, and dropped-line mutation.  Their code paths were
statically reviewed, but the task budget forbids a full rerun after the repair
group.  The generic RUN_02 runner receipt still says
`repair_groups_consumed=0`; `RUN_SPEC_R02.json` is the authoritative scope and
this task receipt records the actual cumulative consumption as one initial
group plus one repair group.
