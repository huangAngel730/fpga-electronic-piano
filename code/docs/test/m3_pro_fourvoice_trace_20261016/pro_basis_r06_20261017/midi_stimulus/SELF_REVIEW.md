# Self-review

## Static review boundary

Reviewed only the three authorized `midi_stimulus` directories.  No shared
document, package, RTL, top, constraint, frozen evidence, or numbered status
file was modified.

Checks performed after RUN_02:

- inspected the bound input hashes in `RUN_SPEC_R02.json`;
- inspected `receipt.json`, raw stdout/stderr, `plan.json`, and all three driver
  files;
- confirmed reset row 0 is `0 0`, release is `800 1`, and first byte start is
  5920 (`800 + 4 * 1280`);
- confirmed 23 contiguous expected event IDs and 63 non-overlapping UART bytes;
- reviewed the SV driver for public ports only: outputs are `sys_rst_n`,
  `midi_rx`, `event_ready`; observations are `event_valid`, `event_data`;
- confirmed the driver contains no hierarchical DUT reference;
- ran `git diff --check` limited to the three authorized directories: exit 0,
  no output.  Because the package is untracked, also scanned every delivered
  text file independently for trailing whitespace and missing final newlines;
  both counts were zero.
- recomputed all 26 entries in `FILE_SHA.json`: zero missing files, size
  mismatches, or SHA-256 mismatches.

## Findings

The RUN_01 reset-start issue was found by post-run source review and repaired
once.  RUN_02 demonstrates the intended cycle-zero reset and post-release idle
interval.  No additional software defect was found in the final static review.

The SV driver remains uncompiled by authorization, so syntax/tool portability
and cycle alignment against a concrete DUT clocking block remain unverified.
This limitation prevents promotion above the stated L1 software / pure-file
level.
