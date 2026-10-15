#!/usr/bin/env python3
"""Bounded, supervised runner for the isolated real N32 delay replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from capture_extract import EXPECTED_OUTER_SHA256, sha256_bytes, sha256_path


TASK_NAME = "m3_n32_delay_replay_20261014"
EXPECTED_M1_EVIDENCE_SHA256 = (
    "90fb74ae1782cb3810a425ce4f357d7f519cd4294fe707ec76d32709711debce"
)
EXPECTED_M1_ARCHIVE_SHA256 = (
    "5c18926ae307301e91ec0e44dcf4a48b2fb57adec71ad46c494b14df59913b06"
)
M1_SOURCE_MEMBERS = {
    "m1td_stereo_delay.sv": (
        "code/output/m2_m1td_whole_prepare_20261015_05/inputs/sources/"
        "m1td_stereo_delay.sv",
        "afba156c187520b03a9b422c3074d6fde48bfeceb590cafa5883b7037626da2a",
    ),
    "m1td_delay_effect.sv": (
        "code/output/m2_m1td_whole_prepare_20261015_05/inputs/sources/"
        "m1td_delay_effect.sv",
        "07bcc6f4d0a448e029b5349a43fa8bcaa4afac32323bffb21fdc0e7c6a9633ac",
    ),
}

M2_SOURCES = {
    "code/rtl/audio_out/m2_n32_output_candidate_20261013/m2_n32_output_transport.sv":
        "d2b6d311fd990072f399d4e42413c47ef70f2f6f2473b1308b085d9aa49ad154",
    "code/rtl/audio_out/m2_polyphony_frame_candidate_20261012/premixed_frame_adapter.sv":
        "d7952a5f986eb8b609cbe657907e418cfe751c6492d6e49469b5e37c390bb56c",
    "code/rtl/audio_out/pcm_result_hold.sv":
        "7656fd0089efd140de784352d1e7809169240e6a09263c8ce9428298b424d52f",
    "code/rtl/audio_out/pcm_frame_buffer.sv":
        "f8bc454a2e627809c2f9f9029c1e5128acf2fd543d7fcc2d3d83b50685f40997",
    "code/rtl/common/pcm_clip_counter.sv":
        "ff530dcba528160459c57e6e0098d0f96ee89b84e5aa0c34f2e85c43891facca",
    "code/rtl/audio_out/i2s_tx.sv":
        "6c703e31064e5943df4e310b3baddd8935362a1c028828d8e11f8f3c016267ad",
    "code/rtl/common/pcm_waveform_observer_candidate/pcm_waveform_observer_bridge.sv":
        "0b937e2d23dc090b5094d789edba5216c34a96eb84eb96d002cdab8aa0c45cfb",
    "code/rtl/common/pcm_waveform_observer_candidate/pcm_frame_observer.sv":
        "f0f755558fbd40a103c1d7d6c73c102eb4f83bf54cc41b09a78fd65609fe13a8",
    "code/rtl/common/visual_mailbox_cdc.sv":
        "df5ef71f0d0b9856cc769023d40b1a62c5ac8b24c5adb7ea60fee42603b5838c",
    "code/rtl/common/reset_sync.sv":
        "59b63cd109428bc4c245d7020e348b76abb4e01ced2306844c28d5f403bb2777",
}
EXPECTED_M2_EVIDENCE_SHA256 = (
    "b37d2084fada1cd595f207ec91c99125f28488cad4d07a1576b1e6c6da0c195c"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def find_repo_root() -> Path:
    here = Path(__file__).resolve()
    candidate = here.parents[4]
    if not (candidate / ".git").exists():
        raise RuntimeError(f"REPO_ROOT_NOT_FOUND from={here}")
    return candidate


class CommandRunner:
    def __init__(self, output_dir: Path, env: dict[str, str]) -> None:
        self.output_dir = output_dir
        self.env = env
        self.calls: list[dict] = []

    def run(
        self,
        name: str,
        argv: list[str],
        cwd: Path,
        timeout: int,
    ) -> subprocess.CompletedProcess[str] | None:
        stdout_path = self.output_dir / f"{name}.stdout.log"
        stderr_path = self.output_dir / f"{name}.stderr.log"
        started = time.monotonic()
        started_at = utc_now()
        timed_out = False
        exit_code: int | None
        stdout = ""
        stderr = ""
        try:
            result = subprocess.run(
                argv,
                cwd=cwd,
                env=self.env,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
            stdout = result.stdout
            stderr = result.stderr
            exit_code = result.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            exit_code = None
            result = None
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        record = {
            "name": name,
            "argv": argv,
            "cwd": cwd.as_posix(),
            "started_at_utc": started_at,
            "elapsed_seconds": round(time.monotonic() - started, 6),
            "timeout_seconds": timeout,
            "timed_out": timed_out,
            "exit_code": exit_code,
            "stdout": stdout_path.name,
            "stderr": stderr_path.name,
        }
        self.calls.append(record)
        with (self.output_dir / "COMMANDS.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
        return result


def require_success(result: subprocess.CompletedProcess[str] | None, name: str) -> None:
    if result is None:
        raise RuntimeError(f"{name}_TIMEOUT")
    if result.returncode != 0:
        raise RuntimeError(f"{name}_EXIT_{result.returncode}")


def extract_m1_sources(repo: Path, runtime_dir: Path) -> dict:
    evidence = repo / "code/docs/evidence/m2_fourvoice_timbre_delay_stage_20261015.zip"
    evidence_sha = sha256_path(evidence)
    if evidence_sha != EXPECTED_M1_EVIDENCE_SHA256:
        raise RuntimeError(f"M1_EVIDENCE_SHA actual={evidence_sha}")
    runtime_dir.mkdir(parents=True, exist_ok=False)
    identities: dict[str, dict] = {}
    with zipfile.ZipFile(evidence) as archive:
        receipt = json.loads(
            archive.read(
                "code/output/m2_m1td_whole_prepare_20261015_05/PREPARATION_RECEIPT.json"
            )
        )
        if receipt.get("m1_zip_sha256") != EXPECTED_M1_ARCHIVE_SHA256:
            raise RuntimeError("M1_ORIGINAL_ARCHIVE_ATTESTATION_MISMATCH")
        for local_name, (member, expected_sha) in M1_SOURCE_MEMBERS.items():
            data = archive.read(member)
            actual_sha = sha256_bytes(data)
            if actual_sha != expected_sha:
                raise RuntimeError(f"M1_SOURCE_SHA member={member} actual={actual_sha}")
            target = runtime_dir / local_name
            target.write_bytes(data)
            identities[local_name] = {
                "evidence_member": member,
                "bytes": len(data),
                "sha256": actual_sha,
            }
    return {
        "original_archive": {
            "availability": "NOT_PRESENT_ON_THIS_MACHINE",
            "attested_sha256": EXPECTED_M1_ARCHIVE_SHA256,
            "attestation": "PREPARATION_RECEIPT.json inside the M2 evidence capsule",
        },
        "evidence_capsule": {
            "path": evidence.relative_to(repo).as_posix(),
            "bytes": evidence.stat().st_size,
            "sha256": evidence_sha,
        },
        "sources": identities,
    }


def verify_frozen_sources(repo: Path) -> dict:
    identities: dict[str, dict] = {}
    for relative, expected in M2_SOURCES.items():
        path = repo / relative
        actual = sha256_path(path)
        if actual != expected:
            raise RuntimeError(f"M2_SOURCE_SHA path={relative} actual={actual} expected={expected}")
        identities[relative] = {"bytes": path.stat().st_size, "sha256": actual}
    evidence = repo / "code/docs/evidence/m2_n32_output_transport_20261013/RAW_EVIDENCE.zip"
    evidence_sha = sha256_path(evidence)
    if evidence_sha != EXPECTED_M2_EVIDENCE_SHA256:
        raise RuntimeError(f"M2_EVIDENCE_SHA actual={evidence_sha}")
    return {
        "evidence_capsule": {
            "path": evidence.relative_to(repo).as_posix(),
            "bytes": evidence.stat().st_size,
            "sha256": evidence_sha,
        },
        "sources": identities,
    }


def deterministic_zip(zip_path: Path, members: list[tuple[str, Path]]) -> dict:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for arcname, path in sorted(members):
            info = zipfile.ZipInfo(arcname, date_time=(2026, 10, 15, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    return {"bytes": zip_path.stat().st_size, "sha256": sha256_path(zip_path)}


def seal(repo: Path, task_dir: Path, output_dir: Path) -> dict:
    seal_dir = output_dir / "SEALED_RESULT_R01"
    seal_dir.mkdir()
    members: list[tuple[str, Path]] = []
    for path in sorted(task_dir.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            members.append((f"source/{path.relative_to(task_dir).as_posix()}", path))
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and seal_dir not in path.parents and "transfer" not in path.parts:
            members.append((f"execution/{path.relative_to(output_dir).as_posix()}", path))
    manifest = {
        "status": "ISOLATED_FUNCTIONAL_REPLAY_PASS_T060_T061_PARTIAL",
        "generated_at_utc": utc_now(),
        "member_count": len(members),
        "files": {
            name: {"bytes": path.stat().st_size, "sha256": sha256_path(path)}
            for name, path in members
        },
        "boundaries": {
            "production_realtime_n32": False,
            "whole_system_sta": False,
            "hardware_audio": False,
            "gowin_calls": 0,
            "device_operations": 0,
        },
    }
    manifest_path = seal_dir / "MANIFEST.json"
    write_json(manifest_path, manifest)
    snapshot_path = seal_dir / "snapshot.zip"
    snapshot_identity = deterministic_zip(snapshot_path, members)
    seal_record = {
        "manifest": {"bytes": manifest_path.stat().st_size, "sha256": sha256_path(manifest_path)},
        "snapshot": snapshot_identity,
        "source_member_count": sum(name.startswith("source/") for name, _ in members),
        "execution_member_count": sum(name.startswith("execution/") for name, _ in members),
    }
    seal_path = seal_dir / "seal.json"
    write_json(seal_path, seal_record)

    transfer_dir = output_dir / "transfer"
    transfer_dir.mkdir()
    transfer_path = transfer_dir / "M3_N32_DELAY_REPLAY_20261015.zip"
    transfer_members = [
        ("SEALED_RESULT_R01/MANIFEST.json", manifest_path),
        ("SEALED_RESULT_R01/seal.json", seal_path),
        ("SEALED_RESULT_R01/snapshot.zip", snapshot_path),
        ("DELIVERY.md", task_dir / "DELIVERY.md"),
    ]
    transfer_identity = deterministic_zip(transfer_path, transfer_members)
    transfer_receipt = {
        "status": "READY_TO_FORWARD_NOT_DELIVERED",
        "path": transfer_path.relative_to(repo).as_posix(),
        **transfer_identity,
    }
    write_json(transfer_dir / "TRANSFER_RECEIPT.json", transfer_receipt)
    return {"seal": seal_record, "transfer": transfer_receipt}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--vectors", type=int, default=1300)
    parser.add_argument(
        "--iverilog",
        type=Path,
        default=Path("E:/FPGA/GAOYUNFPGA/138K/tools/icarus_oss_copy/bin/iverilog.exe"),
    )
    parser.add_argument(
        "--vvp",
        type=Path,
        default=Path("E:/FPGA/GAOYUNFPGA/138K/tools/icarus_oss_copy/bin/vvp.exe"),
    )
    args = parser.parse_args()
    repo = find_repo_root()
    task_dir = Path(__file__).resolve().parent
    output_dir = args.output.resolve()
    if output_dir.exists():
        raise SystemExit(f"REFUSE_EXISTING_OUTPUT {output_dir}")
    output_dir.mkdir(parents=True)

    outer_zip = repo / "code/output/n32_c_full_publication_20261014_r01/transfer/M3_N32_C_FULL_20261014.zip"
    if sha256_path(outer_zip) != EXPECTED_OUTER_SHA256:
        raise SystemExit("C_FULL_OUTER_IDENTITY_MISMATCH")
    if not args.iverilog.is_file() or not args.vvp.is_file():
        raise SystemExit("ICARUS_TOOL_MISSING")

    runtime_m1 = output_dir / "runtime_sources/m1"
    m1_identity = extract_m1_sources(repo, runtime_m1)
    m2_identity = verify_frozen_sources(repo)
    task_sources = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256_path(path)}
        for path in sorted(task_dir.glob("*")) if path.is_file()
    }
    pre_identity = {
        "status": "RECORDED_BEFORE_TOOL_EXECUTION",
        "recorded_at_utc": utc_now(),
        "machine": {
            "computername": os.environ.get("COMPUTERNAME"),
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": sys.executable,
            "python_version": platform.python_version(),
        },
        "budget": {
            "vector_count": args.vectors,
            "compile_timeout_seconds_each": 90,
            "simulation_timeout_seconds_each": 180,
            "checker_timeout_seconds_each": 30,
            "selftest_timeout_seconds": 30,
            "gowin_calls_allowed": 0,
            "device_operations_allowed": 0,
        },
        "tools": {
            "iverilog": {"path": args.iverilog.as_posix(), "sha256": sha256_path(args.iverilog)},
            "vvp": {"path": args.vvp.as_posix(), "sha256": sha256_path(args.vvp)},
        },
        "inputs": {
            "c_full_outer": {
                "path": outer_zip.relative_to(repo).as_posix(),
                "bytes": outer_zip.stat().st_size,
                "sha256": sha256_path(outer_zip),
            },
            "m1": m1_identity,
            "m2": m2_identity,
            "task_sources": task_sources,
        },
        "output_directory": output_dir.relative_to(repo).as_posix(),
    }
    write_json(output_dir / "PRE_EXECUTION_IDENTITY.json", pre_identity)

    env = os.environ.copy()
    env["PATH"] = str(args.iverilog.parent) + os.pathsep + env.get("PATH", "")
    command_runner = CommandRunner(output_dir, env)
    started = time.monotonic()

    require_success(
        command_runner.run("tool_version", [str(args.iverilog), "-V"], repo, 30),
        "tool_version",
    )
    require_success(
        command_runner.run(
            "selftest",
            [sys.executable, str(task_dir / "test_self.py")],
            task_dir,
            30,
        ),
        "selftest",
    )
    vector_dir = output_dir / "extracted_capture"
    require_success(
        command_runner.run(
            "extract_capture",
            [
                sys.executable,
                str(task_dir / "capture_extract.py"),
                "--outer-zip",
                str(outer_zip),
                "--output-dir",
                str(vector_dir),
                "--count",
                str(args.vectors),
            ],
            repo,
            90,
        ),
        "extract_capture",
    )

    source_paths = [repo / relative for relative in M2_SOURCES]
    common_compile = [
        str(args.iverilog), "-g2012", "-s", "tb_m3_n32_delay_replay",
        "-o",
    ]
    compile_tail = [
        str(runtime_m1 / "m1td_delay_effect.sv"),
        str(runtime_m1 / "m1td_stereo_delay.sv"),
        *(str(path) for path in source_paths),
        str(task_dir / "tb_m3_n32_delay_replay.sv"),
    ]

    positive_vvp = output_dir / "positive.vvp"
    require_success(
        command_runner.run(
            "compile_positive",
            common_compile + [str(positive_vvp)] + compile_tail,
            repo,
            90,
        ),
        "compile_positive",
    )
    positive_trace = output_dir / "positive.trace"
    require_success(
        command_runner.run(
            "simulate_positive",
            [
                str(args.vvp), str(positive_vvp),
                f"+VECTORS={str(vector_dir / 'real_publish.mem').replace(os.sep, '/')}",
                f"+TRACE={str(positive_trace).replace(os.sep, '/')}",
                f"+COUNT={args.vectors}",
            ],
            repo,
            180,
        ),
        "simulate_positive",
    )
    positive_receipt = output_dir / "positive.check.json"
    require_success(
        command_runner.run(
            "check_positive",
            [
                sys.executable, str(task_dir / "check_replay.py"),
                "--trace", str(positive_trace),
                "--receipt", str(positive_receipt),
                "--vectors", str(args.vectors),
            ],
            repo,
            30,
        ),
        "check_positive",
    )

    mutant_vvp = output_dir / "bad_left.vvp"
    require_success(
        command_runner.run(
            "compile_bad_left",
            common_compile + [str(mutant_vvp), "-DM2_OUTPUT_BAD_LEFT"] + compile_tail,
            repo,
            90,
        ),
        "compile_bad_left",
    )
    mutant_trace = output_dir / "bad_left.trace"
    require_success(
        command_runner.run(
            "simulate_bad_left",
            [
                str(args.vvp), str(mutant_vvp),
                f"+VECTORS={str(vector_dir / 'real_publish.mem').replace(os.sep, '/')}",
                f"+TRACE={str(mutant_trace).replace(os.sep, '/')}",
                f"+COUNT={args.vectors}",
            ],
            repo,
            180,
        ),
        "simulate_bad_left",
    )
    mutant_receipt = output_dir / "bad_left.check.json"
    mutant_check = command_runner.run(
        "check_bad_left",
        [
            sys.executable, str(task_dir / "check_replay.py"),
            "--trace", str(mutant_trace),
            "--receipt", str(mutant_receipt),
            "--vectors", str(args.vectors),
        ],
        repo,
        30,
    )
    if mutant_check is None or mutant_check.returncode == 0:
        raise RuntimeError("BAD_LEFT_MUTANT_NOT_REJECTED")
    mutant_result = json.loads(mutant_receipt.read_text(encoding="utf-8"))
    if mutant_result.get("diagnostic") != "COMMIT_PCM_MISMATCH":
        raise RuntimeError(f"BAD_LEFT_WRONG_DIAGNOSTIC {mutant_result}")

    positive_result = json.loads(positive_receipt.read_text(encoding="utf-8"))
    result = {
        "status": "PASS",
        "scope": "ISOLATED_REAL_C_FULL_PCM_TO_M1_DELAY_TO_M2_TRANSPORT_REPLAY",
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "tool_calls": len(command_runner.calls),
        "compile_calls": 2,
        "simulation_calls": 2,
        "checker_calls": 2,
        "gowin_calls": 0,
        "device_operations": 0,
        "positive": positive_result,
        "negative": {
            "macro": "M2_OUTPUT_BAD_LEFT",
            "compiled": True,
            "simulated": True,
            "checker_exit_code": mutant_check.returncode,
            "diagnostic": mutant_result["diagnostic"],
        },
        "source_caveat": (
            "The original M1 ZIP is absent on this machine; exact source bytes are taken "
            "from the existing M2 evidence capsule whose preparation receipt attests the "
            "required original ZIP SHA."
        ),
        "limits": [
            "C_FULL source left/right are equal and source clipped is always zero.",
            "No claim of unequal-stereo swap or nonzero-clip phase coverage is made.",
            "No production integration, synthesis, PnR, STA, device, or audible test was run.",
        ],
    }
    write_json(output_dir / "RESULT.json", result)
    seal_result = seal(repo, task_dir, output_dir)
    write_json(output_dir / "FINAL_RECEIPT.json", {**result, **seal_result})
    print(json.dumps({"status": "PASS", **seal_result["transfer"]}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        try:
            raw_args = sys.argv[1:]
            if "--output" in raw_args:
                failure_dir = Path(raw_args[raw_args.index("--output") + 1]).resolve()
                if failure_dir.is_dir():
                    write_json(
                        failure_dir / "ATTEMPT_FAILURE.json",
                        {
                            "status": "FAIL",
                            "failed_at_utc": utc_now(),
                            "exception": type(exc).__name__,
                            "detail": str(exc),
                            "blind_retry": False,
                        },
                    )
        except Exception:
            pass
        print(f"RUNNER_FAIL {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
