# T061 N32-B isolated N32/R1 combination

Latest result (2026-10-14): the bounded N32/R1 LONG=1 run and the three output
mutants passed with the extended, progress-guarded execution documented in
`RESULT_20261014.md`.  This is a T061 partial functional/mathematical result;
physical STA and production integration remain outside this result.

Historical preparation status: `PREPARED_NOT_EXECUTED`.  The B assets are not a PASS until N32-A has
an exact reviewed PASS identity, this directory has been sealed into one
machine-readable execution plan, and that exact plan has passed both review
windows before the bounded runner is invoked.

The isolated composition is:

```text
event -> b_n32_event_router -> m3_balanced_voice_allocator
      -> frozen control snapshot -> frozen B1 scheduler/statebank
      -> b_n32_event_audio_prom -> frozen pROM backend
      -> result_id + left/right PCM + accurate clipped
```

`b_n32_event_router.sv` starts from the frozen router, changes its module and
allocator names, and adds observation-only exports for router state and the
existing sustain-release batch.  `b_n32_event_audio_prom.sv` starts from the
accurate pROM successor, selects that router, exports existing control/release
state, and gates public `read_ready` so a visible handshake is accepted exactly
once at an idle boundary.  These deltas add no audio datapath feedback.
`b_n32_r1_wrapper.sv` fixes the accepted configuration to N32/R1, forwards the
public C observation contract, and contains output-only compile-time mutations
for result ID, PCM, and clipped; no mutation is enabled in the normal case.
The TB instantiates the exact Gowin `GSR` simulation primitive required by the
pROM model; it does not add a DUT clock/reset domain or any board connection.

The existing `B2C 32 1 <long_case>` capture schema remains unchanged.  The
normal lifecycle case uses `long_case=1`; the bounded behavior mutants use
`long_case=0`.  The B observer adds:

```text
K cycle valid ready publish id_hex left_dec right_dec late clipped
```

The checker first binds each K row to the request/reset lifetime and the 32 lane
contributions, so each output-only mutation is rejected with its specified
ledger reason.  It then replays every ordinary row with the existing independent
router/ROM/DSP oracle.  Together these checks verify ID, stereo PCM, the clipped
bit derived from the unsaturated wide sum, HOLD stability, cancel, reset, and
publish alignment.

The final harness copies every HDL, checker, model, ROM, include, and vendor
simulation input into the prepared snapshot.  Plan verification rejects any
compile or checker command that names an active-repository input; execution is
therefore bound to the reviewed snapshot bytes rather than the live worktree.
The active-worktree harness is preparation-only: formal `execute` is rejected
unless Python is running the exact `execution_entrypoint` inside the reviewed
snapshot, with its helper imports resolved from that same snapshot.  Prepare
also copies the complete Icarus executable/plugin closure into
`prepared/tools/iverilog`, including `bin/*.dll`, `lib/*.dll`, and the recursive
`lib/ivl` tree.  The plan binds the three current PE runtime dependencies
`libgcc_s_seh-1.dll`, `libstdc++-6.dll`, and `libwinpthread-1.dll` by identity.
Compile and simulation commands are rejected unless their executable and `-B`
plugin path point into that reviewed tool capsule.  Every child receives an
exact capsule-only `PATH` (`bin;lib`) and capsule-root `YOSYSHQ_ROOT`; the
runner never invokes or copies `environment.bat`, because that script can
perform unrelated GDK cache updates.
The load-visible `bin/*.dll` plus `lib/*.dll` member set must exactly equal the
reviewed tool manifest at copy completion, before execution, and after all
work.  An added, deleted, unbound, or byte-modified DLL is therefore rejected;
the normalized DLL-set digest is also recorded in the plan, attempt, and
receipt.

Loader-only review evidence is collected from a frozen source/test/helper
snapshot, not from the active worktree.  Its receipt binds the exact input
manifest, Python, argv, cwd, raw stdout, and raw stderr and checks the snapshot
again after the tests.  The sealer rereads those raw records once and refuses
to package them if the active authored/dependency bytes no longer equal the
tested snapshot.  The snapshot's actual regular-file set must exactly equal
the input manifest; after one validated read, archive creation uses only those
cached bytes and never rereads the snapshot from disk.  This loader review
remains separate from the later formal B PLAN and cannot bypass the A PASS
gate.

The public C integration contract is machine-readable in
`code/rtl/common/m3_n32_allocator_candidate_20261013/B/b_n32_c_interface.json`.
It freezes the `b_n32_r1_wrapper` parameters, source order, transaction ports,
32-slot identity arrays, control/release observations, and audio/router state
encodings.  These observation outputs do not feed the business path; a C
testbench must not read B internal registers hierarchically.

Software-only checker tests may be run without HDL execution:

```powershell
Set-Location code/tb/audio/t061_n32_allocator_candidate_20261013/B
C:/Users/songdongkuan/miniconda3/python.exe -B -X utf8 -m unittest test_b_n32_check.py
```

Do not invoke an execution plan marked `execution_authorized=false` or
`WAIT_A_PASS`.  Do not reuse a failed or partial output directory, retry a
step, switch tools/machine, or increase the reviewed 300-second per-tool and
900-second total limits.

`b_delivery.py` creates each new PLAN/RESULT review package exclusively.  The
package carries the complete prepared source/tool capsule, B-authored files,
per-file SHA manifests, an evidence manifest, generation metadata, and a
Git-produced binary-safe diff.  A changed byte requires a new Review-Key and
package; an existing sealed directory is never overwritten.
