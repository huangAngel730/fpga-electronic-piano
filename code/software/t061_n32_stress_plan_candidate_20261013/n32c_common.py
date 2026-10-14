"""Strict data contracts for the T061 N32-C stress candidate.

This module is intentionally independent of RTL output.  It validates plans,
expected ledgers, and captures using exact JSON keys and canonical SHA-256
digests.  Booleans are never accepted as integers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any, Iterable


class ContractError(ValueError):
    """Raised when an input or evidence object violates the closed contract."""


# One authoritative list shared by the selftest, static lock, and future
# execution manifest.  Each mutant must fail for the intended diagnostic,
# not merely for some unrelated malformed-capture error.
MUTATION_DIAGNOSTICS = {
    "DROP_TRANSACTION": "IDLE_WITH_OPEN_TRANSACTION",
    "DUPLICATE_TRANSACTION": "RESULT_WITHOUT_ACCEPT",
    "WRONG_SLOT_IDENTITY": "PUBLIC_SLOT_STATE",
    "WRONG_STEAL_VICTIM": "PUBLIC_SLOT_STATE",
    "WRONG_RESULT_ID": "RESULT_PAYLOAD",
    "PCM_LEFT_RIGHT_SWAP": "RESULT_PAYLOAD",
    "PCM_WRONG_BEAT": "RESULT_PAYLOAD",
    "CLIPPED_MISSING": "FIELDS:cycle",
    "CLIPPED_WRONG_BEAT": "RESULT_PAYLOAD",
    "CLIPPED_FULLSCALE_DERIVED": "RESULT_PAYLOAD",
    "DROP_REQUIRED_HOLD": "HOLD_VALID_DROPPED",
    "HOLD_PAYLOAD_UNSTABLE": "RESULT_PAYLOAD",
    "WRONG_READ_CONTEXT": "READ_VALUE:context",
    "READ_OUTSIDE_REQUEST": "READ_RESPONSE_WITHOUT_REQUEST",
    "SAME_EDGE_READ_RESPONSE": "READ_RESPONSE_WITHOUT_REQUEST",
    "RESULT_BEFORE_ACCEPT": "RESULT_WITHOUT_ACCEPT",
    "DROP_ACCEPT": "PLAN_PROGRESS",
    "DUPLICATE_ACCEPT": "DRIVE_SAMPLE_VALID",
    "CANCEL_NOT_DRIVEN": "DRIVE_CANCEL",
    "STALE_AFTER_CANCEL": "RESULT_WITHOUT_ACCEPT",
    "STALE_AFTER_RESET": "RESULT_WITHOUT_ACCEPT",
}


CONTROL_EVENT_SPECS = {
    "pitch_bend": (3, 0),
    "modulation": (4, 1),
    "pitch_range": (4, 4),
}


def require(condition: bool, diagnostic: str) -> None:
    if not condition:
        raise ContractError(diagnostic)


def integer(value: Any, low: int, high: int, name: str) -> int:
    require(type(value) is int and low <= value <= high, f"TYPE_RANGE:{name}")
    return value


def exact_keys(value: Any, keys: Iterable[str], name: str) -> None:
    require(type(value) is dict, f"TYPE:{name}")
    require(set(value) == set(keys), f"FIELDS:{name}")


def strict_json(text: str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            require(key not in result, "DUPLICATE_KEY")
            result[key] = value
        return result

    def no_constant(_value: str) -> None:
        raise ContractError("NONFINITE_JSON")

    try:
        return json.loads(
            text,
            object_pairs_hook=unique,
            parse_constant=no_constant,
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError("JSON_SYNTAX") from exc


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True) + "\n").encode("ascii")


def records_sha256(records: Iterable[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(canonical_bytes(record))
    return digest.hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_reparse_point(path: Path) -> bool:
    """Detect Windows symlinks and junctions on Python 3.11 as well as 3.12."""
    try:
        info = os.lstat(path)
    except OSError:
        return False
    attributes = getattr(info, "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(attributes & flag)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    require(lines and all(line.strip() for line in lines), "EMPTY_JSONL")
    records = [strict_json(line) for line in lines]
    require(all(type(record) is dict for record in records), "JSONL_OBJECT")
    return records


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = b"".join(canonical_bytes(record) for record in records)
    path.write_bytes(payload)


@dataclass
class Slot:
    occupied: bool = False
    releasing: bool = False
    deferred: bool = False
    source: int = 0
    channel: int = 0
    note: int = 0
    velocity: int = 0
    generation: int = 0
    age: int = 0

    def identity(self) -> tuple[int, int, int]:
        return self.source, self.channel, self.note


def slot_digest(slots: list[Slot]) -> str:
    return hashlib.sha256(canonical_bytes([asdict(slot) for slot in slots])).hexdigest()


PUBLIC_SLOT_FIELDS = (
    "occupied", "releasing", "source", "channel", "note", "generation",
)


def public_slot(slot: Slot) -> dict[str, Any]:
    """Return only state that the B wrapper must expose to the C observer."""
    return {name: getattr(slot, name) for name in PUBLIC_SLOT_FIELDS}


def public_slots(slots: list[Slot]) -> list[dict[str, Any]]:
    require(len(slots) == 32, "SLOT_COUNT")
    return [public_slot(slot) for slot in slots]


def public_slot_digest(slots: list[dict[str, Any]]) -> str:
    validate_public_slots(slots)
    return hashlib.sha256(canonical_bytes(slots)).hexdigest()


def validate_public_slots(slots: Any) -> None:
    require(type(slots) is list and len(slots) == 32, "PUBLIC_SLOT_COUNT")
    for lane, slot in enumerate(slots):
        exact_keys(slot, PUBLIC_SLOT_FIELDS, f"public_slot[{lane}]")
        require(type(slot["occupied"]) is bool, f"SLOT_OCCUPIED:{lane}")
        require(type(slot["releasing"]) is bool, f"SLOT_RELEASING:{lane}")
        integer(slot["source"], 0, 15, f"slot.source[{lane}]")
        integer(slot["channel"], 0, 15, f"slot.channel[{lane}]")
        integer(slot["note"], 0, 127, f"slot.note[{lane}]")
        integer(slot["generation"], 0, (1 << 32) - 1,
                f"slot.generation[{lane}]")


def control_digest(controls: dict[str, int], pedals: set[tuple[int, int]]) -> str:
    body = {
        "controls": dict(sorted(controls.items())),
        "pedals": [list(identity) for identity in sorted(pedals)],
    }
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def pack_event(*, event_type: int, source: int, channel: int, note: int = 0,
               velocity: int = 0, expression: int = 0, control_id: int = 0,
               control_value: int = 0) -> int:
    integer(event_type, 0, 7, "event_type")
    integer(source, 0, 15, "source")
    integer(channel, 0, 15, "channel")
    integer(note, 0, 127, "note")
    integer(velocity, 0, 1023, "velocity")
    integer(expression, 0, 1023, "expression")
    integer(control_id, 0, 255, "control_id")
    integer(control_value, 0, 4095, "control_value")
    return ((event_type << 61) | (source << 57) | (channel << 53)
            | (note << 46) | (velocity << 36) | (expression << 26)
            | (control_id << 18) | (control_value << 6))


EVENT_FIELDS = (
    "record", "event_serial", "plan_index", "reset_lifetime", "event_type",
    "source", "channel", "note", "velocity", "expression", "control_id",
    "control_value", "event_word",
)

TXN_FIELDS = (
    "record", "reset_lifetime", "accept_serial", "plan_index", "result_id",
    "disposition", "identity_digest", "control_digest", "focus_source",
    "focus_channel", "focus_note", "active_count", "min_hold_cycles",
    "left_pcm", "right_pcm", "clipped", "pcm_provenance",
)

READ_FIELDS = (
    "record", "read_serial", "plan_index", "reset_lifetime", "slot",
    "occupied", "releasing", "source", "channel", "note", "generation",
    "context", "context_provenance",
)


def validate_event_record(record: dict[str, Any]) -> None:
    exact_keys(record, EVENT_FIELDS, "event")
    require(record["record"] == "EVENT", "EVENT_RECORD")
    integer(record["event_serial"], 0, (1 << 63) - 1, "event_serial")
    integer(record["plan_index"], 0, (1 << 63) - 1, "plan_index")
    integer(record["reset_lifetime"], 0, (1 << 31) - 1, "reset_lifetime")
    for name, high in (("event_type", 7), ("source", 15), ("channel", 15),
                       ("note", 127), ("velocity", 1023),
                       ("expression", 1023), ("control_id", 255),
                       ("control_value", 4095)):
        integer(record[name], 0, high, name)
    integer(record["event_word"], 0, (1 << 64) - 1, "event_word")
    rebuilt = pack_event(**{name: record[name] for name in (
        "event_type", "source", "channel", "note", "velocity",
        "expression", "control_id", "control_value")})
    require(rebuilt == record["event_word"], "EVENT_WORD_MISMATCH")


def validate_txn_record(record: dict[str, Any], *, executable: bool) -> None:
    exact_keys(record, TXN_FIELDS, "txn")
    require(record["record"] == "TXN", "TXN_RECORD")
    integer(record["reset_lifetime"], 0, (1 << 31) - 1, "reset_lifetime")
    integer(record["accept_serial"], 0, (1 << 63) - 1, "accept_serial")
    integer(record["plan_index"], 0, (1 << 63) - 1, "plan_index")
    integer(record["result_id"], 0, (1 << 32) - 1, "result_id")
    require(record["disposition"] in ("PUBLISH", "CANCEL"), "DISPOSITION")
    for name in ("identity_digest", "control_digest"):
        require(type(record[name]) is str and len(record[name]) == 64,
                f"DIGEST:{name}")
    integer(record["focus_source"], 0, 15, "focus_source")
    integer(record["focus_channel"], 0, 15, "focus_channel")
    integer(record["focus_note"], 0, 127, "focus_note")
    integer(record["active_count"], 0, 32, "active_count")
    integer(record["min_hold_cycles"], 0, (1 << 31) - 1,
            "min_hold_cycles")
    if executable and record["disposition"] == "PUBLISH":
        integer(record["left_pcm"], -(1 << 23), (1 << 23) - 1, "left_pcm")
        integer(record["right_pcm"], -(1 << 23), (1 << 23) - 1, "right_pcm")
        require(type(record["clipped"]) is bool, "CLIPPED_TYPE")
        require(record["pcm_provenance"] in (
            "INDEPENDENT_FROZEN_MATH", "SELFTEST_FIXTURE_ONLY"),
            "PCM_PROVENANCE")
    else:
        require(record["left_pcm"] is None and record["right_pcm"] is None
                and record["clipped"] is None, "NONPUBLISH_PAYLOAD")
        require(type(record["pcm_provenance"]) is str, "PCM_PROVENANCE_TYPE")


def validate_read_record(record: dict[str, Any], *, executable: bool) -> None:
    exact_keys(record, READ_FIELDS, "read")
    require(record["record"] == "READ", "READ_RECORD")
    integer(record["read_serial"], 0, (1 << 63) - 1, "read_serial")
    integer(record["plan_index"], 0, (1 << 63) - 1, "plan_index")
    integer(record["reset_lifetime"], 0, (1 << 31) - 1, "reset_lifetime")
    integer(record["slot"], 0, 31, "slot")
    require(type(record["occupied"]) is bool, "READ_OCCUPIED")
    require(type(record["releasing"]) is bool, "READ_RELEASING")
    integer(record["source"], 0, 15, "read.source")
    integer(record["channel"], 0, 15, "read.channel")
    integer(record["note"], 0, 127, "read.note")
    integer(record["generation"], 0, (1 << 32) - 1, "read.generation")
    if executable:
        integer(record["context"], 0, (1 << 74) - 1, "read.context")
        require(record["context_provenance"] in (
            "INDEPENDENT_FROZEN_MATH", "SELFTEST_FIXTURE_ONLY"),
            "READ_CONTEXT_PROVENANCE")
    else:
        require(record["context"] is None, "UNBOUND_READ_CONTEXT")
        require(type(record["context_provenance"]) is str,
                "READ_CONTEXT_PROVENANCE_TYPE")
