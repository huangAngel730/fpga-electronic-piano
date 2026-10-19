"""Reversible gzip parts: shared prewrite budget, explicit EOF, abort-safe close."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sys

import resources
from stream_bridge import CHUNK, Reject, parse_json, require

PART_LIMIT = 32 * CHUNK
DECODED_PART_LIMIT = 31 * CHUNK
DEFAULT_QUOTA = 24 * 1024 * CHUNK
STREAM_SUFFIXES = frozenset({".jsonl", ".csv"})


def _release(streams, budget, primary=None):
    first = primary
    for stream in streams:
        if stream is None:
            continue
        try:
            stream.close()
        except BaseException as error:
            if first is None:
                first = error
            else:
                budget.secondary(error)
    return first


def _atomic_json(path, value):
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    require(len(raw) <= CHUNK, "VOLUME_MANIFEST_TOO_LARGE")
    resources.accounting_mkdir(path.parent, parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with resources.accounting_open(temporary, "xb", "control") as stream:
        require(stream.write(raw) == len(raw), "VOLUME_MANIFEST_SHORT_WRITE")
        stream.flush()
        os.fsync(stream.fileno())
    resources.accounting_replace(temporary, path)


class _PartSink(io.RawIOBase):
    def __init__(self, path, store):
        super().__init__()
        self.path, self.store = path, store
        self.size, self.digest = 0, hashlib.sha256()
        self.current = None
        self.current = resources.accounting_open(path, "xb", "all_stores")

    def writable(self):
        return True

    def write(self, data):
        view, offset = memoryview(data).cast("B"), 0
        while offset < len(view):
            self.store.budget.check()
            block = view[offset:offset + CHUNK]
            take = len(block)
            require(self.size + take <= PART_LIMIT, "VOLUME_COMPRESSED_PART_LIMIT")
            self.store._reserve_local(take)
            require(self.current.write(block) == take, "VOLUME_SHORT_WRITE")
            self.digest.update(block)
            self.size += take
            offset += take
        return len(view)

    def close(self):
        if self.closed:
            return
        if self.current is None:
            super().close()
            return
        primary, first = sys.exc_info()[1], None
        try:
            self.current.flush()
            os.fsync(self.current.fileno())
        except BaseException as error:
            first = error
        first = _release((self.current,), self.store.budget, first)
        try:
            super().close()
        except BaseException as error:
            if first is None:
                first = error
            else:
                self.store.budget.secondary(error)
        if first is not None:
            if primary is None:
                raise first.with_traceback(first.__traceback__)
            self.store.budget.secondary(first)


class VolumeWriter(io.RawIOBase):
    def __init__(self, store, logical, exclusive):
        super().__init__()
        self.store, self.logical = store, logical
        self.sink = self.gzip = None
        self._ready, self._aborted, self._finished = False, False, False
        self._failure = None
        self.digest, self.count = hashlib.sha256(), 0
        self.parts, self.sequence, self.part_count = [], 0, 0
        self.folder = store.folder_for(logical)
        require(not self.folder.exists() if exclusive else True, "VOLUME_LOGICAL_EXISTS")
        resources.accounting_mkdir(self.folder, parents=True, exist_ok=False)
        try:
            self._open_part()
            self._ready = True
        except BaseException as error:
            self._failure = error
            self.abort(error)
            raise

    def writable(self):
        return True

    def tell(self):
        if self.closed:
            raise ValueError("I/O operation on closed logical volume")
        return self.count

    def _open_part(self):
        self.store.budget.check()
        path = self.folder / f"part-{self.sequence:06d}.gz"
        self.sink = _PartSink(path, self.store)
        self.gzip = gzip.GzipFile(filename="", mode="wb", fileobj=self.sink,
                                  compresslevel=6, mtime=0)
        self.part_digest, self.part_count = hashlib.sha256(), 0

    def _close_part(self):
        sink = self.sink
        error = _release((self.gzip, sink), self.store.budget)
        self.gzip = self.sink = None
        if error is not None:
            raise error.with_traceback(error.__traceback__)
        self.parts.append({
            "sequence": self.sequence,
            "logical_offset": self.count - self.part_count,
            "decoded_bytes": self.part_count,
            "decoded_sha256": self.part_digest.hexdigest(),
            "compressed": {"path": f"part-{self.sequence:06d}.gz",
                           "bytes": sink.size, "sha256": sink.digest.hexdigest()}})
        self.sequence += 1

    def write(self, data):
        if self._failure is not None:
            raise self._failure
        try:
            require(not self.closed and not self._aborted and self._ready,
                    "VOLUME_WRITER_CLOSED_OR_ABORTED")
            view, offset = memoryview(data).cast("B"), 0
            while offset < len(view):
                self.store.budget.check()
                if self.part_count == DECODED_PART_LIMIT:
                    self._close_part()
                    self._open_part()
                take = min(CHUNK, DECODED_PART_LIMIT - self.part_count, len(view) - offset)
                block = view[offset:offset + take]
                require(self.gzip.write(block) == take, "VOLUME_GZIP_SHORT_WRITE")
                self.digest.update(block)
                self.part_digest.update(block)
                self.count += take
                self.part_count += take
                offset += take
            return len(view)
        except BaseException as error:
            self._failure = error
            raise

    def abort(self, primary=None):
        if self.closed:
            return
        self._aborted = True
        error = _release((self.gzip, self.sink), self.store.budget, primary)
        self.gzip = self.sink = None
        try:
            super().close()
        except BaseException as secondary:
            if error is None:
                error = secondary
            else:
                self.store.budget.secondary(secondary)
        if error is not None and primary is None:
            raise error.with_traceback(error.__traceback__)

    def close(self):
        if self.closed:
            return
        active = sys.exc_info()[1]
        if active is not None or self._failure is not None or not self._ready:
            self.abort(active or self._failure)
            return
        try:
            self.store.budget.check()
            self._close_part()
            manifest = {
                "schema": "M3_R13_LOGICAL_VOLUME_V1",
                "logical_path": self.logical.relative_to(self.store.workspace).as_posix(),
                "format": "gzip_stream_split_binary", "physical_part_limit": PART_LIMIT,
                "decoded_part_limit": DECODED_PART_LIMIT, "io_request_limit": CHUNK,
                "original": {"bytes": self.count, "sha256": self.digest.hexdigest()},
                "parts": self.parts}
            _atomic_json(self.folder / "MANIFEST.json", manifest)
            self.store.entries[str(self.logical).casefold()] = manifest
            self._finished = True
            super().close()
        except BaseException as error:
            self._failure = error
            self.abort(error)
            raise

    def __exit__(self, kind, value, traceback):
        if kind is None:
            self.close()
        else:
            self.abort(value)
        return False

    def __del__(self):
        try:
            if hasattr(self, "store"):
                self.abort(self._failure)
        except BaseException:
            pass


class _VolumeTextWriter(io.TextIOWrapper):
    def __init__(self, raw, *, encoding, errors, newline):
        # This private writer has a fixed UTF-8, no-translation contract.
        require(encoding == "utf-8" and errors == "strict" and newline == "\n",
                "VOLUME_TEXT_ENCODING_CONTRACT")
        super().__init__(raw, encoding=encoding, errors=errors, newline=newline)
        self._logical_bytes_accepted = 0

    def tell(self):
        if self.closed:
            raise ValueError("I/O operation on closed logical volume")
        if self.buffer._failure is not None:
            raise self.buffer._failure
        # Include accepted text still buffered by TextIOWrapper without
        # flushing each CSV row into the gzip compressor.
        return self._logical_bytes_accepted

    def write(self, text):
        try:
            written = super().write(text)
            accepted = text[:written]
            self._logical_bytes_accepted += (len(accepted) if str.isascii(accepted)
                                            else len(str.encode(accepted, "utf-8", "strict")))
            return written
        except BaseException as error:
            self.buffer._failure = error
            raise

    def __exit__(self, kind, value, traceback):
        if kind is not None:
            raw = self.buffer
            raw.abort(value)
            try:
                super().close()
            except BaseException as secondary:
                raw.store.budget.secondary(secondary)
            return False
        self.close()
        return False

    def close(self):
        if self.closed:
            return
        active = sys.exc_info()[1]
        if active is not None:
            raw = self.buffer
            raw.abort(active)
            try:
                super().close()
            except BaseException as error:
                raw.store.budget.secondary(error)
            return
        super().close()

    def __del__(self):
        try:
            if not self.closed:
                raw = self.buffer
                raw.abort(raw._failure)
                try:
                    super().close()
                except BaseException as error:
                    raw.store.budget.secondary(error)
        except BaseException:
            pass


class _PartSource(io.RawIOBase):
    def __init__(self, path, expected, budget):
        super().__init__()
        self.budget, self.expected = budget, expected
        self.digest, self.count, self.eof = hashlib.sha256(), 0, False
        self.current = resources.accounting_open(path, "rb")

    def readable(self):
        return True

    def readinto(self, buffer):
        self.budget.check()
        view = memoryview(buffer).cast("B")
        require(len(view) <= CHUNK, "VOLUME_READ_BOUND")
        if not view:
            return 0
        data = self.current.read(len(view))
        if data:
            view[:len(data)] = data
            self.digest.update(data)
            self.count += len(data)
            require(self.count <= self.expected["bytes"], "VOLUME_COMPRESSED_SIZE")
        elif not self.eof:
            require({"bytes": self.count, "sha256": self.digest.hexdigest()} == self.expected,
                    "VOLUME_COMPRESSED_IDENTITY")
            self.eof = True
        return len(data)

    def verify_eof(self):
        scratch = bytearray(CHUNK)
        while self.readinto(scratch):
            pass

    def close(self):
        if self.closed:
            return
        primary = sys.exc_info()[1]
        error = _release((self.current,), self.budget)
        try:
            super().close()
        except BaseException as secondary:
            if error is None:
                error = secondary
            else:
                self.budget.secondary(secondary)
        if error is not None:
            if primary is None:
                raise error.with_traceback(error.__traceback__)
            self.budget.secondary(error)


class VolumeReader(io.RawIOBase):
    def __init__(self, store, logical, expected=None):
        super().__init__()
        self.store = store
        self.source = self.gzip = None
        self.manifest = store.manifest(logical)
        self.folder, self.parts = store.folder_for(logical), self.manifest["parts"]
        self.index, self.logical_offset = 0, 0
        self.expected = expected or self.manifest["original"]
        require({key: self.expected[key] for key in ("bytes", "sha256")} ==
                self.manifest["original"], "VOLUME_EXPECTED_MANIFEST_IDENTITY")
        self.digest, self.count, self.done = hashlib.sha256(), 0, False
        self.name, self.mode = str(logical), "rb"

    def _open_part(self):
        if self.index >= len(self.parts):
            return False
        self.store.budget.check()
        part = self.parts[self.index]
        require(part["sequence"] == self.index and part["logical_offset"] == self.logical_offset,
                "VOLUME_SEQUENCE_OR_OFFSET")
        compressed = part["compressed"]
        path = self.folder / compressed["path"]
        require(path.is_file(), "VOLUME_PART_MISSING")
        self.source = _PartSource(path, {"bytes": compressed["bytes"],
                                         "sha256": compressed["sha256"]}, self.store.budget)
        try:
            self.gzip = gzip.GzipFile(mode="rb", fileobj=self.source)
        except BaseException:
            self.source.close()
            raise
        self.part_digest, self.part_count = hashlib.sha256(), 0
        return True

    def _finish_part(self):
        part = self.parts[self.index]
        self.source.verify_eof()
        require(self.part_count == part["decoded_bytes"] and
                self.part_digest.hexdigest() == part["decoded_sha256"],
                "VOLUME_DECODED_PART_IDENTITY")
        error = _release((self.gzip, self.source), self.store.budget)
        self.source = self.gzip = None
        if error is not None:
            raise error.with_traceback(error.__traceback__)
        self.logical_offset += self.part_count
        self.index += 1

    def readable(self):
        return True

    def readinto(self, buffer):
        self.store.budget.check()
        view = memoryview(buffer).cast("B")
        require(len(view) <= CHUNK, "VOLUME_READ_BOUND")
        if not view:
            return 0
        while True:
            if self.gzip is None and not self._open_part():
                if not self.done:
                    require({"bytes": self.count, "sha256": self.digest.hexdigest()} ==
                            {key: self.expected[key] for key in ("bytes", "sha256")},
                            "VOLUME_DECODED_IDENTITY")
                    self.done = True
                return 0
            try:
                data = self.gzip.read(len(view))
            except (gzip.BadGzipFile, EOFError) as error:
                raise Reject("VOLUME_GZIP_DECODE:" + str(error)) from error
            if not data:
                self._finish_part()
                continue
            view[:len(data)] = data
            self.digest.update(data)
            self.part_digest.update(data)
            self.count += len(data)
            self.part_count += len(data)
            require(self.count <= self.expected["bytes"] and
                    self.part_count <= self.parts[self.index]["decoded_bytes"],
                    "VOLUME_DECODED_SIZE")
            return len(data)

    def close(self):
        if self.closed:
            return
        primary = sys.exc_info()[1]
        error = _release((self.gzip, self.source), self.store.budget)
        self.gzip = self.source = None
        try:
            super().close()
        except BaseException as secondary:
            if error is None:
                error = secondary
            else:
                self.store.budget.secondary(secondary)
        if error is not None:
            if primary is None:
                raise error.with_traceback(error.__traceback__)
            self.store.budget.secondary(error)


def _sha(value):
    return (type(value) is str and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


class VolumeStore:
    def __init__(self, workspace: Path, quota_bytes=DEFAULT_QUOTA, *, budget=None):
        require(type(quota_bytes) is int and 0 < quota_bytes <= DEFAULT_QUOTA, "VOLUME_QUOTA")
        shared = resources.get_budget()
        require(budget is None or budget is shared, "ONE_PROCESS_GLOBAL_BUDGET_REQUIRED")
        self.budget = self.quota = shared
        self._local_limit, self._local_attempted = quota_bytes, 0
        self.workspace = Path(workspace).resolve()
        self.root = self.workspace / ".r13_volumes"
        resources.accounting_mkdir(self.root, parents=True, exist_ok=True)
        self.entries = {}

    def _reserve_local(self, count):
        require(self._local_attempted + count <= self._local_limit, "WORKSPACE_QUOTA_EXCEEDED")
        self._local_attempted += count  # additional tighter cap, no separate global grant

    def folder_for(self, logical: Path) -> Path:
        logical = Path(logical).resolve()
        require(logical != self.workspace and logical.is_relative_to(self.workspace), "VOLUME_LOGICAL_SCOPE")
        relative = logical.relative_to(self.workspace).as_posix()
        return self.root / hashlib.sha256(relative.casefold().encode("utf-8")).hexdigest()

    def is_volume(self, logical: Path) -> bool:
        return self.folder_for(logical).joinpath("MANIFEST.json").is_file()

    def manifest(self, logical: Path) -> dict:
        self.budget.check()
        key = str(Path(logical).resolve()).casefold()
        if key in self.entries:
            return self.entries[key]
        path = self.folder_for(logical) / "MANIFEST.json"
        require(path.is_file() and path.stat().st_size <= CHUNK, "VOLUME_MANIFEST_MISSING_OR_LARGE")
        with resources.accounting_open(path, "rb") as stream:
            raw = stream.read(CHUNK)
            require(not stream.read(1), "VOLUME_MANIFEST_TOO_LARGE")
        value = parse_json(raw)
        require(type(value) is dict and set(value) == {
            "schema", "logical_path", "format", "physical_part_limit", "decoded_part_limit",
            "io_request_limit", "original", "parts"} and
            value["schema"] == "M3_R13_LOGICAL_VOLUME_V1" and
            value["format"] == "gzip_stream_split_binary" and
            value["physical_part_limit"] == PART_LIMIT and
            value["decoded_part_limit"] == DECODED_PART_LIMIT and
            value["io_request_limit"] == CHUNK and
            value["logical_path"] == Path(logical).resolve().relative_to(self.workspace).as_posix() and
            type(value["original"]) is dict and set(value["original"]) == {"bytes", "sha256"} and
            type(value["original"]["bytes"]) is int and value["original"]["bytes"] >= 0 and
            _sha(value["original"]["sha256"]) and type(value["parts"]) is list and
            0 < len(value["parts"]) <= resources.MAX_PAYLOAD_PARTS, "VOLUME_MANIFEST_BINDING")
        offset = 0
        for sequence, part in enumerate(value["parts"]):
            require(type(part) is dict and set(part) == {
                "sequence", "logical_offset", "decoded_bytes", "decoded_sha256", "compressed"}
                and type(part["compressed"]) is dict and
                set(part["compressed"]) == {"path", "bytes", "sha256"}, "VOLUME_PART_DESCRIPTOR")
            require(type(part["sequence"]) is int and part["sequence"] == sequence and
                    type(part["logical_offset"]) is int and part["logical_offset"] == offset,
                    "VOLUME_SEQUENCE_OR_OFFSET")
            require(type(part["decoded_bytes"]) is int and 0 <= part["decoded_bytes"] <= DECODED_PART_LIMIT and
                    _sha(part["decoded_sha256"]) and
                    part["compressed"]["path"] == f"part-{sequence:06d}.gz" and
                    type(part["compressed"]["bytes"]) is int and 0 < part["compressed"]["bytes"] <= PART_LIMIT and
                    _sha(part["compressed"]["sha256"]), "VOLUME_PART_BOUNDS_OR_NAME")
            offset += part["decoded_bytes"]
        require(offset == value["original"]["bytes"], "VOLUME_PART_WHOLE_LENGTH")
        self.entries[key] = value
        return value

    def open(self, logical: Path, mode="rb", expected=None):
        self.budget.check()
        logical = Path(logical).resolve()
        if mode in ("xb", "x", "xt", "wb", "w", "wt"):
            require(logical.suffix.casefold() in STREAM_SUFFIXES, "VOLUME_ROLE_NOT_STREAM")
            raw = VolumeWriter(self, logical, "x" in mode)
            return raw if "b" in mode else _VolumeTextWriter(
                raw, encoding="utf-8", errors="strict", newline="\n")
        require(mode in ("rb", "r", "rt"), "VOLUME_OPEN_MODE")
        buffered = io.BufferedReader(VolumeReader(self, logical, expected), buffer_size=CHUNK)
        return buffered if "b" in mode else io.TextIOWrapper(
            buffered, encoding="utf-8", errors="strict", newline=None)

    def descriptor(self, logical: Path) -> dict:
        return dict(self.manifest(logical)["original"])

    def physical_bytes(self) -> int:
        return sum(path.stat().st_size for path in self.root.rglob("*") if path.is_file())
