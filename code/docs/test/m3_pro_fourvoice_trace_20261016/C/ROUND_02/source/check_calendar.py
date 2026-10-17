"""Validate fixture transaction identity/lifetime, then exact independent plan."""
import argparse
import json
from pathlib import Path
import sys

from calendar import build, encode, strict_load


class Rejected(Exception):
    def __init__(self, code, index, expected=None, actual=None):
        self.detail = {"status":"REJECTED", "code":code, "record_index":index,
                       "expected":expected, "actual":actual}
        super().__init__(code)


def check(plan, actual):
    expected = build(plan)
    if not actual or actual[0] != expected[0]:
        raise Rejected("HEADER_OR_SCOPE", 0, expected[0], actual[0] if actual else None)
    state, stalled = {}, {}
    epoch, last_cycle = 0, -1
    for index, row in enumerate(actual[1:], 1):
        if type(row) is not dict:
            raise Rejected("RECORD_STRUCTURE", index, "object", row)
        kind = row.get("kind")
        if kind not in {"RESET","EVENT","FRAME","OFFER","ACCEPT","LANE_TICK","RETURN","PUBLISH","CANCEL","CONSUME","END"}:
            raise Rejected("RECORD_KIND", index, None, row)
        if type(row.get("cycle")) is not int or row["cycle"] < last_cycle:
            raise Rejected("TIME_ORDER", index, None, row)
        last_cycle = row["cycle"]
        if type(row.get("epoch")) is not int:
            raise Rejected("FIELD_TYPE", index, None, row)
        if kind == "RESET":
            if row["epoch"] != epoch + 1:
                raise Rejected("RESET_EPOCH", index, epoch + 1, row)
            if any(v["status"] not in ("CONSUMED","CANCELLED") for v in state.values()):
                raise Rejected("RESET_WITHOUT_CANCEL", index, None, row)
            epoch += 1
            stalled.clear()
            continue
        if row["epoch"] != epoch:
            raise Rejected("STALE_EPOCH", index, epoch, row)
        if kind in ("FRAME", "EVENT"):
            continue
        if kind == "END":
            if index != len(actual) - 1:
                raise Rejected("AFTER_END", index, None, row)
            pending = [k for k,v in state.items() if v["status"] not in ("CONSUMED","CANCELLED")]
            if pending or stalled:
                raise Rejected("UNPUBLISHED_AT_END", index, [], pending)
            continue
        if any(type(row.get(k)) is not int for k in ("frame","slot","lane","req_id")):
            raise Rejected("FIELD_TYPE", index, None, row)
        if row["slot"] != row["lane"] or row["lane"] not in range(4):
            raise Rejected("LANE_IDENTITY", index, row.get("slot"), row)
        key = (epoch, row["req_id"])
        lane_key = (epoch, row["lane"])
        ident = {k:row[k] for k in ("epoch","frame","slot","lane","req_id","data")}
        if kind == "OFFER":
            if type(row.get("valid")) is not int or type(row.get("ready")) is not int or row["ready"] not in (0,1):
                raise Rejected("HANDSHAKE_TYPE", index, None, row)
            if lane_key in stalled:
                previous = stalled[lane_key]
                if row["cycle"] != previous["cycle"] + 1:
                    raise Rejected("BACKPRESSURE_DROP", index, previous, row)
                if row["valid"] != 1:
                    raise Rejected("BACKPRESSURE_VALID", index, 1, row)
                if row["req_id"] != previous["req_id"]:
                    raise Rejected("WRONG_RETRY_ID", index, previous["req_id"], row)
                if ident != previous["ident"]:
                    raise Rejected("BACKPRESSURE_DATA", index, previous["ident"], row)
            if row["valid"] != 1:
                raise Rejected("VALID_REQUIRED", index, 1, row)
            if key in state:
                raise Rejected("DUPLICATE_REQUEST", index, None, row)
            if not row["ready"]:
                stalled[lane_key] = dict(row, ident=ident)
            else:
                stalled.pop(lane_key, None)
                state[key] = {"status":"OFFER_READY", "identity":ident}
            continue
        if key not in state:
            raise Rejected("MISSING_REQUEST", index, None, row)
        s = state[key]
        if ident != s["identity"]:
            raise Rejected("REQUEST_IDENTITY", index, s["identity"], row)
        if kind == "CONSUME" and s["status"] == "CANCELLED":
            raise Rejected("CONSUME_AFTER_CANCEL", index, None, row)
        if kind == "PUBLISH" and s["status"] in ("PUBLISHED", "CONSUMED"):
            raise Rejected("DUPLICATE_PUBLICATION", index, None, row)
        transitions = {"ACCEPT":("OFFER_READY","ACCEPTED"), "LANE_TICK":("ACCEPTED","TICKED"),
                       "RETURN":("TICKED","RETURNED"), "PUBLISH":("RETURNED","PUBLISHED"),
                       "CONSUME":("PUBLISHED","CONSUMED")}
        if kind == "CANCEL":
            if s["status"] not in ("ACCEPTED","TICKED","RETURNED","PUBLISHED"):
                raise Rejected("CANCEL_LIFETIME", index, None, row)
            s["status"] = "CANCELLED"
        else:
            before, after = transitions[kind]
            if s["status"] != before:
                code = "DUPLICATE_LANE_TICK" if kind == "LANE_TICK" and s["status"] == "TICKED" else "TRANSACTION_ORDER"
                raise Rejected(code, index, before, row)
            s["status"] = after
    if actual[-1].get("kind") != "END":
        raise Rejected("END_MISSING", len(actual), expected[-1], None)
    for index in range(max(len(actual), len(expected))):
        a = actual[index] if index < len(actual) else None
        e = expected[index] if index < len(expected) else None
        # Exact JSON types matter: Python True == 1 must not bypass binding.
        if encode([a]) != encode([e]):
            code = "FOUR_LANE_COVERAGE" if e and e.get("lane") == 3 and (a is None or a.get("frame") != e.get("frame") or a.get("lane") != 3) else "CALENDAR_FIRST_DIFFERENCE"
            raise Rejected(code, index, e, a)
    return {"status":"FIXTURE_CALENDAR_PASS", "scope":expected[0]["scope"],
            "records":len(actual), "frames":sum(x["kind"]=="FRAME" for x in actual),
            "lane_ticks":sum(x["kind"]=="LANE_TICK" for x in actual),
            "accepted":sum(x["kind"]=="ACCEPT" for x in actual),
            "cancelled":sum(x["kind"]=="CANCEL" for x in actual),
            "published":sum(x["kind"]=="PUBLISH" for x in actual),
            "consumed":sum(x["kind"]=="CONSUME" for x in actual),
            "pro_dut":"PENDING_PRO_SOURCE_OR_TRACE", "board_release_allowed":False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--actual", type=Path, required=True)
    args = p.parse_args()
    try:
        result = check(strict_load(args.plan.read_text(encoding="utf-8")),
                       [strict_load(x) for x in args.actual.read_text(encoding="utf-8").splitlines()])
    except Rejected as exc:
        print(json.dumps(exc.detail, sort_keys=True))
        return 2
    except (ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status":"REJECTED", "code":"INPUT_STRUCTURE", "error":str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
