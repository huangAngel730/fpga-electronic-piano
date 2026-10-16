# A resume segmented raw observation contract

Accepted by night coordinator in this isolated batch. Algorithms, ROM, clocks, internal registers and all old evidence remain unchanged. Last remaining real functional group only.

Exact machine field/bit-width definitions are frozen in `STARTUP_SCHEMA.json`; producer source paths are given there. No implicit fields, guessed widths or inferred header names are permitted. Startup strings use full declared width and alphabet `01xXzZ`. STARTUP_RESET is the initialization resolution record, not a new main epoch. Final boundary identity key set is also fixed in that file.

## Selection fixed before execution

At EVERY 40MHz rising edge, evaluate the same board-level public-port concatenation: synchronized reset, frame/request/commit/IDs/PCM/clip/pending/play/underflow/pins, MIDI input, shared performance event valid/ready/data, public config valid/ready and active voice count. Main capture begins on the FIRST positive edge on which every observed bit is known and `rst_n===0`. A simulation-only sticky enable preserves ALL later edges even if X returns; all later X triggers failure, never skip. Selection must happen within 64 absolute edges and before any real performance acceptance, else fatal. No force, internal initialization or post-run cropping.

## Files and timebase

- `STARTUP_CAPTURE.jsonl`: `HEADER` schema `M3_R05_STARTUP_PUBLIC_BINARY_V1`, clock_hz40000000; a `STARTUP_TICK` for every absolute positive edge before main starts, containing absolute_cycle (1-based), time_ps (integer exact simulator precision), and original observed fields as binary strings (including actual X/Z). `END` contains absolute_edges (prefix count) and main_first_absolute_cycle. Prefix X is preserved, never translated to zero. Initial reset changes are recorded as `STARTUP_RESET` with absolute_cycle/time_ps/rst_n_binary.
- `STARTUP_INPUTS.jsonl`: header, every prefix edge's public MIDI/event/config/status bits as binary strings with exact time_ps and absolute_cycle; initial raw input state at time0 and subsequent MIDI/raw-reset edges are also retained by the ordinary `REAL_INPUTS.jsonl` timeline. No early input state/edge is discarded. END prefix count must agree with main boundary and startup capture.
- `REAL_CAPTURE.jsonl`: original `M3_R05_PUBLIC_PRE_NBA_V1` header and exact field set. Relative cycle1 maps to main_first_absolute_cycle, and every subsequent positive edge has the next relative cycle. Includes reset intervals and unique END. All active/main-window unknown bits are fatal. first_valid remains null. Epoch0 starts in already-known asserted reset; all subsequent asynchronous RESETs are recorded. This main trace does NOT claim to include the unknown initial prefix.
- `REAL_INPUTS.jsonl`: original `M3_R05_INPUT_PRE_NBA_V1` fields, HEADER→INITIAL_INPUTS at time0, raw input edges, main TICKs with the same relative cycle and synchronized reset as audio capture, unique END. `time_ns` uses original `$time` rounded to integer ns; exact first phase and 25,000ps spacing are supplied by boundary. No physical/analog inference from rounding.
- `STARTUP_BOUNDARY_RAW.json`: simulator-produced selection facts: startup_edges, main_first_absolute_cycle, main_first_time_ps, main_first_time_ns, main_first_relative_cycle=1. `STARTUP_BOUNDARY.json` is a post-run identity binding of these raw facts plus startup/input/main SHA, selection predicate, startup_unknown=true, clock spacing25000ps, absolute_cycle=relative_cycle+startup_edges. Prefix counts and startup/input alignment are checked before publication.
- READY marker appears only after successful unchanged-tool run and complete structural/raw-prefix/main ledger validation; it contains exact receipt, capture, inputs, startup and boundary identities. Missing/failed raw files never produce READY.

## Source snapshots / limitations

Receipt retains schema `M3_R05_NIGHT_OBSERVATION_RUN_V1`, fixed tool commands and original stage/source before-after maps. New `source_snapshot_layout=FLAT_RELATIVE_SHA_MAP_V1`, `source_snapshot_files` maps EACH original repository-relative source key to actual copied file path/bytes/SHA. C must verify this map and exact source bytes; old execution_sources nesting is not used due Windows long-path limit. R05/TX/ROM pins and 3-entry BOARD/TB/OBSERVER candidate manifest remain mandatory.

Prefix is always `startup_unknown=true`; no startup/reset-initialization signoff. Main digital request deadlines / PT8211 decoding can be assessed only for complete observed main windows. first-valid, analog≤10ms, physical PLL/HDMI/STA/board results remain UNKNOWN/unapproved. `board_release_allowed=false`.
