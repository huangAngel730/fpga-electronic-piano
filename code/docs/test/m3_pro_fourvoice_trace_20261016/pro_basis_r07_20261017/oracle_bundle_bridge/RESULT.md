# M3-R7-C oracle bundle bridge result

Status: `IMPLEMENTATION_COMPLETE_L1_TARGETED_SYNTHETIC`; overall Pro evidence
remains `PARTIAL`.  The bridge packages R6-2/3/5 and M2 contracts together
with the actual R7-A row schema, preserves every input byte/SHA and creates a
99-line mechanical association index.  It keeps the bare 61 fields separate
from R7-A metadata/extensions, retains F/A/reset/finish and TX
PCM/ID/clip/HOLD/startup, and never calls M1 arithmetic.

The old B0 narrow profile cannot represent same-edge order, asynchronous
reset edges, separate FRAME F/request A, or TX HOLD/startup.  The deliverable
therefore reports `PENDING_UNSUPPORTED_PROFILE` and does not discard or force
the data into old calendar/public-PCM files.

RUN_01 consumed the initial <=90 s group and failed on its first fixture:
backpressure delayed an accepted MIDI event beyond the nominal generator
arrival window.  Exit was 1 after 0.20785880088806152 s; raw stderr SHA is
`e4704b2897dfa7b500427147460b5ca88b64e0545fe330486b2c89b2ab1ba147`.
The failure is preserved unchanged.

RUN_02 consumed the one allowed <=60 s repair group.  The single affected
99-row fixture passed, exit 0 in 0.2173755168914795 s.  The result is
`SOFTWARE_READY_SYNTHETIC_PENDING_M1_PROFILE`; bundle SHA is
`ca75aa0b8386e7514aabe77054edee18aa5595d518475861863ccb9fb610e035`,
row-index SHA is
`54e61556f628e285ddd8b049f0e2017eb0a09689f18125eb8228cc36d352b22b`,
and contract-gap SHA is
`c4945ab54066021914b84e2c91fc6b5a92ca7f5c099ad0751fe1129b37e52a64`.

The six cases after the RUN_01 first failure were not rerun; they are
`NOT_RUN`, not PASS.  No real R7-A capture exists, and no M1 model/oracle,
HDL compile/simulation, EDA, device, or hardware operation ran.  Real source
authority, M1 apply/slot/release/retire/generation semantics, M1 successor
profile/math, and M2 capture/finish authority remain pending.

No Git write, commit, push, shared-state edit, or old R06 modification was
performed.  `board_release_allowed=false`.
