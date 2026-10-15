# T057 v1 offline recovery cases

These are diagnosis and test recommendations only. The verifier does not send a
frame, open a serial port, or perform a recovery action.

| Observation | Offline conclusion | Contract-preserving next action |
|---|---|---|
| Exact last successful BEGIN/DATA/COMMIT request repeats and the ACK bytes repeat exactly | Legal finite retransmission; apply the logical mutation once | Continue only after the complete ACK; at most two PC retries under the default client policy |
| Exact duplicate response without a new request | Report `DUPLICATE_RESPONSE`; never count another DATA write, COMMIT, or READ coverage item | Keep the duplicate in evidence and verify the next request identity |
| Late byte-identical previous response while a newer request is pending | Report `LATE_DUPLICATE_RESPONSE`; ignore only the old response and keep the newer request pending | Pair the following response against the still-pending request |
| NACK1 frame CRC | Failed request, no publication | Stop blind retry; issue ABORT or a fresh nonzero-session BEGIN after correcting the bytes |
| NACK2/3/4 version, command, or length | Encoder/request defect | Correct the request against `PROTOCOL.md`, then start a fresh transaction |
| NACK5/6/7 session, sequence, or offset | Transaction state mismatch | Do not advance local state; use ABORT or a new BEGIN and restart from seq 1, offset 0 |
| NACK8 incomplete COMMIT | Written contract invalidates the session; frozen RTL history differs | Use ABORT or a new BEGIN. Do not rely on the retained session until M2 resolves the discrepancy |
| NACK9/10 score CRC or event | Score not published; session invalid | Correct independent source data, then start a new BEGIN |
| NACK11 capacity/metadata | Score metadata cannot be accepted | Correct count/length/sample rate/capacity, then start a new BEGIN |
| NACK12 frame/session timeout | Partial frame/staging discarded, old committed score retained | Establish a documented idle boundary, then ABORT or start a new BEGIN |
| NACK13 READ index | Committed score is not changed | Retry only with an index in `0..committed_count-1` |
| NACK14 UART stop bit | Physical-byte evidence is bad | Preserve the capture; diagnose the link before starting a new transaction |
| Missing response / EOF mid-upload | `INCOMPLETE`, not a protocol violation by itself | Acquire the missing direction/timestamp evidence; do not infer ACK or commit |
| Separate TX and RX streams | Global order, latency, and retry causality are `NOT_VERIFIABLE` | Capture one interleaved, timestamped observation stream |
| Chunk timestamps without one timestamp per byte | Order may be available, but response latency and timeout remain `NOT_VERIFIABLE` | Capture exact byte timestamps or explicit frame start/end evidence |
| COMMIT succeeds but STATUS/full READ is missing | Upload bytes may be reconstructed, but end-to-end readback is `INCOMPLETE` | Acquire STATUS and every READ result; ACK alone is not enough |

Every observed NACK keeps the whole trace `INVALID`; a later successful fresh
transaction is reported as recovery evidence but does not erase the NACK.

Recovery fixtures in `selftest.py` include ABORT followed by a clean new BEGIN,
legal exact request replay, duplicate response suppression, terminal NACK,
midstream EOF, and the COMMIT/NACK8 frozen-contract divergence.
