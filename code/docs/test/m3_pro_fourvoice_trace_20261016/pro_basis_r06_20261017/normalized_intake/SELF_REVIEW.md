# M3-R6-3 self-review

Status: `PASS_WITH_EXTERNAL_PENDING`; review scope: the new normalized-intake implementation and its synthetic fixtures.

## Confirmed behavior

- Canonical output contains all 61 contract fields and records source line, same-cycle ordinal, cycle, epoch, trace SHA, source manifest SHA, original event order and explicit missing reasons.
- B2 is an independent 29-column projection. The 36 fields outside that view are never reconstructed from B2.
- `result_clip_mask[1:0]` is reduced only by the explicitly bound `OR`, `BIT0` or `BIT1` policy; an unfrozen policy remains pending.
- `X`/`null` data are retained. Unknown active control or used transaction data fail closed; an idle B2 unknown returns `PENDING_B2_COMPATIBILITY` and prevents CSV export.
- Frame plan and finish gates prevent D3 export while their contracts are pending.
- D3 cancellation takes the active request identity, not `cancel_reason`; reset, cancellation and consume clear projection state.
- Negative cases cover trace identity, transaction ID, epoch, missing cycle row, same-edge ordering, finish/EOF, frame-plan mismatch and cancellation without an active transaction.
- RUN_03 preserved both raw streams for all 15 cases and all 12 frozen identities matched after execution.

## Cancellation repair evidence

- Positive case: `cancel_active_uses_transaction_id`, exit `0`.
- Canonical row: line `3`, 61 fields, `cancel=1`, `cancel_reason=99`.
- D3 row: epoch `0`, cycle `2`, `CANCEL.req_id=7`.
- Negative case: `cancel_without_active_reject`, exit `1`, first failure `CANCEL_STATE_LINE_3`.

No further implementation blocker was found within the declared synthetic scope. RUN_04 and RUN_05 were not used because RUN_03 met acceptance.

## External pending inputs and unverified levels

- `source_target_audit`: present concurrently but not pinned into this package; `PENDING_CURRENT_UNPINNED`.
- `midi_stimulus`: present concurrently but not pinned into this package; `PENDING_CURRENT_UNPINNED`.
- M2 public Pro capture contract/source/trace: not present as an accepted binding; `PENDING_NOT_PRESENT`.
- White-day field deltas remain supporting evidence only and are not publication authority.
- RTL simulation, synthesis, place-and-route, timing and board testing were not run.
