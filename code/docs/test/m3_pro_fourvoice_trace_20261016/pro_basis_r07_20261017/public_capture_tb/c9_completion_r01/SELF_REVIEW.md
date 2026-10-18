# task-day4 B self review

Level: L0 / STATIC / NOT_RUN. User permitted read-only sub-agent assistance; no external reviewer/previewer workflow was started.

Two read-only assistants inspected the six-case CALLABLE_ROUTE, M1 NEXT_INPUT boundaries, streaming conversion, explicit legacy projection and new fixtures. They did not modify files, import/compile candidates, run cases or call tools/devices. The implementing window also performed text/JSON/identity checks only.

Concrete findings resolved before freeze:

- CSV default cell limit would reject a legal 140000-byte metadata cell. Decoder now sets/restores a bounded field limit.
- CSV record parsing could span physical lines. Each bounded physical line is parsed separately with strict syntax and stable C9_CSV_RECORD_SYNTAX rejection.
- Raw projection pass now hashes the exact read bytes, independently of the second raw merge pass and final file identity recheck.
- Mechanical bundle requires raw_capture in missing-role accounting and checks provided raw/reset file SHA against every canonical row's source. Its negative case tests both descriptor tamper and unrelated-but-validly-hashed originals.
- Three-valued actual request handshake keeps known-zero AND unknown false; no request tag becomes FRAME F.
- Legacy intake's preserved row collection is replaced only at its one AST initialization site with an append-only disk sink. The old F/A/transaction algorithms are reused, not rewritten.

Known limits are explicit: raw<=64GiB; JSON line<=1MiB; each reset/end/stdout metadata<=16MiB; outputs<=512GiB/file; canonical rows<=100 million. Legacy intake retains frame/transaction/TX state and history scans, capped at one million event observations; it is not constant-memory or guaranteed linear-time as a whole.

Only ten new seam cases and the original six NOT_RUN cases are offered here. Old C9 C17 is unchanged and left to the coordinator's exact new execution selection. No case is recorded as PASS before the coordinator runs it. All original budgets/receipts/failed artifacts and source bytes remain frozen.

Missing genuine plan mapping, audio_stable policy, independently reconstructed M1 mathematics, real capture authority and M2 admission remain PENDING. Source/structure completeness does not sign DIGITAL_VERIFIED or board release. The member performed no Git writes.
