"""C9-only successor binding to unchanged R8-02; not an admission tool."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
LEGACY = Path(__file__).resolve().parent.parent / "m3r08_02.py"
LEGACY_SHA = "89ebb730b32e1d47650dbbd39f193c11488a2f6b50f524153f1d0430462dd002"


def load_identity(entry):
    path = Path(entry["path"])
    if not path.is_absolute():
        path = ROOT / path
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise ValueError("C9_PATH_ALIAS")
    path = path.resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("C9_INPUT_SCOPE")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError("C9_INPUT_IDENTITY")
    if "bytes" in entry and len(raw) != entry["bytes"]:
        raise ValueError("C9_INPUT_SIZE")
    return path, raw


def evaluate(request):
    if request["schema"] != "M3_R8_02_C9_REQUEST_V1":
        raise ValueError("C9_REQUEST_SCHEMA")
    for entry in request["pinned_inputs"]:
        load_identity(entry)
    if hashlib.sha256(LEGACY.read_bytes()).hexdigest() != LEGACY_SHA:
        raise ValueError("R8_02_LEGACY_CHANGED")
    exports = json.loads(load_identity(request["exports"])[1])
    if exports["schema"] != "M2_R06C9_OBSERVER_EXPORTS_V1" or len(exports["expected_observation_ports"]) != 67:
        raise ValueError("C9_EXPORT_SET")
    spec = importlib.util.spec_from_file_location("c9_reused_r8_02", LEGACY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = module.evaluate(request["capture_request"])
    catalog = original["report"]["modules"]
    ports = catalog[exports["top"]]["ports"]
    expected = exports["expected_observation_ports"]
    if {name for name in ports if name.startswith("obs_")} != set(expected):
        raise ValueError("C9_EXACT_OBSERVATION_PORT_SET")
    comparisons = []
    observer = catalog["r7a_c9_public_observer"]["ports"]
    connected = original["report"]["connections"]
    for name, declaration in expected.items():
        actual, passive = ports[name], observer[name]
        if actual["direction"] != "output" or passive["direction"] != "input" or any(
                actual[key] != declaration[key] or passive[key] != declaration[key] for key in ("width", "signed")):
            raise ValueError("C9_EXPORT_WIDTH_DIRECTION_OR_SIGNED:" + name)
        dut_connections = [item for item in connected if item["module"] == exports["top"] and item["port"] == name]
        passive_connections = [item for item in connected if item["module"] == "r7a_c9_public_observer" and item["port"] == name]
        if len(dut_connections) != 1 or len(passive_connections) != 1 or any(
                item["expression"] != name for item in dut_connections + passive_connections):
            raise ValueError("C9_OBSERVATION_NOT_DIRECTLY_CAPTURED:" + name)
        comparisons.append({"port": name, "DUT": actual, "passive": passive, "official": declaration})
    return {"schema": "M3_R8_02_C9_STATIC_BINDING_RESULT_V1", "status": "PENDING_C9_FUNCTIONAL_AND_HDL_NOT_RUN",
            "legacy_lexical_result": original, "comparisons": comparisons,
            "request": request, "compile_proven": False, "execution_permission": "NOT_GRANTED",
            "real_pass": False, "board_release_allowed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        raw = args.request.read_bytes()
        with (args.output / "INPUT.raw.json").open("xb") as stream:
            stream.write(raw)
        result = evaluate(json.loads(raw))
        code = 3
    except Exception as error:
        result = {"status": "REJECT", "error": type(error).__name__ + ":" + str(error),
                  "real_pass": False, "board_release_allowed": False}
        code = 2
    with (args.output / "RESULT.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
