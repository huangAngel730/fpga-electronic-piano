# R04 ModelSim receipt checker

This directory is an offline-only M3 helper for M1's frozen R04 ModelSim
handoff.  It does not start `vlib`, `vlog`, `vsim`, Gowin, or any device.

## Frozen identity and acceptance contract

- Expected R04 archive SHA-256:
  `1101f1af0809530a150143456aab8ff9a1c66373e9ccbc174c6459e8c916b3bf`
- Expected archive `MANIFEST.json` SHA-256:
  `015bf0199c5118ecfe7ec96bfd0b216d8f195daaf4989ec6bc08779def180815`
- Expected member identities: all 91 entries in that manifest.
- Required simulation marker:
  `PASS M2_M1TD_REAL_CHAIN_BOARD_FUNCTIONAL_ONLY`
- `vlog` and `vsim` exit codes must both be zero.
- Their independent timeout flags must both be `false`.
- The `vlog` transcript must report `Errors: 0` and no compile error.
- Neither raw transcript may contain a FATAL or timeout indication.
- Pre-run and post-run input snapshots must both match the sealed archive.

Exit code `0` means every condition above passed.  Exit code `1` is a valid,
machine-readable rejection.  Exit code `2` means malformed/missing evidence or
an attempt to use a different sealed package.

## Input SHA snapshots

After an authorized operator extracts the complete R04 ZIP into a clean
directory, create one snapshot before the EDA run and another after it.  Keep
the output files outside the extracted input tree.

```powershell
python -X utf8 code/software/r04_receipt_check/snapshot_inputs.py `
  --package <R04.zip> `
  --input-root <clean-extracted-R04-root> `
  --output <new-output>/inputs_before.json

# Only M2's separately approved execution may occur here.

python -X utf8 code/software/r04_receipt_check/snapshot_inputs.py `
  --package <R04.zip> `
  --input-root <clean-extracted-R04-root> `
  --output <new-output>/inputs_after.json
```

The snapshot utility hashes the extracted manifest and all 91 manifest
members.  It rejects missing members, a different ZIP, a different manifest,
or an existing output path.  It never launches a simulator.

## Check an already-finished run

The execution wrapper must independently record the two process exit codes and
timeout decisions in this strict shape:

```json
{
  "vlog": {"exit_code": 0, "timed_out": false},
  "vsim": {"exit_code": 0, "timed_out": false}
}
```

Then run:

```powershell
python -X utf8 code/software/r04_receipt_check/receipt_check.py `
  --package <R04.zip> `
  --vlog-log <new-output>/vlog.stdout_stderr.log `
  --vsim-log <new-output>/vsim.stdout_stderr.log `
  --run-status <new-output>/run_status.json `
  --inputs-before <new-output>/inputs_before.json `
  --inputs-after <new-output>/inputs_after.json `
  --json-out <new-output>/R04_RECEIPT_REVIEW.json
```

The optional JSON output path must be new; the tool refuses to overwrite an
old receipt.  Raw logs are never rewritten.

## Automatic self-test

Command actually used for this delivery:

```powershell
C:\Users\songdongkuan\miniconda3\python.exe -X utf8 `
  code/software/r04_receipt_check/test_receipt_check.py -v
```

The tests use explicitly labelled synthetic logs.  They cover the accepting
case and reject missing PASS, FATAL after PASS, non-zero `vlog`/`vsim` exit,
timeout, missing compile-success marker, and post-run source drift.  They also
check the public CLI's `0`/`1`/`2` exit-code contract.  The sample files under
`examples/` include accepting, missing-PASS, late-FATAL, and non-zero-exit
fixtures; they are parser examples only, never real ModelSim proof.

## Scope and unverified items

This is software L0/L1 evidence for receipt parsing and source-identity
checking only.  It does **not** prove that ModelSim ran, that R04 functionality
passed, that arithmetic is correct, that `max_processing_cycles < 834`, that
resources infer as intended, or that FPGA timing/board audio passes.  Real
ModelSim input/tool/cwd/output identities and execution budgets still require
M2's exact approval.  The checker cannot grant or consume that permission.
