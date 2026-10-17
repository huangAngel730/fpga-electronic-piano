# M3-R6-6 frozen execution declaration

- Baseline: `42d28c4ad8250b9064099da4742fbde12a254444`.
- Group: one new pure-Python software self-test, maximum 90 seconds.
- Output: the previously absent `RUN_01/` directory only.
- Sources: `tx_clock_reset_checker.py`, `fixtures.py`, `selftest.py`,
  `run_once.py`, and `cases.json`, each pinned in `RUN_SPEC.json`.
- Read-only dependency: `consume_capture.py` / `PinDecoder`, SHA-256
  `da91462e8421719e09ffab60d7bbe38d4ee05ac1793ea70e1f09c7a69ccda0cb`.
- Cases: one synthetic positive, seven authority PENDING cases, and twelve
  rejection cases covering startup identity, HOLD inheritance, commit/TX
  separation, same-PCM wrong ID, age boundary, missing/duplicate frames,
  reset/power safety, serial corruption, and invalid finish.
- Runner records argv, cwd, PID, elapsed time, timeout, raw stdout/stderr,
  source/dependency before/after SHA, exit code, and consumption count.
- On timeout the process tree is terminated. Output is never overwritten.
- No HDL compiler/simulator, Gowin, STA, serial port, programmer, download,
  Flash, or hardware operation is allowed.
- If this group exposes a new implementation defect, retain RUN_01 and permit
  only one different minimal repair run of at most 60 seconds. Otherwise no
  second functional run is allowed.
