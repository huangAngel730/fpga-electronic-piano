"""Pure-software positive and designated-negative tests for N32-C v2."""

from __future__ import annotations

import copy
import json

from check_capture import check_records
from generate_plan import StressOracle, generate
from n32c_common import (
    ContractError,
    MUTATION_DIAGNOSTICS,
    public_slot_digest,
    public_slots,
    records_sha256,
)


def bind_selftest_math(expected):
    bound = copy.deepcopy(expected)
    bound[0].update({
        "audio_math_status": "SELFTEST_FIXTURE_ONLY",
        "executable_for_rtl_acceptance": False,
        "b_review_key": "SELFTEST-NOT-B",
        "b_fingerprint": "0" * 64,
    })
    directed = (
        (0, 1, False),
        ((1 << 23) - 1, -(1 << 23), True),
        (-1, (1 << 23) - 2, False),
        (-765432, 17, True),
        (123456, -654321, False),
    )
    for row in bound[1:-1]:
        if row["record"] == "READ":
            row["context"] = ((row["read_serial"] * 65537 + row["slot"])
                              & ((1 << 74) - 1))
            row["context_provenance"] = "SELFTEST_FIXTURE_ONLY"
        elif row["record"] == "TXN" and row["disposition"] == "PUBLISH":
            left, right, clipped = directed[row["accept_serial"] % len(directed)]
            row.update(left_pcm=left, right_pcm=right, clipped=clipped,
                       pcm_provenance="SELFTEST_FIXTURE_ONLY")
    bound[-1]["body_sha256"] = records_sha256(bound[:-1])
    return bound


def _blank_cycle(edge, plan_index, oracle, ready_state, outstanding):
    slots = public_slots(oracle.slots)
    return {
        "record": "CYCLE", "edge": edge, "plan_index": plan_index,
        "reset_lifetime": oracle.reset_lifetime, "rst_n": True,
        "cancel": False, "event_valid": False, "event_ready": True,
        "event_word": 0, "sample_valid": False,
        "sample_ready": True, "sample_id": 0, "result_valid": False,
        "result_ready": ready_state, "result_id": 0, "left_pcm": 0,
        "right_pcm": 0, "clipped": False, "read_valid": False,
        "read_ready": True, "read_slot": 0, "read_out_valid": False,
        "read_context": 0, "audio_state": 0, "router_state": 0,
        "publish": False,
        "control_snapshot_valid": False,
        "control_snapshot_ready": False, "control_snapshot_id": 0,
        "control_snapshot_value": 0, "control_snapshot_occupied": 0,
        "control_snapshot_sources": 0, "control_snapshot_channels": 0,
        "control_snapshot_generations": 0,
        "control_release_valid": False, "control_release_ready": False,
        "control_release_mask": 0, "control_release_generations": 0,
        "backend_release_done_valid": False,
        "backend_release_done_ready": True,
        "backend_release_done_slot": 0,
        "backend_release_done_generation": 0,
        "backend_release_done_mask": 0,
        "aborted": False, "abort_reason": 0,
        "idle": not outstanding, "fault": False, "slots": slots,
        "slot_digest": public_slot_digest(slots),
    }


def capture_from_expected(plan, expected):
    operations = plan[1:-1]
    txns = [row for row in expected[1:-1] if row["record"] == "TXN"]
    reads = [row for row in expected[1:-1] if row["record"] == "READ"]
    txn_by_plan = {row["plan_index"]: row for row in txns}
    read_by_plan = {row["plan_index"]: row for row in reads}
    oracle = StressOracle()
    outstanding = []
    pending_reads = []
    pending_snapshots = []
    cycles = []
    ready_state = True

    def emit(plan_index, op=None, *, drive_event=True, router_state=0,
             observe_release=False, release_batch=None):
        nonlocal ready_state
        row = _blank_cycle(len(cycles), plan_index, oracle,
                           ready_state, outstanding)
        row["router_state"] = router_state
        if router_state != 0:
            row["event_ready"] = False
        if pending_snapshots:
            snapshot_id = pending_snapshots.pop(0)
            row.update(control_snapshot_valid=True,
                       control_snapshot_ready=True,
                       control_snapshot_id=snapshot_id)
        if release_batch is not None:
            mask, generations = release_batch
            row.update(control_release_valid=True,
                       control_release_ready=True,
                       control_release_mask=mask,
                       control_release_generations=generations)
        if op is not None and op["op"] == "set_result_ready":
            ready_state = bool(op["value"])
            row["result_ready"] = ready_state

        publish = [txn for txn in outstanding
                   if txn["disposition"] == "PUBLISH"]
        if publish:
            txn = publish[0]
            row.update(result_valid=True, result_id=txn["result_id"],
                       left_pcm=txn["left_pcm"], right_pcm=txn["right_pcm"],
                       clipped=txn["clipped"], publish=ready_state)
            if ready_state:
                outstanding.remove(txn)

        if pending_reads:
            read = pending_reads.pop(0)
            row.update(read_out_valid=True, read_context=read["context"])

        if observe_release and op is not None:
            lane = op["slot"]
            slot = oracle.slots[lane]
            row.update(
                backend_release_done_valid=True,
                backend_release_done_slot=lane,
                backend_release_done_generation=slot.generation,
                backend_release_done_mask=1 << lane,
            )

        if op is not None:
            name = op["op"]
            if name in {"note_on", "note_off", "cc64", "control_event"}:
                event = next(item for item in expected[1:-1]
                             if item.get("record") == "EVENT"
                             and item["plan_index"] == plan_index)
                row.update(event_valid=drive_event,
                           event_word=event["event_word"] if drive_event else 0)
            elif name == "sample":
                row.update(sample_valid=True, sample_id=op["result_id"],
                           event_ready=False, read_ready=False)
            elif name == "read":
                row.update(read_valid=True, read_slot=op["slot"],
                           event_ready=False, sample_ready=False)
            elif name == "cancel":
                victims = [txn for txn in outstanding
                           if txn["disposition"] == "CANCEL"]
                row.update(cancel=True, aborted=bool(victims),
                           abort_reason=1 if victims else 0,
                           event_ready=False, sample_ready=False,
                           read_ready=False)
            elif name == "reset":
                row.update(rst_n=False, aborted=False, abort_reason=0,
                           event_ready=False, sample_ready=False,
                           read_ready=False)
        cycles.append(row)

        if op is None:
            return
        name = op["op"]
        if name == "sample":
            outstanding.append(txn_by_plan[plan_index])
            pending_snapshots.append(op["result_id"])
        elif name == "read":
            pending_reads.append(read_by_plan[plan_index])
        elif name in {"cancel", "reset"}:
            outstanding[:] = [txn for txn in outstanding
                              if txn["disposition"] != "CANCEL"]
        if name not in {"note_on", "note_off", "cc64", "control_event",
                        "await_release_done", "reset"}:
            oracle.apply(plan_index, op)

    for plan_index, op in enumerate(operations):
        if op["op"] in {"note_on", "note_off", "cc64", "control_event"}:
            emit(plan_index, op, drive_event=True, router_state=0)
            emit(plan_index, op, drive_event=False, router_state=1)
            release_batch = None
            if op["op"] == "cc64" and not op["down"]:
                mask = 0
                generations = 0
                for lane, slot in enumerate(oracle.slots):
                    if (slot.occupied and slot.deferred
                            and slot.source == op["source"]
                            and slot.channel == op["channel"]):
                        mask |= 1 << lane
                        generations |= slot.generation << (32 * lane)
                if mask:
                    release_batch = mask, generations
            oracle.apply(plan_index, op)
            emit(plan_index, op, drive_event=False, router_state=0,
                 release_batch=release_batch)
        elif op["op"] == "await_release_done":
            emit(plan_index, op, observe_release=True, router_state=0)
            emit(plan_index, op, router_state=11)
            oracle.apply(plan_index, op)
            emit(plan_index, op, router_state=0)
        elif op["op"] == "reset":
            oracle.apply(plan_index, op)
            emit(plan_index, op)
            cycles[-1].update(rst_n=False, reset_lifetime=oracle.reset_lifetime,
                              aborted=False, abort_reason=0)
        elif op["op"] == "wait_idle":
            # The real B cancel path enters DRAIN.  Keep the wait operation
            # selected until a later edge actually reports idle.
            while outstanding or pending_reads:
                emit(plan_index, op)
            emit(plan_index, op)
        else:
            emit(plan_index, op)
    while outstanding or pending_reads or pending_snapshots:
        emit(-1)
    emit(-1)

    meta = expected[0]
    capture = [{
        "record": "META", "schema": "t061-n32c-capture-v3",
        "origin": "SELFTEST_FIXTURE_ONLY",
        "plan_sha256": records_sha256(plan),
        "expected_sha256": records_sha256(expected),
        "b_review_key": meta["b_review_key"],
        "b_fingerprint": meta["b_fingerprint"],
        "sampling_phase": "PRE_NBA_PUBLIC_PORTS",
    }, *cycles]
    capture.append(_end_record(capture))
    return capture


def _end_record(capture):
    cycles = capture[1:]
    return {
        "record": "END", "last_edge": len(cycles) - 1,
        "cycles": len(cycles),
        "event_accepts": sum(row.get("event_valid") and row.get("event_ready")
                             for row in cycles),
        "sample_accepts": sum(row.get("sample_valid") and row.get("sample_ready")
                              for row in cycles),
        "results": sum(row.get("result_valid") and row.get("result_ready")
                       for row in cycles),
        "hold_cycles": sum(row.get("result_valid")
                           and not row.get("result_ready") for row in cycles),
        "read_requests": sum(row.get("read_valid") and row.get("read_ready")
                             for row in cycles),
        "read_responses": sum(bool(row.get("read_out_valid")) for row in cycles),
        "cancels": sum(bool(row.get("cancel")) for row in cycles),
        "resets": sum(row.get("rst_n") is False for row in cycles),
        "release_done": sum(bool(row.get("backend_release_done_valid"))
                            for row in cycles),
        "control_snapshots": sum(row.get("control_snapshot_valid")
                                 and row.get("control_snapshot_ready")
                                 for row in cycles),
        "control_releases": sum(row.get("control_release_valid")
                                and row.get("control_release_ready")
                                for row in cycles),
        "body_sha256": records_sha256(capture),
    }


def reseal(capture):
    capture[-1] = _end_record(capture[:-1])


def mutate(base, expected, mutation):
    changed = copy.deepcopy(base)
    cycles = changed[1:-1]
    results = [row for row in cycles if row.get("result_valid")
               and row.get("result_ready")]
    holds = [row for row in cycles if row.get("result_valid")
             and not row.get("result_ready")]
    samples = [row for row in cycles if row.get("sample_valid")]
    read_outputs = [row for row in cycles if row.get("read_out_valid")]
    event_cycles = [row for row in cycles if row.get("event_valid")]
    final = cycles[-1]
    if mutation == "DROP_TRANSACTION":
        results[0].update(result_valid=False, result_id=0, left_pcm=0,
                          right_pcm=0, clipped=False, publish=False)
    elif mutation == "DUPLICATE_TRANSACTION":
        source = results[0]
        final.update(result_valid=True, result_ready=True,
                     result_id=source["result_id"], left_pcm=source["left_pcm"],
                     right_pcm=source["right_pcm"], clipped=source["clipped"],
                     publish=True)
    elif mutation == "WRONG_SLOT_IDENTITY":
        victim = cycles[event_cycles[0]["edge"] + 2]
        victim["slots"][0]["source"] ^= 1
        victim["slot_digest"] = public_slot_digest(victim["slots"])
    elif mutation == "WRONG_STEAL_VICTIM":
        steal_plan = next(row["plan_index"] for row in expected[1:-1]
                          if row.get("record") == "EVENT"
                          and row["source"] == 3 and row["channel"] == 15
                          and row["note"] == 100)
        steal_event = next(row for row in event_cycles
                           if row["plan_index"] == steal_plan)
        victim = cycles[steal_event["edge"] + 2]
        victim["slots"][0], victim["slots"][1] = (
            victim["slots"][1], victim["slots"][0])
        victim["slot_digest"] = public_slot_digest(victim["slots"])
    elif mutation == "WRONG_RESULT_ID":
        results[0]["result_id"] ^= 1
    elif mutation == "PCM_LEFT_RIGHT_SWAP":
        results[0]["left_pcm"], results[0]["right_pcm"] = (
            results[0]["right_pcm"], results[0]["left_pcm"])
    elif mutation == "PCM_WRONG_BEAT":
        results[0]["left_pcm"] = results[1]["left_pcm"]
        results[0]["right_pcm"] = results[1]["right_pcm"]
    elif mutation == "CLIPPED_MISSING":
        del results[0]["clipped"]
    elif mutation == "CLIPPED_WRONG_BEAT":
        donor = next(row for row in results
                     if row["clipped"] != results[0]["clipped"])
        results[0]["clipped"] = donor["clipped"]
    elif mutation == "CLIPPED_FULLSCALE_DERIVED":
        victim = next(row for row in results if row["clipped"]
                      and abs(row["left_pcm"]) != (1 << 23) - 1
                      and abs(row["right_pcm"]) != (1 << 23) - 1)
        victim["clipped"] = (abs(victim["left_pcm"]) == (1 << 23) - 1
                             or abs(victim["right_pcm"]) == (1 << 23) - 1)
    elif mutation == "DROP_REQUIRED_HOLD":
        holds[len(holds) // 2].update(result_valid=False, result_id=0,
                                      left_pcm=0, right_pcm=0, clipped=False)
    elif mutation == "HOLD_PAYLOAD_UNSTABLE":
        holds[1]["left_pcm"] ^= 1
    elif mutation == "WRONG_READ_CONTEXT":
        read_outputs[0]["read_context"] ^= 1
    elif mutation == "READ_OUTSIDE_REQUEST":
        source = read_outputs[0]
        final.update(read_out_valid=True,
                     read_context=source["read_context"])
    elif mutation == "SAME_EDGE_READ_RESPONSE":
        request = next(row for row in cycles if row.get("read_valid")
                       and row.get("read_ready"))
        response = cycles[request["edge"] + 1]
        request.update(read_out_valid=True,
                       read_context=response["read_context"])
        response.update(read_out_valid=False, read_context=0)
    elif mutation == "RESULT_BEFORE_ACCEPT":
        txn = next(row for row in expected[1:-1]
                   if row.get("record") == "TXN"
                   and row["disposition"] == "PUBLISH")
        victim = cycles[samples[0]["edge"] - 1]
        victim.update(result_valid=True, result_ready=True,
                      result_id=txn["result_id"], left_pcm=txn["left_pcm"],
                      right_pcm=txn["right_pcm"], clipped=txn["clipped"],
                      publish=True)
    elif mutation == "DROP_ACCEPT":
        samples[0]["sample_ready"] = False
    elif mutation == "DUPLICATE_ACCEPT":
        final.update(sample_valid=True, sample_ready=True,
                     sample_id=samples[0]["sample_id"],
                     event_ready=False, read_ready=False)
    elif mutation == "CANCEL_NOT_DRIVEN":
        cancel = next(row for row in cycles if row.get("cancel"))
        cancel.update(cancel=False, aborted=False, abort_reason=0)
    elif mutation in {"STALE_AFTER_CANCEL", "STALE_AFTER_RESET"}:
        cancelled = [row for row in expected[1:-1]
                     if row.get("record") == "TXN"
                     and row["disposition"] == "CANCEL"][
                         0 if mutation == "STALE_AFTER_CANCEL" else 1]
        final.update(result_valid=True, result_ready=True,
                     result_id=cancelled["result_id"], left_pcm=0,
                     right_pcm=0, clipped=False, publish=True)
    else:
        raise AssertionError(mutation)
    reseal(changed)
    return changed


def expect_reject(plan, expected, capture, diagnostic, expected_prefix):
    try:
        check_records(plan, expected, capture, allow_selftest_fixture=True)
    except ContractError as exc:
        if not str(exc).startswith(expected_prefix):
            raise AssertionError(
                f"wrong diagnostic:{diagnostic}:{exc};"
                f" expected {expected_prefix}") from exc
        return
    raise AssertionError(f"accepted mutant:{diagnostic}")


def main() -> int:
    plan, skeleton = generate()
    try:
        check_records(plan, skeleton, [], allow_selftest_fixture=False)
    except ContractError:
        pass
    else:
        raise AssertionError("unbound skeleton accepted")

    expected = bind_selftest_math(skeleton)
    capture = capture_from_expected(plan, expected)
    result = check_records(plan, expected, capture,
                           allow_selftest_fixture=True)
    for mutation, expected_prefix in MUTATION_DIAGNOSTICS.items():
        expect_reject(plan, expected,
                      mutate(capture, expected, mutation), mutation,
                      expected_prefix)

    summary = {
        "status": "PASS_SOFTWARE_ONLY", "operations": len(plan) - 2,
        "mutations_rejected": len(MUTATION_DIAGNOSTICS),
        **{f"checked_{name.lower()}": True
           for name in MUTATION_DIAGNOSTICS},
        "positive": result, "rtl": "NOT_RUN_WAIT_B",
        "gowin": "NOT_RUN_PROHIBITED",
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
