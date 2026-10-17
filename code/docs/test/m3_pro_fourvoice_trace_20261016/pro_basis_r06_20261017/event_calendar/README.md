# R06 event calendar candidate

This directory documents the isolated `M3-R6-5 event_calendar` software
candidate.  It consumes the R6-2 independent MIDI plan plus canonical 61-field
public observations and an independently frozen frame plan.  It correlates
event presentation/acceptance with explicit `apply_event_seq`, voice lifecycle,
common `advance_mask=1111`, and request/result/commit/cancel transactions.

The implementation is passive: it reads only public trace fields.  It never
uses `accept+1`, staggered toy lanes, the final slot snapshot, or private
wave/envelope/phase state to manufacture an apply event.

Current authority is incomplete.  M1-R6-1 and M2-R6-1/R6-2 have not supplied
authoritative production semantics or a real exported trace.  Therefore this
package can pass only explicitly labelled synthetic fixtures.  Real mode must
return a `PENDING_*` status until those inputs and the independent frame plan
are present.  A synthetic pass is not a Pro DUT calendar pass.

## Entry points

```powershell
python -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/event_calendar/event_calendar.py --plan <midi-plan.json> --trace <canonical61.jsonl> --binding <binding.json> --frame-plan <frame-plan.json> --output <report.json>
```

Exit codes are `0` for an accepted result, `2` for deterministic rejection,
and `3` for missing authority/evidence (`PENDING_*`).  The bounded self-test is
run only through the frozen `RUN_SPEC.json` and `run_once.py` command recorded
in `RESULT.md`.

No HDL compiler, simulator, Gowin tool, board, serial port, or audio device is
used.  No SystemVerilog observer was created because no authoritative public
Pro port set exists yet; inventing one here would cross the controlled
interface boundary.
