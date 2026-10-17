# Self-review

Scope reviewed: only the new R6-7 software and evidence directories. No shared
top, CST/SDC, task/status document or other candidate package was changed.

Checks completed:

- Exact required/optional keys and stable fail-closed errors are enforced in
  Python; the JSON schema is a field inventory, not a substitute for cross-field
  validation.
- Mandatory claims cannot use `NOT_APPLICABLE`; `board_release_allowed=true` is
  always rejected because this tool has no release authority.
- Fixture records/evidence require explicit fixture mode and cannot enter a
  production record.
- Physical sources are SHA/byte/path checked, reject symlinks/path escape, and
  bind to the same unit/session as the record.
- Bank 3/4/5 must occur exactly once; voltage is finite numeric, bounded and tied
  to raw measurement evidence and full measurement metadata.
- MIDI direction/voltage/common-ground structures and evidence classes are
  distinct. Reference PDFs cannot prove a measurement.
- A photo can identify PT8211/load population, but serial wiring and PA path need
  continuity/waveform/instrument evidence; legacy NEO polarity cannot prove Pro.
- Commercial binary and runtime evidence have separate structured contracts;
  sensitive fields are rejected in both record and index.
- The production record validates only as `VALID_PENDING`; the only
  `VALID_COMPLETE` case is a clearly marked synthetic fixture.
- Independent read-only review findings were incorporated before the successful
  execution. No reviewer/pre-reviewer workflow was enabled.

Known boundary: the Windows CIM query failed before enumeration, and no permitted
commercial-tool launch was made. Consequently actual board/instrument presence,
tool completeness and license validity remain unknown; this is not hidden or
promoted to a pass.
