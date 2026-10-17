# R06 MIDI stimulus result

## Scope and level

This package is the isolated `M3-R6-2 midi_stimulus` deliverable.  Its achieved
level is **L1 software / pure-file generation only**.  The SystemVerilog public
port driver is source-only (**L0, not compiled or simulated**).  No DUT, Pro
four-voice semantics, RTL simulation, EDA flow, bitstream, or hardware was run.

Baseline recorded by the run specification: `42d28c4a`.

## Executed command

The only repair run was:

```powershell
& 'C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/midi_stimulus/run_once.py --spec code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/midi_stimulus/RUN_SPEC_R02.json --output code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/midi_stimulus/RUN_02
```

Actual result: exit `0`, elapsed `0.07098555564880371 s`, timeout `false`,
13 positive checks PASS, 4 negative checks rejected as expected, 23 expected
public events, 63 physical UART bytes, and 0 HDL/simulator/EDA/hardware calls.
The raw stdout/stderr and receipt are retained under `RUN_02/`.

## Proven by RUN_02

- `40 MHz / 31250 baud = 1280` system clocks per MIDI bit, UART 8N1, idle high,
  LSB first.
- Initial reset is asserted at cycle 0 and released at cycle 800.  The first
  byte begins at cycle 5920, exactly four configured idle bits after release.
- Four solo note pairs are represented, followed by four distinct NoteOn
  messages for notes 60/64/67/72 with velocities 24/52/88/120.  Their final
  stop cycles are distinct, so the plan does not inject four notes in one
  system cycle.
- One-by-one NoteOff, NoteOn velocity zero normalization, same-note retrigger,
  fifth-note boundary, Running Status, interleaved `F8`, reset/recovery, and a
  bounded public-event backpressure interval are present.
- Every physical byte records byte sequence, event sequence where applicable,
  role, value, start cycle, and exclusive stop cycle.  Every expected event
  records an independent event sequence, public 64-bit value, source-byte
  range, and arrival window.
- Negative checks reject non-integral clock/baud, a MIDI data byte outside
  0..127, a non-contiguous event sequence, and Running Status without an
  active matching status.

## Preserved first attempt

`RUN_01` remains unchanged.  It passed its then-current software assertions,
but source review found that reset was first asserted at cycle 5120 while the
driver defaulted reset high.  Therefore RUN_01 is **not an accepted final
stimulus**.  `FAILURE_HISTORY.md` records the defect and the single minimal
repair; RUN_02 is the accepted software result.

## Not verified

- M1-owned slot allocation, Release retirement, same-note generation policy,
  fifth-note/preemption behavior, and their transaction closure remain
  `PENDING_M1_SOURCE_SEMANTICS`.
- The public-port driver has not been compiled or connected to a real parser or
  DUT.  Its event log is therefore only an integration fixture, not evidence
  that the parser emits the expected events.
- Arrival-window bounds are fixture expectations and have not been validated
  against the Pro DUT.
- No audio result, four-voice synthesis result, timing result, board result, or
  physical MIDI result is claimed.
