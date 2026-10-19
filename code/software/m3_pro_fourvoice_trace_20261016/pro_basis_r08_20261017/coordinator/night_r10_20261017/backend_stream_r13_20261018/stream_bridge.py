"""Bounded binary helpers shared by the R13 backend successor.

This module deliberately contains no D4 substitute.  It supplies strict
same-buffer JSON controls and byte identities for the private frozen chain.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

CHUNK = 1024 * 1024
MAX_CONTROL = 8 * CHUNK


class Reject(ValueError):
    """Fail-closed contract rejection."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise Reject(reason)


def _pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "DUPLICATE_JSON_KEY:" + key)
        result[key] = value
    return result


def _finite(value):
    value = float(value)
    require(math.isfinite(value), "NONFINITE_JSON")
    return value


def parse_json(raw: bytes):
    return json.loads(raw, object_pairs_hook=_pairs, parse_float=_finite,
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          Reject("NONFINITE_JSON")))


def read_control(path: Path, expected_sha256: str | None = None,
                 limit: int = MAX_CONTROL) -> dict:
    """Read, identify and parse exactly one bounded byte buffer."""
    require(type(limit) is int and 0 < limit <= MAX_CONTROL, "CONTROL_LIMIT")
    digest, blocks, count = hashlib.sha256(), [], 0
    with Path(path).resolve().open("rb", buffering=0) as stream:
        while True:
            block = stream.read(min(CHUNK, limit + 1 - count))
            if not block:
                break
            count += len(block)
            require(count <= limit, "CONTROL_TOO_LARGE")
            digest.update(block)
            blocks.append(block)
    raw = b"".join(blocks)
    stamp = {"bytes": count, "sha256": digest.hexdigest()}
    if expected_sha256 is not None:
        require(stamp["sha256"] == expected_sha256, "CONTROL_SHA256")
    return {"raw": raw, "stamp": stamp, "value": parse_json(raw)}


def read_descriptor_json(descriptor: dict, root: Path) -> dict:
    require(type(descriptor) is dict and set(descriptor) ==
            {"path", "bytes", "sha256"}, "DESCRIPTOR")
    value = Path(descriptor["path"])
    path = (value if value.is_absolute() else Path(root) / value).resolve()
    require(path.is_file(), "DESCRIPTOR_FILE")
    record = read_control(path, descriptor["sha256"])
    require(record["stamp"]["bytes"] == descriptor["bytes"],
            "DESCRIPTOR_BYTES")
    return record


def identity(path: Path) -> dict:
    digest, count = hashlib.sha256(), 0
    with Path(path).resolve().open("rb", buffering=0) as stream:
        while True:
            block = stream.read(CHUNK)
            if not block:
                break
            require(len(block) <= CHUNK, "READ_REQUEST_BOUND")
            digest.update(block)
            count += len(block)
    return {"bytes": count, "sha256": digest.hexdigest()}


def iter_bytes(stream, size: int = CHUNK):
    require(type(size) is int and 0 < size <= CHUNK, "READ_REQUEST_BOUND")
    while True:
        block = stream.read(size)
        if not block:
            return
        require(len(block) <= CHUNK, "READ_REQUEST_BOUND")
        yield block


def strict_child(root: Path, value: Path) -> Path:
    root, value = Path(root).resolve(), Path(value).resolve()
    require(value != root and value.is_relative_to(root), "OUTPUT_SCOPE")
    return value
