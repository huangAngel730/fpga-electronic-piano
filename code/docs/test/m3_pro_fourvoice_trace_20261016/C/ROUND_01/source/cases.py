"""Targeted transaction attacks; expected refusal codes fixed before running."""
import copy
from calendar import build, default_plan


def cases():
    good = build(default_plan())
    result = [("positive", good, "FIXTURE_CALENDAR_PASS", 0)]

    def attack(name, code, change):
        rows = copy.deepcopy(good)
        change(rows)
        result.append((name, rows, code, 2))

    def pos(rows, kind, frame=13, lane=1):
        return next(i for i,x in enumerate(rows) if x["kind"] == kind and x.get("frame") == frame and x.get("lane") == lane)

    def duplicate(rows, kind):
        index = pos(rows, kind)
        rows.insert(index + 1, copy.deepcopy(rows[index]))

    attack("duplicate_lane_tick", "DUPLICATE_LANE_TICK", lambda r:duplicate(r,"LANE_TICK"))
    attack("wrong_lane", "LANE_IDENTITY", lambda r:r[pos(r,"RETURN")].update(lane=2))
    attack("stale_epoch_return", "STALE_EPOCH", lambda r:r[pos(r,"RETURN",16,0)].update(epoch=0))

    def consumed_cancel(rows):
        index = pos(rows,"CANCEL",14,2)
        row = copy.deepcopy(rows[index])
        row.pop("reason")
        row["kind"] = "CONSUME"
        rows.insert(index + 1, row)
    attack("consume_after_accepted_cancel", "CONSUME_AFTER_CANCEL", consumed_cancel)
    attack("dropped_request", "MISSING_REQUEST", lambda r:r.pop(pos(r,"OFFER",0,0)))
    attack("retry_wrong_id", "WRONG_RETRY_ID", lambda r:r[pos(r,"OFFER")+1].update(req_id=9999))
    attack("backpressure_valid_drop", "BACKPRESSURE_VALID", lambda r:r[pos(r,"OFFER")+1].update(valid=0))

    def change_data(rows):
        rows[pos(rows,"OFFER")+1]["data"]["note"] = 71
    attack("backpressure_data_change", "BACKPRESSURE_DATA", change_data)
    attack("backpressure_missing_cycle", "BACKPRESSURE_DROP", lambda r:r.pop(pos(r,"OFFER")+1))
    attack("duplicate_publication", "DUPLICATE_PUBLICATION", lambda r:duplicate(r,"PUBLISH"))

    def missing_four(rows):
        rows[:] = [x for x in rows if not (x.get("frame") == 8 and x.get("lane") == 3)]
    attack("missing_fourth_lane", "FOUR_LANE_COVERAGE", missing_four)

    def unfinished(rows):
        rows[:] = [x for x in rows if not (x.get("frame") == 18 and x.get("lane") == 3 and x["kind"] in ("PUBLISH","CONSUME"))]
    attack("unpublished_at_end", "UNPUBLISHED_AT_END", unfinished)

    def after_reset(rows):
        index = pos(rows,"RETURN",16,0)
        old = next(copy.deepcopy(x) for x in rows if x["kind"] == "RETURN" and x.get("frame") == 15 and x.get("lane") == 0)
        old["cycle"] = rows[index]["cycle"]
        rows.insert(index,old)
    attack("old_published_epoch_after_reset", "STALE_EPOCH", after_reset)
    attack("missing_terminal_end", "END_MISSING", lambda r:r.pop())
    attack("boolean_cycle", "TIME_ORDER", lambda r:r[pos(r,"OFFER",0,0)].update(cycle=True))
    attack("cancel_missing", "RESET_WITHOUT_CANCEL", lambda r:r.pop(pos(r,"CANCEL",15,0)))
    attack("synthetic_claimed_observed", "HEADER_OR_SCOPE", lambda r:r[0].update(scope="OBSERVED_PRO_DUT"))
    return result


def hand_anchors(rows):
    """Independent small tables/counters, rather than DUT-derived expectations."""
    ticks = {(r["frame"],r["lane"]):r for r in rows if r["kind"] == "LANE_TICK"}
    for frame,note in ((0,60),(2,64),(4,67),(6,72)):
        assert ticks[(frame,0)]["data"] == {"active":True,"note":note,"velocity":800}
        assert sum(ticks[(frame,l)]["data"]["active"] for l in range(4)) == 1
        assert all(not ticks[(frame+1,l)]["data"]["active"] for l in range(4))
    assert [ticks[(8,l)]["data"]["note"] for l in range(4)] == [60,64,67,72]
    assert [[ticks[(f,l)]["data"]["note"] for l in range(4)] for f in (9,10,11,12)] == [[None,64,67,72],[None,None,67,72],[None,None,None,72],[None,None,None,None]]
    assert ticks[(13,1)]["cycle"] == 10868 and ticks[(13,1)]["req_id"] == 54
    assert ticks[(14,2)]["req_id"] == 59
    assert [ticks[(16,l)]["req_id"] for l in range(4)] == [1,2,3,4]
    assert all(ticks[(16,l)]["epoch"] == 1 and not ticks[(16,l)]["data"]["active"] for l in range(4))
    counts = {k:sum(r["kind"]==k for r in rows) for k in ("FRAME","EVENT","ACCEPT","LANE_TICK","RETURN","PUBLISH","CANCEL","CONSUME")}
    assert counts == {"FRAME":19,"EVENT":17,"ACCEPT":76,"LANE_TICK":76,"RETURN":75,"PUBLISH":75,"CANCEL":5,"CONSUME":71}
    frames = [r["cycle"] for r in rows if r["kind"] == "FRAME"]
    assert [b-a for a,b in zip(frames,frames[1:])][:6] == [833,833,834,833,833,834]
    return {"status":"HAND_TABLE_ANCHORS_PASS", "counts":counts,
            "solo_notes":[60,64,67,72],"chord_lane_notes":[60,64,67,72],
            "stall_accept_cycle":10868,"reset_restarted_ids":[1,2,3,4]}
