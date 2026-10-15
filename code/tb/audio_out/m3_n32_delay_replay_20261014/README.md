# M3 real N32 PCM → stereo delay → M2 transport replay

This is an isolated functional replay.  It does not modify or replace the
N32 generator, M1 sound/delay RTL, M2 transport, I2S sender, observer, ROM,
production top, constraints, or public interfaces.

## Frozen inputs

- C_FULL transfer ZIP SHA256:
  `eac6e9371a96e91447a75d869d7e7a6dc76252fd89d6c8b621953a396a42c726`
- Continuous capture: 45,522,685 bytes, SHA256
  `daf92770d8b92ec283d9eae726c5a39a8023a28808b0b262376d44c09654c79d`
- Required M1 ZIP identity (historical receipt):
  `5c18926ae307301e91ec0e44dcf4a48b2fb57adec71ad46c494b14df59913b06`
- M2 N32 transport evidence capsule SHA256:
  `b37d2084fada1cd595f207ec91c99125f28488cad4d07a1576b1e6c6da0c195c`

The original M1 ZIP is not present on this machine.  The runner obtains only
the exact final `m1td_stereo_delay` and `m1td_delay_effect` source bytes from
the existing M2 evidence capsule.  Its preparation receipt records the
required original ZIP SHA and the extracted bytes match their frozen hashes.
This limitation is recorded rather than hidden.

## Replay contract

`capture_extract.py` accepts a C_FULL publication only when `P` has an exact
same-cycle, same-ID, same-PCM `K` record with `publish=1`.  `clipped` comes
from K.  The selected 1,300 publications are consecutive entries from reset
lifetime 1 (which has 4,807 entries); reset lifetimes are never concatenated.
Original K/P line numbers, cycle, source ID, PCM and clip are retained.

The testbench maps each frozen source publication to exactly one live M2
transport request ID and logs both identities.  M1 delay output is held until
the M2 result handshake.  The independent Python model checks:

- bypass, enable/disable, delay-length changes and the consequent history flush;
- a gain-only change without history flush;
- fixed-point dry/wet/feedback math and PCM24 saturation;
- request, first valid, HOLD, result acceptance, commit, cancellation and playback;
- commit → pending → held mapping, legal repeated playback and underrun counting;
- observer and pixel-domain PCM observations;
- at least 1,025 enabled samples after the final flush, covering 1,024-entry wrap.

The compiled `M2_OUTPUT_BAD_LEFT` RTL variant is also simulated.  The same
checker must reject it with `COMMIT_PCM_MISMATCH`; textual trace editing is
not used as the behavior counterexample.

## Bounded command

Run from the repository root with a new output directory:

```powershell
& 'C:\Users\songdongkuan\miniconda3\python.exe' `
  .\code\tb\audio_out\m3_n32_delay_replay_20261014\run_replay.py `
  --output .\code\output\m3_n32_delay_replay_20261015_r01
```

The runner refuses an existing output directory.  Each compile is limited to
90 seconds, each simulation to 180 seconds, and each checker to 30 seconds.
It records complete argv, cwd, exit status, timeout and elapsed time in
`COMMANDS.jsonl`.  It performs no Gowin or device operation.

## Scope limits

The real C_FULL publications have equal left/right PCM and `clipped=0`.
Therefore this replay does not claim real-source coverage of unequal-channel
swaps or different clip phases.  The compiled bad-left mutation only proves
that a real nonzero PCM miswire is detected.  The result is isolated
functional verification, not realtime production N32, whole-system 40 MHz
STA, physical audio, or board validation.
