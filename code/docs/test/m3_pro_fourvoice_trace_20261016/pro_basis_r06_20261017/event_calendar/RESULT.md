# R06 / M3-R6-5 event calendar result

## Conclusion

The isolated software checker and bounded self-test are complete. The only
positive result is `PASS_SYNTHETIC_FIXTURE_ONLY`; it is not a real Pro RTL
trace result. No real public-port trace was supplied, so the task remains
`PENDING` for real M1/M2 evidence and `real_pro_calendar_pass` is false.

Baseline: `develop` / `42d28c4ad8250b9064099da4742fbde12a254444`.

## Implemented checks

- Consume the frozen R6-2 MIDI plan and all 61 canonical public fields.
- Match acceptance only from `event_valid && event_ready`, then bind the
  explicit `apply_event_seq` and `apply_data`; never infer application from
  `accept + 1`, a final slot, or private wave/envelope/phase state.
- Track occupied/releasing/note-on/note-off/retire masks and slot notes.
- Require a real `frame_tick` request row, `advance_mask == 4'b1111`, and an
  independently supplied frame plan through the exact finish row.
- Track request/result/commit/cancel per `(epoch, req_id)` using an explicit
  same-edge priority, rejecting commit-after-cancel and cross-epoch commit.
- Return `PENDING_*`, rather than PASS, if trace authority, M1 semantics,
  M2 capture authority, same-edge priority, or the independent frame plan is
  missing.

No SystemVerilog observer was added because the repository contains no
authoritative real Pro public-port export yet. Inventing one here would cross
the controlled-interface boundary.

## Executions

### RUN_01 — preserved first failure

Command:

```powershell
& 'C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/event_calendar/run_once.py --spec code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/event_calendar/RUN_SPEC.json --output code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/event_calendar/RUN_01
```

- Exit: 1 (`FAIL`), elapsed 0.11389780044555664 s, timeout false.
- Cause: the negative `missing_canonical_field` fixture writer indexed the
  deliberately removed field before the checker could reject it.
- `stderr.bin` SHA-256:
  `72a7dba8175363bf3419f13058dedaf4680430991079c1b3b30da3a4c8234121`.
- `receipt.json` SHA-256:
  `436fe8b65230292ec2566b31897e757c8ac774255ba3bc3d37d38734e51d0f6c`.

The single allowed repair changed only the fixture JSONL writer to emit the
canonical keys that are actually present. No checker rule was relaxed.

### RUN_02 — bounded self-test

Command:

```powershell
& 'C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/event_calendar/run_once.py --spec code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/event_calendar/RUN_SPEC_R02.json --output code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/event_calendar/RUN_02
```

- Exit: 0 (`PASS`), elapsed 0.176560640335083 s, timeout false.
- 14 cases: 1 synthetic fixture PASS, 3 authority PENDING, 10 rejected
  negative cases; real trace cases 0.
- Positive fixture: 99 public rows, 23 planned/accepted/applied events,
  13 frame requests, 13 transactions, common advance mask `0xF`, and an exact
  finish at epoch 1 / cycle 1122320.
- Covers held backpressure, variable apply delay, four simultaneous voices,
  one-by-one release and retirement, reset epoch change, same-edge
  result/cancel (cancel wins), and frames after cancellation/idle.
- Negative cases reject missing field/apply/finish/frame, duplicate apply,
  wrong apply data/common mask, extra advance, commit-after-cancel, and
  cross-epoch commit.
- `summary.json` SHA-256:
  `c46b114478e8ff97692c27860ff1c6324ac5a5e7dec4cd805790c66233abbb44`.
- `receipt.json` SHA-256:
  `9456645c790d12672294ff0eccef16c37c21ceb65a04bdf12911f75b766112af`.

## Verification level and remaining dependencies

Verification level is software-only L1 with independently synthesized
fixtures. No RTL simulation, synthesis, PnR, timing, hardware, audio, or real
Pro trace was run or claimed.

Real acceptance still needs all of the following from the controlled M1/M2
path: an authoritative same-version public-port trace, authoritative M1 apply
and slot/retire semantics, the frozen M2 request/commit/cancel contract and
same-edge priority, plus an independent complete frame plan through finish.
Until then, the checker must return a `PENDING_*` result for real evidence.

Git state: not added, committed, or pushed in this task.
