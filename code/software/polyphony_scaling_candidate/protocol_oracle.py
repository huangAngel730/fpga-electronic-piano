"""B1 protocol design oracle. Opaque payloads, NOT audio computation or RTL.

Frame scratch writes are isolated until all N results arrive. DSP non-rollback
progression is outside this oracle; do not use this as a replacement for B2.
Drain acknowledgements are explicit environmental assumptions, not evidence that
any physical ROM/engine has drained. The caller must supply a finite test bound.
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


def unsigned(value, width):
    """Reject Python's bool/int and float/int equality aliases before comparison."""
    return type(value) is int and 0 <= value < 2**width


class ProtocolOracle:
    def __init__(self, identities, *, drain_limit):
        slot_width(len(identities))
        for source, channel, generation in identities:
            if not (unsigned(source, 4) and unsigned(channel, 4) and unsigned(generation, 32)):
                raise ValueError("IDENTITY_WIDTH")
        if type(drain_limit) is not int or drain_limit < 1:
            raise ValueError("DRAIN_LIMIT")
        self.identities = list(identities)
        self.committed = [None] * len(identities)
        self.pedals = [False] * 256
        self.request = None
        self.issued = set()
        self.scratch = {}
        self.drain_limit = drain_limit
        self.draining = False
        self.drain_cycles = 0
        self.drain_failed = False

    def begin(self, request):
        if self.draining:
            raise ValueError("DRAIN_REQUIRED")
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
        if not isinstance(tag, Tag) or self.request is None or self.draining:
            return False
        slot = tag.slot
        if type(slot) is not int or not 0 <= slot < len(self.identities):
            return False
        if not (unsigned(tag.source, 4) and unsigned(tag.channel, 4)
                and unsigned(tag.generation, 32) and unsigned(tag.request, 32)):
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
        # Also fence successful commits: a duplicated result could otherwise
        # survive into a new frame with the same complete tag. Clearing scratch
        # alone is deliberately NOT an acknowledgement of external work drain.
        if self.issued:
            self.draining = True
        self.request = None
        self.issued.clear()
        self.scratch.clear()

    def drain_step(self, *, rom_empty, engine_empty, result_empty):
        """One model clock. All three empties must describe the same old-work fence.

        An empty acknowledgement means no old result can subsequently reappear,
        including duplicates or responses from an accepted but cancelled request.
        A timeout latches closed; reset() cannot bypass it. Actual RTL must prove
        these inputs and its finite bound; the software cannot verify the producer.
        """
        if any(type(flag) is not bool for flag in (rom_empty, engine_empty, result_empty)):
            raise ValueError("DRAIN_INPUT")
        if self.drain_failed:
            raise ValueError("DRAIN_TIMEOUT")
        if not self.draining:
            raise ValueError("NOT_DRAINING")
        self.drain_cycles += 1
        if rom_empty and engine_empty and result_empty:
            self.draining = False
            self.drain_cycles = 0
            return True
        if self.drain_cycles >= self.drain_limit:
            self.drain_failed = True
            raise ValueError("DRAIN_TIMEOUT")
        return False

    def replace(self, slot, source, channel, generation):
        if self.draining:
            raise ValueError("DRAIN_REQUIRED")
        if self.request is not None:
            raise ValueError("EVENT_DURING_ATOMIC_FRAME")
        if not (type(slot) is int and 0 <= slot < len(self.identities)
                and unsigned(source, 4) and unsigned(channel, 4) and unsigned(generation, 32)):
            raise ValueError("IDENTITY_WIDTH")
        self.identities[slot] = (source, channel, generation)

    def pedal(self, source, channel, down):
        if self.draining:
            raise ValueError("DRAIN_REQUIRED")
        if self.request is not None:
            raise ValueError("CONTROL_DURING_ATOMIC_FRAME")
        if not (unsigned(source, 4) and unsigned(channel, 4) and type(down) is bool):
            raise ValueError("PEDAL_INPUT")
        self.pedals[source * 16 + channel] = down

    def reset(self):
        # Local state reset does not reset external pipeline ownership. Keep any
        # existing drain count/failure; repeated cancel/reset cannot extend a limit.
        self.cancel()
        self.committed = [None] * len(self.identities)
        self.identities = [(0, 0, 0)] * len(self.identities)
        self.pedals = [False] * 256
