"""R12 bounded same-buffer JSON and streaming identities; NOT runtime validated."""
from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import tempfile

ROOT = Path(__file__).resolve().parents[7]
OUTPUT = ROOT / "code/output/m3_frontend_close_r12_20261018"
MAX_JSON = 8 * 1024 * 1024
CHUNK = 1024 * 1024
READ_METRICS = {"calls": 0, "bytes": 0, "max_request": 0}


class Reject(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Reject(reason)


def safe_path(value):
    path = Path(value)
    require(not str(path).startswith(("\\\\", "\\??\\")), "ALIAS_OR_DEVICE")
    for part in path.parts:
        require(part.rstrip(" .") == part and not re.fullmatch(
            r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part), "ALIAS_OR_DEVICE")
    for item in (path, *path.parents):
        require(not item.is_symlink() and not item.is_junction(), "ALIAS_OR_DEVICE")
    return path.resolve()


def relative(value):
    require(type(value) is str and value and "\\" not in value and ":" not in value, "RELATIVE_PATH")
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.as_posix() == value and value != "."
            and not any(p in ("..", ".git", ".aws", ".codex") for p in path.parts), "RELATIVE_PATH")
    return value


def validated_path(ref, root=ROOT, *, relative_only=False, allow_external=False):
    require(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}, "DESCRIPTOR")
    require(type(ref["bytes"]) is int and ref["bytes"] >= 0
            and type(ref["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", ref["sha256"]), "DESCRIPTOR_IDENTITY")
    name = relative(ref["path"]) if relative_only else ref["path"]
    require(type(name) is str and bool(name), "DESCRIPTOR_PATH")
    root = safe_path(root)
    path = Path(name)
    path = safe_path(path if path.is_absolute() else root / path)
    require((allow_external or path.is_relative_to(root)) and path.is_file(), "DESCRIPTOR_SCOPE")
    return path


def chunk_read(stream, size=CHUNK):
    require(type(size) is int and 0 < size <= CHUNK, "READ_REQUEST_BOUND")
    READ_METRICS["calls"] += 1
    READ_METRICS["max_request"] = max(READ_METRICS["max_request"], size)
    block = stream.read(size)
    READ_METRICS["bytes"] += len(block)
    return block


def identity(path):
    sha, count = hashlib.sha256(), 0
    with safe_path(path).open("rb") as stream:
        while True:
            block = chunk_read(stream)
            if not block:
                break
            sha.update(block)
            count += len(block)
    return {"bytes": count, "sha256": sha.hexdigest()}


def checked(ref, root=ROOT, **kwargs):
    path = validated_path(ref, root, **kwargs)
    require(identity(path) == {key: ref[key] for key in ("bytes", "sha256")}, "FILE_CHANGED:" + str(path))
    return path


def pairs(items):
    value = {}
    for key, entry in items:
        require(key not in value, "DUPLICATE_JSON_KEY")
        value[key] = entry
    return value


def finite_float(value):
    result = float(value)
    require(math.isfinite(result), "NONFINITE_JSON")
    return result


def parse(raw):
    return json.loads(raw, object_pairs_hook=pairs, parse_float=finite_float,
                      parse_constant=lambda _: (_ for _ in ()).throw(Reject("NONFINITE_JSON")))


class JSONRecord:
    __slots__ = ("raw", "stamp", "value")

    def __init__(self, raw, expected=None):
        self.raw = raw
        self.stamp = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        if expected is not None:
            require(self.stamp == {k: expected[k] for k in self.stamp}, "JSON_IDENTITY_MISMATCH")
        self.value = parse(raw)


def read_stream_json(stream, expected=None, max_bytes=MAX_JSON):
    require(type(max_bytes) is int and 0 < max_bytes <= MAX_JSON, "JSON_BOUND_CONFIG")
    blocks, count = [], 0
    while True:
        block = chunk_read(stream, min(CHUNK, max_bytes + 1 - count))
        if not block:
            break
        count += len(block)
        require(count <= max_bytes, "JSON_BOUND")
        blocks.append(block)
    return JSONRecord(b"".join(blocks), expected)


def read_control(path, max_bytes=MAX_JSON):
    with safe_path(path).open("rb") as stream:
        return read_stream_json(stream, max_bytes=max_bytes)


def read_verified(ref, root=ROOT, *, relative_only=False, allow_external=False):
    path = validated_path(ref, root, relative_only=relative_only, allow_external=allow_external)
    require(ref["bytes"] <= MAX_JSON, "JSON_BOUND")
    with path.open("rb") as stream:
        return read_stream_json(stream, ref)


@contextmanager
def frozen_archive(ref, root=ROOT):
    """Copy and hash the same archive stream; decisions use only private copy."""
    # Application inputs may spell a repository-contained path absolutely.
    # Both forms retain alias checks and the same strict root containment.
    path = validated_path(ref, root, allow_external=False)
    if not Path(ref["path"]).is_absolute():
        relative(ref["path"])
    # Absolute spelling does not grant access to otherwise forbidden members.
    relative(path.relative_to(safe_path(root)).as_posix())
    require(ref["bytes"] <= 256 * 1024 * 1024, "ARCHIVE_BOUND")
    folder = safe_path(OUTPUT / "private_archive_snapshots")
    require(folder.is_relative_to(safe_path(OUTPUT)), "ARCHIVE_SNAPSHOT_SCOPE")
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="r12_", dir=folder) as temporary:
        snapshot = Path(temporary) / "archive.zip"
        sha, count = hashlib.sha256(), 0
        with path.open("rb") as source, snapshot.open("xb") as target:
            while True:
                block = chunk_read(source)
                if not block:
                    break
                count += len(block)
                require(count <= ref["bytes"], "ARCHIVE_SIZE_CHANGED")
                sha.update(block)
                target.write(block)
        require({"bytes": count, "sha256": sha.hexdigest()} ==
                {k: ref[k] for k in ("bytes", "sha256")}, "ARCHIVE_IDENTITY_MISMATCH")
        yield snapshot
