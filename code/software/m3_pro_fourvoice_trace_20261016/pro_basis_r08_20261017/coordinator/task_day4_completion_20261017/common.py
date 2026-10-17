"""File-only helpers for the task-day4 C9 completion; never starts tools."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
from types import ModuleType
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[6]
SOFT = ROOT / "code/software/m3_pro_fourvoice_trace_20261016"
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/task_day4_completion_20261017"
MAX_JSON_LINE = 8 * 1024 * 1024
_MODULES: dict[tuple[str, str], ModuleType] = {}


class ContractReject(ValueError):
    """Evidence is incomplete, changed or incompatible with its contract."""


def require(condition: Any, reason: str) -> None:
    if not condition:
        raise ContractReject(reason)


def no_alias(path: Path | str) -> Path:
    path = Path(path)
    require(not str(path).startswith(("\\\\.\\", "\\\\?\\", "\\??\\")), "DEVICE_PATH")
    require(not any(re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part)
                    for part in path.parts), "DEVICE_NAME")
    for part in (path, *path.parents):
        require(not part.is_symlink() and not part.is_junction(), "PATH_ALIAS")
    return path.resolve()


def identity(path: Path | str) -> dict[str, Any]:
    path = no_alias(path)
    require(path.is_file(), "NOT_REGULAR_FILE:" + str(path))
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
            count += len(block)
    return {"bytes": count, "sha256": digest.hexdigest()}


def artifact(path: Path | str) -> dict[str, Any]:
    path = no_alias(path)
    name = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
    return {"path": name, **identity(path)}


def checked_descriptor(descriptor: dict[str, Any], root: Path = ROOT,
                       allow_external: bool = False) -> Path:
    require(isinstance(descriptor, dict) and {"path", "bytes", "sha256"} <= descriptor.keys(), "FILE_DESCRIPTOR")
    require(isinstance(descriptor["path"], str) and descriptor["path"], "DESCRIPTOR_PATH")
    require(type(descriptor["bytes"]) is int and descriptor["bytes"] >= 0, "DESCRIPTOR_SIZE")
    require(isinstance(descriptor["sha256"], str) and re.fullmatch("[0-9a-f]{64}", descriptor["sha256"]), "DESCRIPTOR_SHA")
    path = Path(descriptor["path"])
    if not path.is_absolute():
        path = root / path
    path = no_alias(path)
    require(allow_external or path.is_relative_to(no_alias(root)), "DESCRIPTOR_SCOPE")
    require(identity(path) == {key: descriptor[key] for key in ("bytes", "sha256")}, "FILE_BYTES_CHANGED:" + str(path))
    return path


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        require(key not in result, "DUPLICATE_JSON_KEY:" + key)
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ContractReject("NONFINITE_JSON:" + value)


def loads(raw: bytes | str) -> Any:
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)


def read_json(path: Path | str, max_bytes: int = 16 * 1024 * 1024) -> Any:
    path = no_alias(path)
    with path.open("rb") as stream:
        raw = stream.read(max_bytes + 1)
    require(len(raw) <= max_bytes, "JSON_SIZE_BOUND")
    return loads(raw)


def write_json(path: Path | str, value: Any) -> None:
    path = no_alias(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def iter_jsonl(path: Path | str, max_line_bytes: int = MAX_JSON_LINE) -> Iterator[dict[str, Any]]:
    path = no_alias(path)
    with path.open("rb") as stream:
        number = 0
        while True:
            raw = stream.readline(max_line_bytes + 1)
            if not raw:
                break
            number += 1
            require(len(raw) <= max_line_bytes, "JSONL_LINE_BOUND:" + str(number))
            require(bool(raw.strip()), "EMPTY_JSONL_LINE:" + str(number))
            row = loads(raw)
            require(isinstance(row, dict), "JSONL_ROW_NOT_OBJECT:" + str(number))
            yield row


def output_directory(path: Path | str) -> Path:
    path = no_alias(path)
    require(path.is_relative_to(ROOT), "OUTPUT_SCOPE")
    path.mkdir(parents=True, exist_ok=False)
    return path


def load_source(path: Path | str, expected_sha: str | None = None,
                module_name: str | None = None) -> ModuleType:
    """Load exact source bytes; do not consult or create a .pyc file.

    Expected SHA comes from a source binding frozen before candidate execution.
    The surrounding runner additionally restricts every repository read/write.
    """
    path = no_alias(path)
    require(path.is_relative_to(ROOT / "code/software") and path.suffix == ".py", "MODULE_SOURCE_SCOPE")
    require(isinstance(expected_sha, str) and re.fullmatch("[0-9a-f]{64}", expected_sha), "FROZEN_SOURCE_SHA_REQUIRED")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected_sha, "MODULE_SOURCE_SHA:" + str(path))
    key = (str(path), expected_sha)
    if key in _MODULES:
        require(identity(path)["sha256"] == expected_sha, "CACHED_MODULE_SOURCE_CHANGED")
        return _MODULES[key]
    name = module_name or "_task_day4_" + expected_sha[:20]
    require(name not in sys.modules or getattr(sys.modules[name], "__file__", None) == str(path), "MODULE_NAME_COLLISION")
    module = ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ""
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), "exec", dont_inherit=True, optimize=0), module.__dict__)
        require(identity(path)["sha256"] == expected_sha, "MODULE_CHANGED_DURING_LOAD")
    except BaseException:
        if sys.modules.get(name) is module:
            del sys.modules[name]
        raise
    _MODULES[key] = module
    return module
