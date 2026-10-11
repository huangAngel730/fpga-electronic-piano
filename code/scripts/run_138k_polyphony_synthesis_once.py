"""Single-attempt synthesis controller. Real EDA execution remains locked.

The private executor is tested with isolated stub programs. The CLI never
passes the authorization boundary; V0282's prepared receipt is unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET

import inspect_polyphony_synthesis_report as reports
import preflight_138k_polyphony_synthesis as gate
import prepare_138k_polyphony_resource as prepared

MAX_SECONDS = 900


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_new(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def plan(project: Path, output: Path) -> dict:
    checked = gate.preflight(project)
    output = output.resolve()
    root = (prepared.ROOT / "code/output").resolve()
    if output == root or not output.is_relative_to(root):
        raise ValueError("OUTPUT_OUTSIDE_NEW_CHILD")
    if output.exists():
        raise ValueError("REFUSE_EXISTING_ATTEMPT")
    return dict(status="ONE_ATTEMPT_READY_EXECUTION_LOCKED", project=checked,
                output=str(output), timeout_seconds=MAX_SECONDS,
                controller_sha256=sha(Path(__file__).read_bytes()),
                execution_authorized=False, automatic_retry=False,
                automatic_fallback=False, PnR=False, STA=False, device=False)


def runtime_inputs(project: Path, output: Path) -> tuple[Path, dict]:
    """Keep source/include/ROM paths at the original frozen, readonly project."""
    project = project.resolve()
    work = output / "project"
    work.mkdir()
    original_project = (project / prepared.PROJECT).read_bytes()
    (work / prepared.PROJECT).write_bytes(original_project)
    original_tcl = (project / "run_synthesis_only.tcl").read_text("ascii")
    old_cd = "cd {" + project.as_posix() + "}"
    old_open = "open_project {" + (project / prepared.PROJECT).as_posix() + "}"
    new_cd = "cd {" + work.as_posix() + "}"
    new_open = "open_project {" + (work / prepared.PROJECT).as_posix() + "}"
    if original_tcl.count(old_cd) != 1 or original_tcl.count(old_open) != 1:
        raise ValueError("EXACT_TCL_LOCATION_ANCHORS")
    relocated = original_tcl.replace(old_cd, new_cd).replace(old_open, new_open)
    if relocated.replace(new_cd, old_cd).replace(new_open, old_open) != original_tcl:
        raise ValueError("NONREVERSIBLE_RUNTIME_LOCATION")
    (work / "run_synthesis_only.tcl").write_bytes(relocated.encode("ascii"))
    return work, dict(original_gprj_sha256=sha(original_project),
                     runtime_gprj_sha256=sha(original_project),
                     original_tcl_sha256=sha(original_tcl.encode("ascii")),
                     runtime_tcl_sha256=sha(relocated.encode("ascii")),
                     changes=["cd working directory", "open copied GPRJ"],
                     frozen_source_include_ROM_paths_unchanged=True)


def stop_owned_tree(process: subprocess.Popen) -> dict:
    """Only terminate the PID launched by this controller and its descendants."""
    if process.poll() is not None:
        return dict(already_exited=True)
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True, timeout=15, check=False)
        detail = dict(command_pid=process.pid, exit_code=result.returncode,
                      stdout=result.stdout.decode("utf-8", errors="replace"),
                      stderr=result.stderr.decode("utf-8", errors="replace"))
    else:
        import signal
        os.killpg(process.pid, signal.SIGKILL)
        detail = dict(command_pid=process.pid, group_terminated=True)
    if process.poll() is None:
        process.kill()
    process.wait(timeout=15)
    return detail


def _execute_one(project: Path, output: Path, *, authorized: bool = False,
                 stub_command: list[str] | None = None,
                 timeout_seconds: float = MAX_SECONDS) -> dict:
    """Future trusted call boundary; stub override is only a private test seam."""
    if authorized is not True:
        raise ValueError("SYNTHESIS_NOT_AUTHORIZED")
    if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= MAX_SECONDS:
        raise ValueError("INVALID_TIMEOUT_BOUND")
    start = time.monotonic()
    info = plan(project, output)
    record = prepared.verify(project)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    result = dict(status="FAIL", exit_code=1, timed_out=False, tool_runs=0,
                  stub_test=stub_command is not None, setup_info=info,
                  source_receipt_sha256=sha((project / "frozen_receipt.json").read_bytes()),
                  PnR=False, STA=False, board_release_allowed=False,
                  resource_admission=False, physical_resources=None)
    process = None
    try:
        work, identities = runtime_inputs(project, output)
        command = stub_command or [record["tool"]["identities"]["shell"]["path"],
                                   "run_synthesis_only.tcl"]
        result.update(command=command, cwd=str(work), runtime_inputs=identities)
        remaining = timeout_seconds - (time.monotonic() - start)
        if remaining <= 0:
            raise ValueError("TIMEOUT_BEFORE_TOOL")
        with (output / "stdout.bin").open("xb") as so, (output / "stderr.bin").open("xb") as se:
            process = subprocess.Popen(command, cwd=work, stdout=so, stderr=se,
                                       start_new_session=os.name != "nt")
            result["tool_runs"] = 1
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                result["timed_out"] = True
                result["timeout_cleanup"] = stop_owned_tree(process)
                raise ValueError("SYNTHESIS_TIMEOUT_NO_RETRY")
        result["tool_exit_code"] = process.returncode
        if process.returncode != 0:
            raise ValueError("TOOL_NONZERO_NO_RETRY")
        prepared.verify(project)
        if time.monotonic() - start >= timeout_seconds:
            result["timed_out"] = True
            raise ValueError("POST_TOOL_DEADLINE_NO_RETRY")
        if any(p.suffix.lower() in (".fs", ".bit") for p in work.rglob("*")):
            raise ValueError("UNEXPECTED_PNR_BITSTREAM")
        names = ("b2l_resource_probe", Path(prepared.PROJECT).stem)
        report_paths = [work / "impl/gwsynthesis" / (n + "_syn_rsc.xml") for n in names]
        found = [p for p in report_paths if p.is_file()]
        if len(found) != 1:
            raise ValueError("EXACTLY_ONE_FRESH_SYNTHESIS_REPORT_REQUIRED")
        report = found[0]
        if not report.resolve().is_relative_to(work.resolve()):
            raise ValueError("REPORT_OUTSIDE_ATTEMPT")
        netlists = [p for p in work.rglob("*.vg") if p.is_file()]
        if not netlists or any(not p.resolve().is_relative_to(work.resolve()) for p in netlists):
            raise ValueError("FRESH_NETLIST_REQUIRED")
        parsed = reports.inspect(report)
        if time.monotonic() - start >= timeout_seconds:
            result["timed_out"] = True
            raise ValueError("REPORT_DEADLINE_NO_RETRY")
        result.update(status="STUB_SYNTHESIS_CONTROLLER_PASS" if stub_command else
                      "SYNTHESIS_ONLY_COMPLETE_NOT_ADMITTED", exit_code=0,
                      resource_report=parsed,
                      netlists=[dict(path=str(p), sha256=sha(p.read_bytes())) for p in netlists])
    except (OSError, ValueError, ET.ParseError, subprocess.SubprocessError) as error:
        result["diagnostic"] = str(error)
    finally:
        if process is not None and process.poll() is None:
            result["exception_cleanup"] = stop_owned_tree(process)
        try:
            prepared.verify(project)
            result["frozen_project_unchanged"] = True
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            result.update(exit_code=1, status="FAIL", frozen_project_unchanged=False,
                          frozen_verification_error=str(error))
        result["artifacts"] = {p.relative_to(output).as_posix(): dict(
            bytes=p.stat().st_size, sha256=sha(p.read_bytes()))
            for p in output.rglob("*") if p.is_file()}
        result["elapsed_seconds"] = time.monotonic() - start
        if result["exit_code"] == 0 and result["elapsed_seconds"] > timeout_seconds:
            result.update(exit_code=1, status="FAIL", timed_out=True,
                          diagnostic="FINALIZATION_DEADLINE_NO_RETRY")
        write_new(output / "receipt.json", result)
    return result


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--project", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--execute", action="store_true")
    args = cli.parse_args()
    try:
        if args.execute:
            raise ValueError("SYNTHESIS_NOT_AUTHORIZED")
        print(json.dumps(plan(args.project, args.output), ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps(dict(status="REJECT", reason=str(error))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
