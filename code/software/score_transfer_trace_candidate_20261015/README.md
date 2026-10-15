# T057 offline transfer trace verifier

This isolated candidate parses existing T057 v1 byte logs and checks framing,
request/response identity, stop-and-wait transactions, upload reconstruction,
STATUS metadata, and full READ back against an independently supplied score or
record file. It never imports the frozen PC codec as its expected-data oracle and
never opens a serial port.

Validation level is **offline software only**. ACK, COMMIT, STATUS, and READ
agreement do not prove an FPGA UART link, playback, sound output, BLE, or timing
closure.

## Frozen inputs

- `code/docs/hardware/score_transfer_v1/PROTOCOL.md`
  SHA-256 `431b5cd7ae678c97bcb0be720a775b51a031f096161a0dbef36bdeea5f41f15b`
- `code/software/score_transfer_v1/score_transfer.py`
  SHA-256 `8e2a065dcea4fef997da2b0fda7e16a314c65c436b654903ca388be407ddfc07`
- historical normal RTL capture decoded SHA-256
  `c6ed14c912ebd40db72e3ffe04691deb1006fab77ef538ac0050ec5db1c7ce28`
- historical T057 delivery ZIP SHA-256
  `29f0da2bb910fe4856d8d9ff4db50a9b2edb1c239da92f47eb9ee07f133db6f9`

The repository contains no independently captured hardware `tx.bin`/`rx.bin`.
The existing `run_j_v22g6p` capture is ModelSim RTL serial simulation and PC
offline replay evidence, not USB-TTL or board evidence.

## Input modes

Direction names are PC-centric:

- `tx`: PC to FPGA request bytes.
- `rx`: FPGA to PC ACK/NACK bytes.

Interleaved JSONL preserves global chunk order. Each line is:

```json
{"direction":"tx","data_hex":"a55a","timestamp_us":1000,"byte_times_us":[1000,1087],"label":"fragment"}
```

`timestamp_us` is the first-byte/chunk ordering hint. A timing claim additionally
requires `byte_times_us`: one monotonic timestamp for every byte in `data_hex`.
This avoids treating one timestamp shared by a fragmented or coalesced chunk as
proof of full-frame response latency. Optional
`idle_before_ms` documents an observed idle gap; this is required to resume after
an oversized frame because the v1 contract discards bytes until 20 ms idle.
Arbitrary fragmentation, sync/header/payload/CRC splits, and multiple frames in
one chunk are supported.

Separate `--tx` and `--rx` raw files can be parsed, but the result is always
`NOT_VERIFIABLE`: separate streams cannot prove global order, response latency,
stop-and-wait behavior, timeout cause, or unambiguous retry pairing.

`--legacy-capture` reads the historical `START/CASE/RX/TX/.../END` simulator
format. Legacy `RX` is mapped to PC `tx`, and legacy `TX` to PC `rx`. `--base64`
accepts its repository carrier while ignoring only ASCII whitespace.

## Independent expectations

Use one of:

- `--expected-json`: a strict original T057 score JSON;
- `--expected-json`: a multi-transaction bundle such as
  `{"schema":1,"transactions":[{"session":7,"score":{...}}]}`;
- `--expected-records FILE --score-id ID [--session SESSION]`: independent raw
  8-byte records.

Expected data is never derived from observed TX/RX. Without an independent
expected input, content correctness is `NOT_VERIFIABLE` and the overall result is
`NOT_VERIFIABLE` unless a stronger `INVALID` or `INCOMPLETE` condition is also present.

## Strict and recovery parsing

- `strict`: any unowned byte, including prefix noise, is `INVALID`.
- `recover`: prefix/inter-frame noise is explicitly reported as
  `RECOVERED_NOISE`; a clean transaction may finish as `RECOVERED`, never as a
  silent clean PASS.
- CRC/version/oversized-length errors remain `INVALID` in both modes. Recovery
  mode only continues diagnosis.
- EOF partial frames and unfinished transactions are `INCOMPLETE`.
- Any observed NACK is `INVALID`, even when a later fresh transaction recovers;
  the report records the recovery without erasing the rejected exchange.

Exit codes are `0` for `PASS` or explicit `RECOVERED`, `2` for `INVALID`, and
`3` for `INCOMPLETE`, and `4` for top-level `NOT_VERIFIABLE`. Per-claim
`NOT_VERIFIABLE` entries explain exactly which conclusions lack evidence.

## Commands

Run from the repository root. Output directories must not already exist.

```powershell
python -B -X utf8 code/software/score_transfer_trace_candidate_20261015/score_trace_verify.py `
  --trace TRACE.jsonl `
  --expected-json EXPECTED.json `
  --mode strict `
  --output code/output/t057_trace_verify_RUN

python -B -X utf8 code/software/score_transfer_trace_candidate_20261015/score_trace_verify.py `
  --tx tx.bin --rx rx.bin `
  --expected-records records.bin --score-id 1 `
  --output code/output/t057_trace_separate_RUN

python -B -X utf8 code/software/score_transfer_trace_candidate_20261015/selftest.py `
  --output code/output/t057_trace_candidate_selftest_RUN

python -B -X utf8 code/software/score_transfer_trace_candidate_20261015/run_repo_gate.py `
  --output code/output/t057_trace_candidate_gate_RUN
```

Each verification writes `report.json`, `report.txt`, `frames.jsonl`, and
`transactions.jsonl` with
input path/size/SHA, direction-local byte offsets, frame identity, raw-frame SHA,
per-frame diagnostics, logical attempt/replay/application records, proven
conclusions, and evidence gaps. The self-test
also preserves each CLI invocation's stdout/stderr, a receipt, a file manifest,
and `evidence.zip`.

## Frozen contract discrepancy

The written contract says every failed COMMIT invalidates the current session.
The frozen RTL/history retains the session for incomplete COMMIT/NACK8 and then
continues DATA. The verifier follows the written contract and emits
`CONTRACT_IMPLEMENTATION_DIVERGENCE_COMMIT_NACK8_SESSION`; it does not select a
new protocol or modify either frozen artifact. M2 must resolve that interface
decision before future hardware-log sign-off.

The frozen PC client also accepts either 12 or 20 response-payload bytes for all
commands. This verifier is stricter: only a successful READ may carry 20 bytes;
all other ACK/NACK responses must carry the 12-byte metadata payload.
