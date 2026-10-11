"""T060 capture2-only diagnostic closure; never grants full audio acceptance."""
import argparse
import base64
from collections import deque
import gzip
import hashlib
import json
from pathlib import Path

from strict_capture import CaptureError, compare_pair, parse_f, parse_jsonl, require

ROOT = Path(__file__).resolve().parents[3]
DOC = ROOT / "code/docs/hardware/audio_math_acceptance_v1"
TB = "code/tb/board/m3_midi_pcm_acceptance/tb_midi_pcm.sv"
FIFO = ("code/rtl/138K_try/clock_trials_20261005/"
        "H_pll_core40_route2/sources/performance_event_fifo.sv")
CAPTURE_SHA = {
    "audio_observation.jsonl": "d17cf87952ac0c663e681e0b47051e9412af4a2979fb509aaa5d7114d5b32cc5",
    "midi_pcm.capture": "bd0035de464cb8c757c7e29a132073181e9e8179aa8303ab1ec110c6990042d6",
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(path):
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": sha(raw)}


def scan(rows):
    """Replay accepted FIFO transactions with pre-NBA count, not post-edge count.

    E precedes K inside the original capture process. Group P/E for atomic FIFO
    update, but retain the exact E/K order for last_frame_cycle. R clears FIFO
    and frame history, NOT the TB's cumulative diagnostic counters.
    """
    groups = []
    for row in rows:
        if row["tag"] == "END":
            continue
        if not groups or groups[-1][0] != row["cycle"]:
            groups.append((row["cycle"], []))
        groups[-1][1].append(row)
    queue = deque()
    full, edge, peak, reset_discarded, pushes, pops = 0, 0, 0, 0, 0, 0
    last_frame, previous_q = 0, None
    full_edges, edge_edges, panic, overlaps, fixture = [], [], [], [], []
    window = False
    for cycle, group in groups:
        tags = [r["tag"] for r in group]
        if "R" in tags:
            require(tags.count("R") == 1 and not any(t in tags for t in ("P", "E", "K")),
                    "CLOSURE_RESET_TRANSACTION")
            reset_discarded += len(queue)
            queue.clear()
            last_frame, previous_q, window = 0, None, False
            continue
        accepted_push = [r for r in group if r["tag"] == "P"]
        accepted_pop = [r for r in group if r["tag"] == "E"]
        require(len(accepted_push) <= 1 and len(accepted_pop) <= 1,
                "CLOSURE_FIFO_MULTIPLE_HANDSHAKES")
        if len(queue) == 32 and accepted_push and accepted_pop:
            full += 1
            full_edges.append(cycle)
        if accepted_pop:
            require(bool(queue), "CLOSURE_FIFO_EMPTY_POP")
            require(queue.popleft() == accepted_pop[0]["values"][0],
                    "CLOSURE_FIFO_PAYLOAD_ORDER")
            pops += 1
        if accepted_push:
            queue.append(accepted_push[0]["values"][0])
            pushes += 1
        require(len(queue) <= 32, "CLOSURE_FIFO_OVERFLOW")
        peak = max(peak, len(queue))
        require(not ("E" in tags and "K" in tags) or tags.index("E") < tags.index("K"),
                "CLOSURE_E_K_OBSERVER_ORDER")
        for row in group:
            tag, values = row["tag"], row["values"]
            if tag == "E":
                if cycle - last_frame < 64:
                    edge += 1
                    edge_edges.append(cycle)
                if values[0] >> 61 == 5:
                    panic.append({"epoch": row["epoch"], "cycle": cycle})
            elif tag == "K":
                # This is a coverage screen, not a generalized bank FSM.
                if previous_q is not None and previous_q < cycle <= previous_q + 20:
                    overlaps.append({"epoch": row["epoch"], "cycle": cycle,
                                     "q_cycle": previous_q})
                last_frame = cycle
            elif tag == "Q":
                previous_q = cycle
            elif tag == "T":
                if values[0] == "sample_edge":
                    window = True
                elif values[0] == "accepted_only":
                    window = False
            elif tag == "M" and window:
                fixture.append({"epoch": row["epoch"], "cycle": cycle,
                                "request_id": values[0], "observed_flag": values[3],
                                "independently_expected_flag": None})
    return dict(full_pop_push=full, edge_events=edge, peak_fifo_level=peak,
                accepted_pushes=pushes, accepted_pops=pops,
                remaining_fifo_entries=len(queue), reset_discarded_entries=reset_discarded,
                full_pop_push_cycles=full_edges, edge_event_cycles=edge_edges,
                accepted_panic_events=panic, observed_q_math_frame_overlaps=overlaps,
                fixture_transition_commits=fixture)


def check(jtext, ftext):
    j, f = parse_jsonl(jtext), parse_f(ftext)
    transport = compare_pair(j, f, observer_counter=True)
    stats = scan(f["rows"])
    require(stats["full_pop_push"] == f["end"][2], "CLOSURE_END_FULL_POP_PUSH")
    require(stats["edge_events"] == f["end"][4], "CLOSURE_END_EDGE_EVENTS")
    return dict(status="T060_TWO_COUNTERS_MATCH_PARTIAL", t060_complete=False,
                checks_newly_recomputed=["full_pop_push", "edge_events"],
                end_values=f["end"], capture_statistics=stats,
                transport_only=transport, new_pcm_math_replay=False,
                remaining_end_counters=["control_stalls", "center_samples", "checks"])


def historical_reference():
    """Verify original carrier and bound receipt; reuse, never retest/relabel it."""
    manifest_path = DOC / "ROUTER_EVIDENCE_MANIFEST_20261010.json"
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    carrier_path = DOC / m["carrier"]
    carrier = carrier_path.read_bytes()
    require(identity(carrier_path) == {"bytes": m["carrier_bytes"],
                                      "sha256": m["carrier_sha256"]}, "CLOSURE_OLD_CARRIER")
    container = gzip.decompress(base64.b64decode(carrier, validate=False))
    require(len(container) == m["container_bytes"] and sha(container) == m["container_sha256"],
            "CLOSURE_OLD_CONTAINER")
    members = json.loads(container)
    name = "code/output/m3_audio_router_final_20261010_01/router/receipt.json"
    entry = members[name]
    raw = base64.b64decode(entry["raw_base64"], validate=True)
    expected = m["archived_raw_files"][name]
    require(len(raw) == expected["bytes"] and sha(raw) == expected["sha256"],
            "CLOSURE_OLD_RECEIPT")
    receipt = json.loads(raw)
    positive = receipt["positive"]
    require(type(positive["exit_code"]) is int and positive["exit_code"] == 0,
            "CLOSURE_OLD_POSITIVE")
    require(positive["result"]["router"]["status"] == "ROUTER_REFERENCE_MATCH",
            "CLOSURE_OLD_ROUTER")
    return {"receipt_member": name, **expected, "reused_not_reexecuted": True,
            "result": positive["result"]}


def anchor(path, needle):
    text = path.read_text(encoding="utf-8")
    require(text.count(needle) == 1, "CLOSURE_SOURCE_ANCHOR:" + needle)
    line = text[:text.index(needle)].count("\n") + 1
    return {"path": path.relative_to(ROOT).as_posix(), "line": line,
            "anchor": needle, **identity(path)}


def audit(bundle):
    original = bundle / "original_Golden"
    inputs = {}
    for name, digest in CAPTURE_SHA.items():
        path = original / name
        require(identity(path)["sha256"] == digest, "CLOSURE_CAPTURE_IDENTITY:" + name)
        inputs[str(path.resolve())] = identity(path)
    result = check((original / "audio_observation.jsonl").read_text(encoding="utf-8"),
                   (original / "midi_pcm.capture").read_text(encoding="utf-8"))
    old = historical_reference()
    m = json.loads((DOC / "ROUTER_EVIDENCE_MANIFEST_20261010.json").read_text(encoding="utf-8"))
    for rel in (TB, FIFO):
        recorded = next(i for i in m["frozen_inputs"]
                        if i["path"].replace("\\", "/").endswith("/" + rel))
        require(sha((ROOT / rel).read_bytes().replace(b"\r\n", b"\n")) == recorded["git_blob_sha256"],
                "CLOSURE_FROZEN_SOURCE:" + rel)
    result.update(original_inputs=inputs, historical_router=old,
                  source_anchors=[anchor(ROOT / TB, s) for s in (
                      "full_pop_push++;", "if(cycle-last_frame_cycle<64)edge_events++;",
                      "control_stalls++;", "center_samples++;", "checks++;",
                      "fixture_select=0;mark(\"fifo_pressure\");")],
                  fifo_source=anchor(ROOT / FIFO, "next_count = count + push - pop;"),
                  oracle_limit_anchors=[anchor(Path(__file__).parent / "router_model.py", s)
                                        for s in ("self.counts[\"retirements\"] += 1",
                                                  "ROUTER_OVERLAPPING_FRAME_MATH_UNCOVERED")],
                  gaps=[
                      {"id": "REAL_RETIREMENT_PANIC", "status": "NOT_COVERED_BY_ORIGINAL_CAPTURE",
                       "need": "M2 decide exclusion or a source-pinned accepted panic/release-to-Idle/reallocation capture; no reset-as-retirement"},
                      {"id": "FRAME_MATH_OVERLAP", "status": "UNSUPPORTED_BY_CURRENT_ORACLE",
                       "need": "M2 define required overlap/cancel contract before minimal additional capture; observed Q-window screen is not full FSM proof"},
                      {"id": "CONTROL_STALLS", "status": "UNOBSERVABLE_FROM_ACCEPTED_E_ONLY",
                       "need": "Continuous FIFO valid/ready/head type+control_id, including unaccepted cycles and resets"},
                      {"id": "CENTER_SAMPLES", "status": "UNOBSERVABLE_ENABLE",
                       "need": "Exact center_compare transition log tied to H handshake; scenario marker is not an enable edge"},
                      {"id": "CHECKS", "status": "UNOBSERVABLE_TASK_INVOCATIONS",
                       "need": "M2 exclude TB self-check count or supply check-call occurrence log; sparse audio events do not encode every call"},
                      {"id": "FIXTURE_SELECT", "status": "TWO_ORIGINAL_FLAGS_NOT_INDEPENDENTLY_DERIVED",
                       "need": "Exact fixture_select transition edges and scheduling region, or M2 exclude flags from mathematical acceptance"}],
                  validation="L0 source audit / L1 software; no new RTL or PCM mathematical result",
                  new_rtl_simulation=False, new_gowin_run=False)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("check", "audit"))
    parser.add_argument("--jsonl", type=Path)
    parser.add_argument("--f-capture", type=Path)
    parser.add_argument("--bundle-root", type=Path)
    args = parser.parse_args()
    try:
        if args.mode == "audit":
            require(args.bundle_root is not None, "CLOSURE_BUNDLE_REQUIRED")
            result = audit(args.bundle_root.resolve())
        else:
            require(args.jsonl is not None and args.f_capture is not None,
                    "CLOSURE_PAIR_REQUIRED")
            result = check(args.jsonl.read_text(encoding="utf-8"),
                           args.f_capture.read_text(encoding="utf-8"))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except CaptureError as error:
        print(json.dumps({"status": "REJECTED_CLOSURE", "diagnostic": str(error)}))
        return 1
    except (OSError, ValueError, KeyError, StopIteration) as error:
        print(json.dumps({"status": "INFRASTRUCTURE_FAILURE", "error": str(error)}))
        return 7


if __name__ == "__main__":
    raise SystemExit(main())
