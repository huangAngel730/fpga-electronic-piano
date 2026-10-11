"""V0284 closure repair only: immutable math, isolated imports, no math replay.

The two fixed historical archives are independent trust anchors: re-signing a
new manifest does not make a changed dependency acceptable. No tool imports a
worktree math module. A worker imports the original nine files inside a fresh
capsule using Python -I -S and a path-and-byte allowlist.
"""

import argparse
import ast
import base64
import hashlib
import importlib
import importlib.abc
import importlib.machinery
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
DOC = ROOT / "code/docs/hardware/polyphony_scaling_v1"
OLD = DOC / "B2M_20261011"
M2 = ROOT / "code/docs/evidence/m2_t061_b2m_review_20261011"
OLD_SHA = "40e83004ce0497b49b91810998c8f60fb34fc3db0fa2f411ecb6560a69a013a5"
M2_SHA = "6bebeb5e5d742105c5e42cd331c9ec03f6426e30de123d569925e65e60f57fa1"
B = "code/software/polyphony_scaling_candidate/"
A = "code/software/audio_math_acceptance_candidate/"
MODULES = {name: B + name + ".py" for name in (
    "b2m_check", "b2k_check", "b2_clock", "b2j_check", "b2c_router_model", "inventory")}
MODULES.update({name: A + name + ".py" for name in (
    "dds_model", "envelope_model", "strict_capture")})
SUPPLEMENT = ("envelope_model", "strict_capture")
ROM = "code/rtl/138K_try/hold_trials_20261005/L_locations_guard065/rom/"
ROMS = ("velocity_gain_rom.mem", "piano_band_4x256_8191.mem",
        "oct_ratio_q16.mem", "sub_ratio_q16.mem", "lfo_sine_q15.mem")
DOCUMENT = "B2M_CLOSURE_REPAIR_20261012.md"
STATUS = "B2M_DEPENDENCY_CLOSURE_PASS_MATH_REUSED_T061_PARTIAL"


def require(condition, diagnostic):
    if not condition:
        raise ValueError(diagnostic)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def meta(data):
    return dict(bytes=len(data), sha256=sha(data))


def dump(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def fresh(path):
    path = path.resolve()
    require(path != ROOT / "code/output" and path.is_relative_to(ROOT / "code/output"),
            "B2M_CLOSURE_OUTPUT_SCOPE")
    path.mkdir(parents=True, exist_ok=False)
    return path


def unzip(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)) and archive.testzip() is None,
                "B2M_CLOSURE_ZIP")
        for name in names:
            p = PurePosixPath(name)
            require(not p.is_absolute() and ".." not in p.parts and "\\" not in name
                    and ":" not in name and not name.endswith("/"), "B2M_CLOSURE_PATH")
        return {n: archive.read(n) for n in names}


def encode(payload):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(payload.items()):
            archive.writestr(name, data)
    raw = stream.getvalue()
    return raw, dict(zip_sha256=sha(raw), members={n: meta(d) for n, d in payload.items()})


def baseline(old_raw, m2_raw):
    require(sha(old_raw) == OLD_SHA and sha(m2_raw) == M2_SHA, "B2M_CLOSURE_ANCHOR_SHA")
    old, reviewed = unzip(old_raw), unzip(m2_raw)
    deps = {}
    for name, path in MODULES.items():
        deps[path] = (reviewed["M2_GIT_SUPPLEMENTAL_NOT_ORIGINAL/" + name + ".py"]
                      if name in SUPPLEMENT else old[path])
    # The original workflow object is evidence, not executed again.
    receipt = json.loads(reviewed["M3_original/workflow_receipt.json"])
    independent = json.loads(reviewed["M2_run/receipt.json"])
    captures = {}
    for label, item in receipt["original_inputs"].items():
        original = old[item["restored_identity"]["path"]]
        require(original == reviewed["M2_run/" + label + ".capture"],
                "B2M_CLOSURE_CAPTURE_DRIFT")
        captures["captures/" + label + ".capture"] = original
    require(independent["exit_code"] == 0 and len(independent["profiles"]) == 3,
            "B2M_CLOSURE_REUSED_RECEIPT")
    require(sum(p["counts"]["published_pcm_checked"] for p in independent["profiles"]) == 63,
            "B2M_CLOSURE_REUSED_PUBLICATIONS")
    require(all(p["counts"]["first_valid_checked"] == 21 for p in independent["profiles"]),
            "B2M_CLOSURE_REUSED_PROFILES")
    # 189 valid/HOLD edges are the M2 signed count, not a new replay count.
    reused = dict(status="REUSED", reviewer="M2", review="V0284",
                  commit="7f4f79648c718f5bf469013e811035c42903aaa3",
                  receipt="historical/M2_RAW_EVIDENCE.zip::M2_run/receipt.json",
                  receipt_sha256=sha(reviewed["M2_run/receipt.json"]),
                  publications=63, valid_hold_edges=189, new_math_replays=0,
                  old_16_steps_executed=False, old_12_tests_executed=False,
                  original_missing_dependency_measurement="NOT_RETROACTIVELY_CREATED",
                  scope="single A4, zero modulation, specified cancellation/reset only")
    payload = {**deps, **captures, **{ROM + n: old[ROM + n] for n in ROMS}}
    return payload, reused


def static_import_closure(payload):
    seen, pending, edges = set(), ["b2m_check"], {}
    while pending:
        module = pending.pop()
        if module in seen:
            continue
        seen.add(module)
        found = set()
        for node in ast.walk(ast.parse(payload[MODULES[module]], filename=MODULES[module])):
            names = ([n.name.split(".")[0] for n in node.names] if isinstance(node, ast.Import)
                     else [node.module.split(".")[0]] if isinstance(node, ast.ImportFrom)
                     and node.module else [])
            for name in names:
                if name in MODULES:
                    found.add(name)
                else:
                    require(name in sys.stdlib_module_names, "B2M_CLOSURE_UNKNOWN_IMPORT:" + name)
        edges[module] = sorted(found)
        pending.extend(found)
    require(seen == set(MODULES), "B2M_CLOSURE_GRAPH_INCOMPLETE")
    return edges


def validate(payload, manifest):
    require(set(payload) == set(manifest["members"]), "B2M_CLOSURE_MEMBERS")
    require(all(meta(data) == manifest["members"][name] for name, data in payload.items()),
            "B2M_CLOSURE_MEMBER_SHA")
    expected, reused = baseline(payload["historical/B2M_original.zip"],
                                payload["historical/M2_RAW_EVIDENCE.zip"])
    for path, data in expected.items():
        require(path in payload, "B2M_CLOSURE_MISSING_DEPENDENCY:" + path)
        require(payload[path] == data, "B2M_CLOSURE_PINNED_IDENTITY:" + path)
    require(json.loads(payload["REUSED.json"]) == reused, "B2M_CLOSURE_REUSED_BINDING")
    return expected, reused, static_import_closure(payload)


def read_package(package):
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    carrier = (package / "evidence.zip.b64").read_bytes()
    require(sha(carrier) == manifest["carrier_sha256"], "B2M_CLOSURE_CARRIER_SHA")
    raw = base64.b64decode(carrier, validate=True)
    require(sha(raw) == manifest["zip_sha256"], "B2M_CLOSURE_ARCHIVE_SHA")
    payload = unzip(raw)
    validate(payload, manifest)
    return payload, manifest


def worker(root, outside=None):
    root = root.resolve()
    contract = json.loads((root / "IMPORTS.json").read_text(encoding="utf-8"))

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname not in MODULES:
                # copy.py probes optional org.python.core on CPython. A missing
                # optional module must remain ImportError, not a guard failure.
                spec = importlib.machinery.PathFinder.find_spec(fullname, path)
                if spec is None:
                    return None
                require(fullname.split(".")[0] in sys.stdlib_module_names,
                        "B2M_CLOSURE_IMPORT_NOT_ALLOWED:" + fullname)
                if spec.origin and spec.origin not in ("built-in", "frozen"):
                    origin = Path(spec.origin).resolve()
                    base = Path(sys.base_prefix).resolve()
                    require((origin.is_relative_to(base / "Lib")
                             and not origin.is_relative_to(base / "Lib/site-packages"))
                            or origin.is_relative_to(base / "DLLs"),
                            "B2M_CLOSURE_STDLIB_SHADOW:" + fullname)
                return None
            spec = importlib.machinery.PathFinder.find_spec(fullname, path)
            require(spec is not None and spec.origin is not None,
                    "B2M_CLOSURE_IMPORT_MISSING:" + fullname)
            origin = Path(spec.origin).resolve()
            require(origin == root / MODULES[fullname] and origin.is_relative_to(root),
                    "B2M_CLOSURE_OUTSIDE_IMPORT:" + fullname)
            require(meta(origin.read_bytes()) == contract[fullname],
                    "B2M_CLOSURE_IMPORT_SHA:" + fullname)
            return spec

    sys.dont_write_bytecode = True
    sys.path[:0] = [str(root / B), str(root / A)]
    sys.meta_path.insert(0, Guard())
    if outside:
        sys.path.insert(0, str(outside.resolve()))
        importlib.import_module("envelope_model")
        raise ValueError("B2M_CLOSURE_OUTSIDE_IMPORT_ACCEPTED")
    importlib.import_module("b2m_check")
    loaded = {}
    for name, path in MODULES.items():
        require(name in sys.modules, "B2M_CLOSURE_RUNTIME_INCOMPLETE:" + name)
        origin = Path(sys.modules[name].__file__).resolve()
        require(origin == root / path, "B2M_CLOSURE_RUNTIME_ORIGIN:" + name)
        loaded[path] = meta(origin.read_bytes())
    return dict(status="ISOLATED_IMPORT_PASS", exit_code=0, imported=loaded,
                math_functions_executed=0, isolated=True, no_site=True)


def restore(payload, destination):
    destination.mkdir(parents=True, exist_ok=False)
    expected, _ = baseline(payload["historical/B2M_original.zip"],
                           payload["historical/M2_RAW_EVIDENCE.zip"])
    for path in expected:
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(payload[path])
    dump(destination / "IMPORTS.json", {n: meta(payload[p]) for n, p in MODULES.items()})


class Bounded:
    def __init__(self, out):
        self.out, self.start, self.steps = out, time.monotonic(), []

    def call(self, label, argv, expected=0, diagnostic=None):
        timeout = min(90, 300 - (time.monotonic() - self.start))
        require(timeout > 0, "B2M_CLOSURE_TOTAL_TIMEOUT")
        begin = time.monotonic()
        env = os.environ.copy()
        for key in ("PYTHONPATH", "PYTHONHOME"):
            env.pop(key, None)
        try:
            result = subprocess.run(argv, cwd=self.out, env=env, capture_output=True,
                                    timeout=timeout, check=False)
            stdout, stderr, code, expired = result.stdout, result.stderr, result.returncode, False
        except subprocess.TimeoutExpired as error:
            stdout, stderr, code, expired = error.stdout or b"", error.stderr or b"", None, True
        for suffix, data in (("stdout", stdout), ("stderr", stderr)):
            with (self.out / (label + "." + suffix + ".bin")).open("xb") as stream:
                stream.write(data)
        step = dict(label=label, command=argv, exit_code=code, expected_exit=expected,
                    timed_out=expired, timeout_seconds=timeout,
                    elapsed_seconds=time.monotonic() - begin,
                    stdout=meta(stdout), stderr=meta(stderr))
        self.steps.append(step)
        dump(self.out / (label + ".execution.json"), step)
        require(not expired and type(code) is int and code == expected,
                "B2M_CLOSURE_STEP:" + label)
        if diagnostic:
            require(json.loads(stdout)["diagnostic"].startswith(diagnostic),
                    "B2M_CLOSURE_DIAGNOSTIC:" + label)
        return json.loads(stdout)


def isolated(payload, out, bounded, outside=None):
    restore(payload, out)
    argv = [sys.executable, "-I", "-S", str(Path(__file__).resolve()),
            "worker", "--root", str(out)]
    if outside:
        argv += ["--outside", str(outside)]
    return bounded.call(out.name, argv, 1 if outside else 0,
                        "B2M_CLOSURE_OUTSIDE_IMPORT:" if outside else None)


def new_payload():
    old_raw = base64.b64decode((OLD / "evidence.zip.b64").read_bytes(), validate=True)
    m2_raw = (M2 / "RAW_EVIDENCE.zip").read_bytes()
    expected, reused = baseline(old_raw, m2_raw)
    for name, data in expected.items():
        if not name.startswith("captures/"):
            require((ROOT / name).read_bytes() == data, "B2M_CLOSURE_CURRENT_DRIFT:" + name)
    payload = dict(expected)
    payload.update({"historical/B2M_original.zip": old_raw,
                    "historical/M2_RAW_EVIDENCE.zip": m2_raw,
                    "REUSED.json": (json.dumps(reused, indent=2) + "\n").encode()})
    for p in (HERE / "b2m_run.py", HERE / "b2m_closure.py", HERE / "test_b2m_closure.py",
              DOC / "deliver_b2m.py", DOC / DOCUMENT):
        payload[p.relative_to(ROOT).as_posix()] = p.read_bytes()
    return payload


def run(out):
    out = fresh(out)
    bounded = Bounded(out)
    report = dict(status="FAIL", exit_code=1, task_complete=False, total_limit_seconds=300,
                  step_limit_seconds=90, new_RTL_simulation=False, new_synthesis=False,
                  new_PnR=False, device_operations=False, new_math_replays=0)
    paths = [ROOT / p for p in MODULES.values()] + [ROOT / (ROM + n) for n in ROMS]
    paths += [HERE / "b2m_closure.py", HERE / "test_b2m_closure.py", HERE / "b2m_run.py",
              DOC / "deliver_b2m.py", OLD / "evidence.zip.b64", OLD / "manifest.json",
              OLD / "seal_receipt.json", M2 / "RAW_EVIDENCE.zip", M2 / "SUMMARY.json"]
    paths += [ROOT / "code/docs" / name for name in (
        "当前状态.md", "任务看板.md", "技术决策记录.md", "验证记录.md", "模块接口规范.md")]
    def identities():
        return {p.relative_to(ROOT).as_posix(): meta(p.read_bytes()) for p in paths}
    report["inputs_before"] = identities()
    report["python_before"] = dict(path=sys.executable, **meta(Path(sys.executable).read_bytes()))
    try:
        payload = new_payload()
        _, manifest = encode(payload)
        _, report["reused_math"], report["static_graph"] = validate(payload, manifest)
        report["new_dependency_before"] = {p: meta(payload[p]) for p in MODULES.values()}
        report["normal"] = isolated(payload, out / "normal_import", bounded)
        report["negative_cases"] = []
        for module in SUPPLEMENT:
            for kind in ("missing", "resigned_changed"):
                bad = dict(payload)
                if kind == "missing":
                    del bad[MODULES[module]]
                    diagnostic = "B2M_CLOSURE_MISSING_DEPENDENCY:"
                else:
                    bad[MODULES[module]] += b"\n# changed dependency, fully re-signed archive\n"
                    diagnostic = "B2M_CLOSURE_PINNED_IDENTITY:"
                raw, resigned = encode(bad)
                # Recalculate ZIP, carrier and EVERY member SHA, not a cheap hash mismatch.
                carrier = base64.b64encode(raw)
                resigned["carrier_sha256"] = sha(carrier)
                bad_dir = out / (kind + "_" + module)
                bad_dir.mkdir()
                (bad_dir / "evidence.zip.b64").write_bytes(carrier)
                dump(bad_dir / "manifest.json", resigned)
                result = bounded.call(bad_dir.name, [sys.executable, "-I", "-S",
                    str(Path(__file__).resolve()), "validate", "--package", str(bad_dir)],
                    1, diagnostic)
                report["negative_cases"].append(dict(case=bad_dir.name, **result))
        outside = out / "outside_models"
        outside.mkdir()
        (outside / "envelope_model.py").write_bytes(payload[MODULES["envelope_model"]])
        result = isolated(payload, out / "outside_import", bounded, outside)
        report["negative_cases"].append(dict(case="outside_import_same_bytes", **result))
        units = bounded.call("new_closure_units", [sys.executable, "-I", "-S",
                            str(HERE / "test_b2m_closure.py")])
        report["new_software_selftests"] = units
        report["new_dependency_after"] = {p: meta((out / "normal_import" / p).read_bytes())
                                          for p in MODULES.values()}
        require(report["new_dependency_before"] == report["new_dependency_after"],
                "B2M_CLOSURE_EXECUTION_DEPENDENCY_DRIFT")
        report.update(status=STATUS, exit_code=0)
    except Exception as error:
        report["diagnostic"] = type(error).__name__ + ":" + str(error)
    report["inputs_after"] = identities()
    report["python_after"] = dict(path=sys.executable, **meta(Path(sys.executable).read_bytes()))
    report["steps"] = bounded.steps
    report["elapsed_seconds"] = time.monotonic() - bounded.start
    if (report["inputs_before"] != report["inputs_after"]
            or report["python_before"] != report["python_after"]
            or report["elapsed_seconds"] > 300):
        report.update(status="FAIL", exit_code=1, diagnostic="B2M_CLOSURE_DRIFT_OR_TIMEOUT")
    dump(out / "receipt.json", report)
    return report


def seal(run_dir, package):
    package = package.resolve()
    require(package != DOC and package.is_relative_to(DOC) and package != OLD,
            "B2M_CLOSURE_PACKAGE_SCOPE")
    report = json.loads((run_dir / "receipt.json").read_text(encoding="utf-8"))
    require(report["status"] == STATUS and type(report["exit_code"]) is int
            and report["exit_code"] == 0 and report["new_math_replays"] == 0
            and report["inputs_before"] == report["inputs_after"]
            and 0 < report["elapsed_seconds"] <= 300
            and len(report["negative_cases"]) == 5, "B2M_CLOSURE_UNQUALIFIED_RUN")
    for name, item in report["inputs_after"].items():
        require(meta((ROOT / name).read_bytes()) == item, "B2M_CLOSURE_SEAL_DRIFT:" + name)
    payload = new_payload()
    payload["new_execution/receipt.json"] = (run_dir / "receipt.json").read_bytes()
    for p in sorted(run_dir.iterdir()):
        if p.is_file() and p.name != "receipt.json":
            payload["new_execution/" + p.name] = p.read_bytes()
    first_failure = ROOT / "code/output/m3_b2m_closure_20261012_01"
    for p in sorted(first_failure.glob("*")):
        if p.is_file():
            payload["repair_first_failure/" + p.name] = p.read_bytes()
    raw, manifest = encode(payload)
    carrier = base64.b64encode(raw)
    manifest.update(carrier_sha256=sha(carrier), status=STATUS, task_complete=False,
                    committed_at_seal=False, pushed_at_seal=False,
                    new_execution_receipt="new_execution/receipt.json")
    validate(payload, manifest)
    package.mkdir(parents=True, exist_ok=False)
    (package / "evidence.zip.b64").write_bytes(carrier)
    dump(package / "manifest.json", manifest)
    result = dict(status="B2M_CLOSURE_SEALED_PENDING_ISOLATED_VERIFY", exit_code=0,
                  zip_sha256=sha(raw), members=len(payload), new_math_replays=0)
    dump(package / "seal_receipt.json", result)
    return result


def qualify_payload(payload):
    """Bind new execution claims to the exact sealed commands and raw logs."""
    r = json.loads(payload["new_execution/receipt.json"])
    require(r["status"] == STATUS and type(r["exit_code"]) is int and r["exit_code"] == 0
            and r["task_complete"] is False and r["new_math_replays"] == 0
            and r["inputs_before"] == r["inputs_after"]
            and r["python_before"] == r["python_after"]
            and r["new_dependency_before"] == r["new_dependency_after"]
            and 0 < r["elapsed_seconds"] <= 300 and r["total_limit_seconds"] == 300
            and r["step_limit_seconds"] == 90 and len(r["negative_cases"]) == 5
            and len(r["steps"]) == 7 and r["new_software_selftests"]["tests_run"] == 8
            and all(r[k] is False for k in ("new_RTL_simulation", "new_synthesis",
                                           "new_PnR", "device_operations")),
            "B2M_CLOSURE_EXECUTION_SCOPE")
    for name, item in r["new_dependency_before"].items():
        require(meta(payload[name]) == item, "B2M_CLOSURE_EXECUTION_SOURCE_SHA")
    for name in (B + "b2m_closure.py", B + "test_b2m_closure.py", B + "b2m_run.py",
                 "code/docs/hardware/polyphony_scaling_v1/deliver_b2m.py"):
        require(meta(payload[name]) == r["inputs_before"][name],
                "B2M_CLOSURE_EXECUTION_TOOL_SHA")
    for step in r["steps"]:
        require(type(step["exit_code"]) is int and step["exit_code"] == step["expected_exit"]
                and step["timed_out"] is False
                and 0 <= step["elapsed_seconds"] <= step["timeout_seconds"] <= 90,
                "B2M_CLOSURE_EXECUTION_STEP")
        label = step["label"]
        require(json.loads(payload["new_execution/" + label + ".execution.json"]) == step,
                "B2M_CLOSURE_EXECUTION_LOG")
        for stream in ("stdout", "stderr"):
            require(meta(payload["new_execution/" + label + "." + stream + ".bin"])
                    == step[stream], "B2M_CLOSURE_EXECUTION_LOG_SHA")
    require(r["reused_math"] == json.loads(payload["REUSED.json"]),
            "B2M_CLOSURE_EXECUTION_REUSED")
    return r


def verify(package, output):
    out = fresh(output)
    bounded = Bounded(out)
    payload, manifest = read_package(package)
    qualify_payload(payload)
    _, reused, graph = validate(payload, manifest)
    # Models come exclusively from payload, not the current repository.
    result = isolated(payload, out / "sealed_import", bounded)
    report = dict(status="B2M_CLOSURE_ISOLATED_PACKAGE_VERIFIED", exit_code=0,
                  zip_sha256=manifest["zip_sha256"], members=len(payload),
                  imported=result["imported"], reused_math=reused, static_graph=graph,
                  new_math_replays=0, task_complete=False, steps=bounded.steps)
    dump(out / "receipt.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "seal", "verify", "worker", "validate"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--outside", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.mode == "run":
            result = run(args.output)
        elif args.mode == "seal":
            result = seal(args.run, args.package)
        elif args.mode == "verify":
            result = verify(args.package, args.output)
        elif args.mode == "worker":
            result = worker(args.root, args.outside)
        else:
            read_package(args.package)
            result = dict(status="B2M_CLOSURE_STATIC_VALID", exit_code=0)
    except Exception as error:
        result = dict(status="FAIL", exit_code=1, diagnostic=str(error))
    if args.mode == "run":
        print(json.dumps({k: result.get(k) for k in (
            "status", "exit_code", "elapsed_seconds", "diagnostic")}, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
