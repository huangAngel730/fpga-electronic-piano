# T052 runner field contract

`T052_RUNNER_ACCEPTANCE_V1` is a future-run configuration format. A valid
configuration pins every input and executable by byte count and SHA-256. Input
roles must include `DUT`, `TB`, `ROM` and `CHECKER`. The exact executable path
and version arguments belong to the configuration rather than PATH discovery.

The only accepted step order is `compile`, `simulate`, `check`. Each step owns
its stdout, stderr, step receipt and declared output artifacts. A declared
artifact must be absent before its step and present afterward. The capture and
request log are mandatory critical artifacts and cannot be supplied as inputs.

Success requires all three exits to be zero, every requested marker to be
present, every declared artifact to exist, both critical artifacts to have
been produced by this run, and all config/input/tool identities to remain
stable. Any failure ends the sequence without retry and writes `FAIL_PARTIAL`.

On Windows the child starts suspended, joins a private Job Object and then
resumes. A timeout terminates that Job Object. On POSIX the runner uses a new
process group and terminates that group. No process-name scan or system-wide
kill is used.

The included tests cover a complete fake success, misleading PASS text with a
nonzero exit, zero exit without artifacts, missing ROM, missing dependency,
missing tool, stale
capture input, parent/child timeout cleanup with retained partial bytes, output
overwrite refusal and v5 limit enforcement. These are software fixtures, not
evidence that the T052 RTL, sound mathematics or physical design passed.
