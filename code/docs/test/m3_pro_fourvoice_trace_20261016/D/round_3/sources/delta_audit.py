"""Only new metadata/identity delta; reuses immutable successful serial evidence."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from check_fixture import cancel_at_reset, finalize_dispositions
from preflight import ROOT, DOCS, identity
from run_round import guarded_exit, source_set


def write(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")


def key(row):
    return tuple(row[k] for k in ("epoch", "frame", "slot", "lane", "req_id"))


def validate_link(link, records, result):
    accepts = {key(r): r for r in records if r["kind"] == "ACCEPT"}
    consumed = {key(r): r for r in records if r["kind"] == "CONSUME"}
    cancelled = {key(r): r for r in records if r["kind"] == "CANCEL"}
    stereo = {(r["epoch"], r["id"]): r for r in result["serial_frames"] if r["id"]}
    ledger = {(r["epoch"], r["id"]): r for r in result["request_ledger"]}
    seen = set()
    expected_d = {}
    per_epoch = Counter()
    for frame in (r for r in records if r["kind"] == "FRAME"):
        pair = frame["epoch"], frame["frame"]
        if any(k[:2] == pair for k in consumed):
            per_epoch[pair[0]] += 1
            expected_d[pair] = (pair[0], per_epoch[pair[0]])
    for row in link:
        k = tuple(row["c_identity"])
        assert k in accepts and k not in seen, "MISSING_DUPLICATE_OR_UNKNOWN_C_ID"
        seen.add(k)
        if k in cancelled:
            assert row["disposition"] == "CANCELLED" and row["d_identity"] is None, "CANCELLED_MAPPED"
        else:
            assert k in consumed and row["disposition"] == "CONSUMED", "C_NOT_CONSUMED"
            dk = tuple(row["d_identity"])
            assert dk == expected_d[k[:2]] and dk[0] == k[0], "D_SERIAL_ID_OR_EPOCH"
            assert dk in stereo and dk in ledger, "D_SERIAL_NOT_COMPLETE"
            assert row["d_serial_last_rise"] == stereo[dk]["last_rise"], "D_SERIAL_LAST_RISE"
            assert row["c_cycle"] == consumed[k]["cycle"], "C_CONSUME_CYCLE"
    assert seen == set(accepts), "MISSING_C_LANE"
    assert len(seen) == 76 and len(consumed) == 71 and len(cancelled) == 5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    # Expectations precede execution of the new checks.
    write(out / "EXPECTED.json", {"reset": "known cancellation distinguished from END tail",
          "source_guard": "drift/add/remove ->65; unchanged ->original child exit",
          "C_link": "76 accepted lane IDs,71 consumed,5 cancelled;18 diagnostic stereo groups",
          "negative_links": ["old_epoch", "missing_lane", "duplicate_identity", "cancelled_mapped", "wrong_serial_id"],
          "old_serial_groups_reexecuted": 0})
    inputs = [DOCS / "round_1/cases/positive/RESULT.json",
              DOCS / "round_1/cases/positive/FIXTURE_CAPTURE.jsonl",
              DOCS / "round_1/cases/INPUT_PLAN.json",
              DOCS / "round_1/cases/positive/CASE_RECEIPT.json"]
    cdir = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/C"
    inputs += [cdir / n for n in ("LATEST_RECEIPT.json", "CALENDAR.json", "CALENDAR_CONTRACT.json")]
    frozen = [identity(p) for p in inputs]
    result = json.loads(inputs[0].read_text(encoding="utf-8"))
    plan = json.loads(inputs[2].read_text(encoding="utf-8"))
    original = json.loads(inputs[3].read_text(encoding="utf-8"))
    assert frozen[0]["sha256"] == identity(inputs[0])["sha256"]
    assert frozen[1] == original["capture"] and frozen[2] == original["input_plan"]
    assert result["capture_sha256"] == frozen[1]["sha256"] and original["passed"]
    latest = json.loads((cdir / "LATEST_RECEIPT.json").read_text(encoding="utf-8"))
    assert identity(cdir / "CALENDAR.json") == latest["calendar_json"]
    assert identity(cdir / "CALENDAR_CONTRACT.json") == latest["contract"]
    assert latest["calendar_json"]["sha256"] == "c53a75a8b103998ce81c38224fef265d8499103378c59dd8fd60bf32abef82e8"
    assert latest["contract"]["sha256"] == "9b600ef9638bb107bd8e662e856251073ba23b2db57eb9ca34285bd656d4d78f"
    # Test only reset-reporting helper, including inflight and already complete controls.
    toy = {(0, 1): {"status": "IN_FLIGHT", "next_frame_deadline": "UNKNOWN_TAIL"},
           (0, 2): {"status": "COMMITTED", "next_frame_deadline": "UNKNOWN_TAIL"},
           (0, 3): {"status": "COMMITTED", "sample_cycle": 12, "next_frame_deadline": "PROVEN"},
           (0, 4): {"status": "COMMITTED", "sample_cycle": 13, "next_frame_deadline": "PROVEN"},
           (1, 1): {"status": "COMMITTED", "next_frame_deadline": "UNKNOWN_TAIL"}}
    completed = [{"epoch": 0, "id": 4}]
    cancel_at_reset(toy, 0, 20, completed)
    cancel_at_reset(toy, 0, 21, completed)
    finalize_dispositions(toy, completed)
    assert toy[(0, 1)]["status"] == "CANCELLED_RESET"
    assert toy[(0, 2)]["sample_disposition"] == "CANCELLED_RESET_BEFORE_SAMPLE"
    assert toy[(0, 3)]["serial_disposition"] == "CANCELLED_RESET_BEFORE_SERIAL_COMPLETE"
    assert toy[(0, 3)]["next_frame_deadline"] == "PROVEN" and toy[(0, 2)]["cancel_cycle"] == 20
    assert toy[(0, 4)]["serial_disposition"] == "COMPLETE" and "cancel_cycle" not in toy[(0, 4)]
    assert toy[(1, 1)]["serial_disposition"] == "UNKNOWN_TAIL"
    ledger = {(r["epoch"], r["id"]): deepcopy(r) for r in result["request_ledger"]}
    reset_cycle = plan["epochs"][1]["reset_start"]
    cancel_at_reset(ledger, 0, reset_cycle, result["serial_frames"])
    dispositions = finalize_dispositions(ledger, result["serial_frames"])
    assert ledger[(0, 22)]["next_frame_deadline"] == "CANCELLED_RESET"
    assert ledger[(0, 21)]["serial_disposition"] == "CANCELLED_RESET_BEFORE_SERIAL_COMPLETE"
    assert ledger[(1, 22)]["next_frame_deadline"] == "UNKNOWN_TAIL"
    assert dispositions == {"COMPLETE": 40, "CANCELLED_RESET_BEFORE_SERIAL_COMPLETE": 2, "UNKNOWN_TAIL": 2}
    write(out / "RESET_DISPOSITION_AUDIT.json", {"derived_from_existing_pass": True,
          "full_decoder_reexecuted": False, "reset_cycle": reset_cycle,
          "serial_dispositions": dispositions, "request_ledger": list(ledger.values())})
    guard_dir = out / "guard_fixture"
    guard_dir.mkdir()
    sample = guard_dir / "sample.py"
    sample.write_text("# initial\n", encoding="utf-8")
    before = source_set(guard_dir)
    assert guarded_exit(0, before, source_set(guard_dir)) == 0
    assert guarded_exit(1, before, source_set(guard_dir)) == 1
    sample.write_text("# changed\n", encoding="utf-8")
    assert guarded_exit(0, before, source_set(guard_dir)) == 65
    assert guarded_exit(0, before, {}) == 65
    assert guarded_exit(0, before, {**before, "added.py": before["sample.py"]}) == 65
    for n in (1, 2):
        old = json.loads((DOCS / f"round_{n}/RUN_RECEIPT.json").read_text(encoding="utf-8"))
        assert old["source_before"] == old["source_after"], "OLD_ROUND_SOURCE_DRIFT"
    records = json.loads((cdir / "CALENDAR.json").read_text(encoding="utf-8"))["records"]
    contract = json.loads((cdir / "CALENDAR_CONTRACT.json").read_text(encoding="utf-8"))
    assert contract["identity"] == ["epoch", "frame", "slot", "lane", "req_id"]
    accepts = [r for r in records if r["kind"] == "ACCEPT"]
    consumed = {key(r): r for r in records if r["kind"] == "CONSUME"}
    cancelled = {key(r): r for r in records if r["kind"] == "CANCEL"}
    per_epoch = Counter()
    groups = {}
    for frame in (r for r in records if r["kind"] == "FRAME"):
        pair = frame["epoch"], frame["frame"]
        if any(k[:2] == pair for k in consumed):
            per_epoch[pair[0]] += 1
            groups[pair] = (pair[0], per_epoch[pair[0]])
    stereo = {(r["epoch"], r["id"]): r for r in result["serial_frames"] if r["id"]}
    link = []
    for r in accepts:
        k = key(r)
        dk = groups.get(k[:2]) if k in consumed else None
        link.append({"c_identity": list(k), "c_data": r["data"],
                     "disposition": "CONSUMED" if k in consumed else "CANCELLED",
                     "c_cycle": consumed[k]["cycle"] if k in consumed else cancelled[k]["cycle"],
                     "d_identity": list(dk) if dk else None,
                     "d_serial_last_rise": stereo[dk]["last_rise"] if dk else None})
    validate_link(link, records, result)
    write(out / "C_IDENTITY_LINK.json", {"schema": "D_C_DIAGNOSTIC_CROSSWALK_V1",
          "scope": "RETIMED_HAND_VECTOR_IDENTITY_ONLY_NOT_PRO_DUT",
          "mapping": "Within each C epoch, consumed frame groups map by ordinal to existing D request IDs1..N. Each lane retains the full five-field C identity. Cancelled lanes have no D target.",
          "PCM": "Independent D hand vectors; not a sum or mathematical function of C notes/lanes",
          "timing": "C and D cycles remain separate; no common execution/causal latency claim",
          "groups": len(groups), "rows": link, "inputs": frozen,
          "board_release_allowed": False})
    negative_results = []
    for fault in ("old_epoch", "missing_lane", "duplicate_identity", "cancelled_mapped", "wrong_serial_id"):
        bad = deepcopy(link)
        if fault == "old_epoch":
            bad[0]["c_identity"][0] = 9
        elif fault == "missing_lane":
            bad.pop()
        elif fault == "duplicate_identity":
            bad[1] = deepcopy(bad[0])
        elif fault == "cancelled_mapped":
            next(r for r in bad if r["disposition"] == "CANCELLED")["d_identity"] = [0, 1]
        else:
            bad[0]["d_identity"] = [0, 2]
        write(out / (fault + "_LINK.json"), bad)
        try:
            validate_link(bad, records, result)
        except AssertionError as exc:
            negative_results.append({"fault": fault, "rejected": True, "first_difference": str(exc)})
        else:
            raise AssertionError("NEGATIVE_NOT_REJECTED:" + fault)
    assert [identity(p) for p in inputs] == frozen, "INPUT_DRIFT"
    write(out / "RESULT.json", {"passed": True, "level": "L1_METADATA_IDENTITY_DELTA_ONLY",
          "reset_dispositions": dispositions, "source_guard": "PASS_5_CONTROLS",
          "prior_rounds_source_identity": "UNCHANGED_BOTH", "C_groups": len(groups), "C_lane_ids": len(link),
          "C_negative_results": negative_results, "inputs": frozen,
          "old_serial_groups_reexecuted": 0, "Pro_DUT": "PENDING_SOURCE_AND_TRACE", "board_release_allowed": False})
    print(json.dumps({"passed": True, "serial_dispositions": dispositions, "C_groups": len(groups),
                      "C_lane_ids": len(link), "new_negative_links_rejected": len(negative_results)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
