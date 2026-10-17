# M3-R6-7 hardware identity result

Result: **software deliverable complete; physical identity remains
`UNKNOWN/PENDING`; board release is false.**

## Delivered

- A fail-closed CLI validator for the 138K Pro identity/electrical evidence
  contract.
- A SHA-checked index of local official, derived and historical comparison
  sources, with reference evidence separated from physical evidence.
- A production pending record covering complete chip identity, core/Dock
  revisions, Bank 3/4/5, MIDI direction/FPGA-side voltage/common ground,
  PT8211/serial/PA/safe-load path and commercial-tool identity/runtime status.
- Pro-vs-legacy candidate differences and a safe physical test-point plan.
- One frozen pure-software self-test group with the first wrapper failure
  preserved, one source-changing repair, and 17/17 repaired cases passing.

## Actual verification level

- Validator: software L1 self-test, exit `0`, 17/17 cases, 0.421 s internal.
- Hardware identity/electrical readiness: L0 static-source preparation only.
- Synthesis, simulation, timing, programming and board operation: not run.
- No FPGA/Gowin/Programmer/ModelSim/Icarus invocation occurred.

## Required physical evidence still missing

All 20 mandatory claim groups remain pending/unknown: four identity claims,
three Bank measurements, three MIDI claims, four audio-path claims and six
commercial-tool identity/runtime claims. Required next originals are in-focus
board/chip/component photos, raw Bank/MIDI/continuity/waveform CSV or instrument
exports, instrument metadata and exact official source pages. Old 138K C/NEO
evidence is negative comparison only.

The package never grants board release. Unknown-level adapters must not be
connected, and no bitstream may be downloaded on the strength of this result.

## Failure history

Attempt 1 exited `1` before any case because the wrapper compared a relative
output path with an absolute repository root. The traceback and original frozen
SHA set are preserved under `RUN_01`. The repair resolves the frozen output once
and writes the changed-source result under `ATTEMPT_02_REPAIRED`; it did not
repeat the same source or overwrite attempt 1.
