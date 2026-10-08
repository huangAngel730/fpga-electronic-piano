"""Bounded full-top new/reference waveform integration simulation only."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
CAD = Path("D:/Gowin/oss-cad-suite")
TB = ROOT / "code/tb/board/t058_waveform_integration_20261008"
sys.path.insert(0, str(ROOT / "code/scripts"))
import prepare_138k_waveform_integration as project
import prepare_138k_l_project as original


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project", type=Path, default=ROOT / "code/build/138k_waveform/candidate_20261008")
    p.add_argument("--output", type=Path)
    p.add_argument("--mode", type=int, choices=[0, 1, 2])
    p.add_argument("--vendor-startup", action="store_true")
    p.add_argument("--display-raster", action="store_true")
    p.add_argument("--negative", choices=["audio_pcm","video_alignment"])
    args = p.parse_args()
    project.validate(args.project)
    out = (args.output or ROOT / "code/output" / ("t058_waveform_integration_" + time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6])).resolve()
    out.relative_to((ROOT / "code/output").resolve())
    out.mkdir(parents=True, exist_ok=False)
    src = out / "sources"
    src.mkdir()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env["PATH"] = str(CAD / "bin") + os.pathsep + str(CAD / "lib") + os.pathsep + env.get("PATH", "")
    start = time.monotonic()
    deadline = start + 1800
    executed_runner_bytes = Path(__file__).read_bytes()
    (out / "executed_runner.py").write_bytes(executed_runner_bytes)
    receipt = dict(date="2026-10-08", passed=False, partial=args.mode is not None, steps={}, modes={},
                   source_sha256={}, adaptations=[], DVI_IP="simulation stub: NO TMDS/hardware proof",
                   clock_model="original vendorPLL" if args.vendor_startup else "nominal40/25/125clock simulation model; not PLL proof", programmed=False)

    def run(name, command, limit):
        left = deadline - time.monotonic()
        if left <= 0:
            raise ValueError("TOTAL_DEADLINE")
        step_started = time.monotonic()
        effective_limit = min(limit, left)
        with (out / (name + ".stdout.log")).open("wb") as so, (out / (name + ".stderr.log")).open("wb") as se:
            process = subprocess.Popen(list(map(str, command)), cwd=out, env=env, stdout=so, stderr=se, creationflags=subprocess.CREATE_NO_WINDOW)
            timed = False
            try:
                process.wait(timeout=min(limit, left))
            except subprocess.TimeoutExpired:
                timed = True
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=20)
                process.wait(timeout=20)
        elapsed = time.monotonic() - step_started
        if elapsed > effective_limit + 1.0:
            timed = True
        receipt["steps"][name] = dict(command=list(map(str, command)), exit_code=process.returncode, timed_out=timed, elapsed_seconds=round(elapsed,3), limit_seconds=effective_limit,
                                      stdout_sha256=sha((out / (name + ".stdout.log")).read_bytes()), stderr_sha256=sha((out / (name + ".stderr.log")).read_bytes()))
        print(name, "exit", process.returncode, flush=True)
        if process.returncode or timed:
            raise ValueError(name + " failed; inspect original stdout/stderr")

    def adapt(name, raw, dest=None):
        text = raw.decode("utf-8")
        adapted = re.sub(r"\bint unsigned\b", "integer", text)
        adapted = re.sub(r'`include "[^"]*/(sine_table\.svh|sustain_controller_ports\.svh)"', r'`include "\1"', adapted)
        if name == "voice_allocator_4.sv":
            fields = {"note_active": 1, "in_release": 1, "source": 4, "channel": 4, "note": 8, "age": 2}
            if adapted.count("    voice_slot_t slots [0:3];") != 1:
                raise ValueError("allocator mechanical adaptation identity")
            declarations = "\n".join("    logic " + ("[" + str(w-1) + ":0] " if w > 1 else "") + "sim_slot_" + f + " [0:3];" for f,w in fields.items())
            adapted = adapted.replace("    voice_slot_t slots [0:3];", declarations, 1)
            adapted = adapted.replace("                slots[i] <= '0;", "\n".join("                sim_slot_" + f + "[i] <= '0;" for f in fields), 1)
            for field in fields:
                adapted = re.sub(r"slots\[([^\]]+)\]\." + field + r"\b", r"sim_slot_" + field + r"[\1]", adapted)
        if name == "reference_audio_visual_top.sv":
            adapted = adapted.replace("AUDIO_VISUAL_COEXISTENCE_TOP_SV", "REFERENCE_AUDIO_VISUAL_TOP_SV")
        if dest:
            for old,new in dest.items():
                adapted = adapted.replace(old,new)
        target = src / name
        target.write_text(adapted, encoding="utf-8", newline="\n")
        if adapted != text:
            receipt["adaptations"].append(dict(file=name, only_integer_qualifier_array_struct_paths_or_reference_module_names=True, original_sha256=sha(raw), adapted_sha256=sha(target.read_bytes())))
        return target

    try:
        truth = original.archive_truth()
        tree, entries, oldroot = original.project_description(truth["project"])
        for file in (args.project / "inputs/sources").iterdir():
            receipt["source_sha256"][str(file.relative_to(ROOT)).replace("\\", "/")] = sha(file.read_bytes())
            if file.name != "DVI_TX_Top.v" and (args.vendor_startup or file.name != "TMDS_PLL_800_600_60.v"):
                adapt(file.name, file.read_bytes())
        # Original TOP/probe as separate module names; same original core/ROM inputs.
        redirects = {oldroot: (args.project / "inputs").as_posix(), "module audio_visual_coexistence_top": "module reference_audio_visual_top", "audio_visual_display_probe #": "reference_display_probe #"}
        adapt("reference_audio_visual_top.sv", truth["inputs"]["sources/audio_visual_coexistence_top.sv"], redirects)
        adapt("reference_display_probe.sv", truth["inputs"]["sources/audio_visual_display_probe.sv"], {"module audio_visual_display_probe": "module reference_display_probe"})
        dvi = ROOT / "code/rtl/138K_try/clock_trials_20261005/dvi_sim_stub.v"
        vendor = ROOT / "code/rtl/138K_try/tools/gowin_1_9_11_03/IDE/simlib/gw5a/prim_sim.v"
        if not dvi.is_file() or not vendor.is_file():
            raise ValueError("DVI simulation stub/vendor PLL model missing")
        bench = ROOT / "code/tb/board/clock40_startup_20261006/tb_clock40_startup.sv" if args.vendor_startup else TB / ("tb_display_integration.sv" if args.display_raster else "tb_integration.sv")
        clock_model = vendor if args.vendor_startup else TB / "clock_plan_sim.v"
        for file in [dvi, clock_model, bench, Path(__file__)]:
            receipt["source_sha256"][str(file.relative_to(ROOT)).replace("\\", "/")] = sha(file.read_bytes())
        excluded = {"DVI_TX_Top.v"} if args.vendor_startup else {"DVI_TX_Top.v", "TMDS_PLL_800_600_60.v"}
        names = [Path(e.attrib["path"]).name for e in entries if e.attrib["type"] == "file.verilog" and Path(e.attrib["path"]).name not in excluded]
        names += ["pcm_frame_observer.sv", "pcm_waveform_observer_bridge.sv", "pcm_waveform_candidate.sv", "reference_audio_visual_top.sv", "reference_display_probe.sv"]
        units = [src / n for n in names]
        if args.negative:
            if args.vendor_startup or args.display_raster or args.mode != 0:
                raise ValueError("negative case must be nominal shorttopMODE0")
            target = src / ("audio_visual_coexistence_top.sv" if args.negative=="audio_pcm" else "audio_visual_display_probe.sv")
            before = ".pcm_left  (buffered_left)" if args.negative=="audio_pcm" else "dvi_hs<=hs_d2;"
            after = ".pcm_left  (buffered_left ^ 24'sh000100)" if args.negative=="audio_pcm" else "dvi_hs<=hs_d1;"
            body = target.read_text(encoding="utf-8")
            if body.count(before)!=1:raise ValueError("negative patch identity")
            target.write_text(body.replace(before,after,1),encoding="utf-8",newline="\n")
            # The diagnostic testcase ends normally only on the specified
            # semantic failure. Any other assertion/compile/timeout remains FAIL.
            bench_copy = src/"tb_negative.sv"
            body=bench.read_text(encoding="utf-8")
            if args.negative=="audio_pcm":
                before='$fatal(1,"AUDIO_EQUivalence");'
                after='begin $fdisplay(fd,"REJECT AUDIO_PCM_CHANGED");$display("NEGATIVE_COMPLETE AUDIO_PCM_CHANGED");$fclose(fd);$finish;end'
            else:
                before='$fatal(1,"COMPOSITE_ALIGNMENT actual=%h expected=%h x=%0d y=%0d",{dut.u_visual.dvi_hs,dut.u_visual.dvi_vs,dut.u_visual.dvi_de,dut.u_visual.dvi_r,dut.u_visual.dvi_g,dut.u_visual.dvi_b},expect3,dut.u_visual.pixel_x,dut.u_visual.pixel_y);'
                after='begin $fdisplay(fd,"REJECT VIDEO_ALIGNMENT_CHANGED");$display("NEGATIVE_COMPLETE VIDEO_ALIGNMENT_CHANGED");$fclose(fd);$finish;end'
            if body.count(before)!=1:raise ValueError("negative oracle entry identity")
            bench_copy.write_text(body.replace(before,after,1),encoding="utf-8",newline="\n")
            bench=bench_copy
            receipt["negative_scope"]=dict(kind=args.negative,only_new_simulation_copies_mutated=True,completed_at_specified_assertion=True)
        receipt["compiled_inputs_sha256"] = {str(file):sha(file.read_bytes()) for file in units+[dvi,clock_model,bench]}
        run("tool_version", [CAD / "bin/iverilog.exe", "-B", CAD / "lib/ivl", "-V"], 30)
        for mode in [args.mode] if args.mode is not None else [0, 1, 2]:
            image = out / ("mode" + str(mode) + ".vvp")
            top = "tb_clock40_startup" if args.vendor_startup else "tb_display_integration" if args.display_raster else "tb_waveform_integration"
            parameter = top + (".SCENARIO=" if args.vendor_startup else ".MODE=") + str(mode)
            run("mode" + str(mode) + "_compile", [CAD / "bin/iverilog.exe", "-B", CAD / "lib/ivl", "-g2012", "-I", args.project / "inputs/include", "-s", top, "-P" + parameter, "-o", image, *units, dvi, clock_model, bench], 120)
            capture = out / ("mode" + str(mode) + ".capture")
            sim_command = [CAD / "bin/vvp.exe", image, "+CAPTURE=" + str(capture)]
            if args.display_raster:
                import base64
                sealed = ROOT/"code/tb/audio_out/m3_clock40_pcm_serial_acceptance/evidence"
                raw = base64.b64decode(b"".join((sealed/"normal_capture.b64").read_bytes().split()),validate=True)
                table = json.loads((sealed/"raw_manifest.json").read_text(encoding="utf-8"))
                if sha(raw)!=table["normal_capture.b64"]["raw_sha256"]:
                    raise ValueError("REAL_CAPTURE_SHA")
                rows=[line.split() for line in raw.decode("ascii").splitlines() if line.startswith("A ")]
                stimulus=[]
                for i,row in enumerate(rows):
                    period=int(round((float(rows[i+1][1])-float(row[1]))/25)) if i+1<len(rows) else 833
                    stimulus.append((i,int(row[4]),int(row[5]),period))
                vectors=out/"real_samples.txt"
                vectors.write_text("".join(" ".join(map(str,row))+"\n" for row in stimulus),encoding="ascii")
                sim_command += ["+VECTORS="+str(vectors),"+COUNT="+str(len(stimulus))]
                receipt["original_A_capture_sha256"]=sha(raw)
                receipt["real_vector_sha256"]=sha(vectors.read_bytes())
            run("mode" + str(mode) + "_run", sim_command, 900 if args.display_raster else 600)
            log = (out / ("mode" + str(mode) + "_run.stdout.log")).read_text(encoding="utf-8",errors="replace")
            if args.negative:
                reason="AUDIO_PCM_CHANGED" if args.negative=="audio_pcm" else "VIDEO_ALIGNMENT_CHANGED"
                if "NEGATIVE_COMPLETE "+reason not in log:
                    raise ValueError("specified behavioral rejection missing")
                checked=subprocess.run([sys.executable,"-B","-X","utf8",TB/"check_capture.py",capture],cwd=out,env=env,capture_output=True,timeout=30)
                (out/"negative_check.stdout.log").write_bytes(checked.stdout)
                (out/"negative_check.stderr.log").write_bytes(checked.stderr)
                if checked.returncode!=1 or reason.encode() not in checked.stdout:
                    raise ValueError("independent checker failed to reject semantic mutation")
                receipt["modes"]["negative_"+args.negative]=dict(passed=True,compile_exit=0,run_exit=0,check_exit=1,reason=reason,capture_sha256=sha(capture.read_bytes()),testcase_ended_at_semantic_assertion=True)
                continue
            marker = "PASS essential startup scenario=" + str(mode) if args.vendor_startup else "PASS INTEGRATED_DISPLAY" if args.display_raster else "PASS FULL_TOP SHORT_EQ_MODE=" + str(mode)
            if marker not in log or "ERROR" in log or "Unable to open" in log:
                raise ValueError("missing full simulation PASS or ROM/vendor error")
            if args.vendor_startup:
                original_capture = out / "startup.capture"
                if not original_capture.exists() or b"END scenario=" not in original_capture.read_bytes():
                    raise ValueError("vendor startup capture incomplete")
                capture.write_bytes(original_capture.read_bytes())
                receipt["modes"]["vendor_" + str(mode)] = dict(passed=True,capture_sha256=sha(capture.read_bytes()),scope="actual vendorPLL startup/reset only; not long raster")
                continue
            lines = capture.read_text(encoding="ascii").splitlines()
            if not lines[-1].startswith("END "):
                raise ValueError("capture incomplete")
            values = list(map(int,lines[-1].split()[1:]))
            if args.display_raster:
                if len(values)!=7 or values[0]<3360000 or values[2]!=5849 or values[3]!=5849 or values[4]<1:
                    raise ValueError("display nonempty window/raster coverage missing")
                receipt["modes"]["display_"+str(mode)]=dict(passed=True,scope="same integrated display_probe full raster; recorded PCM replay, not simultaneous livecore",final_coverage=values,capture_sha256=sha(capture.read_bytes()),terminal_line=lines[-1])
            else:
                if len(values) != 9 or values[0] < 100000 or values[2] < 200000:
                    raise ValueError("nonempty detailed coverage missing")
                receipt["modes"][str(mode)] = dict(passed=True, scope="short actualtop audio equivalence and warmupvideo; longraster separately required", final_coverage=values, capture_sha256=sha(capture.read_bytes()), terminal_line=lines[-1])
        receipt["passed"] = True
    except (OSError,ValueError,subprocess.SubprocessError,IndexError,KeyError) as error:
        receipt["error"] = str(error)
        print("FAIL", error, flush=True)
    receipt["elapsed_seconds"] = round(time.monotonic()-start,3)
    if receipt["elapsed_seconds"] > 1800:
        receipt["passed"] = False
        receipt["error"] = "TOTAL_ELAPSED_LIMIT_EXCEEDED"
    receipt["executed_runner_snapshot_sha256"] = sha(executed_runner_bytes)
    project.validate(args.project)
    (out / "receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    print("receipt",out/"receipt.json","passed",receipt["passed"],flush=True)
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
