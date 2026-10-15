"""M1 R01 fixed input schedule and independent transaction calendar.

No HDL invocation and no PCM math. All expected transactions depend on controls,
never on observed ready/valid. The 128-edge plan and old captures are untouched.
"""
from dataclasses import dataclass

VERSION = "T052_LONG_50M1042_FROZEN_FCW_R01"
M1_SHA = "56574246ebd7fe75bf59ea7f583ffe2c00f5593b8567230dbb6992cfe857b555"
FCW = (0x04B17E4D, 0x0962FC9A, 0x12C5F935, 0x258BF26A)
COUNT = 256 + 8192 * 1042 + 16
FIELDS = (("rst_n", 1), ("frame", 1), ("cancel", 1), ("req", 1),
          ("id", 32), ("enable", 1), ("mask", 4), ("fcw0", 32),
          ("fcw1", 32), ("fcw2", 32), ("fcw3", 32), ("ready", 1))
REQUESTS = {
    4: 0xFFFFFFFE, 8: 0xFFFFFFFF, 12: 0, 16: 0, 25: 0, 27: 1,
    30: 2, 34: 3, 42: 4, 46: 5, 50: 6, 54: 7, 58: 8,
    124: 0xA5A5A5A5, 132: 0xA5A5A5A5,
}
EXTRA = {5, 6, 7, 26, 33, 45, 29, 41, 44, 43}
RESETS = ((0, 0, 0), (80, 4, 1), (2560, 128, 0), (2640, 132, 1))


def controls(cycle):
    """Return all 170 input bits for exactly one independently planned edge."""
    if type(cycle) is not int or not 0 <= cycle < COUNT:
        raise ValueError("CYCLE_RANGE")
    row = dict(rst_n=1, frame=0, cancel=0, req=0, id=0,
               enable=1, mask=15, ready=1,
               **{f"fcw{i}": value for i, value in enumerate(FCW)})
    if cycle < 256:
        row["rst_n"] = int(not (cycle <= 3 or 128 <= cycle <= 131))
        row["frame"] = int(cycle in {29, 41, 43, 44})
        row["cancel"] = int(cycle in {26, 33, 43, 45})
        row["req"] = int(cycle in REQUESTS or cycle in EXTRA)
        row["id"] = REQUESTS.get(cycle, 0xDEADBEEF if cycle in EXTRA else 0)
        row["ready"] = int(not (16 <= cycle <= 23 or 34 <= cycle <= 40
                                   or 124 <= cycle <= 127))
        if cycle in {46, 54}:
            row["enable"] = 0
        if cycle in {50, 54}:
            row["mask"] = 0
    elif cycle < COUNT - 16:
        frame, offset = divmod(cycle - 256, 1042)
        row["frame"] = int(offset == 0)
        row["req"] = int(offset == 1 or frame % 64 == 0 and offset in {2, 3, 4})
        row["ready"] = int(not (frame % 64 == 0 and offset < 32))
        row["mask"] = 1 << (frame // 1024) if frame < 4096 else 15
        row["id"] = (0xFFFFFFF0 + frame // 2) & 0xFFFFFFFF
    else:
        row["id"] = 0xFEF
    return row


def pack(row):
    value = 0
    if set(row) != {key for key, _ in FIELDS}:
        raise ValueError("CONTROL_FIELDS")
    for key, width in FIELDS:
        item = row[key]
        if type(item) is not int or not 0 <= item < 1 << width:
            raise ValueError("CONTROL_TYPE_OR_RANGE:" + key)
        value = value << width | item
    return value


def unpack(value):
    if type(value) is not int or not 0 <= value < 1 << 170:
        raise ValueError("CONTROL_WIDTH")
    result = {}
    for key, width in reversed(FIELDS):
        result[key] = value & ((1 << width) - 1)
        value >>= width
    return result


@dataclass
class Calendar:
    """Frozen IDLE/CALC/HOLD FSM, including retained invalid-period result ID."""
    state: int = 0
    valid: int = 0
    result_id: int = 0
    epoch: int = 1
    serial: int = 0
    pending: tuple | None = None
    previous_reset: int = 0
    accepted: int = 0
    published: int = 0
    cancelled: int = 0

    def step(self, cycle, row):
        events = []
        # Reset occurs on the preceding negedge: clear before PRE_NBA sampling.
        if not row["rst_n"] and self.previous_reset:
            if self.pending is not None:
                events.append(self.event("CANCEL", cycle, "reset", cycle * 20))
                self.cancelled += 1
            self.pending = None
            self.epoch += 1
            self.serial = 0
        if not row["rst_n"]:
            self.state = self.valid = self.result_id = 0
        ports = (int(self.state == 0), self.valid, self.result_id)
        if not row["rst_n"]:
            pass
        elif row["frame"] or row["cancel"]:
            if self.pending is not None:
                reason = "frame+cancel" if row["frame"] and row["cancel"] else (
                    "frame" if row["frame"] else "cancel")
                events.append(self.event("CANCEL", cycle, reason))
                self.cancelled += 1
            self.state = self.valid = self.result_id = 0
            self.pending = None
        elif self.state == 0:
            self.valid = 0
            if row["req"]:
                self.serial += 1
                self.pending = (self.epoch, self.serial, row["id"])
                self.accepted += 1
                events.append(self.event("ACCEPT", cycle))
                self.state = 1
        elif self.state == 1:
            self.state = 2
        elif self.valid and row["ready"]:
            events.append(self.event("PUBLISH", cycle))
            self.published += 1
            self.pending = None
            self.valid = self.state = 0
        else:
            self.valid = 1
            self.result_id = self.pending[2]
        self.previous_reset = row["rst_n"]
        return ports, events

    def event(self, kind, cycle, reason=None, time_ns=None):
        value = dict(event=kind, cycle=cycle,
                     time_ns=10 + 20 * cycle if time_ns is None else time_ns,
                     key=list(self.pending))
        if reason is not None:
            value["reason"] = reason
        return value

    def end(self, count):
        return dict(type="END", rows=count, accepted=self.accepted,
                    published=self.published, cancelled=self.cancelled,
                    open=int(self.pending is not None))
