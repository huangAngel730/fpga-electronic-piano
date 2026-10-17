# M3-R6-3 normalized intake result

Status: `IMPLEMENTATION_COMPLETE_L1_SYNTHETIC`; validation level: `L1_SOFTWARE_ONLY`.

The CLI ingests a bound JSONL observation, validates the pinned 61-field contract and provenance identities, and writes a canonical 61-field stream with input line, same-cycle order, cycle/epoch, source/input SHA and per-field missing reasons. It derives a separate 29-column B2 view without feeding that lossy view back into canonical data. Unknown values remain `X`/`null`; a row with an unknown B2 field is retained in `B2_VIEW.jsonl`, marked `PENDING_B2_COMPATIBILITY`, and prevents `B2_PUBLIC.csv` generation.

The binding fails closed on incorrect trace/reference SHA, wrong request identity or epoch, a dropped cycle row, invalid same-edge order, rows after finish, a missing frozen finish, a frame-plan mismatch and cancellation without an active transaction. Unfrozen contracts return `PENDING_SAME_EDGE_ORDER`, `PENDING_FRAME_PLAN`, `PENDING_FINISH_CONTRACT`, or `PENDING_PRO_SOURCE_OR_TRACE`. All receipts force `pro_dut_pass=false`, `board_release_allowed=false`, and `real_finish_pass=false`.

The D3 projection now tracks the active `(epoch, req_id)` independently. REQUEST sets the active identity; RESET, CANCEL and non-startup-zero CONSUME clear it. A cancellation exports the active request ID and leaves `cancel_reason` unchanged in canonical data. The dedicated positive case proves `cancel_reason=99` remains in the 61-field row while D3 emits `CANCEL.req_id=7`; cancellation without an active request is rejected with `CANCEL_STATE_LINE_3`.

`RUN_03` passed its bounded synthetic suite: 15 cases total, 6 accepted and 9 rejected, in `2.8781445026397705 s`. Every case retains its raw stdout/stderr, and all 12 frozen files matched after execution. No old checker/mapper, HDL simulator, EDA tool or hardware was run. Because the first newly authorized repair attempt passed, RUN_04 and RUN_05 were not created.

This closes the M3-R6-3 software implementation scope only. It is not a real Pro DUT pass or board-release result. Source-target audit, MIDI stimulus and the M2 public-capture contract/source/trace remain external unpinned dependencies for real integration.
