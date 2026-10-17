# M3-R6-4 tool_plan_adapter result

## Outcome

- Result: `PASS_SOFTWARE_FIXTURE_ONLY`
- Verification level: `L1_SOFTWARE_FIXTURE_ONLY`
- Frozen baseline: `42d28c4ad8250b9064099da4742fbde12a254444`
- Machine: `LAPTOP-KSS1MRR7`
- Functional groups consumed: 1 of 1
- Group limit / elapsed: 90 s / 2.203 s
- Group exit code: 0
- Fixed Python fixture process launches: 3
- Real Icarus / ModelSim / Gowin / RTL simulation / hardware launches: 0
- Board release: false

## Exact group command

Working directory:

```text
E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano
```

Command:

```powershell
& 'C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -X utf8 'code\software\m3_pro_fourvoice_trace_20261016\pro_basis_r06_20261017\tool_plan_adapter\run_selftest.py'
```

Observed stdout:

```json
{"result": "PASS_SOFTWARE_FIXTURE_ONLY", "level": "L1_SOFTWARE_FIXTURE_ONLY", "elapsed_seconds": 2.203, "exit_code": 0, "error": null, "fixture_process_launches": 3, "real_tool_launches": 0}
```

## Cases

1. Correct binding: assemble, audit and run passed; Windows Job attached;
   stdout/stderr each retained three lines and the timestamped stream retained
   six events.
2. Fixed worker exit 7: runner returned exit 1 and retained the exact first
   failure `{stage: fixture_process, exit_code: 7, timed_out: false}`.
3. Source mutation after assembly: audit returned exit 2 / `INPUT_CHANGED`
   before marker creation or process launch.
4. Caller-supplied `approved: true`: assembly returned exit 2 /
   `CALLER_MUST_NOT_SET_APPROVED`.
5. Valid real-tool-shaped request without M2 admission: execution returned exit
   4 / `M2_EXECUTION_ADMISSION_REQUIRED_REAL_TOOL_NOT_LAUNCHED`; no real output,
   marker, or process was created.
6. Pre-existing output directory: execution returned exit 5 and did not consume
   the plan.
7. Concurrent consumers: exactly one returned 0 and ran the fixture; the other
   returned 3 / `PLAN_ALREADY_CONSUMED_OR_IN_PROGRESS`.

## Key evidence SHA-256

- `TEST_SCOPE.json`: `d6753e26203fed8814ede8a0f54c7dbbd97d2cd42848925b2bf3a7ec53f5f5b4`
- `RUN_01/GROUP_RECEIPT.json`: `f52dbd58eb6a74ffb510892820471f5c99c83f719d189d21400374b321a0d856`
- Valid process receipt: `79e41863a217acd67f1bba37339e1adb9cd7b080d45bdf38c43e78c523b4fc65`
- Expected-error process receipt: `1cb38c3d03fcb23e4cc91d1aa4d70451ebc6022905373e06d2af95b7d622a163`
- Concurrent winner receipt: `7e0aa62d3aaf38e01f8dcd48ede664280e665e1451d54ab02d3701c7c84bed81`
- Delivery ZIP (59,551 bytes, 76 entries, full readback):
  `1a501d76271f1751722de464b7c0eedd223d76d4595f7fe98290a5b8182b3d7c`

The source, dependency, executable, argv, cwd, output, timeout, before/after
identities, raw logs, consumption markers, and individual call exit codes are
recorded in `TEST_SCOPE.json` and `RUN_01/GROUP_RECEIPT.json`.

## Boundaries

This result validates only the new plan adapter with the fixed Python fixture.
It is not a real-tool approval, RTL simulation result, synthesis result, timing
result, board result, or Pro four-voice acceptance.  Any real tool plan still
requires a separate exact M2 admission artifact and executor path.
