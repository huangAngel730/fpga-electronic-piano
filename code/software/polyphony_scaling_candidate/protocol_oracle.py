"""B1 protocol design oracle. Opaque payloads, NOT audio computation or RTL.

Frame scratch writes are isolated until all N results arrive. DSP non-rollback
progression is outside this oracle; do not use this as a replacement for B2.
"""
from dataclasses import dataclass

from inventory import slot_width


@dataclass(frozen=True)
class Tag:
    slot: int
    source: int
    channel: int
    generation: int
    request: int


class ProtocolOracle:
    def __init__(self, identities):
        slot_width(len(identities))
        for source, channel, generation in identities:
            if not (0 <= source < 16 and 0 <= channel < 16 and 0 <= generation < 2**32):
                raise ValueError("IDENTITY_WIDTH")
        self.identities = list(identities)
        self.committed = [None] * len(identities)
        self.pedals = [False] * 256
        self.request = None
        self.issued = set()
        self.scratch = {}

    def begin(self, request):
        if self.request is not None:
            raise ValueError("BUSY")
        if type(request) is not int or not 0 <= request < 2**32:
            raise ValueError("REQUEST_WIDTH")
        self.request = request
        self.issued.clear()
        self.scratch.clear()

    def issue(self, slot):
        if self.request is None or type(slot) is not int or not 0 <= slot < len(self.identities):
            raise ValueError("INVALID_ISSUE")
        if slot in self.issued:
            raise ValueError("DUPLICATE_ISSUE")
        self.issued.add(slot)
        return Tag(slot, *self.identities[slot], self.request)

    def accept(self, tag, payload):
        if not isinstance(tag, Tag) or self.request is None:
            return False
        slot = tag.slot
        if type(slot) is not int or not 0 <= slot < len(self.identities):
            return False
        expected = Tag(slot, *self.identities[slot], self.request)
        if tag != expected or slot not in self.issued or slot in self.scratch:
            return False
        self.scratch[slot] = payload
        return True

    def commit(self):
        n = len(self.identities)
        if self.request is None or len(self.scratch) != n or len(self.issued) != n:
            raise ValueError("INCOMPLETE_FRAME")
        self.committed = [self.scratch[i] for i in range(n)]
        self.cancel()
        return tuple(self.committed)

    def cancel(self):
        self.request = None
        self.issued.clear()
        self.scratch.clear()

    def replace(self, slot, source, channel, generation):
        if self.request is not None:
            raise ValueError("EVENT_DURING_ATOMIC_FRAME")
        if not (0 <= slot < len(self.identities) and 0 <= source < 16
                and 0 <= channel < 16 and 0 <= generation < 2**32):
            raise ValueError("IDENTITY_WIDTH")
        self.identities[slot] = (source, channel, generation)

    def pedal(self, source, channel, down):
        if self.request is not None:
            raise ValueError("CONTROL_DURING_ATOMIC_FRAME")
        if not (0 <= source < 16 and 0 <= channel < 16 and type(down) is bool):
            raise ValueError("PEDAL_INPUT")
        self.pedals[source * 16 + channel] = down

    def reset(self):
        self.cancel()
        self.committed = [None] * len(self.identities)
        self.identities = [(0, 0, 0)] * len(self.identities)
        self.pedals = [False] * 256
