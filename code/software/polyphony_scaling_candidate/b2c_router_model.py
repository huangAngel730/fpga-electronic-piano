"""Independent N4/N8 extension of the accepted lifecycle reference.

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

    def __init__(self, n=8):
        require(type(n) is int and n in (4, 8), "ROUTER_N")
        self.n = n
        self.state = "IDLE"
        self.slots = [dict(source=0, channel=0, note=0, velocity=0,
                           generation=0, occupied=False, releasing=False,
                           key=False, deferred=False, age=i, fcw=0)
                      for i in range(self.n)]
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
        require(type(release_done) is int and 0 <= release_done < (1 << self.n), "ROUTER_RELEASE_MASK")
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
                lane = min(range(self.n), key=lambda i: self.slots[i]["age"])
            self.counts["retrigger" if match is not None else "free_allocate" if free is not None else "steal"] += 1
            age = self.slots[lane]["age"]
            for i, s in enumerate(self.slots):
                if i != lane and s["age"] > age:
                    s["age"] -= 1
            self.slots[lane]["age"] = self.n-1
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
            if self.index == self.n:
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
