# M3-R6-6 static self-review

## Scope and independence

- Only the new isolated software and evidence directories were written.
- No HDL/TB was added because no authoritative Pro public observer interface
  exists yet.
- The old decoder is dynamically loaded only after exact SHA verification; it
  was not copied or modified.
- TX identity comes from the explicit sidecar and independent selection plan.
  Commit and PCM equality are not identity sources.
- The independent frame plan is compared through the explicit finish row, so
  idle/cancel periods cannot hide missing or duplicate frames.

## Semantics checked

- Startup zero gates the raw ID field and reports `request_id=null`.
- HOLD repeats ID, PCM24 and clip from the prior selected frame.
- Per-epoch request/result/commit/cancel state is compared to the independent
  calendar; internal completion must be strictly younger than 833 cycles.
- TX adoption occurs only on an observed planned frame, which separately has
  833/834-cycle cadence.
- The pinned decoder checks serial phase, slot length, channel order, signed
  LSBJ16 data and quantization.
- `time_ps`, rather than a WAV header, proves the software fixture cadence.
- PA is forced low during reset, PLL unlock, or audio-unstable periods.
- Reset truncation and an unauthoritative tail do not become PASS. Explicit
  finish rejects open or committed-but-unadopted transactions and partial
  serial state.

## Execution and static review

The single frozen group passed 20/20 cases. No repair run was required. Final
static checks parse every JSON file, verify source/dependency and selected
product hashes, check hand-written LF/final-newline/trailing-whitespace rules,
scan for forbidden identity inference patterns, and run `git diff --check` on
the authorized directories.

## Limits

All positive input is explicitly synthetic. There is no real Pro sidecar,
public pin trace, M1 oracle, real timebase, or frozen real finish in this
package. No analog behavior, FPGA LRCLK, physical PA polarity, synthesis,
timing, or board behavior has been verified.
