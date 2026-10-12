# T052 bounded runner software successor

This isolated candidate addresses the runner evidence gaps recorded by M2 for
the T052 v5 delivery. It does not replace M1's `run_tb.py` and does not run a
real simulator during qualification.

The contract implemented by `runner.py` requires:

- a fresh output directory and a fresh copied work directory;
- exact input bytes/SHA, including explicit DUT, TB, ROM and checker roles;
- absolute tool paths, executable bytes/SHA and a successful version query;
- compile, simulate and independent check in that order, with v5-or-lower
  limits of 300, 900 and 600 seconds and an explicit total no greater than
  1800 seconds;
- capture and request artifacts created by this invocation;
- exit-code, marker and artifact checks together; a `PASS:` string alone is
  insufficient;
- source/tool/config identity checks before and after execution;
- original partial stdout/stderr and visible artifacts on timeout or failure;
- termination of only the process tree launched by the failing step;
- a receipt for missing ROM, dependency, tool, nonzero exit, timeout and
  missing artifact failures.

Qualification command (software fake tools only):

```powershell
& 'E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe' -I -S -B -X utf8 code/software/t052_runner_acceptance_candidate_20261012/delivery.py qualify --output code/output/m3_t052_runner_20261013_01
```

The qualification uses the current Python executable as a pinned fake tool.
It does not invoke ModelSim, Icarus, VVP, Gowin or any T052 mathematics. The
candidate therefore establishes L0/L1 software behavior only. M2 must review
it before M1 adopts any part of the contract for a real RTL run.

Complete T052 remains `PARTIAL`. No synthesis, PnR, STA, device, serial,
installation, programming or wiring operation is included.
