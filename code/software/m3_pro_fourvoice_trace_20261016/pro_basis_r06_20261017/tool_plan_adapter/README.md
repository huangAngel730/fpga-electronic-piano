# M3-R6-4 tool plan adapter

This package assembles and audits a content-bound tool plan.  It binds source,
ROM, testbench, executable, dependencies, argv, cwd, exclusive output,
timeout, and an atomic consumption marker before a process can start.

The executable path in this M3 package is intentionally split in two:

- `SOFTWARE_FIXTURE` accepts only the bundled Python worker, the pinned
  `windows_job.py`, the exact fixture authority, and `approved: false`.
- `REAL_TOOL_REQUEST` can be assembled and audited, but `run-fixture` always
  returns exit 4 with `M2_EXECUTION_ADMISSION_REQUIRED_REAL_TOOL_NOT_LAUNCHED`.
  M3 cannot turn a JSON field or environment variable into approval.

The fixture launch is suspended first, attached to a Windows Job with
kill-on-close, then resumed.  stdout and stderr are drained concurrently into
raw files and a timestamped JSONL event stream.  A non-zero child exit is
retained as the first failure in `RECEIPT.json`.

## Commands

Run from the repository root with the frozen Python executable or an equivalent
Python 3.12 installation:

```powershell
python -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/tool_plan_adapter/run_selftest.py
```

`run_selftest.py` is one-shot and creates the exclusive `RUN_01` evidence
directory.  It must not be rerun against an existing directory.  The CLI forms
used by the self-test are:

```text
plan_adapter.py assemble --spec SPEC.json --output PLAN.json
plan_adapter.py audit --plan PLAN.json --sha256 PLAN_SHA256
plan_adapter.py run-fixture --plan PLAN.json --sha256 PLAN_SHA256
```

This package does not modify or call M2's `owned_executor`, and it contains no
Icarus, ModelSim, Gowin, RTL simulation, programmer, or hardware launch route.
