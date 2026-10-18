"""Pinned algorithms with per-call imports, helpers and artifact IO.

No production test callback exists here. Runtime proof belongs to the owned
controller; frozen source, shared modules and pathlib are never patched.
"""
import builtins
import hashlib
from contextlib import ExitStack
import pathlib
from pathlib import Path
import sys
import types
import uuid
import json_identity as ji
import capture_identity as ci

ROOT, OUTPUT = ji.ROOT, ji.OUTPUT
N10 = ROOT / "code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017"
D4 = N10.parent / "task_day4_completion_20261017"


class _PathFactory:
    """Path constructor for one private module's globals, never pathlib.Path."""
    def __init__(self, io_policy):
        self.io = io_policy

    def __call__(self, *parts):
        return self.io.path(Path(*parts))

    def __getattr__(self, name):
        value = getattr(Path, name)
        if name in ("cwd", "home"):
            return lambda: self.io.path(value())
        return value


class FrozenBufferPath:
    """Only a private old function's explicit read_bytes boundary.

    PE parsing still needs a bounded in-memory body. This is not a constant
    memory claim and must never wrap a large raw/stdout/stderr role.
    """
    def __init__(self, path, stamp, max_bytes, io_policy):
        self.path = io_policy.path(path)
        self.stamp, self.max_bytes = stamp, max_bytes
        self.raw = None

    def __fspath__(self):
        return str(self.path)

    def __str__(self):
        return str(self.path)

    def __getattr__(self, name):
        return getattr(self.path, name)

    def read_bytes(self):
        if self.raw is None:
            ji.require(self.stamp["bytes"] <= self.max_bytes, "R12_BUFFER_ROLE_BOUND")
            blocks, count, digest = [], 0, hashlib.sha256()
            with self.path.open("rb") as stream:
                while True:
                    block = ji.chunk_read(stream)
                    if not block:
                        break
                    count += len(block)
                    ji.require(count <= min(self.max_bytes, self.stamp["bytes"]), "R12_BUFFER_ROLE_BOUND")
                    blocks.append(block)
                    digest.update(block)
            ji.require({"bytes": count, "sha256": digest.hexdigest()} ==
                       {k: self.stamp[k] for k in ("bytes", "sha256")}, "R12_BUFFER_CHANGED")
            self.raw = b"".join(blocks)
        return self.raw


class SnapshotPath:
    """Read-only archive copy boundary; displayed identity remains original."""
    def __init__(self, original, snapshot):
        self.original, self.snapshot = original, snapshot

    def __fspath__(self):
        return str(self.original)

    def __str__(self):
        return str(self.original)

    def __getattr__(self, name):
        return getattr(self.original, name)

    def open(self, mode="r", *args, **kwargs):
        ji.require(mode == "rb", "R12_ARCHIVE_READ_ONLY")
        return self.snapshot.open(mode, *args, **kwargs)


class ArchiveFacade:
    def __init__(self, base, snapshots):
        self.base, self.snapshots = base, snapshots

    def __getattr__(self, name):
        return getattr(self.base, name)

    def checked_descriptor(self, descriptor):
        original = self.base.checked_descriptor(descriptor)
        snapshot = self.snapshots.get(str(original).casefold())
        return SnapshotPath(original, snapshot) if snapshot is not None else original

    checked = checked_descriptor


class DependencyContext:
    def __init__(self, dependency_ref):
        ji.require(dependency_ref is not None, "R12_FROZEN_DEPENDENCIES_REQUIRED")
        manifest = ji.read_verified(dependency_ref).value
        ji.require(manifest.get("schema") == "M3_R12_PINNED_DEPENDENCIES_V1", "R12_DEPENDENCY_SCHEMA")
        self.identities = {}
        for descriptor in manifest["old_source_files"]:
            path = ji.validated_path(descriptor)
            ji.require(path.is_relative_to(ROOT / "code/software") and path.suffix == ".py", "R12_SOURCE_SCOPE")
            key = str(path).casefold()
            ji.require(key not in self.identities, "R12_DEPENDENCY_DUPLICATE")
            self.identities[key] = descriptor
        self.modules, self.facades, self.trace, self.expected = {}, {}, [], {}
        self.io = ci.ArtifactIO(self.expected)
        self.prefix = "_r12_private_" + uuid.uuid4().hex + "_"
        self.snapshot_stack, self.snapshots = ExitStack(), {}
        self.private_modules = {}
        self.generated_modules = []
        self._module_globals = {}
        self._intake_exec_scope = []
        self._bootstrap_depth = 0
        self._path_factory = _PathFactory(self.io)
        self._private_sys = types.ModuleType(self.prefix + "sys")
        self._private_sys.__dict__.update(vars(sys))
        self._private_sys.modules = self.private_modules
        self._private_pathlib = types.ModuleType(self.prefix + "pathlib")
        self._private_pathlib.__dict__.update(vars(pathlib))
        self._private_pathlib.Path = self._path_factory
        self._private_types = types.ModuleType(self.prefix + "types")
        self._private_types.__dict__.update(vars(types))
        self._private_types.ModuleType = self._make_module

    def _import(self, name, globals=None, locals=None, fromlist=(), level=0):
        """Bind local successors and generated old AST modules explicitly."""
        if level == 0:
            local = {"json_identity": ji, "capture_identity": ci,
                     "sys": self._private_sys, "types": self._private_types}
            if name in local:
                return local[name]
            if name == "pathlib" and self._bootstrap_depth == 0:
                return self._private_pathlib
        return builtins.__import__(name, globals, locals, fromlist, level)

    def _make_module(self, name, doc=None):
        module = types.ModuleType(self.prefix + name, doc)
        module.__dict__["__builtins__"] = {
            **vars(builtins), "__import__": self._import,
            "exec": self._exec_derived}
        self.generated_modules.append(module)
        self._module_globals[id(module.__dict__)] = module
        return module

    def _exec_derived(self, code, globals=None, locals=None):
        """Adapt helper AST modules created inside frozen pure-part loaders.

        Only this context's module dictionary is accepted. The selected old
        AST/function bodies execute unchanged; their helper/Path slots are
        bound before the frozen caller can consume them.
        """
        module = self._module_globals.get(id(globals))
        if module is None and self._intake_exec_scope:
            # The frozen intake adapter deliberately clones old.__dict__ and
            # inserts one sink. Admit precisely that clone only while the
            # original pinned adapter is on this private call stack.
            old, sink, source = self._intake_exec_scope[-1]
            expected = {**old.__dict__, "_d4_preserved_sink": sink}
            ji.require(type(globals) is dict and globals.keys() == expected.keys()
                       and all(globals[key] is value for key, value in expected.items())
                       and locals is None and code.co_filename == str(source),
                       "R12_INTAKE_DERIVED_SCOPE")
            isolated = self._make_module("intake_analyzer_clone")
            isolated.__dict__.update(globals)
            self._bind_paths(isolated)
            builtins.exec(code, isolated.__dict__)
            # The untouched caller reads only this derived function. Its
            # __globals__ remains the registered, private module dictionary.
            globals["analyze"] = isolated.__dict__["analyze"]
            return
        ji.require(module is not None and globals is module.__dict__,
                   "R12_DERIVED_MODULE_SCOPE")
        builtins.exec(code, globals, locals)
        if getattr(module, "__file__", None):
            self.adapt(module)
        else:
            self._bind_paths(module)

    def _bind_paths(self, module):
        """Include precomputed metadata Paths, not just later constructors."""
        for slot, value in list(module.__dict__.items()):
            if isinstance(value, Path):
                setattr(module, slot, self.io.path(value))
        for slot in ("Path", "_Path"):
            if getattr(module, slot, None) is Path:
                setattr(module, slot, self._path_factory)

    def facade(self, original):
        key = id(original)
        if key not in self.facades:
            self._bind_paths(original)
            self.facades[key] = ci.IdentityFacade(
                original, self.load, self.expected, io_policy=self.io)
        return self.facades[key]

    def buffer_path(self, path, limit=ji.MAX_JSON):
        path = ji.safe_path(path)
        bound = self.expected.get(str(path).casefold())
        ji.require(bound is not None, "R12_BUFFER_IDENTITY_NOT_BOUND")
        return FrozenBufferPath(path, bound["stamp"], limit, self.io)

    def _json_meta(self, path, limit):
        """Preserve the old metadata byte bound using verified chunked IO.

        The original reset/END/stdout parsers receive the same complete bytes.
        No one-shot read(MAX+1), truncated return or substituted parser is used.
        """
        parts, count = [], 0
        with self.io.path(path).open("rb") as stream:
            while True:
                block = stream.read(min(ji.CHUNK, limit + 1 - count))
                if not block:
                    break
                count += len(block)
                ji.require(count <= limit, "METADATA_SIZE_BOUND")
                parts.append(block)
        return b"".join(parts)

    def load(self, path, expected_sha=None, module_name=None):
        path = ji.safe_path(path)
        key = str(path).casefold()
        ji.require(key in self.identities, "R12_UNFROZEN_DEPENDENCY:" + str(path))
        descriptor = self.identities[key]
        ji.require(expected_sha in (None, descriptor["sha256"]), "R12_DEPENDENCY_PIN")
        if key in self.modules:
            ji.checked(descriptor)
            return self.modules[key]
        # Read one bounded SOURCE buffer and compile exactly those hashed bytes.
        blocks, count = [], 0
        with path.open("rb") as stream:
            while True:
                block = ji.chunk_read(stream)
                if not block:
                    break
                count += len(block)
                ji.require(count <= 4 * ji.CHUNK, "R12_SOURCE_BOUND")
                blocks.append(block)
        raw = b"".join(blocks)
        ji.require(len(raw) == descriptor["bytes"] and hashlib.sha256(raw).hexdigest() == descriptor["sha256"], "R12_SOURCE_CHANGED")
        name = self.prefix + descriptor["sha256"][:20]
        module = self._make_module(descriptor["sha256"][:20])
        module.__file__, module.__package__ = str(path), ""
        self.private_modules[name] = module
        self._bootstrap_depth += 1
        try:
            exec(compile(raw, str(path), "exec", dont_inherit=True), module.__dict__)
        finally:
            self._bootstrap_depth -= 1
        self.modules[key] = module
        self.adapt(module)
        self.trace.append({"source": descriptor, "private_module": name,
                           "changes": "Explicit helper/factory/output slots only; frozen algorithm source unchanged"})
        return module

    def adapt(self, module):
        # These are private module namespaces only. Canonical modules and
        # frozen files are never modified or monkeypatched.
        # Bootstrap executes first. Its precomputed Path constants and all
        # later constructors/nested AST modules then use this invocation's IO.
        for slot in ("OUT", "_OUTPUT", "OUTPUT"):
            value = getattr(module, slot, None)
            if isinstance(value, Path) and value.is_relative_to(ROOT / "code/output"):
                setattr(module, slot, OUTPUT)
        self._bind_paths(module)
        for slot in ("c", "_COMMON"):
            helper = getattr(module, slot, None)
            if isinstance(helper, types.ModuleType):
                setattr(module, slot, self.facade(helper))
        for slot in ("helpers", "support", "shared"):
            factory = getattr(module, slot, None)
            if callable(factory):
                helper_path = getattr(module, "COMMON_PATH", getattr(module, "COMMON", None))
                helper_sha = getattr(module, "COMMON_SHA", None)
                if helper_path is None or not isinstance(helper_sha, str):
                    # Only known factories receive explicit adapters below.
                    continue
                def injected(*args, _path=helper_path, _sha=helper_sha, **kwargs):
                    return self.facade(self.load(_path, _sha))
                setattr(module, slot, injected)
        path = Path(module.__file__)
        if path == N10 / "capture_link_r01/entry.py":
            module.helpers = lambda: self.facade(self.load(N10 / "common.py", module.COMMON_SHA))
            module.capture_module = lambda: self.load(D4 / "chain.py", module.CAPTURE_SHA)
            module.preparation_module = lambda: self.load(N10 / "chain.py", module.PREPARATION_SHA)
        elif path == N10 / "capture_link_r01/application_adapter.py":
            def build(request, out):
                result = self.load(module._SOURCE, module._SOURCE_SHA).build_application(request, out)
                ji.require(isinstance(result, dict) and result.get("schema") == "M3_C9_APPLICATION_BUILD_RESULT_V1",
                           "R12_APPLICATION_RESULT_SCHEMA")
                ji.require(all(result.get(flag) is False for flag in
                               ("execution_allowed", "real_pass", "board_release_allowed")), "R12_APPLICATION_AUTHORITY")
                return result
            module.build_application = build
        elif path == N10 / "admission/adapter.py":
            # Reuse the assembler itself through this context, so its helper
            # factories and generated-artifact identities cannot fall back to
            # the old whole-file descriptor path.
            def build(request, out):
                scope = ji.safe_path(out)
                ji.require(scope != OUTPUT and scope.is_relative_to(OUTPUT), "R12_APPLICATION_OUTPUT_SCOPE")
                assembler = self.load(module.SOURCE, module.SOURCE_SHA)
                result = assembler.build_application(request, scope)
                facade = assembler.helpers()
                derivation = {"schema": "M3_R10_APPLICATION_OUTPUT_DERIVATION_V1",
                              "source": facade.artifact(module.SOURCE),
                              "source_module_file": str(module.SOURCE), "source_bytes_changed": False,
                              "changed_globals": ["OUTPUT", "helpers", "read_archive"],
                              "dependency_injection": "R12 private namespaces, streaming identity and frozen archive copies",
                              "adapted_output_root": str(OUTPUT), "actual_output": str(scope),
                              "strict_descendant": True, "fresh_namespace_not_cached_original": True,
                              "request_window_reference": request["window_reference"],
                              "other_validation_and_permission_logic": "PINNED_ALGORITHMS_RUNTIME_UNVERIFIED",
                              "permission": "NOT_GRANTED", "execution_allowed": False,
                              "HDL_executed": False, "board_release_allowed": False}
                facade.write_json(scope / "OUTPUT_SCOPE_DERIVATION.json", derivation)
                adapted = {**result, "artifacts": {**result["artifacts"],
                           "output_scope_derivation": facade.artifact(scope / "OUTPUT_SCOPE_DERIVATION.json")}}
                facade.write_json(scope / "ADAPTER_RESULT.json", adapted)
                return adapted
            module.build_application = build
        elif path == N10 / "capture_complete_r11/entry.py":
            module.legacy_module = lambda: self.load(module.LEGACY, module.LEGACY_SHA)
        elif path == N10 / "chain.py":
            module.helpers = lambda: self.facade(self.load(
                N10 / "common.py", "025d801ffcb98697f7732632feb8b6a6c214fc551bbd2e5c382ce3eded11c2f5"))
        elif path.name == "m3r08_common.py":
            # Old functions retain this private namespace as __globals__.
            facade = self.facade(module)
            original_checked = module.checked_file
            module.identity = lambda p: {"path": str(ji.safe_path(p)), **facade.identity(p)}
            def checked_file(entry, external=False):
                checked_path, actual = original_checked(entry, external=external)
                return self.buffer_path(checked_path, 64 * ji.CHUNK), actual
            module.checked_file = checked_file
        elif path.name == "assembler.py" and path.parent.name == "c9_completion_r01":
            module.helpers = lambda: ArchiveFacade(
                self.facade(self.load(module.COMMON, module.COMMON_SHA)), self.snapshots)
            original_archive = module.read_archive
            def read_archive(descriptor):
                stamp = {k: descriptor[k] for k in ("path", "bytes", "sha256")}
                original = ji.validated_path(stamp)
                key = str(original).casefold()
                if key not in self.snapshots:
                    self.snapshots[key] = self.snapshot_stack.enter_context(ji.frozen_archive(stamp))
                snapshot = self.snapshots[key]
                snap_ref = {"path": snapshot.relative_to(ROOT).as_posix(),
                            "bytes": descriptor["bytes"], "sha256": descriptor["sha256"]}
                payload, _, members = original_archive(snap_ref)
                return payload, stamp, members
            module.read_archive = read_archive
        elif path.name == "frame_plan_generator_candidate.py":
            original_generate = module.generate
            def generate(input_path, rules_path, output_dir):
                return original_generate(self.buffer_path(input_path), self.buffer_path(rules_path), output_dir)
            module.generate = generate
        elif path.name == "intake_adapter.py" and path.parent.name == "c9_completion_r01":
            original_analyzer = module._streaming_analyzer
            def streaming_analyzer(old, preserved_sink):
                old_key = str(ji.safe_path(old.__file__)).casefold()
                ji.require(self.modules.get(old_key) is old,
                           "R12_INTAKE_SOURCE_NOT_PRIVATE")
                self._intake_exec_scope.append((old, preserved_sink, module.OLD_PATH))
                try:
                    return original_analyzer(old, preserved_sink)
                finally:
                    self._intake_exec_scope.pop()
            module._streaming_analyzer = streaming_analyzer
        elif path.name == "c9_stream.py":
            # This frozen IO primitive read(MAX_META_BYTES+1) in one request.
            # Keep its limit/return bytes and all downstream parsers intact.
            module.bounded_metadata = lambda p: self._json_meta(
                p, module.MAX_META_BYTES)
        elif path.name == "c9_oracle_bridge.py":
            facade = self.facade(module)
            module._sha256 = lambda p: facade.identity(p)["sha256"]
            original_resolve = module._resolve
            def resolve(repo_root, descriptor, role):
                result = original_resolve(repo_root, descriptor, role)
                if role == "source_closure":
                    return result
                return self.buffer_path(result)
            module._resolve = resolve

    def link(self):
        return self.load(N10 / "capture_link_r01/entry.py")

    def complete(self):
        return self.load(N10 / "capture_complete_r11/entry.py")

    def close(self):
        try:
            self.snapshot_stack.close()
        finally:
            # All registrations belong to this dictionary, never sys.modules.
            self.private_modules.clear()
            self.modules.clear()
            self.facades.clear()
            self.generated_modules.clear()
            self._module_globals.clear()
            self._intake_exec_scope.clear()
