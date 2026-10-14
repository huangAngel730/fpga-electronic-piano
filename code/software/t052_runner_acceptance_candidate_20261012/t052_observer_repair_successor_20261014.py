"""One-shot T052 successor for the independently reviewed observer fix.

Preparation performs identity checks and writes a fresh config, approval, and
binding only.  Launch consumes exactly one outer marker and delegates the
existing compile/run/check implementation under the original time budgets.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import types


ROOT = Path("E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano")
HERE = Path(__file__).resolve().parent
REVIEW_KEY = "T052-M3-20261014-OBSERVER-REPAIR-PRELAUNCH-R08"
ATTEMPT_NUMBER = 2
PYTHON = Path(
    "C:/Users/songdongkuan/.cache/codex-runtimes/"
    "codex-primary-runtime/dependencies/python/python.exe"
)
ONESHOT = ROOT / (
    "code/software/t052_publication_acceptance_candidate_20261012/"
    "rtl_capture_precheck_20261012/oneshot_20261013/oneshot.py"
)
CHECKER = ROOT / (
    "code/software/t052_publication_acceptance_candidate_20261012/"
    "rtl_capture_precheck_20261012/successor_20261013/checker.py"
)
ENV_SUCCESSOR = HERE / "t052_environment_successor_20261014.py"
SUPERVISOR = HERE / "supervisor_20261013.py"
RUNNER_TAIL = HERE / "runner_tail_20261013.py"
RUNNER = HERE / "runner.py"
WINDOWS_JOB = HERE / "windows_job.py"

OBSERVER = ROOT / (
    "code/tb/audio/t052_publication_acceptance_candidate_20261012/"
    "successor_20261013/t052_public_observer_v2.sv"
)
SCHEDULE_CHECK = OBSERVER.parent / "schedule_check.py"
TEST_SCHEDULE = OBSERVER.parent / "test_schedule.py"

OLD_ROOT = ROOT / "code/output/m3_t052_full_capture_prepare_20261014_03"
OLD_CONFIG = OLD_ROOT / "prepared/config.json"
OLD_MANIFEST = OLD_ROOT / "prepared/manifest.json"
OLD_APPROVAL = OLD_ROOT / "approval.json"
OLD_OUTER_MARKER = OLD_ROOT / "outer_consumed.json"
OLD_CHILD_MARKER = OLD_ROOT / "prepared/consumed.json"
OLD_RECEIPT = OLD_ROOT / "prepared/actual_once/receipt.json"
OLD_PARENT = ROOT / "code/output/m3_t052_full_capture_parent_20261014_03"
OLD_OBSERVATION = OLD_PARENT / "observation.json"
OLD_SEAL = ROOT / (
    "code/output/m3_t052_review_seal_20261014_r03/"
    "T052_M3_FULL_R03.zip"
)

ATTEMPT_ROOT = ROOT / "code/output/m3_t052_observer_repair_prepare_20261014_10"
PREPARED = ATTEMPT_ROOT / "prepared"
CONFIG = PREPARED / "config.json"
MANIFEST = PREPARED / "manifest.json"
APPROVAL = ATTEMPT_ROOT / "approval.json"
BINDING = ATTEMPT_ROOT / "observer_repair_binding.json"
OUTER_MARKER = ATTEMPT_ROOT / "outer_consumed.json"
WORKER_MARKER = ATTEMPT_ROOT / "worker_entry_consumed.json"
LAUNCH_COMMAND = ATTEMPT_ROOT / "launch_command.json"
CHILD_MARKER = PREPARED / "consumed.json"
OUTPUT = PREPARED / "actual_once"
PARENT = ROOT / "code/output/m3_t052_observer_repair_parent_20261014_10"
ATTEMPT09_FAILURE_SEAL = ROOT / (
    "code/output/m3_t052_observer_repair_attempt09_failure_seal_20261014/"
    "T052_OBSERVER_REPAIR_ATTEMPT09_FAILURE.zip"
)

BOOTSTRAP_CODE = (
    "import hashlib,pathlib,sys\n"
    "p=pathlib.Path(sys.argv[1]).resolve();n=int(sys.argv[2]);h=sys.argv[3];r=sys.argv[4]\n"
    "b=p.read_bytes()\n"
    "if len(b)!=n or hashlib.sha256(b).hexdigest()!=h: raise SystemExit('CONTROLLER_IDENTITY')\n"
    "if ('REVIEW_KEY = \\\"'+r+'\\\"').encode('utf-8') not in b: raise SystemExit('REVIEW_KEY')\n"
    "sys.argv=[str(p),*sys.argv[5:]]\n"
    "g={'__name__':'__main__','__file__':str(p),'__package__':None,'__cached__':None}\n"
    "exec(compile(b,str(p),'exec'),g,g)\n"
)
CHECKER_BOOTSTRAP_CODE = (
    "import hashlib,importlib.util,json,pathlib,sys\n"
    "cp=pathlib.Path(sys.argv[1]).resolve();cn=int(sys.argv[2]);ch=sys.argv[3]\n"
    "ap=pathlib.Path(sys.argv[4]).resolve();an=int(sys.argv[5]);ah=sys.argv[6]\n"
    "mp=pathlib.Path(sys.argv[7]).resolve();mn=int(sys.argv[8]);mh=sys.argv[9]\n"
    "cb=cp.read_bytes();ab=ap.read_bytes();mb=mp.read_bytes()\n"
    "if len(cb)!=cn or hashlib.sha256(cb).hexdigest()!=ch: raise SystemExit('CHECKER_IDENTITY')\n"
    "if len(ab)!=an or hashlib.sha256(ab).hexdigest()!=ah: raise SystemExit('CALENDAR_IDENTITY')\n"
    "if len(mb)!=mn or hashlib.sha256(mb).hexdigest()!=mh: raise SystemExit('MANIFEST_IDENTITY')\n"
    "a=sys.argv[10:];snap={ap:ab,mp:mb}\n"
    "if a[a.index('--manifest')+1]!=str(mp) or a[a.index('--manifest-sha')+1]!=mh: raise SystemExit('MANIFEST_ARG')\n"
    "for z in ('--plan','--receipt','--controls','--observations','--publications','--resets'):\n"
    " p=pathlib.Path(a[a.index(z)+1]).resolve();snap[p]=p.read_bytes()\n"
    "rp=pathlib.Path(a[a.index('--receipt')+1]).resolve()\n"
    "if hashlib.sha256(snap[rp]).hexdigest()!=a[a.index('--receipt-sha')+1]: raise SystemExit('RECEIPT_IDENTITY')\n"
    "m=json.loads(mb);pp=pathlib.Path(a[a.index('--plan')+1]).resolve();ps=m['plan']\n"
    "if len(snap[pp])!=ps['bytes'] or hashlib.sha256(snap[pp]).hexdigest()!=ps['sha256']: raise SystemExit('PLAN_IDENTITY')\n"
    "rb=pathlib.Path.read_bytes;rt=pathlib.Path.read_text\n"
    "def br(self):\n"
    " q=self.resolve();return snap[q] if q in snap else rb(self)\n"
    "def tr(self,encoding=None,errors=None):\n"
    " q=self.resolve();return snap[q].decode(encoding or 'utf-8',errors or 'strict') if q in snap else rt(self,encoding=encoding,errors=errors)\n"
    "pathlib.Path.read_bytes=br;pathlib.Path.read_text=tr\n"
    "class L:\n"
    " def create_module(self,s): return None\n"
    " def exec_module(self,m): exec(compile(ab,str(ap),'exec'),m.__dict__,m.__dict__)\n"
    "o=importlib.util.spec_from_file_location\n"
    "def f(n,p,*a,**k):\n"
    " q=pathlib.Path(p).resolve()\n"
    " return importlib.util.spec_from_loader(n,L(),origin=str(q)) if q==ap else o(n,p,*a,**k)\n"
    "importlib.util.spec_from_file_location=f\n"
    "sys.argv=[str(cp),*a]\n"
    "g={'__name__':'t052_pinned_checker','__file__':str(cp),'__package__':None,'__cached__':None}\n"
    "exec(compile(cb,str(cp),'exec'),g,g)\n"
    "raise SystemExit(g['main']())\n"
)

EXPECTED_OBSERVER = {
    "bytes": 8327,
    "sha256": "ec5e18ddc6d41f6de8ec229da42ccbd9550bfbb85eb9cbf461181c811e7769d3",
}
EXPECTED_AUDIT_SOURCES = {
    str(SCHEDULE_CHECK.resolve()): {
        "bytes": 11457,
        "sha256": "1cda95fe1a284d5138dc662f7dff16ef00a1b8ee3f0b714ac100f6bffe90f189",
    },
    str(TEST_SCHEDULE.resolve()): {
        "bytes": 5278,
        "sha256": "bcc44ee90633c0945d53333a8af6bd47d29005165995f1db7c14e2f7194ee3da",
    },
}
OLD_OBSERVER_SHA = "d8bb2dd012c2dcb5ef31caf4ee5399e3a1b84514068816d0d932068c780ea88a"
PLAN_SHA = "b2d0cb1ba0bf3cd4b2d636f3d4cb7ac286558238ae2b52c3e9e43ba54ee5ef02"
CALENDAR_SHA = "0fdf4bb1530453cbbce14136bcae082ca1ff28e04d96402065f4c916ecf36058"
PRIMARY_TOOLS = {
    "compile": "5c1f4e38c6dc0807aeab8814d63af97313bef5813e815e17021ae8e36e0a0bab",
    "runtime": "d38cc76e6946136aaf46db8a3bf34bec2a54bad564dfe146686579ca2d39c9ed",
    "python": "d41bad46673f64e0d02f23797f53f90ccf60f27d6eda8d86dd2d4bbeae5a858c",
}
BUDGETS = {"total": 300, "compile": 90, "run": 90, "check": 90}
CALLS = {"compile": 1, "run": 1, "check": 1, "version_queries": 0}


def need(condition: bool, diagnostic: str) -> None:
    if not condition:
        raise ValueError(diagnostic)


def identity(path: Path | str) -> dict[str, object]:
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def read(path: Path | str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def decode_json(raw: bytes) -> dict:
    def unique_pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_pairs,
                      parse_constant=lambda value: need(
                          False, "NONFINITE_JSON:" + value))


def read_bound_json(path: Path, expected_sha: str) -> tuple[dict, dict, bytes]:
    raw = path.read_bytes()
    actual = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    need(actual["sha256"] == expected_sha, "BOUND_JSON_SHA:" + str(path))
    return decode_json(raw), actual, raw


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n").encode("utf-8")


def write_new(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical_json_bytes(value))


def spec(path: Path) -> dict[str, object]:
    path = path.resolve()
    return {"path": path.relative_to(ROOT).as_posix(), **identity(path)}


def source_container_identities(manifest: dict) -> dict[str, dict[str, object]]:
    """Bind archive files separately from the member identities in manifest."""
    result = {}
    for item in manifest["sources"].values():
        if "member" not in item:
            continue
        path = Path(item["path"])
        if not path.is_absolute():
            path = ROOT / path
        path = path.resolve()
        result[str(path)] = identity(path)
    return result


def preparation_modules():
    env = load_unpinned("t052_observer_env_prepare", ENV_SUCCESSOR)
    old = load_unpinned("t052_observer_oneshot_prepare", ONESHOT)
    checker = load_unpinned("t052_observer_checker_prepare", CHECKER)
    return env, old, checker


def load_unpinned(name: str, path: Path):
    module_spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def bootstrap_argv(controller: dict[str, object], mode: str,
                   config_sha: str, approval_sha: str, binding_sha: str,
                   *, parent_pid: int | None = None) -> list[str]:
    argv = [str(PYTHON.resolve()), "-I", "-S", "-B", "-X", "utf8",
            "-c", BOOTSTRAP_CODE, str(Path(__file__).resolve()),
            str(controller["bytes"]), str(controller["sha256"]), REVIEW_KEY,
            mode, "--config-sha", config_sha,
            "--approval-sha", approval_sha,
            "--binding-sha", binding_sha]
    if parent_pid is not None:
        argv.extend(["--parent-pid", str(parent_pid)])
    return argv


def checker_bootstrap_argv(argv: list[str], checker_identity: dict,
                           calendar_path: Path,
                           calendar_raw: bytes,
                           manifest_raw: bytes) -> list[str]:
    checker_index = argv.index(str(CHECKER))
    need(checker_index > 0 and Path(argv[0]).resolve() == PYTHON.resolve(),
         "CHECKER_OR_PYTHON_COMMAND")
    calendar_identity = {
        "bytes": len(calendar_raw),
        "sha256": hashlib.sha256(calendar_raw).hexdigest(),
    }
    manifest_identity = {
        "bytes": len(manifest_raw),
        "sha256": hashlib.sha256(manifest_raw).hexdigest(),
    }
    return [*argv[:checker_index], "-c", CHECKER_BOOTSTRAP_CODE,
            str(CHECKER.resolve()), str(checker_identity["bytes"]),
            str(checker_identity["sha256"]), str(calendar_path.resolve()),
            str(calendar_identity["bytes"]), str(calendar_identity["sha256"]),
            str(MANIFEST.resolve()), str(manifest_identity["bytes"]),
            str(manifest_identity["sha256"]),
            *argv[checker_index + 1:]]


def software_identity(config: dict, path: Path) -> dict[str, object]:
    key = path.resolve().as_posix()
    need(key in config["software"], "SOFTWARE_NOT_BOUND:" + key)
    return config["software"][key]


def capture_software(config: dict, binding: dict) -> dict[str, bytes]:
    controller_path = Path(__file__).resolve()
    controller = software_identity(config, controller_path)
    need(binding["successor"]
         == {"path": str(controller_path), **controller},
         "CONTROLLER_BINDING")
    captured = {}
    for path_text, expected in config["software"].items():
        path = Path(path_text).resolve()
        raw = path.read_bytes()
        need({"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
             == expected, "SOFTWARE_DRIFT:" + path_text)
        captured[str(path)] = raw
    return captured


def execute_buffer(name: str, path: Path, raw: bytes):
    module = types.ModuleType(name)
    module.__file__ = str(path.resolve())
    module.__package__ = ""
    module.__cached__ = None
    sys.modules[name] = module
    exec(compile(raw, module.__file__, "exec"), module.__dict__, module.__dict__)
    return module


class BufferLoader:
    def __init__(self, path: Path, raw: bytes):
        self.path = path.resolve()
        self.raw = raw

    def create_module(self, _spec):
        return None

    def exec_module(self, module) -> None:
        exec(compile(self.raw, str(self.path), "exec"),
             module.__dict__, module.__dict__)


def capture_plain_spec(item: dict) -> tuple[Path, bytes]:
    need(set(item) == {"path", "bytes", "sha256"}, "CAPTURE_SPEC_FIELDS")
    path = Path(item["path"])
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    raw = path.read_bytes()
    need({"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
         == {"bytes": item["bytes"], "sha256": item["sha256"]},
         "CAPTURE_SPEC_IDENTITY:" + str(path))
    return path, raw


def verified_modules(config: dict, binding: dict, calendar_spec: dict):
    captured = capture_software(config, binding)
    calendar_path, calendar_raw = capture_plain_spec(calendar_spec)
    captured[str(calendar_path)] = calendar_raw

    def raw(path: Path) -> bytes:
        resolved = str(path.resolve())
        need(resolved in captured, "HELPER_NOT_CAPTURED:" + resolved)
        return captured[resolved]

    execute_buffer("windows_job", WINDOWS_JOB, raw(WINDOWS_JOB))
    original_spec = importlib.util.spec_from_file_location

    def pinned_spec(name, location, *args, **kwargs):
        path = Path(location).resolve()
        if path == RUNNER.resolve():
            return importlib.util.spec_from_loader(
                name, BufferLoader(path, raw(RUNNER)), origin=str(path))
        return original_spec(name, location, *args, **kwargs)

    importlib.util.spec_from_file_location = pinned_spec
    try:
        tail = execute_buffer(
            "runner_tail_20261013", RUNNER_TAIL, raw(RUNNER_TAIL))
    finally:
        importlib.util.spec_from_file_location = original_spec
    supervisor = execute_buffer(
        "t052_observer_supervisor", SUPERVISOR, raw(SUPERVISOR))
    env = execute_buffer("t052_observer_env", ENV_SUCCESSOR, raw(ENV_SUCCESSOR))
    checker = execute_buffer("t052_observer_checker", CHECKER, raw(CHECKER))
    old = execute_buffer("t052_observer_oneshot", ONESHOT, raw(ONESHOT))

    def pinned_import(_name, path):
        resolved = Path(path).resolve()
        if resolved == RUNNER_TAIL.resolve():
            return tail
        if resolved == CHECKER.resolve():
            return checker
        raise ValueError("UNPINNED_DYNAMIC_IMPORT:" + str(resolved))

    old.import_file = pinned_import
    return (env, old, checker, supervisor, tail, captured, calendar_path,
            calendar_raw)


def verify_tools(old, manifest: dict) -> None:
    suite = Path(manifest["tools"]["compile"]["path"]).parents[1]
    need(manifest["tools"] == old.tool_inventory(suite), "TOOL_INVENTORY_DRIFT")
    need(len(manifest["tools"]) == 1014, "TOOL_COUNT")
    need({key: manifest["tools"][key]["sha256"] for key in PRIMARY_TOOLS}
         == PRIMARY_TOOLS, "PRIMARY_TOOL_SHA")


def prepare() -> dict:
    need(platform.node() == "LAPTOP-KSS1MRR7", "MACHINE_MISMATCH")
    need(not ATTEMPT_ROOT.exists() and not PARENT.exists(), "ATTEMPT_OCCUPIED")
    env, old, checker = preparation_modules()
    need(identity(OBSERVER) == EXPECTED_OBSERVER, "OBSERVER_IDENTITY")
    for path, expected in EXPECTED_AUDIT_SOURCES.items():
        need(identity(path) == expected, "AUDIT_SOURCE_IDENTITY:" + path)

    old_manifest = read(OLD_MANIFEST)
    old_config = read(OLD_CONFIG)
    verify_tools(old, old_manifest)
    need(old_manifest["sources"]["observer"]["sha256"] == OLD_OBSERVER_SHA,
         "OLD_OBSERVER_IDENTITY")
    need(old_manifest["plan"]["sha256"] == PLAN_SHA, "PLAN_SHA")
    need(old_manifest["calendar"]["sha256"] == CALENDAR_SHA, "CALENDAR_SHA")

    manifest = json.loads(json.dumps(old_manifest))
    manifest["sources"]["observer"] = spec(OBSERVER)
    manifest["run_argv"] = [
        "+OBSERVER_SHA=" + EXPECTED_OBSERVER["sha256"]
        if value.startswith("+OBSERVER_SHA=") else value
        for value in manifest["run_argv"]
    ]
    PREPARED.mkdir(parents=True)
    write_new(MANIFEST, manifest)
    checker.load_manifest(MANIFEST, identity(MANIFEST)["sha256"])

    software_paths = [Path(__file__).resolve(), ONESHOT, CHECKER, ENV_SUCCESSOR,
                      SUPERVISOR, RUNNER_TAIL, RUNNER, WINDOWS_JOB,
                      SCHEDULE_CHECK, TEST_SCHEDULE]
    environment = dict(old_config["environment"])
    environment["TEMP"] = str((OUTPUT / "work").resolve())
    environment["TMP"] = str((OUTPUT / "work").resolve())
    config = dict(old_config)
    config.update(
        manifest={"path": str(MANIFEST.resolve()), **identity(MANIFEST)},
        software={path.as_posix(): identity(path) for path in software_paths},
        budgets_seconds=BUDGETS,
        calls=CALLS,
        output=str(OUTPUT.resolve()),
        marker=str(CHILD_MARKER.resolve()),
        worker_entry_marker=str(WORKER_MARKER.resolve()),
        environment=environment,
        T052_complete=False,
    )
    write_new(CONFIG, config)
    config_sha = identity(CONFIG)["sha256"]
    approval = {
        "schema": "T052_128_ONESHOT_APPROVAL_V1",
        "scope": "ONE_COMPILE_ONE_128_EDGE_RUN_ONE_CHECK",
        "approved": True,
        "config_sha256": config_sha,
        "machine": platform.node(),
        "calls": CALLS,
        "budgets_seconds": BUDGETS,
        "accept_static_dependency_inventory": True,
    }
    write_new(APPROVAL, approval)

    preserved = [OLD_CONFIG, OLD_MANIFEST, OLD_APPROVAL, OLD_OUTER_MARKER,
                 OLD_CHILD_MARKER, OLD_RECEIPT, OLD_OBSERVATION, OLD_SEAL,
                 ATTEMPT09_FAILURE_SEAL]
    binding = {
        "schema": "T052_OBSERVER_REPAIR_BINDING_V1",
        "review_key": REVIEW_KEY,
        "status": "PREPARED_AWAITING_INDEPENDENT_AUDIT",
        "attempt": ATTEMPT_NUMBER,
        "machine": platform.node(),
        "config": {"path": str(CONFIG.resolve()), **identity(CONFIG)},
        "manifest": {"path": str(MANIFEST.resolve()), **identity(MANIFEST)},
        "approval": {"path": str(APPROVAL.resolve()), **identity(APPROVAL)},
        "successor": {"path": str(Path(__file__).resolve()), **identity(__file__)},
        "observer_before_sha256": OLD_OBSERVER_SHA,
        "observer_after": {"path": str(OBSERVER.resolve()), **identity(OBSERVER)},
        "audit_sources": {path: identity(path) for path in EXPECTED_AUDIT_SOURCES},
        "frozen_source_roles": ["dut", "dds", "mixer", "rom", "tb", "driver_mem"],
        "plan_sha256": PLAN_SHA,
        "calendar_sha256": CALENDAR_SHA,
        "tools": {"count": 1014, "primary": PRIMARY_TOOLS},
        "source_containers": source_container_identities(manifest),
        "calls": CALLS,
        "budgets_seconds": BUDGETS,
        "automatic_retries": 0,
        "checker_bootstrap": {
            "bytes": len(CHECKER_BOOTSTRAP_CODE.encode("utf-8")),
            "sha256": hashlib.sha256(
                CHECKER_BOOTSTRAP_CODE.encode("utf-8")).hexdigest(),
        },
        "compile_argv": manifest["compile_argv"],
        "run_argv": manifest["run_argv"],
        "output": str(OUTPUT.resolve()),
        "child_marker": str(CHILD_MARKER.resolve()),
        "outer_marker": str(OUTER_MARKER.resolve()),
        "worker_entry_marker": str(WORKER_MARKER.resolve()),
        "launch_command": str(LAUNCH_COMMAND.resolve()),
        "parent": str(PARENT.resolve()),
        "preserved_evidence": {
            str(path.resolve()): identity(path) for path in preserved
        },
    }
    write_new(BINDING, binding)
    approval_sha = identity(APPROVAL)["sha256"]
    binding_sha = identity(BINDING)["sha256"]
    controller = software_identity(config, Path(__file__).resolve())
    launch_command = {
        "schema": "T052_STDLIB_BYTE_BOOTSTRAP_COMMAND_V1",
        "review_key": REVIEW_KEY,
        "argv": bootstrap_argv(controller, "launch", config_sha,
                               approval_sha, binding_sha),
        "cwd": str(ROOT.resolve()),
        "controller": {"path": str(Path(__file__).resolve()), **controller},
        "bootstrap": {"bytes": len(BOOTSTRAP_CODE.encode("utf-8")),
                      "sha256": hashlib.sha256(
                          BOOTSTRAP_CODE.encode("utf-8")).hexdigest()},
    }
    write_new(LAUNCH_COMMAND, launch_command)
    verify_config(config_sha, approval_sha, binding_sha, phase="prelaunch")
    return {
        "status": "PREPARED_LOCKED",
        "tool_calls": {"compile": 0, "run": 0, "check": 0, "gowin": 0},
        "config": binding["config"],
        "manifest": binding["manifest"],
        "approval": binding["approval"],
        "binding": {"path": str(BINDING.resolve()), **identity(BINDING)},
        "launch_command": {"path": str(LAUNCH_COMMAND.resolve()),
                           **identity(LAUNCH_COMMAND)},
    }


def verify_config(config_sha: str, approval_sha: str, binding_sha: str,
                  *, phase: str, parent_pid: int | None = None) -> tuple:
    need(platform.node() == "LAPTOP-KSS1MRR7", "MACHINE_MISMATCH")
    config, config_identity, _config_raw = read_bound_json(CONFIG, config_sha)
    approval, approval_identity, _approval_raw = read_bound_json(
        APPROVAL, approval_sha)
    binding, binding_identity, _binding_raw = read_bound_json(
        BINDING, binding_sha)
    controller = software_identity(config, Path(__file__).resolve())
    need(binding["review_key"] == REVIEW_KEY
         and binding["launch_command"] == str(LAUNCH_COMMAND.resolve())
         and config["worker_entry_marker"] == str(WORKER_MARKER.resolve())
         and binding["worker_entry_marker"] == str(WORKER_MARKER.resolve()),
         "EXECUTION_BINDING")
    need(binding["checker_bootstrap"] == {
        "bytes": len(CHECKER_BOOTSTRAP_CODE.encode("utf-8")),
        "sha256": hashlib.sha256(
            CHECKER_BOOTSTRAP_CODE.encode("utf-8")).hexdigest(),
    }, "CHECKER_BOOTSTRAP_BINDING")
    expected_launch_command = {
        "schema": "T052_STDLIB_BYTE_BOOTSTRAP_COMMAND_V1",
        "review_key": REVIEW_KEY,
        "argv": bootstrap_argv(controller, "launch", config_sha,
                               approval_sha, binding_sha),
        "cwd": str(ROOT.resolve()),
        "controller": {"path": str(Path(__file__).resolve()), **controller},
        "bootstrap": {"bytes": len(BOOTSTRAP_CODE.encode("utf-8")),
                      "sha256": hashlib.sha256(
                          BOOTSTRAP_CODE.encode("utf-8")).hexdigest()},
    }
    launch_raw = LAUNCH_COMMAND.read_bytes()
    expected_launch_raw = canonical_json_bytes(expected_launch_command)
    need(launch_raw == expected_launch_raw,
         "LAUNCH_COMMAND_BINDING")
    launch_identity = {
        "bytes": len(expected_launch_raw),
        "sha256": hashlib.sha256(expected_launch_raw).hexdigest(),
    }
    manifest_raw = MANIFEST.read_bytes()
    manifest_identity = {
        "bytes": len(manifest_raw),
        "sha256": hashlib.sha256(manifest_raw).hexdigest(),
    }
    current_manifest = {"path": str(MANIFEST.resolve()), **manifest_identity}
    need(current_manifest == config["manifest"]
         and current_manifest == binding["manifest"],
         "MANIFEST_BINDING")
    manifest_candidate = decode_json(manifest_raw)
    expected_container_paths = {
        str((Path(item["path"]) if Path(item["path"]).is_absolute()
             else ROOT / item["path"]).resolve())
        for item in manifest_candidate["sources"].values()
        if "member" in item
    }
    need(set(binding["source_containers"]) == expected_container_paths,
         "SOURCE_CONTAINER_SET")
    for path_text, expected in binding["source_containers"].items():
        need(identity(Path(path_text)) == expected,
             "SOURCE_CONTAINER_DRIFT:" + path_text)
    old_manifest = read(OLD_MANIFEST)
    (env, old, checker, supervisor, tail, captured, calendar_path,
     calendar_raw) = verified_modules(
         config, binding, manifest_candidate["calendar"])
    checker_identity = checker.identity
    checker_read_json = checker.read_json

    def pinned_identity(path):
        if Path(path).resolve() == MANIFEST.resolve():
            return manifest_identity
        return checker_identity(path)

    def pinned_read_json(path):
        if Path(path).resolve() == MANIFEST.resolve():
            return checker.decode(manifest_raw)
        return checker_read_json(path)

    checker.identity = pinned_identity
    checker.read_json = pinned_read_json
    manifest = checker.load_manifest(MANIFEST, current_manifest["sha256"])
    need(config["machine"] == platform.node(), "CONFIG_MACHINE")
    need(config["budgets_seconds"] == BUDGETS and config["calls"] == CALLS,
         "BUDGETS_OR_CALLS")
    need(identity(OBSERVER) == EXPECTED_OBSERVER, "OBSERVER_DRIFT")
    for role in binding["frozen_source_roles"]:
        need(manifest["sources"][role] == old_manifest["sources"][role],
             "FROZEN_SOURCE_CHANGED:" + role)
    need(manifest["sources"]["observer"] == spec(OBSERVER),
         "OBSERVER_MANIFEST")
    need(manifest["plan"] == old_manifest["plan"]
         and manifest["calendar"] == old_manifest["calendar"],
         "PLAN_OR_CALENDAR_CHANGED")
    need(manifest["compile_argv"] == old_manifest["compile_argv"],
         "COMPILE_COMMAND_CHANGED")
    expected_run = [
        "+OBSERVER_SHA=" + EXPECTED_OBSERVER["sha256"]
        if value.startswith("+OBSERVER_SHA=") else value
        for value in old_manifest["run_argv"]
    ]
    need(manifest["run_argv"] == expected_run, "RUN_COMMAND_CHANGED")
    verify_tools(old, manifest)
    need(software_identity(config, CHECKER)["sha256"] == old.CHECKER_SHA,
         "CHECKER_CHANGED")
    suite = Path(manifest["tools"]["compile"]["path"]).parents[1]
    actual_environment = old.fixed_environment(suite, OUTPUT / "work")
    audit = env.environment_audit(config["environment"], actual_environment,
                                  suite, OUTPUT)
    expected_approval = {
        "schema": "T052_128_ONESHOT_APPROVAL_V1",
        "scope": "ONE_COMPILE_ONE_128_EDGE_RUN_ONE_CHECK",
        "approved": True,
        "config_sha256": config_sha,
        "machine": platform.node(),
        "calls": CALLS,
        "budgets_seconds": BUDGETS,
        "accept_static_dependency_inventory": True,
    }
    need(approval == expected_approval, "APPROVAL_SCOPE")
    need(binding["config"] == {"path": str(CONFIG.resolve()),
                               **config_identity}
         and binding["approval"] == {"path": str(APPROVAL.resolve()),
                                     **approval_identity},
         "BINDING_CONTROL_SHA")
    for path, expected in binding["preserved_evidence"].items():
        need(identity(path) == expected, "PRESERVED_EVIDENCE_DRIFT:" + path)
    need(phase in ("prelaunch", "worker"), "VERIFY_PHASE")
    if phase == "prelaunch":
        need(not OUTPUT.exists() and not CHILD_MARKER.exists()
             and not OUTER_MARKER.exists() and not WORKER_MARKER.exists()
             and not PARENT.exists(),
             "ATTEMPT_NOT_FRESH")
    else:
        need(type(parent_pid) is int and parent_pid > 0, "WORKER_PARENT_PID")
        need(not OUTPUT.exists() and not CHILD_MARKER.exists(),
             "WORKER_OUTPUT_ALREADY_CONSUMED")
        need(PARENT.is_dir(), "WORKER_PARENT_MISSING")
        expected_outer = {
            "schema": "T052_OBSERVER_REPAIR_OUTER_MARKER_V1",
            "attempt": ATTEMPT_NUMBER,
            "machine": platform.node(),
            "config_sha256": config_sha,
            "approval_sha256": approval_sha,
            "binding_sha256": binding_sha,
            "worker_parent_pid": parent_pid,
            "automatic_retries": 0,
        }
        need(OUTER_MARKER.is_file() and read(OUTER_MARKER) == expected_outer,
             "OUTER_MARKER_STATE")
        expected_worker = {
            "schema": "T052_OBSERVER_REPAIR_WORKER_ENTRY_V1",
            "review_key": REVIEW_KEY,
            "attempt": ATTEMPT_NUMBER,
            "machine": platform.node(),
            "config_sha256": config_sha,
            "approval_sha256": approval_sha,
            "binding_sha256": binding_sha,
            "parent_pid": parent_pid,
            "automatic_retries": 0,
        }
        need(WORKER_MARKER.is_file() and read(WORKER_MARKER) == expected_worker,
             "WORKER_MARKER_STATE")
    controls = {
        str(CONFIG.resolve()): config_identity,
        str(APPROVAL.resolve()): approval_identity,
        str(BINDING.resolve()): binding_identity,
        str(MANIFEST.resolve()): manifest_identity,
        str(LAUNCH_COMMAND.resolve()): launch_identity,
    }
    return (config, manifest, audit, env, old, checker, supervisor, tail,
            captured, binding, controls, calendar_path, calendar_raw,
            manifest_raw)


def worker(config_sha: str, approval_sha: str, binding_sha: str,
           parent_pid: int) -> dict:
    need(os.getppid() == parent_pid, "WORKER_PARENT_PROCESS")
    write_new(WORKER_MARKER, {
        "schema": "T052_OBSERVER_REPAIR_WORKER_ENTRY_V1",
        "review_key": REVIEW_KEY,
        "attempt": ATTEMPT_NUMBER,
        "machine": platform.node(),
        "config_sha256": config_sha,
        "approval_sha256": approval_sha,
        "binding_sha256": binding_sha,
        "parent_pid": parent_pid,
        "automatic_retries": 0,
    })
    verified = verify_config(config_sha, approval_sha, binding_sha,
                             phase="worker", parent_pid=parent_pid)
    (config, manifest, audit, _env, old, checker, _supervisor, tail,
     _software_raw, _binding, _controls, calendar_path,
     calendar_raw, manifest_raw) = verified
    captured = {}

    def patched_verify(config_path, pinned_sha):
        need(Path(config_path).resolve() == CONFIG.resolve(), "WORKER_CONFIG_PATH")
        need(pinned_sha == config_sha, "WORKER_CONFIG_PIN")
        captured["audit"] = audit
        return config, manifest, checker

    def patched_permit(approval_path, pinned_approval_sha,
                       config_path, verified_config):
        need(Path(approval_path).resolve() == APPROVAL.resolve(),
             "WORKER_APPROVAL_PATH")
        need(pinned_approval_sha == approval_sha, "WORKER_APPROVAL_PIN")
        need(Path(config_path).resolve() == CONFIG.resolve()
             and verified_config is config, "WORKER_PERMIT_CONFIG")

    original_run_process = tail._run_process
    checker_expected = software_identity(config, CHECKER)

    def pinned_run_process(output, name, argv, cwd, seconds, budget):
        command = list(argv)
        if name == "check":
            command = checker_bootstrap_argv(
                command, checker_expected, calendar_path, calendar_raw,
                manifest_raw)
        return original_run_process(
            output, name, command, cwd, seconds, budget)

    old.verify = patched_verify
    old.require_permit = patched_permit
    tail._run_process = pinned_run_process
    result = old.execute(CONFIG, config_sha, APPROVAL, approval_sha)
    if OUTPUT.is_dir() and "audit" in captured:
        write_new(OUTPUT / "environment_precheck.json", captured["audit"])
    print(json.dumps(result, ensure_ascii=False))
    return result


def launch_attempt(config_sha: str, approval_sha: str, binding_sha: str) -> dict:
    verified = verify_config(config_sha, approval_sha, binding_sha,
                             phase="prelaunch")
    (config, manifest, _audit, _env, _old, _checker, supervisor, _tail,
     _raw, binding, controls, _calendar_path, _calendar_raw,
     _manifest_raw) = verified
    parent_pid = os.getpid()
    write_new(OUTER_MARKER, {
        "schema": "T052_OBSERVER_REPAIR_OUTER_MARKER_V1",
        "attempt": ATTEMPT_NUMBER,
        "machine": platform.node(),
        "config_sha256": config_sha,
        "approval_sha256": approval_sha,
        "binding_sha256": binding_sha,
        "worker_parent_pid": parent_pid,
        "automatic_retries": 0,
    })
    controller = software_identity(config, Path(__file__).resolve())
    argv = bootstrap_argv(controller, "worker", config_sha, approval_sha,
                          binding_sha, parent_pid=parent_pid)
    sources = {str(Path(path).resolve()): expected
               for path, expected in config["software"].items()}
    for item in [*manifest["sources"].values(), manifest["plan"],
                 manifest["calendar"]]:
        path = Path(item["path"])
        if not path.is_absolute():
            path = ROOT / path
        path_text = str(path.resolve())
        if "member" in item:
            need(path_text in binding["source_containers"],
                 "SOURCE_CONTAINER_UNBOUND:" + path_text)
            sources[path_text] = binding["source_containers"][path_text]
        else:
            sources[path_text] = {
                "bytes": item["bytes"], "sha256": item["sha256"]}
    sources.update({
        **controls,
        str(OUTER_MARKER.resolve()): identity(OUTER_MARKER),
    })
    result = supervisor.observe_run(PARENT, argv, ROOT,
                                    OUTPUT / "receipt.json", sources,
                                    total_seconds=300, step_seconds=300)
    print(json.dumps(result, ensure_ascii=False))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("prepare")
    verify = sub.add_parser("verify")
    worker_parser = sub.add_parser("worker")
    launch_parser = sub.add_parser("launch")
    for item in (verify, worker_parser, launch_parser):
        item.add_argument("--config-sha", required=True)
        item.add_argument("--approval-sha", required=True)
        item.add_argument("--binding-sha", required=True)
    worker_parser.add_argument("--parent-pid", required=True, type=int)
    args = parser.parse_args()
    try:
        if args.mode == "prepare":
            result = prepare()
        elif args.mode == "verify":
            config, manifest, audit, *_ = verify_config(
                args.config_sha, args.approval_sha, args.binding_sha,
                phase="prelaunch")
            result = {"status": "VERIFIED_LOCKED", "exit_code": 0,
                      "tool_calls": {"compile": 0, "run": 0,
                                     "check": 0, "gowin": 0},
                      "source_roles": len(manifest["sources"]),
                      "tool_files": len(manifest["tools"]),
                      "environment_audit": audit}
        elif args.mode == "worker":
            result = worker(args.config_sha, args.approval_sha,
                            args.binding_sha, args.parent_pid)
        else:
            result = launch_attempt(args.config_sha, args.approval_sha,
                                    args.binding_sha)
    except Exception as error:
        result = {"status": "FAIL_LOCKED", "exit_code": 1,
                  "diagnostic": type(error).__name__ + ":" + str(error)}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return int(result.get("exit_code", 0))


if __name__ == "__main__":
    raise SystemExit(main())
