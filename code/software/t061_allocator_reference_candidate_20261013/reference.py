"""Independent edge model for the frozen allocator contract (no HDL execution).

All predicates inspect the pre-edge state. Field writes resolve in the order
release_done, note_on, note_off. Packed slot layout is the frozen 18+SW bits.
This oracle uses ordered Python sets/minima, not the candidate's reduction tree.
"""

from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path


class ContractError(ValueError):
    """A malformed input, capture, or mismatch with the independent contract."""


def integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ContractError(f"TYPE_RANGE:{name}")
    return value


def exact_keys(value, keys, name):
    if type(value) is not dict or set(value) != set(keys):
        raise ContractError(f"FIELDS:{name}")


@dataclass(frozen=True)
class Edge:
    rst_n: int = 1
    note_on: int = 0
    note_off: int = 0
    source: int = 0
    channel: int = 0
    note: int = 0
    release_done: int = 0

    @classmethod
    def from_dict(cls, raw, n):
        exact_keys(raw, cls.__dataclass_fields__, "edge")
        edge = cls(**raw)
        edge.validate(n)
        return edge

    def validate(self, n):
        for name in ("rst_n", "note_on", "note_off"):
            integer(getattr(self, name), 0, 1, name)
        integer(self.source, 0, 15, "source")
        integer(self.channel, 0, 15, "channel")
        integer(self.note, 0, 255, "note")
        integer(self.release_done, 0, (1 << n) - 1, "release_done")


@dataclass(frozen=True)
class Slot:
    active: int = 0
    release: int = 0
    source: int = 0
    channel: int = 0
    note: int = 0
    age: int = 0

    def packed(self, sw):
        return ((self.active << (17 + sw)) | (self.release << (16 + sw))
                | (self.source << (12 + sw)) | (self.channel << (8 + sw))
                | (self.note << sw) | self.age)

    @classmethod
    def unpack(cls, value, sw):
        integer(value, 0, (1 << (18 + sw)) - 1, "packed_slot")
        return cls((value >> (17 + sw)) & 1, (value >> (16 + sw)) & 1,
                   (value >> (12 + sw)) & 15, (value >> (8 + sw)) & 15,
                   (value >> sw) & 255, value & ((1 << sw) - 1))

    def matches(self, edge):
        return (self.source, self.channel, self.note) == (
            edge.source, edge.channel, edge.note)


OUTPUT_KEYS = ("allocated_slot", "slot_valid", "release_slot",
               "release_target_valid")


class Allocator:
    def __init__(self, n):
        if type(n) is not int or n not in (4, 8, 16, 32):
            raise ContractError("N_SUPPORTED")
        self.n = n
        self.sw = n.bit_length() - 1
        self.reset()

    def reset(self):
        self.slots = [Slot(age=i) for i in range(self.n)]
        self.outputs = dict.fromkeys(OUTPUT_KEYS, 0)

    def load_slots(self, packed):
        """Explicit verification injection, never claimed naturally reachable."""
        if type(packed) is not list or len(packed) != self.n:
            raise ContractError("SLOT_COUNT")
        self.slots = [Slot.unpack(value, self.sw) for value in packed]

    def snapshot(self):
        return {"outputs": dict(self.outputs),
                "slots": [slot.packed(self.sw) for slot in self.slots]}

    def choose(self, old, edge):
        matches = [i for i, s in enumerate(old)
                   if (s.active or s.release) and s.matches(edge)]
        if matches:
            return min(matches)
        idle = [i for i, s in enumerate(old) if not (s.active or s.release)]
        if idle:
            return min(idle)
        return min(range(self.n), key=lambda i: (old[i].age, i))

    def step(self, edge):
        if type(edge) is not Edge:
            raise ContractError("EDGE_TYPE")
        edge.validate(self.n)
        if not edge.rst_n:
            self.reset()
            return self.snapshot()
        old = tuple(self.slots)
        new = list(old)
        self.outputs["slot_valid"] = 0
        self.outputs["release_target_valid"] = 0
        for i, slot in enumerate(old):
            if (edge.release_done >> i) & 1 and slot.release:
                new[i] = replace(new[i], active=0, release=0)
        if edge.note_on:
            target = self.choose(old, edge)
            target_age = old[target].age
            for i, slot in enumerate(old):
                if i != target and slot.age > target_age:
                    new[i] = replace(new[i], age=slot.age - 1)
            new[target] = Slot(1, 0, edge.source, edge.channel, edge.note,
                               self.n - 1)
            self.outputs["allocated_slot"] = target
            self.outputs["slot_valid"] = 1
        if edge.note_off:
            off_targets = [i for i, s in enumerate(old)
                           if s.active and s.matches(edge)]
            for i in off_targets:
                new[i] = replace(new[i], active=0, release=1)
            if off_targets:
                self.outputs["release_slot"] = max(off_targets)
                self.outputs["release_target_valid"] = 1
        self.slots = new
        return self.snapshot()


def strict_json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ContractError("DUPLICATE_KEY")
            result[key] = value
        return result

    def no_constant(value):
        raise ContractError("NONFINITE_JSON")

    try:
        return json.loads(text, object_pairs_hook=unique,
                          parse_constant=no_constant)
    except (ValueError, TypeError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError("JSON_SYNTAX") from exc


def validate_snapshot(raw, n):
    exact_keys(raw, ("outputs", "slots"), "snapshot")
    exact_keys(raw["outputs"], OUTPUT_KEYS, "outputs")
    for key in OUTPUT_KEYS:
        integer(raw["outputs"][key], 0,
                1 if key.endswith("valid") else n - 1, key)
    if type(raw["slots"]) is not list or len(raw["slots"]) != n:
        raise ContractError("SLOT_COUNT")
    for value in raw["slots"]:
        Slot.unpack(value, n.bit_length() - 1)


def compare_records(vectors, capture, n):
    """Recompute all expectations from inputs, then compare complete snapshots.

    Vectors: {index,label,input,inject_slots,expected}; capture records:
    {index,outputs:{four public outputs},slots:[N packed slot integers]}.
    An omitted/duplicate/extra record, field, or wrong integer type is rejected.
    """
    if len(vectors) != len(capture) or not vectors:
        raise ContractError("RECORD_COUNT")
    model = Allocator(n)
    for index, (vector, actual) in enumerate(zip(vectors, capture)):
        exact_keys(vector, ("index", "label", "input", "inject_slots",
                            "expected"), "vector")
        exact_keys(actual, ("index", "outputs", "slots"), "capture")
        integer(vector["index"], index, index, "vector.index")
        integer(actual["index"], index, index, "capture.index")
        if type(vector["label"]) is not str or not vector["label"]:
            raise ContractError("LABEL")
        if vector["inject_slots"] is not None:
            model.load_slots(vector["inject_slots"])
        expected = model.step(Edge.from_dict(vector["input"], n))
        validate_snapshot(vector["expected"], n)
        if vector["expected"] != expected:
            raise ContractError(f"GOLDEN_RECOMPUTE:{index}")
        observed = {key: actual[key] for key in ("outputs", "slots")}
        validate_snapshot(observed, n)
        if observed["outputs"] != expected["outputs"]:
            raise ContractError(f"ALLOCATOR_PUBLIC:{index}")
        if observed["slots"] != expected["slots"]:
            raise ContractError(f"ALLOCATOR_STATE:{index}")
    return {"status": "PASS", "n": n, "edges": len(vectors),
            "public_values": 4 * len(vectors),
            "slot_values": n * len(vectors)}


def read_jsonl(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if not lines or any(not line.strip() for line in lines):
        raise ContractError("EMPTY_RECORD")
    return [strict_json(line) for line in lines]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--n", required=True, type=int)
    parser.add_argument("--vectors", required=True, type=Path)
    parser.add_argument("--capture", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = compare_records(read_jsonl(args.vectors),
                                 read_jsonl(args.capture), args.n)
        print(json.dumps(result, sort_keys=True))
    except (ContractError, OSError) as exc:
        print(json.dumps({"status": "FAIL", "diagnostic": str(exc)}))
        raise SystemExit(1)
