"""R10 output-scope adapter. Import does not load candidates or write files."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import types

ROOT = Path(__file__).resolve().parents[7]
OUTPUT = ROOT / "code/output/m3_c9_chain_night_r10_20261017"
SOURCE = ROOT / "code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/build_admission_bundle/c9_completion_r01/assembler.py"
SOURCE_SHA = "ae4ad0f3fefa1bc28e099a2aabcb827f733358d9bd93988af31e5de20a824ccf"


def safe_path(value):
    path = Path(value)
    if str(path).startswith(("\\\\", "\\??\\")):
        raise ValueError("R10_OUTPUT_ALIAS")
    for part in path.parts:
        if part.rstrip(" .") != part or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part):
            raise ValueError("R10_OUTPUT_ALIAS")
    for item in (path, *path.parents):
        if item.is_symlink() or item.is_junction():
            raise ValueError("R10_OUTPUT_ALIAS")
    return path.resolve()


def descriptor(path):
    path = Path(path)
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def write_json(path, value):
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8"))


def read_request(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY:" + key)
            result[key] = value
        return result

    def constant(value):
        raise ValueError("NONFINITE_JSON:" + value)

    with safe_path(path).open("rb") as stream:
        raw = stream.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("JSON_SIZE_BOUND")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def build_application(request, out):
    out = safe_path(out)
    scope = safe_path(OUTPUT)
    if out == scope or not out.is_relative_to(scope):
        raise ValueError("R10_STRICT_OUTPUT_SCOPE")
    # Load a fresh namespace. Never mutate the existing/cached D4 module.
    source = safe_path(SOURCE)
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise ValueError("R10_ASSEMBLER_PIN_CHANGED")
    module = types.ModuleType("_r10_application_" + SOURCE_SHA[:20])
    module.__file__, module.__package__ = str(source), ""
    exec(compile(raw, str(source), "exec", dont_inherit=True), module.__dict__)
    old_output = module.OUTPUT
    module.OUTPUT = scope
    result = module.build_application(request, out)
    if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_SHA:
        raise ValueError("R10_ASSEMBLER_CHANGED_DURING_BUILD")
    derivation = {"schema": "M3_R10_APPLICATION_OUTPUT_DERIVATION_V1",
                  "source": descriptor(source), "source_module_file": module.__file__,
                  "source_bytes_changed": False, "changed_globals": ["OUTPUT"],
                  "original_output_root": str(old_output), "adapted_output_root": str(scope),
                  "actual_output": str(out), "strict_descendant": True,
                  "fresh_namespace_not_cached_original": True,
                  "other_validation_and_permission_logic": "UNCHANGED_PINNED_SOURCE",
                  "request_window_reference": request["window_reference"],
                  "permission": "NOT_GRANTED", "execution_allowed": False,
                  "HDL_executed": False, "board_release_allowed": False}
    write_json(out / "OUTPUT_SCOPE_DERIVATION.json", derivation)
    adapted = {**result, "artifacts": {**result["artifacts"],
               "output_scope_derivation": descriptor(out / "OUTPUT_SCOPE_DERIVATION.json")}}
    # Preserve the original assembler RESULT.json; the wrapper has its own result.
    write_json(out / "ADAPTER_RESULT.json", adapted)
    return adapted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = build_application(read_request(args.request), args.output)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 3
    except Exception as error:
        print(json.dumps({"status": "REJECT", "error": type(error).__name__, "reason": str(error),
                          "execution_allowed": False}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
