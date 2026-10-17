# M3-R6-6 TX / clock / reset checker

This is an isolated software boundary checker. It accepts a frozen binding,
canonical 61-field public trace plus `time_ps`, an independent R6-5 transaction
and TX-selection calendar, an independent frame plan, and an M1-owned PCM24
oracle. It reuses the pinned `PinDecoder` by exact SHA instead of copying the
decoder.

The checker distinguishes three identities and never substitutes one for
another:

1. internal request/result/commit/cancel identity;
2. explicit TX-adoption sidecar identity;
3. the PCM bits reconstructed from BCLK/WS/DIN.

Startup zero has no request identity; the raw sidecar ID field must contain
zero only as a gated unused value. A HOLD must repeat the previously adopted
request ID, PCM24 and clip exactly. A commit does not create a TX adoption.
PCM equality is never used to infer identity, so two requests may legally have
identical PCM while remaining distinct.

Internal completion is separately checked as `age < 833` system cycles. TX
consumption occurs only on an independently planned frame; legal 833/834-cycle
frame spacing is not subjected to the internal completion inequality.

The pinned decoder checks 32 BCLK rising edges per half-slot, WS-low right,
WS-high left, zero padding followed by 16-bit LSBJ payload, signed decoding,
and `saturate((PCM24 + 128) // 256)`. Timestamped frame intervals establish
the synthetic 48 kHz result; a WAV header is never accepted as an FPGA clock
source. PA must be low during reset, PLL unlock, or audio-unstable time.

Reset-truncated serial data and a non-authoritative observation tail remain
UNKNOWN/PENDING. A declared finish with any open or committed-but-unadopted
transaction, or partial serial word, is rejected. EOF alone is not finish.

All successful self-test output remains
`PASS_SYNTHETIC_FIXTURE_ONLY` with `real_pro_tx_pass=false`. A real PASS is
impossible until M2 supplies the frozen same-version sidecar/public pins/time
and finish contract, M3-R6-5 supplies its real ledger and selection plan, and
M1 supplies its same-basis read-only PCM oracle.

No TB directory is created: no authoritative Pro observer ports currently
exist for this package, and inventing HDL ports here would cross the controlled
interface boundary.
