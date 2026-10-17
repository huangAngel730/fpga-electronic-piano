"""One bounded static audit+seal group. No simulator, EDA or Git command."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import zipfile  # Include archive dependencies in the identity closure.

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
JOB = ROOT / "code/software/t052_runner_acceptance_candidate_20261012/windows_job.py"
DEADLINE = datetime.fromisoformat("2026-10-17T06:04:35+00:00")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identities(paths):
    return {str(p): {"bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(set(paths))}


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    began = time.monotonic()
    prior = list(HERE.glob("RUN_*/CONSUMED.json"))
    fingerprint_paths = [HERE / name for name in ("audit_static.py", "seal_static.py", "run_static.py", "ANCHOR_SPEC.json",
                                                 "INTEGRATION_DIFF.md", "CDC_PATHS.md", "WIRING_PROPOSAL.md")]
    fingerprint = identities(fingerprint_paths)
    assert len(prior) < 2, "TWO_GROUP_LIMIT"
    assert not any(json.loads(p.read_text(encoding="utf-8")).get("passed")
                   for p in HERE.glob("RUN_*/FINAL_RECEIPT.json")), "SUCCESS_STOP"
    assert not any(json.loads(p.read_text(encoding="utf-8"))["fingerprint"] == fingerprint for p in prior), "IDENTICAL_RETRY_FORBIDDEN"
    out = HERE / f"RUN_{len(prior)+1:02d}"
    out.mkdir(exist_ok=False)
    products = out / "products"
    products.mkdir()
    frozen = out / "execution_sources"
    frozen.mkdir()
    for source in (HERE / "audit_static.py", HERE / "seal_static.py", HERE / "run_static.py", JOB):
        shutil.copyfile(source, frozen / source.name)
        assert sha(source) == sha(frozen / source.name)
    job_spec = importlib.util.spec_from_file_location("frozen_owned_job", frozen / JOB.name)
    job_module = importlib.util.module_from_spec(job_spec)
    job_spec.loader.exec_module(job_module)
    inputs = json.loads((HERE / "INPUT_IDENTITIES.json").read_text(encoding="utf-8"))
    input_paths = [Path(item[k]) for item in inputs for k in ("source", "frozen")]
    input_paths += [p for p in HERE.iterdir() if p.is_file() and p.suffix in (".py", ".ps1", ".md", ".json")]
    input_paths += [JOB]
    pyroot = Path(sys.executable).parent
    tool_paths = [Path(sys.executable)] + list(pyroot.glob("python*.dll")) + list(pyroot.glob("vcruntime*.dll"))
    tool_paths += list((pyroot / "Library/bin").glob("libcrypto*.dll"))
    tool_paths += list((pyroot / "Library/bin").glob("libssl*.dll"))
    tool_paths += [Path(module.__file__) for module in list(sys.modules.values())
                   if getattr(module, "__file__", None) and Path(module.__file__).is_file()]
    before = {"inputs": identities(input_paths), "tools": identities(tool_paths)}
    write(out / "before.json", before)
    env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "COMSPEC", "OS", "PROCESSOR_ARCHITECTURE",
                                      "NUMBER_OF_PROCESSORS", "USERPROFILE", "HOMEDRIVE", "HOMEPATH") if k in os.environ}
    env.update(PATH=os.pathsep.join([str(pyroot), str(pyroot / "Library/bin"), str(Path(os.environ["SystemRoot"]) / "System32")]),
               TEMP=str(out), TMP=str(out), PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    write(out / "environment.json", env)
    calls = []
    error = None
    metadata = {"task": "TASK_DAY_E1_PRO_INTEGRATION_STATIC_DIFF", "head_at_discovery": "414e1a9d3ee0617c5e8ba72dd4b22c36122c9926",
                "remote_live_pointer": "NOT_FETCHED_BY_THIS_WINDOW", "machine": platform.node(), "platform": platform.platform(),
                "python_executable": sys.executable, "python_version": sys.version,
                "round": len(prior)+1, "round_limit": 2, "group_limit_seconds": 90,
                "deadline_utc": DEADLINE.isoformat(), "actual_level": "L0_STATIC_ONLY",
                "board_release_allowed": False, "old_allowances_restored": False,
                "simulator_EDA_hardware_git_commands": 0}
    write(out / "metadata.json", metadata)

    def run(label, script):
        remaining = min(90 - (time.monotonic() - began), (DEADLINE - datetime.now(timezone.utc)).total_seconds())
        assert remaining > 0, "GROUP_OR_GLOBAL_DEADLINE"
        argv = [sys.executable, "-B", "-X", "utf8", str(frozen / script), str(HERE), str(products)]
        call = {"argv": argv, "cwd": str(ROOT), "timeout_seconds": remaining,
                "start_utc": datetime.now(timezone.utc).isoformat(), "exit_code": None,
                "timeout": False, "process_created": False}
        write(out / (label + ".launch.json"), call)
        job = job_module.WindowsJob()
        started = time.monotonic()
        try:
            with (out / (label + ".stdout")).open("xb") as stdout, (out / (label + ".stderr")).open("xb") as stderr:
                if not (out / "CONSUMED.json").exists():
                    write(out / "CONSUMED.json", {"round": len(prior)+1, "fingerprint": fingerprint,
                                                  "reserved_before_process_create": True, "old_allowances_restored": False})
                process = subprocess.Popen(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                           stdout=stdout, stderr=stderr, creationflags=0x00000004)
                call.update(pid=process.pid, process_created=True)
                job.attach_and_resume(process)
                try:
                    call["exit_code"] = process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    call["timeout"] = True
                    job.terminate()
                    call["exit_code"] = process.wait(timeout=5)
        finally:
            job.close()
            call["elapsed_seconds"] = time.monotonic() - started
            call["end_utc"] = datetime.now(timezone.utc).isoformat()
            call["stdout_sha256"] = sha(out / (label + ".stdout"))
            call["stderr_sha256"] = sha(out / (label + ".stderr"))
            write(out / (label + ".receipt.json"), call)
            calls.append({"label": label, **call})
        assert call["exit_code"] == 0 and not call["timeout"], "CALL_FAILED:" + label

    try:
        run("audit", "audit_static.py")
        after_audit = {"inputs": identities(input_paths), "tools": identities(tool_paths)}
        write(out / "after_audit.json", after_audit)
        assert before == after_audit, "IDENTITY_DRIFT_DURING_AUDIT"
        run("seal", "seal_static.py")
    except Exception as exc:
        error = repr(exc)
    after = {"inputs": identities(input_paths), "tools": identities(tool_paths)}
    stable = before == after
    passed = error is None and stable and time.monotonic() - began < 90
    receipt = {**metadata, "passed": passed, "error": error, "source_and_tool_identity_stable": stable,
               "elapsed_seconds": time.monotonic() - began, "calls": calls,
               "positive_negative_RTL": "NOT_RUN", "first_failure": None if passed else error,
               "formal_integration": "PENDING_PRO_SOURCE_OR_PRODUCERS", "submitted": False, "pushed": False}
    write(out / "after.json", after)
    write(out / "FINAL_RECEIPT.json", receipt)
    if passed:
        for name in ("RESULT.json", "ANCHORS_VERIFIED.json", "READ_ONLY_REFERENCES.json", "FINAL_SOURCE_INDEX.md", "PACKAGE_STATUS.json"):
            shutil.copyfile(products / name, HERE / name)
            assert sha(products / name) == sha(HERE / name)
        write(HERE / "FINAL_RECEIPT.json", receipt)
        publish = sorted(p.relative_to(ROOT).as_posix() for p in HERE.rglob("*") if p.is_file()
                         and p.relative_to(HERE).parts[0] != "INPUT_ORIGINALS")
        publish.append((HERE / "PUBLISH_FILE_LIST.json").relative_to(ROOT).as_posix())
        write(HERE / "PUBLISH_FILE_LIST.json", {"files": publish, "local_only_excluded": "INPUT_ORIGINALS/**",
                                               "git_actions_performed": 0, "publication_owner": "night_task_1"})
    else:
        write(HERE / f"FAILED_RUN_{len(prior)+1:02d}.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
