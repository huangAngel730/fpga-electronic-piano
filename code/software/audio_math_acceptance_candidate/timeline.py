"""capture2-only accepted-input DDS replay; never a full PCM golden.

STATE's printed counter races with observation_cycle++ in another active
process. A unique (epoch, request_id) D token identifies the logical tick edge;
only counter-old or counter-new labels are classified. Raw rows stay intact.
This classification is reported separately for M2 review, not signed as A1.
Q occupancy/slot routing are observed INPUTS to the DDS/PitchMod boundary;
allocator/release/CC64 correctness belongs to the subsequent A2/router work.
"""
from collections import Counter, defaultdict, deque

from dds_model import MASK32, PianoDDS, note_fcw, pitch_mod, signed
from strict_capture import compare_pair, require


def lane_word(packed, lane, width):
    return (packed >> (lane * width)) & ((1 << width) - 1)


def pack(values, width):
    return sum((value & ((1 << width) - 1)) << (i * width)
               for i, value in enumerate(values))


def event_fields(word):
    return {"type": (word >> 61) & 7, "source": (word >> 57) & 15,
            "channel": (word >> 53) & 15, "note": (word >> 46) & 127,
            "velocity": (word >> 36) & 1023, "control": (word >> 18) & 255,
            "value": (word >> 6) & 4095}


def replay(json_capture, f_capture, roms):
    """Check independently derived FCW/phase/table, including terminal STATE.

    E is the accepted event, not queued U/P. N supplies the allocation lane;
    E supplies note/velocity/identity. No observed F/D/STATE FCW is an oracle.
    RESET discards in-flight requests and resets LFO/DDS/controls/slot history.
    """
    transport = compare_pair(json_capture, f_capture, observer_counter=True)
    tick_states, on_states, off_states = defaultdict(list), [], []
    for state in json_capture["rows"]:
        if state["tag"] != "STATE":
            continue
        if state["tick"]:
            tick_states[state["epoch"], state["pending_request_id"]].append(state)
        elif state["note_on"]:
            on_states.append(state)
        else:
            off_states.append(state)
    lanes = [PianoDDS() for _ in range(4)]
    base, lfo, slots = [0] * 4, [0] * 4, [None] * 4
    controls, requests, note_queue = {}, {}, deque()
    counts, stage_delays = Counter(), defaultdict(Counter)
    used, event_history = set(), []
    fixture_transition_window = False

    def check_state(state, fcw, slot):
        key = state["epoch"], state["cycle"], state["lane"]
        require(key not in used, "TIMELINE_DUPLICATE_STATE")
        used.add(key)
        if slot is not None:
            for name in ("source", "channel", "note", "velocity", "generation"):
                require(state[name] == slot[name], f"STATE_EVENT_IDENTITY:{name}:{key}")
        else:
            require(all(state[name] == 0 for name in
                        ("source", "channel", "note", "velocity", "generation")),
                    f"STATE_RESET_SLOT:{key}")
        actual = int(state["dds_fcw"], 16)
        require(actual == fcw, f"DDS_FCW:{key}:expected={fcw:08x}:actual={actual:08x}")
        velocity = slot["velocity"] if slot else 0
        before = lanes[state["lane"]].edge(fcw, velocity, bool(state["tick"]), bool(state["note_on"]))
        for name in ("phase_acc", "table"):
            actual = int(state[name], 16) if name == "phase_acc" else state[name]
            require(actual == before[name], f"DDS_{name}:{key}:expected={before[name]}:actual={actual}")
        counts["state_rows"] += 1
        counts["fcw_comparisons"] += 1
        counts["phase_comparisons"] += 1
        counts["table_comparisons"] += 1

    # Off-only observations do not clock DDS or its table window. Their order
    # relative to N/D is recovered from the observer's adjacent counter labels.
    # No off-only STATE in this frozen capture shares an N/D ambiguity window.
    off_by_epoch = defaultdict(list)
    for state in off_states:
        off_by_epoch[state["epoch"]].append(state)
    for row in f_capture["rows"]:
        tag = row["tag"]
        if tag == "END":
            continue
        epoch, cycle, values = row["epoch"], row["cycle"], row["values"]
        if tag in ("N", "D", "R"):
            for state in off_by_epoch[epoch]:
                key = state["epoch"], state["cycle"], state["lane"]
                if key not in used and state["cycle"] + 1 < cycle:
                    check_state(state, base[state["lane"]], slots[state["lane"]])
                elif key not in used and state["cycle"] <= cycle <= state["cycle"] + 1:
                    require(False, f"OFF_STATE_EDGE_AMBIGUOUS:{key}")
        if tag == "R":
            require(not note_queue, "RESET_UNMATCHED_ACCEPTED_NOTE")
            counts["reset_cancelled_requests"] += len(requests)
            requests.clear()
            controls.clear()
            base, lfo, slots = [0] * 4, [0] * 4, [None] * 4
            for lane in lanes:
                lane.reset()
            counts["resets"] += 1
            fixture_transition_window = False
        elif tag == "T":
            if values[0] == "sample_edge":
                fixture_transition_window = True
            elif values[0] == "accepted_only":
                fixture_transition_window = False
        elif tag == "E":
            event = event_fields(values[0])
            event_history.append((epoch, cycle))
            identity = event["source"], event["channel"]
            word = list(controls.get(identity, (0, 0, 2)))
            if event["type"] == 3 and event["control"] == 0:
                word[0] = signed(event["value"], 12)
            elif event["type"] == 4 and event["control"] == 1:
                word[1] = event["value"]
            elif event["type"] == 4 and event["control"] == 4 and event["value"] <= 24:
                word[2] = event["value"]
            controls[identity] = tuple(word)
            if event["type"] == 0 and event["velocity"]:
                note_queue.append((epoch, cycle, event))
            counts["accepted_events"] += 1
        elif tag == "N":
            mask = values[0]
            require(mask in (1, 2, 4, 8), "NOTE_ON_NOT_SINGLE_LANE")
            lane = mask.bit_length() - 1
            require(bool(note_queue), "NOTE_ON_WITHOUT_ACCEPTED_EVENT")
            event_epoch, event_cycle, event = note_queue.popleft()
            require(event_epoch == epoch and event_cycle < cycle, "NOTE_EVENT_ORDER")
            generation = ((slots[lane]["generation"] if slots[lane] else 0) + 1) & MASK32
            slots[lane] = {name: event[name] for name in ("source", "channel", "note", "velocity")}
            slots[lane]["generation"] = generation
            base[lane] = note_fcw(event["note"])
            matching = [state for state in on_states if state["epoch"] == epoch and state["lane"] == lane
                        and cycle - state["cycle"] in (0, 1)]
            require(len(matching) == 1, "NOTE_ON_STATE_BINDING")
            require(not matching[0]["tick"], "NOTE_ON_TICK_OVERLAP_UNCOVERED")
            check_state(matching[0], base[lane], slots[lane])
            lfo[lane] = 0
            counts["note_on"] += 1
        elif tag == "Q":
            req, occupied, sources, channels, generations, observed_base, notes = values
            key = epoch, req
            require(key not in requests, "DUPLICATE_Q_TOKEN")
            for lane in range(4):
                require(lane_word(observed_base, lane, 32) == base[lane], f"Q_BASE_FCW:{key}:{lane}")
                slot = slots[lane]
                for observed, width, name in ((sources, 4, "source"), (channels, 4, "channel"),
                                              (generations, 32, "generation"), (notes, 8, "note")):
                    require(lane_word(observed, lane, width) == (slot[name] if slot else 0),
                            f"Q_EVENT_IDENTITY:{name}:{key}:{lane}")
            control = [controls.get((lane_word(sources, i, 4), lane_word(channels, i, 4)), (0, 0, 2))
                       if occupied & (1 << i) else (0, 0, 2) for i in range(4)]
            requests[key] = {"Q": cycle, "base": list(base), "control": control,
                             "identity": [occupied, sources, channels, generations], "stage": "Q"}
            counts["q_base_lane_comparisons"] += 4
        elif tag in ("S", "C", "F", "D", "H", "M"):
            key = epoch, values[0]
            require(key in requests, f"ORPHAN_STAGE:{tag}:{key}")
            token = requests[key]
            previous = {"S": "Q", "C": "S", "F": "C", "D": "F", "H": "D", "M": "H"}[tag]
            require(token["stage"] == previous, f"STAGE_ORDER:{tag}:{key}")
            delay = cycle - token[previous]
            expected_delay = {"S": 5, "C": 0, "F": 8, "D": 1, "H": 6, "M": 1}[tag]
            require(delay == expected_delay, f"STAGE_DELAY:{tag}:{key}:{delay}")
            stage_delays[tag][str(delay)] += 1
            token[tag], token["stage"] = cycle, tag
            if tag == "S":
                require(not any(e == epoch and token["Q"] < c <= token["Q"] + 4
                                for e, c in event_history), "EVENT_DURING_ATOMIC_CONTROL_READ")
                expected = [pack([c[i] for c in token["control"]], w)
                            for i, w in enumerate((12, 12, 5))]
                require(values[1:] == expected, f"CONTROL_SNAPSHOT:{key}")
                counts["control_lane_comparisons"] += 4
            elif tag == "C":
                occupied = token["identity"][0]
                computed = []
                for lane in range(4):
                    if occupied & (1 << lane):
                        computed.append(pitch_mod(token["base"][lane], *token["control"][lane], lfo[lane], *roms))
                        lfo[lane] = (lfo[lane] + 447392) & MASK32
                        counts["occupied_lfo_launches"] += 1
                    else:
                        computed.append(0)
                token["computed"] = computed
            elif tag == "F":
                require(values[1:5] == token["identity"], f"FCW_RESULT_IDENTITY:{key}")
                require(values[5] == pack(token["computed"], 32), f"PITCH_MOD_FCW:{key}")
                counts["pitch_fcw_lane_comparisons"] += 4
            elif tag == "D":
                computed = [token["computed"][i] if token["identity"][0] & (1 << i)
                            else token["base"][i] for i in range(4)]
                require(values[1] == pack(computed, 32), f"D_COMPUTED_FCW:{key}")
                group = tick_states[key]
                require(len(group) == 4, f"D_STATE_GROUP:{key}")
                for state in group:
                    lane = state["lane"]
                    check_state(state, computed[lane], slots[lane])
                counts["ticks"] += 1
            elif tag == "H":
                require(values[1] == token["identity"][0], f"H_OCCUPIED:{key}")
                require(values[4] == pack([lane.active_table for lane in lanes], 2), f"H_DDS_TABLE:{key}")
                counts["h_table_lane_comparisons"] += 4
            elif tag == "M":
                # Frozen TB sets fixture_select only in the overload and
                # accepted-only stimulus segment, between these T markers.
                # Exact transition edges inside that segment are not logged;
                # do not invent their values from neighboring PCM samples.
                if not fixture_transition_window:
                    require(values[3] == 0, f"M_FIXTURE_KNOWN_ZERO:{key}")
                    counts["fixture_known_zero_compared"] += 1
                else:
                    counts["fixture_transition_window_unobservable"] += 1
                del requests[key]
                counts["commits"] += 1
    require(not note_queue and not requests, "TIMELINE_UNDRAINED")
    require(len(used) == json_capture["counts"]["STATE"], "UNBOUND_STATE")
    return {"status": "PARTIAL_A1_DDS_MATH", "complete_audio_golden": False,
            "a1_complete": False, "counter_classification_requires_M2_review": True,
            "transport": transport, "comparisons": dict(counts),
            "stage_delay_histograms": {k: dict(v) for k, v in stage_delays.items()},
            "not_proven": ["Allocator choice/occupancy/release/CC64", "Envelope/ROM/gain/mix/PCM math",
                           "Five unobservable F END counters", "Physical hardware"]}
