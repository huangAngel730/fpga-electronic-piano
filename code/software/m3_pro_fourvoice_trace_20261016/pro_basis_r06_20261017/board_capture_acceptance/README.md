# R6-8 software-side schema

This directory contains only the machine-readable session schema for a future
Tang Mega 138K Pro same-version capture. It contains no programmer, serial,
logic-analyser, oscilloscope, audio, or device executor.

The schema is an evidence inventory, not execution authority. A session may
leave fields null while `status=BLOCKED_PREFLIGHT`; an actual run must bind the
complete part/package, board and Dock revisions, Bank voltages, licensed tool
runtime, exact source/ROM/constraints/PLL/top identities, complete PnR/STA,
one exact `.fs`, recovery identity, and one explicit SRAM-only permission.

Legacy PG484 pins, legacy `.fs` identities, legacy download permissions and
Flash operations are outside this package.
