"""File-only R10 coordinator helpers, with no I/O on import."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[6]
REL = Path("m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017")
DOC = ROOT / "code/docs/test" / REL
SW = ROOT / "code/software" / REL
OUT = ROOT / "code/output/m3_c9_chain_night_r10_20261017"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def no_alias(path):
    path = Path(path)
    for part in (path, *path.parents):
        require(not part.is_symlink() and not part.is_junction(), "PATH_ALIAS")
    return path.resolve()


def ref(path):
    path = no_alias(path)
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def checked(descriptor):
    require(isinstance(descriptor, dict) and {"path", "bytes", "sha256"} <= descriptor.keys(), "DESCRIPTOR")
    path = Path(descriptor["path"])
    path = no_alias(path if path.is_absolute() else ROOT / path)
    require(path.is_relative_to(ROOT), "REFERENCE_SCOPE")
    actual = ref(path)
    require(all(actual[k] == descriptor[k] for k in ("bytes", "sha256")), "REFERENCE_BYTES_CHANGED")
    return path


def read(path):
    raw = Path(path).read_bytes()
    require(len(raw) <= 16 * 1024 * 1024, "JSON_BOUND")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))


def save(path, value):
    path = Path(path)
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        stream.write(raw)


def load(descriptor, name):
    path = checked(descriptor)
    raw = path.read_bytes()
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), "exec", dont_inherit=True), module.__dict__)
    return module


def install_guard():
    allowed = (OUT.resolve(), DOC.resolve())
    def writable(path):
        if isinstance(path, int):
            return
        path = no_alias(path)
        require(any(path.is_relative_to(base) for base in allowed), "WRITE_OUTSIDE_R10_SCOPE")
    def audit(event, args):
        if (event == "subprocess.Popen" or event.startswith("socket.")
                or event in ("os.system", "os.startfile", "os.posix_spawn", "ctypes.dlopen", "ctypes.dlsym")
                or event.startswith(("os.exec", "os.spawn"))):
            raise PermissionError("N10_NO_PROCESS_NETWORK_NATIVE_ROUTE:" + event)
        if event == "open":
            path, mode, flags = args
            if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
                writable(path)
        if event in ("os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.utime", "os.truncate"):
            writable(args[0])
        if event in ("os.rename", "os.link", "os.symlink"):
            writable(args[0])
            writable(args[1])
        if event == "os.chdir":
            raise PermissionError("N10_CWD_CHANGE_FORBIDDEN")
    sys.addaudithook(audit)
