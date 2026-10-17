# M3-R6-7 handoff to coordinator

M3-R6-7 `hardware_identity` is complete within its software/static-preparation
scope. Baseline remains `42d28c4ad8250b9064099da4742fbde12a254444`; no Git
write, board operation or FPGA/commercial-tool invocation was performed.

Implementation:

- `code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/hardware_identity/`
- `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/hardware_identity/`
- transport archive:
  `M3_R6_7_HARDWARE_IDENTITY_20261017.zip`
  (31,403 bytes; SHA-256
  `da4238bfafa39efa8c562285d3cf9d3657207e335175a399a350cb3403f15d6b`)

Verification: one frozen software group. Attempt 1 failed before cases with a
relative/absolute path wrapper error (exit 1, 0.573568 s), was preserved and
repaired with changed source. Attempt 2 passed 17/17 cases (exit 0, 0.421 s
internal, 0.928005 s process wall time). Exact commands, exits and raw results
are under `RUN_01`; the 24-entry file manifest independently rechecked PASS.

Actual level: validator software L1 self-test; hardware identity remains L0
static-source preparation. The production record is `VALID_PENDING`, release is
false, and 20 physical/tool claim groups remain `UNKNOWN/PENDING`. No physical
core/Dock/chip identity, Bank voltage, MIDI level/common-ground, PT8211/PA path,
safe load, attached instrument or runtime license was established. The 4072
Rev1.10/4071f3 Rev1.5 and associated pins are reference candidates only; old
138K C/NEO 31005 material is negative comparison only.

Coordinator action: retain this as the strict intake/validation package. Do not
upgrade board status until original photos, raw CSV/instrument exports and
non-secret tool runtime receipts are supplied and pass the validator. No M2
release is requested by this package.
