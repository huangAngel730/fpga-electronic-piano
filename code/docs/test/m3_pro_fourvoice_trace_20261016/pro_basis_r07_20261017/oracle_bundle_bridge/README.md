# M3-R7-C oracle bundle bridge

This isolated Python tool packages R6-2 MIDI input, R6-3 normalized public
rows, R6-5 independent frame plan, and the frozen M2 capture schemas into a
lossless M1 handoff.  It reads the R7-A `M3_R7A_PUBLIC_ROW_V1` envelope,
keeps the nested 61-key `fields` object separate from `source`, `extensions`,
`missing_reasons`, and `events`, copies every input byte, records its SHA-256,
and emits a one-line-per-source-row index with cycle, epoch, explicit event
links, separate `FRAME_F` and request-acceptance `A`, reset/finish facts, and
TX PCM/ID/clip/HOLD/startup fields.  Unknown handshake and mask values remain
three-state facts with reasons; they are not collapsed to false or zero.

The tool deliberately does not emit an old B0 calendar or public-PCM file.
The legacy `R06_SETTLED_SIMULTANEOUS_LANE_TICKS_V1` profile cannot express
same-edge ordering, asynchronous reset edges, separate F/A facts, or TX
HOLD/startup metadata without loss.  `CONTRACT_GAPS.json` therefore reports
`PENDING_UNSUPPORTED_PROFILE` while preserving all source evidence for M1 to
define the successor arithmetic/profile contract.

Current input is the frozen R6 synthetic public fixture.  R7-A real capture
has not arrived, so this package can reach only L1 software-fixture readiness;
it cannot prove real Pro capture, M1 arithmetic, RTL, EDA, or hardware.
