"""Independent H/capture2 four-voice routing and pre-NBA clock oracle.

Inputs: accepted E words, RESET, K frame edges and J sample requests, ROM.
Never reads N/Q/STATE to choose a lane, occupancy, off edge or retirement.
Only the frozen fixed-latency sample path is modeled; overlapping K during
math is explicitly unsupported, not silently approximated.
"""
from collections import Counter

from dds_model import note_fcw
from envelope_model import Envelope
from strict_capture import require


def fields(word):
    require(type(word) is int and 0 <= word < 1 << 64, "ROUTER_EVENT_WORD")
    return dict(type=(word >> 61) & 7, source=(word >> 57) & 15,
                channel=(word >> 53) & 15, note=(word >> 46) & 127,
                velocity=(word >> 36) & 1023, control=(word >> 18) & 255,
                value=(word >> 6) & 4095)


def packed(values, width):
    return sum(v << (i * width) for i, v in enumerate(values))


class Router:
    """Clocked router/controller/allocator with independent lifecycle state."""

    def __init__(self):
        self.state = "IDLE"
        self.slots = [dict(source=0, channel=0, note=0, velocity=0,
                           generation=0, occupied=False, releasing=False,
                           key=False, deferred=False, age=i, fcw=0)
                      for i in range(4)]
        self.pedals = set()
        self.pending = {}
        self.retire = {}
        self.target = self.index = 0
        self.on = self.off = 0
        self.held = None
        self.allocated = self.released = None
        self.counts = Counter()

    def retire_lane(self):
        return next((i for i, s in enumerate(self.slots)
                     if self.retire.get(i) == s["generation"] and
                     s["occupied"] and s["releasing"]), None)

    def busy(self):
        return self.state != "IDLE" or bool(self.pending) or self.retire_lane() is not None

    def snapshot(self):
        return [packed([int(s["occupied"]) for s in self.slots], 1),
                packed([s["source"] for s in self.slots], 4),
                packed([s["channel"] for s in self.slots], 4),
                packed([s["generation"] for s in self.slots], 32),
                packed([s["fcw"] for s in self.slots], 32),
                packed([s["note"] for s in self.slots], 8)]

    @staticmethod
    def identity(slot):
        return tuple(slot[n] for n in ("source", "channel", "note"))

    def queue_release(self, lane):
        s = self.slots[lane]
        s["deferred"] = False
        # Controller releasing is distinct from router releasing until APPLY.
        self.pending[lane] = s["generation"]

    def edge(self, event=None, release_done=0, owner=True):
        require(type(release_done) is int and 0 <= release_done < 16, "ROUTER_RELEASE_MASK")
        require(type(owner) is bool, "ROUTER_OWNER_TYPE")
        retire_lane = self.retire_lane()  # pre-NBA, before new done latches
        ready = self.state == "IDLE" and not self.pending and retire_lane is None and owner
        require(event is None or ready, "ROUTER_ACCEPT_WHILE_BUSY")
        for i, s in enumerate(self.slots):
            if release_done & (1 << i) and s["occupied"] and s["releasing"]:
                self.retire[i] = s["generation"]
        self.on = self.off = 0
        if self.state == "IDLE":
            if self.pending:
                self.index, self.state = 0, "SCAN"
            elif retire_lane is not None:
                self.target, self.state = retire_lane, "RETIRE"
            elif event is not None:
                self.held = fields(event)
                e = self.held
                self.counts["accepted_events"] += 1
                if e["type"] == 0 and e["velocity"]:
                    self.state = "ALLOC_SEND"
                elif e["type"] == 1 or e["type"] == 0 and not e["velocity"]:
                    match = next((i for i, s in enumerate(self.slots) if s["occupied"] and
                                  self.identity(s) == self.identity(e)), None)
                    self.target = match if match is not None else 0
                    self.state = "CTRL_OFF" if match is not None else "IGNORE"
                    self.counts["matched_note_off" if match is not None else "unmatched_note_off"] += 1
                elif e["type"] == 4 and e["control"] == 6:
                    self.state = "PEDAL"
                elif e["type"] == 5:
                    self.state = "PANIC"
                else:
                    self.state = "IGNORE"
        elif self.state == "ALLOC_SEND":
            e = self.held
            match = next((i for i, s in enumerate(self.slots) if s["occupied"] and
                          self.identity(s) == self.identity(e)), None)
            free = next((i for i, s in enumerate(self.slots) if not s["occupied"]), None)
            lane = match if match is not None else free
            if lane is None:
                lane = min(range(4), key=lambda i: self.slots[i]["age"])
            self.counts["retrigger" if match is not None else "free_allocate" if free is not None else "steal"] += 1
            age = self.slots[lane]["age"]
            for i, s in enumerate(self.slots):
                if i != lane and s["age"] > age:
                    s["age"] -= 1
            self.slots[lane]["age"] = 3
            self.allocated, self.state = lane, "ALLOC_APPLY"
        elif self.state == "ALLOC_APPLY":
            self.target = self.allocated
            s, e = self.slots[self.target], self.held
            s.update({n: e[n] for n in ("source", "channel", "note", "velocity")})
            s.update(occupied=True, releasing=False, fcw=note_fcw(e["note"]),
                     generation=(s["generation"] + 1) & 0xffffffff)
            self.retire.pop(self.target, None)
            self.state = "CTRL_ON"
        elif self.state == "CTRL_ON":
            s = self.slots[self.target]
            s.update(key=True, deferred=False)
            self.on, self.state = 1 << self.target, "IDLE"
        elif self.state == "CTRL_OFF":
            s = self.slots[self.target]
            if s["key"] and not s["releasing"]:
                s["key"] = False
                if (s["source"], s["channel"]) in self.pedals:
                    s["deferred"] = True
                    self.counts["pedal_deferred"] += 1
                else:
                    self.queue_release(self.target)
            self.state = "IDLE"
        elif self.state == "PEDAL":
            identity = self.held["source"], self.held["channel"]
            if self.held["value"] >= 2048:
                self.pedals.add(identity)
            else:
                self.pedals.discard(identity)
                for i, s in enumerate(self.slots):
                    if s["occupied"] and not s["key"] and s["deferred"] and not s["releasing"] and (s["source"], s["channel"]) == identity:
                        self.queue_release(i)
            self.state = "IDLE"
        elif self.state == "PANIC":
            self.pedals.clear()
            for i, s in enumerate(self.slots):
                s.update(key=False, deferred=False)
                if s["occupied"] and not s["releasing"]:
                    self.queue_release(i)
            self.state = "IDLE"
        elif self.state == "SCAN":
            if self.index == 4:
                self.state = "ACK"
            else:
                s = self.slots[self.index]
                matches = self.pending.get(self.index) == s["generation"] and s["occupied"]
                if matches and not s["releasing"]:
                    self.state = "RELEASE_SEND"
                else:
                    self.index += 1
        elif self.state == "RELEASE_SEND":
            self.released, self.state = self.index, "RELEASE_APPLY"
        elif self.state == "RELEASE_APPLY":
            s = self.slots[self.index]
            if s["occupied"] and self.pending.get(self.index) == s["generation"]:
                s["releasing"] = True
                self.off = 1 << self.index
                self.counts["off_pulses"] += 1
            self.index += 1
            self.state = "SCAN"
        elif self.state == "ACK":
            self.pending.clear()
            self.state = "IDLE"
        elif self.state == "RETIRE":
            self.slots[self.target].update(occupied=False, releasing=False, key=False, deferred=False)
            self.retire.pop(self.target, None)
            self.counts["retirements"] += 1
            self.state = "IDLE"
        elif self.state == "IGNORE":
            self.state = "IDLE"
        else:
            raise ValueError("ROUTER_UNKNOWN_STATE")


class ClockOracle:
    """Sparse clock execution; jump only after all lane pipelines fixed-point."""

    def __init__(self, gain_rom):
        self.gain_rom = gain_rom
        self.router = Router()
        self.env = [Envelope(gain_rom) for _ in range(4)]
        self.phase, self.delay, self.request = "IDLE", 0, 0
        self.q_cycle = None
        self.epoch, self.cycle = 0, 0
        self.states, self.qs, self.ns, self.ticks = [], [], [], []
        self.counts = Counter()

    def edge(self, cycle, epoch, event=None, frame=False, request=None, reset=False):
        require(cycle == self.cycle + 1, "ROUTER_CLOCK_ORDER")
        self.cycle = cycle
        if reset:
            self.counts.update(self.router.counts)
            self.router = Router()
            self.phase, self.q_cycle, self.request = "IDLE", None, 0
            for env in self.env:
                env.reset(cycle)
            self.epoch = epoch
            self.counts["resets"] += 1
            return
        r = self.router
        busy, on, off = r.busy(), r.on, r.off
        tick = self.phase == "MATH" and cycle == self.q_cycle + 14 and not frame
        if on:
            self.ns.append((epoch, cycle, on))
        if self.phase == "CAPTURE" and not frame:
            self.qs.append((epoch, cycle, self.request, r.snapshot()))
        if tick:
            self.ticks.append((epoch, cycle, self.request))
        release_done = 0
        for i, env in enumerate(self.env):
            s = r.slots[i]
            if s["occupied"] and s["releasing"] and env.state == 0 and not on & (1 << i):
                release_done |= 1 << i
            before = env.edge(tick, bool(on & (1 << i)), bool(off & (1 << i)), s["velocity"])
            if tick or (on | off) & (1 << i):
                self.states.append(dict(epoch=epoch, cycle=cycle, lane=i, tick=int(tick),
                                        pending_request_id=self.request,
                                        note_on=int(bool(on & (1 << i))), note_off=int(bool(off & (1 << i))),
                                        occupied=int(s["occupied"]), **{k: s[k] for k in
                                        ("source", "channel", "note", "velocity", "generation")}, **before))
        owner = self.phase == "IDLE" and request is None and not frame
        r.edge(event, release_done, owner)
        if frame:
            require(self.phase != "MATH", "ROUTER_OVERLAPPING_FRAME_MATH_UNCOVERED")
            self.phase = "DRAIN"
        elif self.phase == "DRAIN":
            self.phase = "WAIT" if request is not None else "IDLE"
        elif self.phase == "IDLE" and request is not None:
            self.phase = "WAIT"
        elif self.phase == "WAIT" and not busy and not on and not off:
            self.delay, self.phase = 6, "SETTLE"
        elif self.phase == "SETTLE":
            if self.delay == 0:
                self.phase = "CAPTURE"
            else:
                self.delay -= 1
        elif self.phase == "CAPTURE":
            self.q_cycle, self.phase = cycle, "MATH"
        elif self.phase == "MATH" and cycle == self.q_cycle + 20:
            self.phase = "IDLE"
        if request is not None:
            self.request = request

    def advance(self, cycle, epoch, **inputs):
        # At most 12 quiet edges to settle the existing envelope pipelines;
        # this also exposes release_done and completes any ensuing retirement.
        while self.cycle + 1 < cycle:
            stable = self.phase == "IDLE" and not self.router.busy() and not (self.router.on | self.router.off)
            if stable:
                before = [e.registers() for e in self.env]
                done = any(s["occupied"] and s["releasing"] and e.state == 0
                           for s, e in zip(self.router.slots, self.env))
                self.edge(self.cycle + 1, self.epoch)
                if not done and before == [e.registers() for e in self.env]:
                    for env in self.env:
                        env.cycle += cycle - self.cycle - 1
                    self.cycle = cycle - 1
            else:
                self.edge(self.cycle + 1, self.epoch)
        self.edge(cycle, epoch, **inputs)


def derive(f_capture, gain_rom):
    """Projection is intentional: only stimulus tags feed this model."""
    inputs = {}
    end_cycle = 0
    for row in f_capture["rows"]:
        if row["tag"] == "END":
            continue
        end_cycle = max(end_cycle, row["cycle"])
        if row["tag"] not in ("R", "E", "K", "J"):
            continue
        key = row["cycle"]
        epoch, values = row["epoch"], row["values"]
        entry = inputs.setdefault(key, {"epoch": epoch})
        name = {"R": "reset", "E": "event", "K": "frame", "J": "request"}[row["tag"]]
        require(name not in entry, "ROUTER_DUPLICATE_STIMULUS:" + name)
        entry[name] = True if name in ("reset", "frame") else values[0]
    model = ClockOracle(gain_rom)
    for cycle, entry in sorted(inputs.items()):
        model.advance(cycle, **entry)
    model.advance(end_cycle + 1, model.epoch)
    model.counts.update(model.router.counts)
    return model


def compare_router(model, json_capture, f_capture):
    actual_n = [(r["epoch"], r["cycle"], r["values"][0]) for r in f_capture["rows"] if r["tag"] == "N"]
    require(actual_n == model.ns, "ROUTER_N_LANE_OR_EDGE")
    actual_q = [(r["epoch"], r["cycle"], r["values"][0], r["values"][1:])
                for r in f_capture["rows"] if r["tag"] == "Q"]
    require(actual_q == model.qs, "ROUTER_Q_OCCUPANCY_IDENTITY_OR_EDGE")
    actual_d = [(r["epoch"], r["cycle"], r["values"][0]) for r in f_capture["rows"] if r["tag"] == "D"]
    require(actual_d == model.ticks, "ROUTER_D_REQUEST_OR_EDGE")
    # Matching is structural, never chosen using envelope values. The only
    # printed-cycle alternatives are the M2-confirmed active-region counter
    # old/new labels. Every actual and expected row must bind once.
    actual = [r for r in json_capture["rows"] if r["tag"] == "STATE"]
    require(len(actual) == len(model.states), "ROUTER_STATE_COUNT")
    by_lane = {(e, i): [] for e in range(1, model.epoch + 1) for i in range(4)}
    for s in actual:
        by_lane[s["epoch"], s["lane"]].append(s)
    offsets, bindings, predicted_states = Counter(), {}, {}
    for expected in model.states:
        lane_rows = by_lane[expected["epoch"], expected["lane"]]
        require(bool(lane_rows), "ROUTER_STATE_MISSING")
        observed = lane_rows.pop(0)
        offset = expected["cycle"] - observed["cycle"]
        require(offset in (0, 1), "ROUTER_STATE_COUNTER_LABEL")
        for key in ("tick", "note_on", "note_off", "occupied", "source", "channel", "note", "velocity", "generation", "pending_request_id"):
            require(expected[key] == observed[key], "ROUTER_STATE_" + key)
        for key in ("raw_state", "public_state", "level_q16", "start_q16", "peak_q16", "sustain_q16", "step_q16_twos33", "elapsed", "envelope"):
            value = int(observed[key], 16) if "q16" in key else observed[key]
            require(expected[key] == value, "ROUTER_ENVELOPE_" + key)
        bindings[(observed["epoch"], observed["cycle"], observed["lane"])] = expected["cycle"]
        predicted_states[(observed["epoch"], observed["cycle"], observed["lane"])] = expected
        offsets[("tick" if expected["tick"] else "on" if expected["note_on"] else "off", offset)] += 1
    return {"status": "ROUTER_REFERENCE_MATCH", "independent_inputs": ["R", "E", "K", "J", "velocity ROM"],
            "n_compared": len(model.ns), "q_compared": len(model.qs), "tick_groups": len(model.ticks),
            "state_rows": len(model.states), "lifecycle_counts": dict(model.counts),
            "counter_label_histogram": {f"{k[0]}:{k[1]}": v for k, v in offsets.items()},
            "off_edges": [{k: s[k] for k in ("epoch", "cycle", "lane", "generation")} for s in model.states if s["note_off"]],
            "state_actual_cycles": bindings, "predicted_states": predicted_states,
            "predicted_n": {(e, c): mask for e, c, mask in model.ns},
            "predicted_q": {(e, req): value for e, c, req, value in model.qs}}
