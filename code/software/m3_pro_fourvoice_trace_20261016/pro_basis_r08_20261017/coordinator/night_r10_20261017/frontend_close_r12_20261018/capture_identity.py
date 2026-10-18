"""Private bounded artifact IO; frozen helpers and global pathlib stay unchanged."""
import hashlib
import io
from pathlib import Path

import json_identity as ji

ROOT, OUTPUT = ji.ROOT, ji.OUTPUT
MAX_LOGICAL_READ = 16 * ji.CHUNK + 1
STREAM_ROLES = frozenset({
    "raw", "raw_capture", "public_rows", "stdout", "stderr", "resets",
    "reset_edges", "pins", "raw_pins", "pin_capture", "raw_edges",
    "capture_stdout", "capture_stderr",
})


def identity_fields(stamp):
    return {key: stamp[key] for key in ("bytes", "sha256")}


class MemoryReader(io.BytesIO):
    def __init__(self, raw, name):
        super().__init__(raw)
        self.name = str(name)


class ArtifactReader(io.RawIOBase):
    """One sequential handle, bounded physical reads, verified EOF.

    Normal close drains this same handle and reports drained bytes separately.
    Exception unwinding records incomplete identity without claiming verified EOF.
    """
    def __init__(self, policy, path, expected, streaming):
        super().__init__()
        self.policy, self.path = policy, path
        self.expected, self.streaming = expected, streaming
        self.source = None
        self.digest, self.count = hashlib.sha256(), 0
        self.pending, self.position = bytearray(), 0
        self.eof, self.verified, self.reported = False, False, False
        self.drained = 0
        self.drain_on_close = True
        self.name, self.mode = str(path), "rb"
        self.source = path.open("rb", buffering=0)

    def readable(self):
        return True

    def writable(self):
        return False

    def seekable(self):
        return False

    def tell(self):
        return self.position

    def seek(self, *args):
        raise ji.Reject("R12_ARTIFACT_SEEK_FORBIDDEN")

    def fileno(self):
        raise ji.Reject("R12_ARTIFACT_FILENO_FORBIDDEN")

    def pull(self, size):
        ji.require(not self.closed, "R12_STREAM_CLOSED")
        if self.eof:
            return b""
        block = self.policy.pull(self.source, min(size, ji.CHUNK))
        self.count += len(block)
        self.digest.update(block)
        if self.expected is not None:
            ji.require(self.count <= self.expected["bytes"], "R12_STREAM_SIZE_CHANGED")
        if not block:
            self.eof = True
            actual = {"bytes": self.count, "sha256": self.digest.hexdigest()}
            ji.require(self.expected is None or actual == identity_fields(self.expected),
                       "R12_STREAM_IDENTITY_MISMATCH")
            self.verified = self.expected is not None
        return block

    def read(self, size=-1):
        ji.require(type(size) is int, "R12_READ_SIZE")
        if size < 0:
            if self.streaming:
                self.policy.metrics["whole_read_rejected"] += 1
                raise ji.Reject("R12_WHOLE_STREAM_READ_FORBIDDEN")
            parts, count = [], 0
            while True:
                block = self.read(ji.CHUNK)
                count += len(block)
                ji.require(count <= ji.MAX_JSON, "R12_BUFFER_ROLE_BOUND")
                if not block:
                    break
                parts.append(block)
            return b"".join(parts)
        # Legacy bounded_metadata uses read(16MiB+1). This is a bounded
        # logical buffer, not permission for an equally large physical read.
        ji.require(0 <= size <= MAX_LOGICAL_READ, "R12_STREAM_READ_REQUEST_BOUND")
        if not size:
            return b""
        parts, remaining = [], size
        if self.pending:
            take = min(remaining, len(self.pending))
            parts.append(bytes(self.pending[:take]))
            del self.pending[:take]
            remaining -= take
        while remaining and not self.eof:
            block = self.pull(remaining)
            if not block:
                break
            parts.append(block)
            remaining -= len(block)
        result = b"".join(parts)
        self.position += len(result)
        return result

    read1 = read

    def readall(self):
        return self.read()

    def readlines(self, hint=-1):
        if self.streaming:
            self.policy.metrics["whole_read_rejected"] += 1
            raise ji.Reject("R12_WHOLE_STREAM_READ_FORBIDDEN")
        return super().readlines(hint)

    def readinto(self, buffer):
        view = memoryview(buffer).cast("B")
        data = self.read(min(len(view), ji.CHUNK))
        view[:len(data)] = data
        return len(data)

    readinto1 = readinto

    def readline(self, size=-1):
        ji.require(type(size) is int, "R12_READLINE_SIZE")
        unlimited = size < 0
        limit = ji.MAX_JSON + 1 if unlimited else size
        ji.require(0 <= limit <= ji.MAX_JSON + 1, "R12_LOGICAL_LINE_BOUND")
        parts, remaining = [], limit
        while remaining:
            if not self.pending:
                block = self.pull(min(remaining, ji.CHUNK))
                if not block:
                    break
                self.pending.extend(block)
            stop = self.pending.find(b"\n", 0, remaining)
            take = stop + 1 if stop >= 0 else min(remaining, len(self.pending))
            parts.append(bytes(self.pending[:take]))
            del self.pending[:take]
            remaining -= take
            if stop >= 0:
                break
        result = b"".join(parts)
        self.position += len(result)
        # Explicit readline(MAX+1) leaves the old parser's MAX rejection intact.
        ji.require(not unlimited or len(result) < limit or result.endswith(b"\n"),
                   "R12_LOGICAL_LINE_BOUND")
        return result

    def report(self):
        if not self.reported:
            self.reported = True
            self.policy.metrics["streams"].append({
                "path": str(self.path), "bytes": self.count,
                "sha256": self.digest.hexdigest(), "bytes_returned": self.position,
                "drained_bytes": self.drained, "buffered_unreturned": len(self.pending),
                "eof": self.eof, "digest_complete": self.eof,
                "verified": self.verified,
                "declared": bool(self.policy.expected(self.path)
                                 and self.policy.expected(self.path)["declared"]),
            })
            if self.verified:
                self.policy.metrics["stream_verified"] += 1

    def finish(self, drain):
        if self.closed:
            return
        if self.source is None:
            super().close()
            return
        try:
            if drain:
                self.drained += len(self.pending)
                self.pending.clear()
                while not self.eof:
                    self.drained += len(self.pull(ji.CHUNK))
        finally:
            self.report()
            self.source.close()
            super().close()

    def close(self):
        self.finish(self.drain_on_close)

    def __exit__(self, exc_type, exc_value, traceback):
        self.finish(exc_type is None)
        return False


class ArtifactTextReader(io.TextIOWrapper):
    """Text iteration has the same logical row and whole-read bounds."""
    def __init__(self, reader, streaming, **kwargs):
        self.streaming = streaming
        self.policy = reader.policy if isinstance(reader, ArtifactReader) else None
        super().__init__(reader, **kwargs)

    def read(self, size=-1):
        if self.streaming:
            if size < 0:
                self.policy.metrics["whole_read_rejected"] += 1
                raise ji.Reject("R12_WHOLE_STREAM_READ_FORBIDDEN")
            ji.require(type(size) is int and size <= MAX_LOGICAL_READ,
                       "R12_STREAM_READ_REQUEST_BOUND")
        return super().read(size)

    def readline(self, size=-1):
        if not self.streaming:
            return super().readline(size)
        unlimited = size < 0
        limit = ji.MAX_JSON + 1 if unlimited else size
        ji.require(type(limit) is int and 0 <= limit <= ji.MAX_JSON + 1,
                   "R12_LOGICAL_LINE_BOUND")
        line = super().readline(limit)
        ji.require(not unlimited or len(line) < limit or line.endswith("\n"),
                   "R12_LOGICAL_LINE_BOUND")
        return line

    def readlines(self, hint=-1):
        if self.streaming:
            self.policy.metrics["whole_read_rejected"] += 1
            raise ji.Reject("R12_WHOLE_STREAM_READ_FORBIDDEN")
        return super().readlines(hint)

    def __next__(self):
        line = self.readline()
        if not line:
            raise StopIteration
        return line

    def __exit__(self, exc_type, exc_value, traceback):
        if isinstance(self.buffer, ArtifactReader):
            self.buffer.drain_on_close = exc_type is None
        return super().__exit__(exc_type, exc_value, traceback)


class ArtifactPath:
    """Composition proxy; inject only at the private helpers' Path boundaries."""
    def __init__(self, policy, value):
        self.policy, self.value = policy, Path(value)

    def __fspath__(self):
        return str(self.value)

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return "ArtifactPath(" + repr(str(self.value)) + ")"

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        try:
            return self.value == Path(other)
        except TypeError:
            return False

    def __truediv__(self, other):
        return self.policy.path(self.value / other)

    def __rtruediv__(self, other):
        return self.policy.path(Path(other) / self.value)

    @property
    def parent(self):
        return self.policy.path(self.value.parent)

    @property
    def parents(self):
        return tuple(self.policy.path(p) for p in self.value.parents)

    def __getattr__(self, name):
        target = getattr(self.value, name)
        if not callable(target):
            return self.policy.path(target) if isinstance(target, Path) else target
        ji.require(name in {
            "as_posix", "as_uri", "match", "full_match", "is_absolute",
            "is_reserved", "is_relative_to", "relative_to", "resolve",
            "absolute", "expanduser", "with_name", "with_stem", "with_suffix",
            "joinpath", "stat", "lstat", "exists", "is_file", "is_dir",
            "is_symlink", "is_junction", "is_mount", "is_block_device",
            "is_char_device", "is_fifo", "is_socket", "samefile", "owner",
            "group", "readlink",
        }, "R12_UNSUPPORTED_PATH_OPERATION:" + name)
        def method(*args, **kwargs):
            result = target(*args, **kwargs)
            return self.policy.path(result) if isinstance(result, Path) else result
        return method

    def iterdir(self):
        return (self.policy.path(p) for p in self.value.iterdir())

    def glob(self, pattern, **kwargs):
        return (self.policy.path(p) for p in self.value.glob(pattern, **kwargs))

    def rglob(self, pattern, **kwargs):
        return (self.policy.path(p) for p in self.value.rglob(pattern, **kwargs))

    def walk(self, *args, **kwargs):
        for directory, names, files in self.value.walk(*args, **kwargs):
            yield self.policy.path(directory), names, files

    def mkdir(self, *args, **kwargs):
        return self.policy.write_path(self.value).mkdir(*args, **kwargs)

    def touch(self, *args, **kwargs):
        return self.policy.write_path(self.value).touch(*args, **kwargs)

    def unlink(self, *args, **kwargs):
        return self.policy.write_path(self.value).unlink(*args, **kwargs)

    def rmdir(self):
        return self.policy.write_path(self.value).rmdir()

    def rename(self, target):
        result = self.policy.write_path(self.value).rename(self.policy.write_path(target))
        return self.policy.path(result)

    def replace(self, target):
        result = self.policy.write_path(self.value).replace(self.policy.write_path(target))
        return self.policy.path(result)

    def open(self, mode="r", *args, **kwargs):
        return self.policy.open(self.value, mode, *args, **kwargs)

    def read_bytes(self):
        return self.policy.read_bytes(self.value)

    def read_text(self, encoding=None, errors=None, newline=None):
        with self.open("r", encoding=encoding or "utf-8",
                       errors=errors or "strict", newline=newline) as stream:
            return stream.read()

    def write_bytes(self, data):
        with self.open("wb") as stream:
            return stream.write(data)

    def write_text(self, data, encoding=None, errors=None, newline=None):
        with self.open("w", encoding=encoding or "utf-8",
                       errors=errors or "strict", newline=newline) as stream:
            return stream.write(data)


class ArtifactIO:
    """Shared stamp/root/external/declared registry and per-invocation metrics.

    Plain pathlib.Path(proxy) discards interception. The private loader must
    route every old Path construction/read boundary through this policy.
    """
    def __init__(self, registry):
        ji.require(type(registry) is dict, "R12_IDENTITY_REGISTRY")
        self.registry = registry
        self.metrics = {"calls": 0, "bytes": 0, "max_request": 0, "opens": 0,
                        "json_verified": 0, "stream_verified": 0,
                        "whole_read_rejected": 0, "streams": []}

    def pull(self, stream, size):
        ji.require(type(size) is int and 0 < size <= ji.CHUNK, "READ_REQUEST_BOUND")
        self.metrics["calls"] += 1
        self.metrics["max_request"] = max(self.metrics["max_request"], size)
        block = ji.chunk_read(stream, size)
        self.metrics["bytes"] += len(block)
        return block

    def expected(self, value):
        return self.registry.get(str(ji.safe_path(value)).casefold())

    def register(self, descriptor, root=ROOT, *, external=False, declared=True, role=None):
        ji.require(type(descriptor) is dict
                   and {"path", "bytes", "sha256"} <= descriptor.keys(), "FILE_DESCRIPTOR")
        ref = {key: descriptor[key] for key in ("path", "bytes", "sha256")}
        path = ji.validated_path(ref, root, allow_external=external)
        stamp = {"path": str(path), **identity_fields(ref)}
        key, prior = str(path).casefold(), self.expected(path)
        ji.require(prior is None or identity_fields(prior["stamp"]) == identity_fields(stamp),
                   "CONFLICTING_PATH_IDENTITY")
        roles = set(prior.get("roles", [])) if prior else set()
        if role is not None:
            ji.require(type(role) is str and bool(role), "R12_ARTIFACT_ROLE")
            roles.add(role)
        self.registry[key] = {
            "stamp": stamp, "root": ji.safe_path(root), "external": external,
            "declared": bool(declared or (prior and prior["declared"])),
            "roles": sorted(roles),
        }
        return path

    def bind(self, roles):
        ji.require(type(roles) is dict, "R12_ARTIFACT_BINDINGS")
        for role, descriptor in roles.items():
            self.register(descriptor, role=role)
        return self

    def path(self, value, *parts):
        if isinstance(value, ArtifactPath) and value.policy is self and not parts:
            return value
        return ArtifactPath(self, Path(value, *parts))

    def write_path(self, value):
        path = ji.safe_path(value)
        ji.require(path != ji.safe_path(OUTPUT) and path.is_relative_to(ji.safe_path(OUTPUT)),
                   "R12_WRITE_SCOPE")
        return path

    def streaming(self, path, entry=None):
        roles = entry.get("roles", []) if entry else []
        return bool(set(roles) & STREAM_ROLES) or path.suffix.casefold() == ".jsonl"

    def json_record(self, value, max_bytes=ji.MAX_JSON):
        path = ji.safe_path(value)
        ji.require(type(max_bytes) is int and 0 < max_bytes <= ji.MAX_JSON, "JSON_BOUND_CONFIG")
        entry = self.expected(path)
        ji.require(not self.streaming(path, entry), "R12_STREAM_NOT_CONTROL_JSON")
        expected = entry["stamp"] if entry else None
        if expected:
            ji.require(expected["bytes"] <= max_bytes, "JSON_BOUND")
        parts, count = [], 0
        self.metrics["opens"] += 1
        with path.open("rb", buffering=0) as stream:
            while True:
                block = self.pull(stream, min(ji.CHUNK, max_bytes + 1 - count))
                if not block:
                    break
                count += len(block)
                ji.require(count <= max_bytes, "JSON_BOUND")
                parts.append(block)
        record = ji.JSONRecord(b"".join(parts), expected)
        self.metrics["json_verified"] += 1
        return record

    def identity(self, value):
        path = ji.safe_path(value)
        entry = self.expected(path)
        self.metrics["opens"] += 1
        reader = ArtifactReader(self, path, entry["stamp"] if entry else None, True)
        with reader:
            while reader.read(ji.CHUNK):
                pass
        return {"bytes": reader.count, "sha256": reader.digest.hexdigest()}

    def read_bytes(self, value):
        path = ji.safe_path(value)
        entry = self.expected(path)
        if self.streaming(path, entry) or path.stat().st_size > ji.MAX_JSON:
            self.metrics["whole_read_rejected"] += 1
            raise ji.Reject("R12_WHOLE_STREAM_READ_FORBIDDEN")
        if path.suffix.casefold() == ".json":
            return self.json_record(path).raw
        with self.open(path, "rb") as stream:
            return stream.read()

    def open(self, value, mode="r", buffering=-1, encoding=None, errors=None,
             newline=None, **kwargs):
        path = ji.safe_path(value)
        ji.require(type(mode) is str and mode and not kwargs, "R12_OPEN_OPTIONS")
        if any(flag in mode for flag in "wax+"):
            self.write_path(path)
            return path.open(mode, buffering=buffering, encoding=encoding,
                             errors=errors, newline=newline)
        ji.require(mode in ("r", "rt", "rb"), "R12_READ_ONLY_MODE")
        entry = self.expected(path)
        streaming = self.streaming(path, entry)
        if path.suffix.casefold() == ".json" and not streaming:
            reader = MemoryReader(self.json_record(path).raw, path)
        else:
            self.metrics["opens"] += 1
            reader = ArtifactReader(self, path, entry["stamp"] if entry else None,
                                    streaming or path.stat().st_size > ji.MAX_JSON)
        if "b" in mode:
            ji.require(encoding is None and errors is None and newline is None,
                       "R12_BINARY_OPEN_OPTIONS")
            return reader
        return ArtifactTextReader(reader, isinstance(reader, ArtifactReader) and reader.streaming,
                                  encoding=encoding or "utf-8",
                                  errors=errors or "strict", newline=newline)


class IdentityFacade:
    def __init__(self, original, loader, registry, io_policy=None):
        self._original, self._loader, self._expected = original, loader, registry
        self.io = io_policy if io_policy is not None else ArtifactIO(registry)
        ji.require(self.io.registry is registry, "R12_SHARED_REGISTRY_REQUIRED")
        self.observations = []

    def __getattr__(self, name):
        return getattr(self._original, name)

    def identity(self, path):
        path = ji.safe_path(path)
        result = self.io.identity(path)
        self.io.register({"path": str(path), **result}, declared=False,
                         external=not path.is_relative_to(ROOT))
        self.observations.append({"operation": "identity", "path": str(path), **result})
        return result

    def ref(self, path):
        path = ji.safe_path(path)
        return {"path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
                **self.identity(path)}

    artifact = ref
    descriptor = ref

    def checked(self, descriptor, root=ROOT, allow_external=False):
        path = self.io.register(descriptor, root, external=allow_external)
        self.io.identity(path)
        return self.io.path(path)

    checked_descriptor = checked

    def read(self, path, max_bytes=ji.MAX_JSON):
        actual = ji.safe_path(path)
        expected = self.io.expected(actual)
        record = self.io.json_record(actual, min(max_bytes, ji.MAX_JSON))
        self.observations.append({
            "operation": "same_buffer_json", "path": str(actual),
            "frozen_descriptor": bool(expected and expected["declared"]),
            "bound_previous_observation": expected is not None, **record.stamp,
        })
        return record.value

    read_json = read
    read_request = read

    def no_alias(self, path):
        return self.io.path(ji.safe_path(path))

    def output_directory(self, path):
        path = ji.safe_path(path)
        ji.require(path != OUTPUT and path.is_relative_to(OUTPUT), "R12_OUTPUT_SCOPE")
        path.mkdir(parents=True, exist_ok=False)
        return self.io.path(path)

    def save(self, path, value):
        path = ji.safe_path(path)
        ji.require(path.is_relative_to(OUTPUT) and path != OUTPUT, "R12_WRITE_SCOPE")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            import json
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")

    write_json = save

    def load_source(self, path, expected_sha=None, module_name=None):
        return self._loader(path, expected_sha, module_name)

    def load(self, descriptor, name):
        path = self.checked(descriptor)
        return self._loader(path, descriptor["sha256"], name)

    loads = staticmethod(ji.parse)
    require = staticmethod(ji.require)
