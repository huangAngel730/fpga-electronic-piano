"""Private, source-pinned R12 -> R11 -> R10 -> real D4 binding.

Only private module dictionaries are adapted.  Frozen files and canonical
``sys.modules`` entries are never changed.
"""
from __future__ import annotations

import builtins
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import uuid
import zipfile

import resources
from stream_bridge import CHUNK, Reject, require
from volume_io import STREAM_SUFFIXES, VolumeStore

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]
R12 = HERE.parent / "frontend_close_r12_20261018"
PINS = {
    "json_identity.py": "d601d68bb2ee5d4ba4c4a435bdf3709dc943f05bb4858d516b854c507c9e6ae4",
    "capture_identity.py": "360731186004a9008e8a5e1cac1bb32c059b8653a380dc39ee3bb9be45b17bbb",
    "capture_link_successor.py": "369b6f5b4f692ea86013ce02c92bf411e7469175a3b8671f1ba2abcdcd551328",
    "capture_entry.py": "b993a2cfd35cb2b435cda5ce2be1533c2f8836f8448b2aa7dd5237f2c6e5699e",
}

_TEST_HOOK = None


def install_test_hook(hook_or_none) -> None:
    """Install one private R13 fault hook; callback exceptions pass unchanged."""
    global _TEST_HOOK
    require(hook_or_none is None or callable(hook_or_none),
            "R13_BINDING_TEST_HOOK")
    _TEST_HOOK = hook_or_none


def _event(name: str, payload: dict) -> None:
    if _TEST_HOOK is not None:
        _TEST_HOOK(name, payload)


def _source(name: str) -> bytes:
    path = R12 / name
    blocks = []
    with resources.accounting_open(path, "rb") as stream:
        while True:
            block = stream.read(CHUNK)
            if not block:
                break
            blocks.append(block)
    raw = b"".join(blocks)
    require(len(raw) <= 4 * CHUNK and
            hashlib.sha256(raw).hexdigest() == PINS[name],
            "R13_FROZEN_SOURCE_CHANGED:" + name)
    return raw


def _module(name: str, imports: dict[str, ModuleType] | None = None) -> ModuleType:
    path, raw = R12 / name, _source(name)
    module = ModuleType("_r13_private_" + name.replace(".", "_") + "_" +
                        uuid.uuid4().hex)
    module.__file__, module.__package__ = str(path), ""
    original_import = builtins.__import__
    def private_import(target, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and imports and target in imports:
            return imports[target]
        return original_import(target, globals, locals, fromlist, level)
    module.__dict__["__builtins__"] = {**vars(builtins),
                                       "__import__": private_import}
    exec(compile(raw, str(path), "exec", dont_inherit=True), module.__dict__)
    return module


def _install_private_readers(ci) -> None:
    base_reader = ci.ArtifactReader
    base_text_reader = ci.ArtifactTextReader

    class HookedArtifactReader(base_reader):
        """The real R12 reader with observable physical pull/close boundaries."""
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._r13_unwinding_exception = None
            self._r13_close_reported = False

        def pull(self, size):
            requested = min(size, CHUNK)
            resources.get_budget().check()
            _event("reader_before_pull", {
                "reader": self, "path": self.path,
                "requested_size": requested, "count": self.count,
                "eof": self.eof,
            })
            block = super().pull(size)
            _event("reader_after_pull", {
                "reader": self, "path": self.path, "count": self.count,
                "returned_bytes": len(block), "eof": self.eof,
            })
            return block

        def finish(self, drain):
            if self.closed or self._r13_close_reported:
                return super().finish(drain)
            primary = None
            try:
                _event("reader_before_close", {
                    "reader": self, "path": self.path,
                    "count": self.count, "eof": self.eof,
                    "unwinding_exception": self._r13_unwinding_exception,
                })
            except BaseException as error:
                if self._r13_unwinding_exception is None:
                    primary = error
                else:
                    resources.get_budget().secondary(error)
            try:
                super().finish(drain if primary is None else False)
            except BaseException as error:
                if (primary is None and
                        self._r13_unwinding_exception is None):
                    primary = error
                else:
                    resources.get_budget().secondary(error)
            finally:
                self._r13_close_reported = True
                try:
                    _event("reader_after_close", {
                        "reader": self, "path": self.path,
                        "count": self.count, "eof": self.eof,
                        "closed": bool(self.source is None or
                                       self.source.closed),
                    })
                except BaseException as error:
                    if (primary is None and
                            self._r13_unwinding_exception is None):
                        primary = error
                    else:
                        resources.get_budget().secondary(error)
            if primary is not None:
                raise primary.with_traceback(primary.__traceback__)

        def __exit__(self, exc_type, exc_value, traceback):
            self._r13_unwinding_exception = exc_value
            return super().__exit__(exc_type, exc_value, traceback)

    class HookedArtifactTextReader(base_text_reader):
        def __exit__(self, exc_type, exc_value, traceback):
            if isinstance(self.buffer, HookedArtifactReader):
                self.buffer._r13_unwinding_exception = exc_value
            return super().__exit__(exc_type, exc_value, traceback)

    ci.ArtifactReader = HookedArtifactReader
    ci.ArtifactTextReader = HookedArtifactTextReader


def _install_private_identity(ci, ji, output_root: Path) -> None:
    """Route private identity/snapshot/facade IO through the shared budget."""
    def identity(path):
        digest, count = hashlib.sha256(), 0
        with resources.accounting_open(ji.safe_path(path), "rb") as stream:
            while True:
                block = ji.chunk_read(stream)
                if not block:
                    break
                digest.update(block)
                count += len(block)
        return {"bytes": count, "sha256": digest.hexdigest()}

    def read_control(path, max_bytes=ji.MAX_JSON):
        with resources.accounting_open(ji.safe_path(path), "rb") as stream:
            return ji.read_stream_json(stream, max_bytes=max_bytes)

    def read_verified(ref, root=ROOT, *, relative_only=False,
                      allow_external=False):
        path = ji.validated_path(ref, root, relative_only=relative_only,
                                 allow_external=allow_external)
        ji.require(ref["bytes"] <= ji.MAX_JSON, "JSON_BOUND")
        with resources.accounting_open(path, "rb") as stream:
            return ji.read_stream_json(stream, ref)

    @contextmanager
    def frozen_archive(ref, root=ROOT):
        path = ji.validated_path(ref, root, allow_external=False)
        if not Path(ref["path"]).is_absolute():
            ji.relative(ref["path"])
        ji.relative(path.relative_to(ji.safe_path(root)).as_posix())
        ji.require(ref["bytes"] <= 256 * CHUNK, "ARCHIVE_BOUND")
        folder = ji.safe_path(output_root / "private_archive_snapshots")
        ji.require(folder.is_relative_to(output_root),
                   "ARCHIVE_SNAPSHOT_SCOPE")
        resources.accounting_mkdir(folder, parents=True, exist_ok=True)
        snapshot_dir = folder / ("r13_" + uuid.uuid4().hex)
        resources.accounting_mkdir(snapshot_dir, exist_ok=False)
        snapshot = snapshot_dir / "archive.zip"
        digest, count = hashlib.sha256(), 0
        with resources.accounting_open(path, "rb") as source:
            with resources.accounting_open(snapshot, "xb",
                                           category="plain_aux") as target:
                while True:
                    block = source.read(CHUNK)
                    if not block:
                        break
                    count += len(block)
                    ji.require(count <= ref["bytes"],
                               "ARCHIVE_SIZE_CHANGED")
                    digest.update(block)
                    target.write(block)
        ji.require({"bytes": count, "sha256": digest.hexdigest()} ==
                   {key: ref[key] for key in ("bytes", "sha256")},
                   "ARCHIVE_IDENTITY_MISMATCH")
        yield snapshot

    base_facade = ci.IdentityFacade

    class AccountingIdentityFacade(base_facade):
        def output_directory(self, path):
            path = ji.safe_path(path)
            ji.require(path != output_root and
                       path.is_relative_to(output_root),
                       "R12_OUTPUT_SCOPE")
            resources.accounting_mkdir(path, parents=True, exist_ok=False)
            return self.io.path(path)

        def save(self, path, value):
            path = ji.safe_path(path)
            ji.require(path.is_relative_to(output_root) and
                       path != output_root, "R12_WRITE_SCOPE")
            primary = sys.exc_info()[1]
            try:
                raw = (json.dumps(value, ensure_ascii=False, indent=2,
                                  allow_nan=False) + "\n").encode("utf-8")
                resources.accounting_mkdir(path.parent, parents=True,
                                           exist_ok=True)
                resources.accounting_save_bytes(path, raw,
                                                category="all_other",
                                                exclusive=True)
            except BaseException as secondary:
                if primary is None or secondary is primary:
                    raise
                resources.get_budget().secondary(secondary)

        write_json = save

    ji.identity = identity
    ji.read_control = read_control
    ji.read_verified = read_verified
    ji.frozen_archive = frozen_archive
    ci.IdentityFacade = AccountingIdentityFacade


class _OwnedZipFile:
    """Private ZipFile path adapter; canonical zipfile is never patched."""
    def __init__(self, file, mode="r", *args, **kwargs):
        self._stream = None
        target = getattr(file, "snapshot", file)
        if hasattr(file, "read") or hasattr(file, "write"):
            self._zip = zipfile.ZipFile(file, mode, *args, **kwargs)
            return
        physical_mode = "rb" if mode == "r" else (
            "xb" if mode == "x" else "wb")
        self._stream = resources.accounting_open(
            Path(target), physical_mode, category="plain_aux")
        try:
            self._zip = zipfile.ZipFile(self._stream, mode, *args, **kwargs)
        except BaseException as primary:
            try:
                self._stream.close()
            except BaseException as secondary:
                resources.get_budget().secondary(secondary)
            raise primary.with_traceback(primary.__traceback__)

    def __getattr__(self, name):
        return getattr(self._zip, name)

    def __enter__(self):
        self._zip.__enter__()
        return self._zip

    def __exit__(self, exc_type, exc_value, traceback):
        cleanup_error = None
        try:
            result = self._zip.__exit__(exc_type, exc_value, traceback)
        except BaseException as error:
            result = False
            if exc_value is None:
                cleanup_error = error
            elif error is not exc_value:
                resources.get_budget().secondary(error)
        if self._stream is not None:
            try:
                self._stream.close()
            except BaseException as secondary:
                if exc_value is not None or cleanup_error is not None:
                    resources.get_budget().secondary(secondary)
                else:
                    cleanup_error = secondary
        if cleanup_error is not None:
            raise cleanup_error.with_traceback(cleanup_error.__traceback__)
        if exc_value is not None:
            return False
        return result


def _private_zip_namespace():
    module = ModuleType("_r13_private_zipfile_" + uuid.uuid4().hex)
    module.__dict__.update(vars(zipfile))
    module.ZipFile = _OwnedZipFile
    return module


def _volume_policy(ci, ji, store: VolumeStore, output_root: Path):
    base_path, base_io = ci.ArtifactPath, ci.ArtifactIO

    class LogicalPath(base_path):
        def _volume(self):
            return (self.value.resolve().is_relative_to(store.workspace) and
                    store.is_volume(self.value))

        def exists(self):
            return self._volume() or self.value.exists()

        def is_file(self):
            return self._volume() or self.value.is_file()

        def stat(self, *args, **kwargs):
            if self._volume():
                return SimpleNamespace(st_size=store.descriptor(self.value)["bytes"])
            return self.value.stat(*args, **kwargs)

        def mkdir(self, parents=False, exist_ok=False):
            return resources.accounting_mkdir(
                self.policy.write_path(self.value), parents=parents,
                exist_ok=exist_ok)

        def rename(self, target):
            target = self.policy.write_path(target)
            resources.accounting_replace(self.policy.write_path(self.value),
                                         target)
            return self.policy.path(target)

        replace = rename

    class LogicalIO(base_io):
        def path(self, value, *parts):
            if isinstance(value, LogicalPath) and value.policy is self and not parts:
                return value
            return LogicalPath(self, Path(value, *parts))

        def _logical(self, value):
            path = ji.safe_path(value)
            if not path.is_relative_to(output_root):
                return False
            if path.suffix.casefold() in STREAM_SUFFIXES:
                return True
            return path.is_relative_to(store.workspace) and store.is_volume(path)

        def register(self, descriptor, root=ROOT, *, external=False,
                     declared=True, role=None):
            require(type(descriptor) is dict and
                    {"path", "bytes", "sha256"} <= descriptor.keys(),
                    "FILE_DESCRIPTOR")
            raw_path = Path(descriptor["path"])
            path = ji.safe_path(raw_path if raw_path.is_absolute() else Path(root) / raw_path)
            if not self._logical(path):
                return super().register(descriptor, root, external=external,
                                        declared=declared, role=role)
            require((external or path.is_relative_to(Path(root).resolve())) and
                    store.is_volume(path), "DESCRIPTOR_SCOPE")
            stamp = {"path": str(path), "bytes": descriptor["bytes"],
                     "sha256": descriptor["sha256"]}
            require(store.descriptor(path) == {"bytes": descriptor["bytes"],
                                               "sha256": descriptor["sha256"]},
                    "VOLUME_DESCRIPTOR_IDENTITY")
            key, prior = str(path).casefold(), self.expected(path)
            require(prior is None or
                    {k: prior["stamp"][k] for k in ("bytes", "sha256")} ==
                    {k: stamp[k] for k in ("bytes", "sha256")},
                    "CONFLICTING_PATH_IDENTITY")
            roles = set(prior.get("roles", [])) if prior else set()
            if role:
                roles.add(role)
            self.registry[key] = {"stamp": stamp, "root": Path(root).resolve(),
                                  "external": external,
                                  "declared": bool(declared or
                                                   (prior and prior["declared"])),
                                  "roles": sorted(roles)}
            return path

        def open(self, value, mode="r", buffering=-1, encoding=None,
                 errors=None, newline=None, **kwargs):
            path = ji.safe_path(value)
            writing = any(flag in mode for flag in "wax+")
            is_stored = (path.is_relative_to(store.workspace) and
                         store.is_volume(path))
            if ((writing and path.is_relative_to(store.workspace) and
                 path.suffix.casefold() in STREAM_SUFFIXES) or
                    (not writing and is_stored)):
                require(not kwargs and "+" not in mode and "a" not in mode,
                        "VOLUME_OPEN_OPTIONS")
                if writing:
                    self.write_path(path)
                entry = self.expected(path)
                expected = entry["stamp"] if entry else None
                self.metrics["opens"] += 1
                return store.open(path, mode, expected)
            if writing:
                require(not kwargs, "R13_ACCOUNTING_OPEN_OPTIONS")
                self.write_path(path)
                return resources.accounting_open(
                    path, mode, category="all_other", encoding=encoding,
                    errors=errors, newline=newline)
            return super().open(path, mode, buffering=buffering,
                                encoding=encoding, errors=errors,
                                newline=newline, **kwargs)

        def identity(self, value):
            path = ji.safe_path(value)
            if (not path.is_relative_to(store.workspace) or
                    not store.is_volume(path)):
                return super().identity(path)
            expected = store.descriptor(path)
            digest, count = hashlib.sha256(), 0
            self.metrics["opens"] += 1
            with store.open(path, "rb", expected) as stream:
                while True:
                    block = stream.read(CHUNK)
                    if not block:
                        break
                    require(len(block) <= CHUNK, "READ_REQUEST_BOUND")
                    digest.update(block)
                    count += len(block)
            actual = {"bytes": count, "sha256": digest.hexdigest()}
            require(actual == expected, "VOLUME_IDENTITY_MISMATCH")
            self.metrics["stream_verified"] += 1
            return actual

    return LogicalIO


def _install_private_codec_scalar_cache(module):
    """Memoize only successful immutable cells in one private codec instance."""
    original_json = module.json
    dump_cache, load_cache = {}, {}
    options = {"ensure_ascii": False, "separators": (",", ":"), "allow_nan": False}

    def immutable(value):
        kind = type(value)
        return (kind in (type(None), bool) or
                (kind is int and value.bit_length() <= 256) or
                (kind is str and len(value) <= 256))

    def dumps(value, *args, **kwargs):
        if args or kwargs != options or not immutable(value):
            return original_json.dumps(value, *args, **kwargs)
        key = (type(value), value)
        if key in dump_cache:
            return dump_cache[key]
        encoded = original_json.dumps(value, **kwargs)
        if len(dump_cache) < 4096:
            dump_cache[key] = encoded
        return encoded

    private_json = ModuleType("_r13_private_codec_json_" + uuid.uuid4().hex)
    private_json.__dict__.update(vars(original_json))
    private_json.dumps = dumps
    module.json = private_json
    original_support = module.support
    support_cache = []

    class CodecSupport:
        def __init__(self, original):
            self.original = original

        def __getattr__(self, name):
            return getattr(self.original, name)

        def loads(self, raw, *args, **kwargs):
            if args or kwargs or type(raw) is not str or len(raw) > 256:
                return self.original.loads(raw, *args, **kwargs)
            if raw in load_cache:
                return load_cache[raw]
            value = self.original.loads(raw)
            # Containers always remain newly parsed objects. Exceptions are
            # never cached; strict syntax/duplicate/NaN handling is original.
            if immutable(value) and len(load_cache) < 4096:
                load_cache[raw] = value
            return value

    def support():
        if not support_cache:
            support_cache.append(CodecSupport(original_support()))
        return support_cache[0]

    module.support = support


def run_frozen_chain(envelope: dict, dependency_ref: dict, output_dir: Path,
                     quota_bytes: int) -> dict:
    """Invoke the real frozen successor once under a private volume policy."""
    output_dir = Path(output_dir).resolve()
    output_root = output_dir.parent.resolve()
    require(output_dir != output_root and output_dir.is_relative_to(output_root),
            "R13_PRIVATE_OUTPUT_SCOPE")
    # Keep the logical D4 output child fresh.  The volume store lives in its
    # already-created stable output parent and serves every descendant.
    store = VolumeStore(output_root, quota_bytes)
    ji = _module("json_identity.py")
    ji.OUTPUT = output_root
    ci = _module("capture_identity.py", {"json_identity": ji})
    ci.OUTPUT = output_root
    _install_private_readers(ci)
    _install_private_identity(ci, ji, output_root)
    ci.ArtifactIO = _volume_policy(ci, ji, store, output_root)
    successor = _module("capture_link_successor.py",
                        {"json_identity": ji, "capture_identity": ci})
    successor.OUTPUT = output_root
    base_snapshot_path = successor.SnapshotPath

    class AccountingSnapshotPath(base_snapshot_path):
        def open(self, mode="r", *args, **kwargs):
            ji.require(mode == "rb", "R12_ARCHIVE_READ_ONLY")
            ji.require(not args and not kwargs, "R13_SNAPSHOT_OPEN_OPTIONS")
            return resources.accounting_open(self.snapshot, "rb")

    successor.SnapshotPath = AccountingSnapshotPath
    base_context = successor.DependencyContext
    private_zip = _private_zip_namespace()

    class AccountingDependencyContext(base_context):
        def adapt(self, module):
            super().adapt(module)
            if getattr(module, "zipfile", None) is zipfile:
                module.zipfile = private_zip
            if Path(module.__file__).name == "c9_codec.py":
                _install_private_codec_scalar_cache(module)
            if Path(module.__file__).name == "c9_capture.py":
                original_pure = module.legacy_pure
                def pure_with_scalar_cache():
                    pure = original_pure()
                    original_scalar, cache = pure.scalar, {}
                    def scalar(bits, spec):
                        # Cache only immutable argument values of the frozen
                        # pure scalar decoder. New/invalid values still run
                        # its unchanged validation; exceptions are not cached.
                        if (type(bits) is not str or len(bits) > 256 or
                                type(spec) is not dict or
                                type(spec.get("width")) is not int or
                                type(spec.get("signed")) is not bool):
                            return original_scalar(bits, spec)
                        key = (bits, spec["width"], spec["signed"])
                        if key not in cache:
                            result = original_scalar(bits, spec)
                            if len(cache) < 4096:
                                cache[key] = result
                            return result
                        return cache[key]
                    pure.scalar = scalar
                    return pure
                module.legacy_pure = pure_with_scalar_cache
            # Frozen helper factories are called for every output row. The
            # R12 factory rehashes its source even on an already compiled
            # module cache hit. Keep the same helper for this invocation;
            # first load and terminal close still verify exact source bytes.
            helper_path = getattr(module, "COMMON_PATH", getattr(module, "COMMON", None))
            if helper_path is not None and isinstance(getattr(module, "COMMON_SHA", None), str):
                for name in ("helpers", "support", "shared"):
                    factory = getattr(module, name, None)
                    if not callable(factory):
                        continue
                    cache = []
                    def once(*args, _factory=factory, _cache=cache, **kwargs):
                        if not _cache:
                            _cache.append(_factory(*args, **kwargs))
                        return _cache[0]
                    setattr(module, name, once)

        def close(self):
            primary, first = sys.exc_info()[1], None
            try:
                for key in tuple(self.modules):
                    ji.checked(self.identities[key])
            except BaseException as error:
                if primary is None:
                    first = error
                else:
                    resources.get_budget().secondary(error)
            try:
                super().close()
            except BaseException as error:
                if primary is None and first is None:
                    first = error
                else:
                    resources.get_budget().secondary(error)
            if first is not None:
                raise first.with_traceback(first.__traceback__)

    successor.DependencyContext = AccountingDependencyContext
    capture = _module("capture_entry.py", {
        "json_identity": ji, "capture_link_successor": successor})
    result = capture.process(envelope, output_dir,
                             dependency_ref=dependency_ref)
    result["R13_volume_store"] = {
        "schema": "M3_R13_VOLUME_STORE_SUMMARY_V1",
        "physical_bytes": store.physical_bytes(),
        "quota_bytes": quota_bytes,
        "logical_volumes": sorted(store.entries.values(),
                                  key=lambda item: item["logical_path"]),
        "direct_plaintext_intermediate": False,
    }
    return result
