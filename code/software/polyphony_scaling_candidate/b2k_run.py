"""Bounded in-flight cancellation sweep; unchanged functional RTL, no EDA."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

from inventory import BASELINE, FROZEN, ROOT, identity, verify_manifest
from b2d_run import sources
from b2k_check import FIELDS, STATUS, check


def changed(raw, kind):
    """One semantic mutation, retaining all CASE/T/FCW records and complete END."""
    lines = raw.decode("ascii").splitlines()
    rows = [i for i, line in enumerate(lines) if line.startswith("T ")]
    def data(index):
        return dict(zip(FIELDS, map(int, lines[index].split()[1:])))
    if kind == "bad_end":
        target = next(i for i, line in enumerate(lines) if line.startswith("END "))
        lines[target] = "END "+str(int(lines[target].split()[1])+1)
        return ("\n".join(lines)+"\n").encode("ascii")
    if kind in ("early_ready", "late_ready"):
        target = next(i for i in rows if data(i)["sv"] and data(i)["sr"] and data(i)["sid"] == 4)
        if kind == "early_ready":
            target = next(i for i in rows if data(i)["cycle"] == data(target)["cycle"]+11)
        else:
            target = next(i for i in rows if data(i)["sv"] and data(i)["sr"] and data(i)["sid"] == 1)
        field, value = "sr", int(kind == "early_ready")
    elif kind == "cancel_advance":
        target = next(i for i in rows if data(i)["cancel"] and data(i)["sid"] == 19)
        field, value = "advance", 1
    elif kind in ("rollback_phase", "wrong_slot"):
        target = next(i for i in rows if data(i)["lv"] and data(i)["slot"] == 0 and data(i)["sid"] == 22)
        field = "phase" if kind == "rollback_phase" else "slot"
        value = 0 if field == "phase" else 1
    elif kind == "lost_lane":
        target = next(i for i in rows if data(i)["lv"] and data(i)["cancel"])
        field, value = "lv", 0
    elif kind == "false_publish":
        target = next(i for i in rows if data(i)["cancel"])
        field, value = "publish", 1
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
    tb = ROOT / "code/tb/common/polyphony_scaling_candidate/tb_b2k_cancel.sv"
    functional = sources()[:-1]
    inputs = sorted(candidate.glob("*.py"))+[ROOT/"code/software/audio_math_acceptance_candidate/dds_model.py"]+functional+[tb, FROZEN/"input_manifest.json",
        ROOT / "code/scripts/run_m3_polyphony_scaling_acceptance.py"]
    # Original frozen inputs, all previous evidence seals, all 8 shared files.
    doc = ROOT / "code/docs/hardware/polyphony_scaling_v1"
    protected = [p for d in doc.iterdir() if d.is_dir() for p in d.rglob("*") if p.is_file()]
    protected += [ROOT / p for p in (
        "code/docs/当前状态.md", "code/docs/任务看板.md", "code/docs/验证记录.md",
        "code/docs/技术决策记录.md", "code/docs/模块接口规范.md",
        "code/rtl/board/electronic_piano_top.sv", "code/rtl/common/audio_defs_pkg.sv",
        "code/constraints/electronic_piano.cst")]
    receipt = dict(stage="T061_B2K_INFLIGHT_CANCEL", status="FAIL", exit_code=1,
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
        base = [str(iv), "-g2012", "-I", str(FROZEN/"include"), "-s", "tb_b2k_cancel"]
        reports, captures = [], []
        for n, response in ((4, 1), (32, 1), (32, 64)):
            label = f"B2K_N{n}_R{response}"
            image, report = output/(label+".vvp"), output/(label+".json")
            run.command(label+"_compile", base+[f"-DB2K_N={n}", f"-DB2K_RESPONSE={response}",
                        "-o", str(image)]+[str(p) for p in functional+[tb]])
            run.command(label+"_simulate", [str(vvp), str(image)])
            capture = ROOT/run.steps[-1]["stdout"]["path"]
            raw = run.command(label+"_check", [sys.executable, "-B", "-X", "utf8",
                        str(candidate/"b2k_check.py"), "--input", str(capture), "--output", str(report)])
            reports.append(json.loads(raw))
            captures.append(capture)
        negatives = []
        reasons = {"early_ready": "CANCEL_SR", "late_ready": "CANCEL_SR",
                   "cancel_advance": "CANCEL_ADVANCE", "rollback_phase": "NONROLLBACK_PHASE",
                   "wrong_slot": "CANCEL_SLOT", "lost_lane": "FCW_ORDER",
                   "false_publish": "CANCEL_PUBLISH", "bad_end": "END_COUNT"}
        for kind, reason in reasons.items():
            path = output/(kind+".txt")
            path.write_bytes(changed(captures[2].read_bytes(), kind))
            raw = run.command(kind+"_reject", [sys.executable, "-B", "-X", "utf8",
                str(candidate/"b2k_check.py"), "--input", str(path)], expected_exit=1)
            if reason.encode() not in raw:
                raise ValueError("WRONG_NEGATIVE_DIAGNOSTIC:"+kind)
            negatives.append(dict(kind=kind, diagnostic=reason, exit_code=1))
        wrapper = ROOT / "code/rtl/common/polyphony_scaling_candidate/b2d_event_audio.sv"
        mutations = (
            ("ignore_control", "DRAIN:if(!sched_busy && be_empty && control_ready && !control_valid)",
             "DRAIN:if(!sched_busy && be_empty)", "CANCEL_IDLE"),
            ("ignore_backend", "DRAIN:if(!sched_busy && be_empty && control_ready && !control_valid)",
             "DRAIN:if(control_ready && !control_valid)", "CANCEL_IDLE"))
        compiled = []
        for name, old, new, reason in mutations:
            original = wrapper.read_text(encoding="utf-8")
            if original.count(old) != 1:
                raise ValueError("MUTATION_ANCHOR")
            replacement = output/(name+".sv")
            replacement.write_text(original.replace(old, new), encoding="utf-8", newline="\n")
            image = output/(name+".vvp")
            selected = [replacement if p == wrapper else p for p in functional]
            run.command(name+"_compile", base+["-DB2K_N=32", "-DB2K_NEGATIVE_OBSERVE", "-o", str(image)]+[str(p) for p in selected+[tb]])
            run.command(name+"_simulate", [str(vvp), str(image)])
            path = ROOT/run.steps[-1]["stdout"]["path"]
            if sum(line.startswith(b"END ") for line in path.read_bytes().splitlines()) != 1:
                raise ValueError("INCOMPLETE_BEHAVIOR_NEGATIVE")
            raw = run.command(name+"_check", [sys.executable, "-B", "-X", "utf8",
                str(candidate/"b2k_check.py"), "--input", str(path)], expected_exit=1)
            if reason.encode() not in raw:
                raise ValueError("WRONG_BEHAVIOR_DIAGNOSTIC:"+name)
            compiled.append(dict(name=name, diagnostic=reason, compile_exit=0, simulation_exit=0, checker_exit=1))
        run.command("cancel_unit", [sys.executable, "-B", "-X", "utf8", "-m", "unittest",
                    "discover", "-s", str(candidate), "-p", "test_b2k.py", "-v"])
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
