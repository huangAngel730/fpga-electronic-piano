# Failure and repair history

`RUN_01` executed the frozen software group and exited 1 after 0.11389780044555664
seconds.  The accepted synthetic case had already completed, but the
`missing_canonical_field` negative fixture then failed inside the fixture
serializer with `KeyError: 'apply_data'`.  The serializer required every
canonical key while this negative intentionally removed one, so the malformed
input never reached the checker.  Raw stdout/stderr, the run receipt, and all
partially generated case artifacts remain unchanged under `RUN_01/`.

The single permitted minimal repair changes only the fixture writer to emit
canonical keys that are present, allowing that deliberately incomplete row to
reach `load_jsonl()` and be rejected as `MISSING_CANONICAL_FIELD`.  No checker
rule, authority boundary, MIDI input, frame plan, or expected diagnostic was
relaxed.  `RUN_02` is the only repair software group and has a 60 second bound.
