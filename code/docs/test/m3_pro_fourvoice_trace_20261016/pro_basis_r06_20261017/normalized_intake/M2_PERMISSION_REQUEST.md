# M3-R6-3 additional repair authorization record

Status: `GRANTED_AND_CONSUMED_ONE_OF_THREE`.

The controller granted up to three additional, evidence-driven, maximum-90-second pure-software attempts, limited to the existing normalized-intake directories. The first authorized attempt implemented the frozen minimum cancellation fix and passed, so work stopped without creating RUN_04 or RUN_05.

Consumed authorization:

- Source repair limited to `normalize_intake.py`, `selftest.py`, `cases.json` and package documentation.
- D3 projection maintains the active `(epoch, req_id)`; REQUEST sets it and RESET/CANCEL/CONSUME clear it.
- CANCEL exports the active request ID. `cancel_reason` remains only in canonical 61-field data because the pinned D3 schema has no reason field.
- Added an active-cancellation positive fixture and a cancellation-without-active rejection fixture.
- Executed exclusive `RUN_03` with a 90-second limit; actual elapsed time `2.8781445026397705 s`, exit `0`.

Unused attempts: two. They were not exercised because acceptance was reached and no no-change reruns are permitted.
