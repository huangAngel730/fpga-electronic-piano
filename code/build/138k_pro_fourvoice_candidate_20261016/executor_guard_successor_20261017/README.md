# M2 Windows Job software executor successor

## Current R03 cancellation cleanup and evidence

R02's ordinary-exception cleanup still missed `KeyboardInterrupt`/`SystemExit`
before attachment. R03 moves unattached-current-Popen-handle cleanup into
`finally`, records `BaseException`, and re-raises it after cleanup. Its one
separately authorized `KeyboardInterrupt` fault injection passed in 0.098566
seconds, exit 0. The case root exited 1, its handle signaled, the original
interruption propagated, both raw streams were empty, and no child/grandchild
or escape markers existed. Five prelaunch/post-run input identities matched.

Current executor SHA256:
`86227ae2637adf270df056b30ad67c751cb930daad50d1eb788f76228a090979`.
R03 targeted script SHA256:
`bccfb2978ac28368c164e76b6c887ea3121e8c0e40fb4cb56af5fa4ecbc0a98b`.
R01's five fixtures belong to its older SHA, R02's two faults to its SHA, and
only this one R03 fault ran against the final source. R01/R02 were not rerun.
All three scopes are consumed. There is no P7/Pro/HDL/EDA permission or claim
of final-version full-suite execution, uninterruptible OS behavior, or host-wide
orphan absence. `P7=BLOCKED_EXECUTOR_GUARD` remains in force.

## Preserved R02 targeted repair and evidence

Static self-review found a gap in R01: after suspended `Popen`, launch metadata
was written before Job attachment; a metadata write failure could strand an
unassigned suspended root. R02 attaches/resumes before writing launch metadata.
If any created root has not successfully attached, the exception handler kills
and waits using that invocation's own `Popen` handle. It also verifies the root
handle is signaled in final cleanup. No historical PID is terminated.

One separate authorized R02 group ran only two new fault-injection cases:
post-attachment launch-metadata write failure and failure before attachment.
`targeted_fix_r02.py` exited 0 in 0.118751 seconds, with
`PASS_TWO_TARGETED_SOFTWARE_FAULTS` / `L1_SOFTWARE_FAULT_INJECTION_ONLY`.
`RUN_02/PRELAUNCH.json` froze executor, targeted script, dummy, Python, and helper;
the final receipt proves those same identities after the run. R02 did not rerun
R01's five behavior groups and does not claim their full rerun on the new SHA.
The older executor is restored under evidence `SOURCE_R01/`, with its exact
RUN_01 identity verified and restoration provenance explicitly recorded.

Current executor SHA256:
`1cd67eaeed4195b12dbfe62898fbde28ec46908fdceea89e1574111c04f3b68d`.
Targeted R02 script SHA256:
`6bcebaad1e7175a18e195604511376edf69012663e18627fc5e65f7fae248c5b`.
Both groups are consumed. No automatic rerun or Pro/HDL permission is created.

## Preserved R01 software fixture scope

This is a new software-only process-control successor. It does not import, run,
edit, or unlock the old P7 runner. The old `M2_P7_ALLOW_FRESH_ICARUS` variable is
neither read nor set. The command-line interface always returns denial/exit 2;
there is no HDL, Pro, EDA, or arbitrary-command launch route.

`owned_executor.py` permits only the current Python executable with `-I -S -B`,
this directory's exact `software_dummy.py`, and five fixed fixture modes. It
checks executor/dummy/Python/pinned Windows Job helper identities before launch
and after completion. Outputs are exclusive per-case directories under the new
evidence `RUN_01`, `RUN_02`, or `RUN_03`; case reuse and other output roots are refused.

Every fixture process is created suspended, attached to its fresh owned Windows
Job, then resumed. Raw stdout/stderr go directly to exclusive files. Timeouts
and observed log overflow call `TerminateJobObject`; `finally` closes the Job,
whose pinned helper sets kill-on-close. Surviving descendants after a parent
exits are cleaned by kill-on-close. The executor obtains synchronize/query
handles only from its own Job membership, rechecks each handle's membership,
and waits for those handles to signal; it never kills historical PIDs or scans
the global process list.

The file-byte check is polling. The process can exceed the configured threshold
before detection and stop; it is not a hard byte cap or filesystem quota.

The one authorized software group has already run. Its original receipt is
`code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/executor_guard_successor_20261017/RUN_01/RECEIPT.json`.
Do not rerun it: the output directory is intentionally non-reusable. A later
implementation or test needs a new exact path and effective permission.

Actual command (one group, <=90 seconds):

```powershell
python -B -X utf8 code/build/138k_pro_fourvoice_candidate_20261016/executor_guard_successor_20261017/selftest_once.py
```

Observed result: exit 0, 3.579587 seconds, `PASS_SOFTWARE_ONLY`,
`L1_SOFTWARE_PROCESS_CONTROL_ONLY`. Normal exit 0, expected exit 7, a real
three-generation timeout, parent-exits-descendants-remain, observed log overflow,
and unapproved command/CLI denial passed. This proves only the exercised Python
fixtures and this software control mechanism. It is not P7 RTL evidence, current
global orphan absence, Pro tool permission, or board release. P7 remains
`BLOCKED_EXECUTOR_GUARD`; `board_release_allowed=false`.

The pinned helper is read-only:
`code/software/t052_runner_acceptance_candidate_20261012/windows_job.py`, SHA256
`5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b`.
The invocation used `-B`; no cache is created alongside that old helper.

The group before/after input snapshots contain executor, dummy, Python, and
helper only. They do not contain `selftest_once.py`. Its reported SHA is the
current post-run seal identity; there is no independent before/after evidence
for that selftest source. Original execution receipts are preserved without
backfilling, and the group is not rerun to fill this evidence boundary.
