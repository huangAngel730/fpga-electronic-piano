"""Prepare-only exact failed-A compile diagnostic. No process/tool execution.

Reuse the verified allocator.v. Do not relower, run vvp, restore consumed A/B
permission, install tools, or modify source text/ROM. A future compile needs a
new explicit approval bound to this prepared receipt.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "code/docs/evidence/m2_ab_failure_t052_static_review_20261013/RAW_EVIDENCE.zip"
EVIDENCE_SHA = "6a531fae9c846ad2098c26919cc063cac9df9e84f7ff89a18e4d4890c92ccf56"
PREFIX = "received/T060/m3_t060_AB_authorized_20261012_01/"
SNAP = PREFIX + "snapshot/"
TB_REL = "code/tb/board/m3_midi_pcm_acceptance/t060_minclosure_20261011/"
IV = Path("D:/Gowin/oss-cad-suite/bin/iverilog.exe")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(raw):
    return dict(bytes=len(raw), sha256=sha(raw))


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def package(output):
    raw = EVIDENCE.read_bytes()
    if sha(raw) != EVIDENCE_SHA:
        raise ValueError("PINNED_FAILURE_ARCHIVE_SHA")
    with zipfile.ZipFile(EVIDENCE) as z:
        failed = json.loads(z.read(PREFIX + "A_compile.receipt.json"))
        run = json.loads(z.read(PREFIX + "receipt.json"))
        compiled = json.loads(z.read(PREFIX + "actual_compiled_sources_A.json"))
        if failed["exit_code"] != 3221225477 or failed["timeout"] or run["automatic_retries"] != 0:
            raise ValueError("EXACT_EXCEPTION_PROVENANCE")
        snapshot_root = failed["cwd"].replace("\\", "/").removesuffix("/future_group_A")
        payload = {}
        original_paths = {}
        for path, pin in compiled["inputs"].items():
            normalized = path.replace("\\", "/")
            if not normalized.startswith(snapshot_root + "/"):
                raise ValueError("FAILED_INPUT_OUTSIDE_SNAPSHOT")
            rel = normalized[len(snapshot_root) + 1:]
            if rel.startswith("future_group_A/"):
                dest = rel.removeprefix("future_group_A/")
            elif rel == TB_REL + "tb_minclosure.sv":
                dest = "tb/tb_minclosure.sv"
            else:
                raise ValueError("UNEXPECTED_COMPILE_INPUT:" + rel)
            data = z.read(SNAP + rel)
            if identity(data) != pin:
                raise ValueError("FAILED_SOURCE_SHA:" + rel)
            payload[dest] = data
            original_paths[dest] = normalized
        for path, pin in compiled["include_files"].items():
            name = path.replace("\\", "/").split("/future_group_A/", 1)[1]
            data = z.read(SNAP + "future_group_A/" + name)
            if identity(data) != pin:
                raise ValueError("FAILED_INCLUDE_SHA")
            payload[name] = data
        observer = z.read(SNAP + TB_REL + "observer.svh")
        if identity(observer) != compiled["observer"]:
            raise ValueError("FAILED_OBSERVER_SHA")
        payload["tb/observer.svh"] = observer
        for name in z.namelist():
            if name.startswith(SNAP + "future_group_A/rom/"):
                payload[name.removeprefix(SNAP + "future_group_A/")] = z.read(name)
        # Omit old partial A.vvp, stimulus and lowering script: compile only.
        original_argv = failed["argv"]
        if original_argv[:5] != [str(IV).replace("\\", "/"), "-g2012", "-I", "include", "-I"]:
            raise ValueError("EXACT_FAILED_COMPILE_OPTIONS")
        mapped = []
        if original_argv[6:10] != ["-s", "tb_minclosure", "-o", "A.vvp"]:
            raise ValueError("EXACT_FAILED_TOP_OUTPUT_OPTIONS")
        for arg in original_argv[10:]:
            if arg in payload:
                mapped.append(arg)
            elif arg.replace("\\", "/").endswith("/" + TB_REL + "tb_minclosure.sv"):
                mapped.append("tb/tb_minclosure.sv")
            else:
                raise ValueError("UNMAPPED_COMPILE_ARGUMENT:" + arg)
        if set(mapped) != set(original_paths) or len(mapped) != 20:
            raise ValueError("EXACT_TWENTY_COMPILED_INPUTS")
        original_tool_key = next(k for k in run["tools_before"] if k.endswith("/iverilog.exe"))
        original_tool = run["tools_before"][original_tool_key]
        vvp = z.read(SNAP + "future_group_A/A.vvp")
        match = re.search(rb":file_names (\d+);\s*([\s\S]*)\Z", vvp)
        entries = re.findall(rb'^\s*".*";\s*$', match.group(2), re.M) if match else []
        if not match or int(match.group(1)) != 23 or len(entries) != 23 or b'"$finish"' not in vvp:
            raise ValueError("RESIDUAL_CODE_TAIL_SHAPE_DRIFT")
    tools = {IV.as_posix(): identity(IV.read_bytes())}
    for path in sorted((IV.parent.parent / "lib/ivl").rglob("*")):
        if path.is_file():
            tools[path.as_posix()] = identity(path.read_bytes())
    for folder in (IV.parent, IV.parent.parent / "lib"):
        for path in sorted(folder.glob("*.dll")):
            tools[path.as_posix()] = identity(path.read_bytes())
    command = [str(IV), "-g2012", "-I", "include", "-I", "tb", "-s", "tb_minclosure", "-o", "diagnostic_A.vvp", *mapped]
    report = dict(schema=1, status="PREPARED_COMPILE_ONLY_NOT_AUTHORIZED",
                  frozen_failure_archive_sha256=EVIDENCE_SHA,
                  original_config_sha256=run["config"]["sha256"],
                  original_compile_exit=failed["exit_code"], original_argv=original_argv,
                  original_cwd=failed["cwd"], original_inputs=original_paths,
                  proposed_command=command, proposed_cwd=str(output / "inputs"),
                  argv_changes=["include TB path relocated", "TB filename relocated", "new output filename", "explicit M2 local compiler identity"],
                  source_byte_changes=0, lower_runs=0, vvp_runs=0, EDA_runs=0,
                  planned_maximum_compile_calls=1, proposed_total_seconds=90,
                  automatic_retry=False, execution_authorized=False,
                  original_consumed_permission_restored=False,
                  residual_vvp_copied=False,
                  original_compiler_identity=original_tool,
                  proposed_compiler_identity=tools[IV.as_posix()],
                  compiler_identity_changed=tools[IV.as_posix()] != original_tool,
                  proposed_tool_files=tools,
                  residual_static_tail=dict(bytes=len(vvp), sha256=sha(vvp), file_table_entries=23,
                                            finish_emitted=True, runnable="UNKNOWN_NOT_EXECUTED"),
                  compile_pass_would_not_certify_A_B_or_sound=True,
                  full_T060_T061_complete=False,
                  inputs={name: identity(data) for name, data in sorted(payload.items())})
    return payload, report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--check", action="store_true")
    cli.add_argument("--execute", action="store_true")
    args = cli.parse_args()
    try:
        if args.execute:
            raise ValueError("COMPILE_DIAGNOSTIC_NEW_PERMISSION_REQUIRED")
        out = args.output.resolve()
        root = (ROOT / "code/output").resolve()
        if out == root or not out.is_relative_to(root):
            raise ValueError("OUTPUT_SCOPE")
        payload, report = package(out)
        expected = {"inputs/" + n: b for n, b in payload.items()}
        expected["diagnostic_receipt.json"] = canonical(report)
        if args.check:
            actual = {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()}
            if actual != expected:
                raise ValueError("EXACT_PREPARED_DIAGNOSTIC_IDENTITY")
        else:
            if out.exists():
                raise ValueError("REFUSE_EXISTING_DIAGNOSTIC")
            out.mkdir(parents=True)
            for name, raw in expected.items():
                path = out / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as stream:
                    stream.write(raw)
        print(json.dumps(dict(status=report["status"], inputs=len(payload), compiled_sources=20,
                              compiler_identity_changed=report["compiler_identity_changed"],
                              execution_authorized=False, actual_tool_calls=0)))
        return 0
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(json.dumps(dict(status="REJECT", diagnostic=str(exc))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
