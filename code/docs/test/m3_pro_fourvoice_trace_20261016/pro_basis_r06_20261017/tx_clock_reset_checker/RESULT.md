# R06 / M3-R6-6 TX-clock-reset checker result

## Result

The software boundary implementation is complete. `RUN_01` passed all 20
frozen cases in 5.205964088439941 seconds without timeout or repair:

- 1 `PASS_SYNTHETIC_FIXTURE_ONLY`;
- 7 explicit `PENDING_*` authority cases;
- 12 deterministic rejection cases;
- 0 real trace cases and 0 HDL/simulator/EDA/hardware calls.

This is L1 software-only evidence. `real_pro_tx_pass=false`; it is not a Pro
RTL, physical 48 kHz, analog audio, timing, or board-release result.

## Command

```powershell
& 'C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/tx_clock_reset_checker/run_once.py --spec code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/tx_clock_reset_checker/RUN_SPEC.json --output code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/tx_clock_reset_checker/RUN_01
```

Outer exit 0; child exit 0; timeout false; source/dependency identities were
unchanged. No second functional run was made.

## Positive synthetic coverage

The 7,600-row explicit fixture produced two active epochs and a final reset
epoch. It checked eight TX frames, six complete decoded stereo frames, seven
transactions, two startup-zero frames, one HOLD, ID 0 as a valid non-startup
identity, two PCM-identical but ID-distinct transactions, and two reset-
truncated serial tails marked `RESET_TRUNCATED_UNKNOWN`.

The timestamp result was exactly 48,000 Hz from the 40 MHz timebase. Frame
intervals followed 833/834 cycles with a three-interval sum of 2,500. The
pinned decoder enforced 64 BCLK rising edges per stereo frame, 32-bit slots,
WS-low right / WS-high left, LSBJ16 signed payload and the approved rounded,
saturated PCM24-to-PCM16 conversion.

Internal completion ages were checked independently (`20` or `30`, always
`<833`). TX consumption occurred at later real frame boundaries, including a
request-to-TX age of 833, proving that the internal deadline is not incorrectly
applied to legal 833/834 frame consumption.

## Negative and PENDING coverage

The checker correctly rejected startup with a request ID, changed HOLD clip,
commit marked as TX off-frame, same-PCM wrong ID, internal age 833, missing
frame after cancellation, duplicate frame plan, non-silent reset pin, PA before
lock, serial-bit corruption, finish with an unconsumed commit, and duplicate
finish.

It returned PENDING, not PASS, for missing TX sidecar, public pins, real
timebase, R6-5 calendar, M1 PCM oracle, independent frame plan, and an EOF-only
tail without a frozen finish contract.

## Remaining real dependencies

Real execution requires the same-version M2 TX-adoption sidecar, public
BCLK/WS/DIN and actual timebase, frozen finish semantics and frame plan; the
M3-R6-5 real transaction/TX-selection ledger; and the M1 same-basis read-only
PCM24/clip oracle. None is present in this package, so real status remains
PENDING.

Baseline: `42d28c4ad8250b9064099da4742fbde12a254444`. Git state: not added,
committed, or pushed.
