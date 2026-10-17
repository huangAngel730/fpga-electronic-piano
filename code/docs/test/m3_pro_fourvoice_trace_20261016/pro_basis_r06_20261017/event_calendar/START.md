# Frozen software-group plan

- Package: `M3-R6-5 event_calendar`.
- Repository and `origin/develop` baseline before implementation:
  `42d28c4ad8250b9064099da4742fbde12a254444`.
- Runtime: bundled CPython, invoked with `-B -X utf8`.
- Budget: one new pure-software group, at most 90 seconds.
- Exclusive output: corresponding `RUN_01/` below this directory.
- Inputs: files and exact identities in `INPUT_IDENTITIES.json`, plus the
  implementation/case hashes frozen in `RUN_SPEC.json` before execution.
- Cases: one labelled synthetic positive, three authority PENDING cases, and
  ten deterministic rejection cases.  They cover actual-apply linkage,
  one-by-one retirement, common mask `1111`, missing/extra frame advances,
  cancel-then-commit, cross-epoch commit, same-edge cancel/result priority,
  missing finish, and canonical-field completeness.
- Explicitly unavailable: authoritative M1-R6-1 semantics, M2-R6-1 sampling
  and priority contract, M2-R6-2 real public export, independent real frame
  plan, and a real Pro trace.
- Prohibited calls: HDL compiler/simulator, Icarus, ModelSim, Gowin, serial,
  board, download, audio, and Git writes.
