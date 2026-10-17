# R6-4 R07 narrow consumer candidate

`consumer.py` adds an independently pinned spec to the original fixed-worker
fixture consumer. It reconstructs the complete normalized plan in audit and
immediately before Popen. Rehashing a modified plan grants no permission.
The original adapter, original seven scenarios and originals are read-only.

Run from the repository root with the pinned Python in `TRUST.json`:

```text
consumer.py assemble --spec REPO_SPEC --spec-sha256 PINNED_SPEC_SHA --plan REPO_PLAN
consumer.py audit --spec REPO_SPEC --spec-sha256 PINNED_SPEC_SHA --plan REPO_PLAN --sha256 PLAN_SHA
consumer.py run-fixture --spec REPO_SPEC --spec-sha256 PINNED_SPEC_SHA --plan REPO_PLAN --sha256 PLAN_SHA
```

Plans/specs/output/markers are confined to this candidate's docs `RUN_01`.
The cwd, executable, worker, Python DLL and helper identities are fixed.
Inputs are the original three inert fixture files; no HDL executes.
The spec hash is an independent content pin, never an execution approval.
Real tools remain disabled. This is not an accepted real-tool executor and
does not extend old timeout, descendant, overflow or cleanup qualification.

`freeze.py` freezes one targeted repair group; `run_once.py` consumes it once.
The original R06 repair limit is 60 seconds (55 seconds work plus 5 seconds
cleanup), not a new R7 group. Do not rerun after ATTEMPT/CONSUMED exists.
