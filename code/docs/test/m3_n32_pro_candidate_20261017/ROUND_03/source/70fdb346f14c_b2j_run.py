"""Bounded new public completion test; no changed functional RTL or EDA."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

from inventory import BASELINE, FROZEN, ROOT, identity, verify_manifest
from b2d_run import sources
from b2j_check import FIELDS, STATUS, check


def changed(raw, kind):
    """Complete capture with one semantic mutation, original END preserved."""
    lines = raw.decode("ascii").splitlines()
    rows = [i for i, line in enumerate(lines) if line.startswith("T ")]
    def data(index):
        return dict(zip(FIELDS, map(int, lines[index].split()[1:])))
    if kind in ("early_ready", "late_ready"):
        p = next(i for i in rows if data(i)["publish"])
        target = p+2 if kind == "early_ready" else p+3
        field, value = "sr", int(kind == "early_ready")
    elif kind in ("early_valid", "late_valid"):
        first = next(i for i in rows if data(i)["rv"])
        target = first-1 if kind == "early_valid" else first
        field, value = "rv", int(kind == "early_valid")
    elif kind == "held_tuple":
        target = next(i for i in rows if data(i)["rv"] and not data(i)["rr"])
        field, value = "left", data(target)["left"] ^ 1
    elif kind == "false_publish":
        target = next(i for i in rows if data(i)["rv"] and not data(i)["rr"])
        field, value = "publish", 1
    elif kind == "read_admission":
        target = next(i for i in rows if data(i)["read"] and data(i)["idle"])
        field, value = "sr", 1
    elif kind == "bad_end":
        target = next(i for i, line in enumerate(lines) if line.startswith("END "))
        lines[target] = "END "+str(int(lines[target].split()[1])+1)
        return ("\n".join(lines)+"\n").encode("ascii")
    else:
        raise ValueError("UNKNOWN_MUTANT")
    row = data(target)
    row[field] = value
    lines[target] = "T "+" ".join(str(row[key]) for key in FIELDS)
    return ("\n".join(lines)+"\n").encode("ascii")


def execute(args):
    sys.path.insert(0, str(ROOT / "code/scripts"))
    from run_m3_polyphony_scaling_acceptance import Run
    from b1_run import external
    output = args.output.resolve()
    output.relative_to(ROOT / "code/output")
    output.mkdir(parents=True, exist_ok=False)
    run = Run(output)
    candidate = ROOT / "code/software/polyphony_scaling_candidate"
    tb = ROOT / "code/tb/common/polyphony_scaling_candidate/tb_b2j_completion.sv"
    functional = sources()[:-1]
    inputs = sorted(candidate.glob("*.py"))+functional+[tb, FROZEN/"input_manifest.json",
        ROOT / "code/scripts/run_m3_polyphony_scaling_acceptance.py"]
    # Original frozen inputs, all previous evidence seals, all 8 shared files.
    doc = ROOT / "code/docs/hardware/polyphony_scaling_v1"
    protected = [p for d in doc.iterdir() if d.is_dir() for p in d.rglob("*") if p.is_file()]
    protected += [ROOT / p for p in (
        "code/docs/当前状态.md", "code/docs/任务看板.md", "code/docs/验证记录.md",
        "code/docs/技术决策记录.md", "code/docs/模块接口规范.md",
        "code/rtl/board/electronic_piano_top.sv", "code/rtl/common/audio_defs_pkg.sv",
        "code/constraints/electronic_piano.cst")]
    receipt = dict(stage="T061_B2J_PUBLIC_COMPLETION", status="FAIL", exit_code=1,
                   command=[sys.executable, *sys.argv], task_complete=False,
                   step_limit_seconds=900, workflow_limit_seconds=1800,
                   functional_revision="52ad3dc", new_functional_HDL=False,
                   new_TB=True, new_RTL_simulation=True, new_synthesis=False,
                   new_PnR=False, device_operations=False,
                   candidate_sources_before=[identity(p) for p in inputs],
                   frozen_inputs_before=verify_manifest(),
                   old_seal_and_shared_before=[identity(p) for p in protected])
    code = 1
    try:
        for path in [FROZEN/"input_manifest.json"]+[ROOT/item["path"] for item in receipt["frozen_inputs_before"]]:
            blob = run.command("pinned_frozen", ["git", "show", BASELINE+":"+path.relative_to(ROOT).as_posix()])
            if blob.replace(b"\r\n", b"\n") != path.read_bytes().replace(b"\r\n", b"\n"):
                raise ValueError("FROZEN_GIT_SOURCE_CHANGED")
        for path in functional:
            rel = path.relative_to(ROOT).as_posix()
            blob = run.command("pinned_functional", ["git", "show", "52ad3dc:"+rel])
            if blob.replace(b"\r\n", b"\n") != path.read_bytes().replace(b"\r\n", b"\n"):
                raise ValueError("FUNCTIONAL_SOURCE_CHANGED:"+rel)
        iv, vvp = args.iverilog.resolve(), args.vvp.resolve()
        suite = iv.parent.parent
        run.extra_env = {"YOSYSHQ_ROOT": str(suite)+os.sep}
        run.extra_path = [str(suite/"bin"), str(suite/"lib")]
        run.command("iverilog_version", [str(iv), "-V"])
        run.command("vvp_version", [str(vvp), "-V"])
        base = [str(iv), "-g2012", "-I", str(FROZEN/"include"), "-s", "tb_b2j_completion"]
        reports, captures = [], []
        for n, response in ((4, 1), (32, 1), (32, 8)):
            label = f"B2J_N{n}_R{response}"
            image, report = output/(label+".vvp"), output/(label+".json")
            run.command(label+"_compile", base+[f"-DB2J_N={n}", f"-DB2J_RESPONSE={response}",
                        "-o", str(image)]+[str(p) for p in functional+[tb]])
            run.command(label+"_simulate", [str(vvp), str(image)])
            capture = ROOT/run.steps[-1]["stdout"]["path"]
            raw = run.command(label+"_check", [sys.executable, "-B", "-X", "utf8",
                        str(candidate/"b2j_check.py"), "--input", str(capture), "--output", str(report)])
            reports.append(json.loads(raw))
            captures.append(capture)
        negatives = []
        for kind in ("early_ready", "late_ready", "early_valid", "late_valid", "held_tuple",
                     "false_publish", "read_admission", "bad_end"):
            path = output/(kind+".txt")
            path.write_bytes(changed(captures[1].read_bytes(), kind))
            raw = run.command(kind+"_reject", [sys.executable, "-B", "-X", "utf8",
                str(candidate/"b2j_check.py"), "--input", str(path)], expected_exit=1)
            require_reason = {"early_ready": "COMPLETION_SR", "late_ready": "COMPLETION_SR",
                "early_valid": "COMPLETION_RV", "late_valid": "COMPLETION_RV",
                "held_tuple": "HELD_RESULT_CHANGED", "false_publish": "COMPLETION_PUBLISH",
                "read_admission": "COMPLETION_SR", "bad_end": "END_COUNT"}[kind]
            if require_reason.encode() not in raw:
                raise ValueError("WRONG_NEGATIVE_DIAGNOSTIC:"+kind)
            negatives.append(dict(kind=kind, diagnostic=require_reason, exit_code=1))
        wrapper = ROOT / "code/rtl/common/polyphony_scaling_candidate/b2d_event_audio.sv"
        mutations = (
            ("early_drain", "DRAIN:if(!sched_busy && be_empty && control_ready && !control_valid)",
             "DRAIN:if(be_empty && control_ready && !control_valid)", "COMPLETION_IDLE"),
            ("ignore_read", "idle && !cancel && !read_valid", "idle && !cancel", "COMPLETION_SR"))
        compiled = []
        for name, old, new, reason in mutations:
            original = wrapper.read_text(encoding="utf-8")
            if original.count(old) != 1:
                raise ValueError("MUTATION_ANCHOR")
            replacement = output/(name+".sv")
            replacement.write_text(original.replace(old, new), encoding="utf-8", newline="\n")
            image = output/(name+".vvp")
            selected = [replacement if p == wrapper else p for p in functional]
            run.command(name+"_compile", base+["-DB2J_N=32", "-o", str(image)]+[str(p) for p in selected+[tb]])
            run.command(name+"_simulate", [str(vvp), str(image)])
            path = ROOT/run.steps[-1]["stdout"]["path"]
            if sum(line.startswith(b"END ") for line in path.read_bytes().splitlines()) != 1:
                raise ValueError("INCOMPLETE_BEHAVIOR_NEGATIVE")
            raw = run.command(name+"_check", [sys.executable, "-B", "-X", "utf8",
                str(candidate/"b2j_check.py"), "--input", str(path)], expected_exit=1)
            if reason.encode() not in raw:
                raise ValueError("WRONG_BEHAVIOR_DIAGNOSTIC:"+name)
            compiled.append(dict(name=name, diagnostic=reason, compile_exit=0, simulation_exit=0, checker_exit=1))
        run.command("completion_unit", [sys.executable, "-B", "-X", "utf8", "-m", "unittest",
                    "discover", "-s", str(candidate), "-p", "test_b2j.py", "-v"])
        receipt.update(status=STATUS, profiles=reports, negatives=negatives, compiled_negatives=compiled,
                       tools=dict(iverilog=external(iv), vvp=external(vvp)))
        code = 0
    except Exception as error:
        receipt["error"] = type(error).__name__+":"+str(error)
    finally:
        receipt.update(candidate_sources_after=[identity(p) for p in inputs],
                       frozen_inputs_after=verify_manifest(),
                       old_seal_and_shared_after=[identity(p) for p in protected])
        for name in ("candidate_sources", "frozen_inputs", "old_seal_and_shared"):
            if receipt[name+"_before"] != receipt[name+"_after"]:
                code = 1
                receipt.update(status="FAIL", error="INPUT_CHANGED:"+name)
        receipt.update(exit_code=code, steps=run.steps, elapsed_seconds=round(time.monotonic()-run.start, 6))
        receipt["outputs"] = [identity(p) for p in output.rglob("*") if p.is_file()]
        (output/"receipt.json").write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(dict(status=receipt["status"], exit_code=code, error=receipt.get("error"),
                         receipt=str(output/"receipt.json"))))
    raise SystemExit(code)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--iverilog", type=Path, default=Path("D:/Gowin/oss-cad-suite/bin/iverilog.exe"))
    parser.add_argument("--vvp", type=Path, default=Path("D:/Gowin/oss-cad-suite/bin/vvp.exe"))
    execute(parser.parse_args())
