"""D040 bounded source-bound host regressions; never install or touch devices."""
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MAIN = "code/software/score_ble_bridge_candidate/main/main.c"
ACTIVITY = "code/software/score_ble_android_candidate/app/src/main/java/org/m3/score/MainActivity.kt"
PROTOCOL = "code/software/score_ble_android_candidate/app/src/main/java/org/m3/score/Protocol.java"
BASE = "5be92d9"
OLD_SHA = {MAIN: "2afc1cbc8fa53e3382d9c80082858195b9ab8602e596c750e13a4ea6e525c1d8",
           ACTIVITY: "3513bd1c143e929443703d57e9c416d20ba603f193f07d9a04db33117e951746"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def function(text, signature):
    """Find the definition (not forward declaration), then balanced braces.

    The four extracted C bodies contain no braces inside strings/comments.
    Kotlin helpers likewise use no interpolated strings, making this explicit
    small-source extractor deterministic; unexpected drift fails binding.
    """
    start = text.index(signature)
    opening = text.index("{", start)
    depth = 0
    for end in range(opening, len(text)):
        if text[end] == "{":
            depth += 1
        elif text[end] == "}":
            depth -= 1
            if depth == 0:
                return text[start:end + 1]
    raise ValueError("unbalanced source function")


def c_functions(text):
    return "\n\n".join(function(text, signature) for signature in (
        "static uint32_t ms(void)", "static int gap_event(struct ble_gap_event *e,",
        "static void reset_cb(int reason)", "static void io_task(void *arg)"))


def kotlin_region(text):
    return text.split("// TARGET_ADAPTER_HOST_BEGIN:", 1)[1].split("// TARGET_ADAPTER_HOST_END", 1)[0].split("\n", 1)[1]


def java_helpers(region):
    """Narrow fail-closed Kotlin-to-Java spelling adapter, NOT a Kotlin compiler.

    Bodies/conditions and constants originate in the actual Activity. Only JVM
    declarations, null-safe callback syntax and UTF8 conversion spelling change.
    Both runtimes use Java String's UTF8 encoder. No independent algorithm is
    substituted. Full mapping + input/output are sealed for M2's review.
    """
    kinds = {"Long": "long", "String": "String", "Boolean": "boolean", "ByteArray": "byte[]"}
    fields = {"rawLog": "StringBuilder", "rawLogBytes": "int", "logIncomplete": "boolean",
              "scanning": "boolean", "scanGeneration": "long", "destroyed": "boolean"}
    output = []
    sync = False
    for line in region.splitlines():
        code = line.strip()
        if not code or code.startswith("//"):
            continue
        if code == "@Synchronized":
            sync = True
            continue
        field = re.fullmatch(r"private (val|var) (\w+) = (.+)", code)
        method = re.fullmatch(r"private fun (\w+)\((.*?)\)(?:: (\w+))? \{", code)
        if field:
            const, name, value = field.groups()
            value = "new StringBuilder()" if value == "StringBuilder()" else value
            code = "private " + ("final " if const == "val" else "") + fields[name] + " " + name + " = " + value + ";"
        elif code == "private var scanTimeout: Runnable? = null":
            code = "private Runnable scanTimeout = null;"
        elif method:
            name, params, result = method.groups()
            converted = []
            if params:
                for item in params.split(", "):
                    arg, kind = item.split(": ")
                    converted.append(kinds[kind] + " " + arg)
            code = "private " + ("synchronized " if sync else "") + kinds.get(result, "void") + " " + name + "(" + ", ".join(converted) + ") {"
            sync = False
        else:
            code = code.replace("scanTimeout?.let { handler.removeCallbacks(it) }", "if (scanTimeout != null) { handler.removeCallbacks(scanTimeout); }")
            code = code.replace("scanTimeout?.let { handler.keepCallbacks(it) }", "if (scanTimeout != null) { handler.keepCallbacks(scanTimeout); }")
            code = code.replace("val line =", "String line =").replace("val byteCount =", "int byteCount =")
            code = code.replace("now.toString()", "Long.toString(now)")
            code = code.replace(".toByteArray(Charsets.UTF_8).size", ".getBytes(StandardCharsets.UTF_8).length")
            code = code.replace(".toByteArray(Charsets.UTF_8)", ".getBytes(StandardCharsets.UTF_8)")
            code = code.replace("line.length", "line.length()")
            if not code.endswith(("{", "}", ";")):
                code += ";"
        if re.search(r"\b(val|var|fun|Charsets)\b|\?\.let|toByteArray", code):
            raise ValueError("untranslated Kotlin token: " + code)
        output.append(code)
    if sync:
        raise ValueError("dangling synchronization annotation")
    return "\n".join(output)


def binding(main, activity):
    for anchor in ("uint32_t read_epoch=bridge.epoch;", "uint16_t read_conn=conn;",
                   "uint8_t read_connected=bridge.connected;",
                   "if(!read_connected || !bridge.connected || read_epoch!=bridge.epoch || read_conn!=conn) n=0;"):
        if main.count(anchor) != 1:
            raise ValueError("C current source binding " + anchor)
    read = main.index("int n=uart_read_bytes")
    before = main[main.index("for(;;) {", main.index("static void io_task")):read]
    if not (before.index("xSemaphoreTake") < before.index("read_epoch") < before.index("xSemaphoreGive")):
        raise ValueError("UART snapshot outside mutex")
    for anchor in ("appendLogLine(SystemClock.elapsedRealtime(), text)", "it.write(exportLogBytes())",
                   "val token = scanGeneration", "if (scanTimeoutCurrent(token))", "handler.postDelayed(timeout,10000)",
                   "handler.removeCallbacks(it)", "if (!permitted()) { stopScan(); return }", "if (destroyed) return"):
        if anchor not in activity:
            raise ValueError("Activity integration binding " + anchor)
    stopped = function(activity, "private fun stopScan()")
    if "cancelScanTimeout()" not in stopped or "scanning = false" not in stopped:
        raise ValueError("scan stop binding")
    destroy = function(activity, "override fun onDestroy()")
    if not destroy.index("destroyed = true") < destroy.index("stopScan()") < destroy.index("removeCallbacksAndMessages"):
        raise ValueError("destroy cancellation binding")
    scan = function(activity, "private fun scan()")
    if not scan.index("stopScan()\n") < scan.index("scanning = true") < scan.index("val token ="):
        raise ValueError("scan restart binding")
    return {"uart_mutex_read_order": True, "activity_integration_anchors": True,
            "limitation": "static binding outside extracted helpers; not target compilation"}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--gcc", type=Path, default=Path("D:/program/OSsystem/MinGW/bin/gcc.exe"))
    cli.add_argument("--jdk", type=Path, default=Path("E:/FPGA/Bpan/Vivado/Vivado2020_2/2020.2/tps/win64/jre11.0.2"))
    args = cli.parse_args()
    out = args.output.resolve()
    if out.exists() or not out.is_relative_to((ROOT / "code/output").resolve()) or not out.name.startswith("m3_t059_target_adapter_repair_"):
        cli.error("require unique code/output/m3_t059_target_adapter_repair_* output")
    out.mkdir(parents=True)
    started = time.monotonic()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("JAVA_TOOL_OPTIONS", None)
    env["PATH"] = str(args.gcc.parent) + os.pathsep + env.get("PATH", "")
    steps = []
    receipt = {"passed": False, "steps": steps, "authorization_baseline": BASE, "device_operations": False,
               "target_sdk_kotlin_apk_compiled": False, "old_evidence_modified": False,
               "scope": "source-bound host tests, not ESP-IDF/Android runtime"}

    def execute(label, command):
        remaining = 1800 - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("total 1800s")
        folder = out / label
        folder.mkdir()
        begin = time.monotonic()
        process = subprocess.Popen([str(part) for part in command], cwd=ROOT, env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        timed = False
        try:
            stdout, stderr = process.communicate(timeout=min(600, remaining))
        except subprocess.TimeoutExpired:
            timed = True
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=15, check=False)
            stdout, stderr = process.communicate(timeout=15)
        (folder / "stdout.log").write_bytes(stdout)
        (folder / "stderr.log").write_bytes(stderr)
        item = {"label": label, "command": [str(p) for p in command], "exit": process.returncode,
                "timed_out": timed, "seconds": round(time.monotonic() - begin, 6),
                "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr)}
        steps.append(item)
        print(label, process.returncode, (stdout + stderr).decode("utf-8", errors="replace")[-320:], flush=True)
        if timed:
            raise TimeoutError(label)
        return process.returncode, stdout + stderr

    def require(label, command):
        code, data = execute(label, command)
        if code:
            raise ValueError(label + " failed")
        return data

    try:
        frozen = json.loads((ROOT / "code/docs/evidence/m3_night_tasks_baseline_20261007.json").read_text(encoding="utf-8"))["frozen_candidate_sha256"]
        unchanged = {}
        for name, expected in frozen.items():
            if name not in OLD_SHA:
                actual = sha((ROOT / name).read_bytes())
                if actual != expected:
                    raise ValueError("other eight frozen source changed " + name)
                unchanged[name] = actual
        if len(unchanged) != 8:
            raise ValueError("expected eight immutable business files")
        receipt["eight_unchanged_sources"] = unchanged
        old = {}
        versions = {}
        snapshots = out / "sources"
        snapshots.mkdir()
        for name, expected in OLD_SHA.items():
            raw = require("old_" + Path(name).name.replace(".", "_"), ["git", "show", BASE + ":" + name])
            if sha(raw) != expected:
                raise ValueError("approved old source SHA " + name)
            current = (ROOT / name).read_bytes()
            versions[name] = {"old_sha256": expected, "new_sha256": sha(current)}
            old[name] = raw.decode("utf-8")
            (snapshots / ("old_" + Path(name).name)).write_bytes(raw)
            (snapshots / ("new_" + Path(name).name)).write_bytes(current)
        receipt["adapter_versions"] = versions
        current_main = (ROOT / MAIN).read_text(encoding="utf-8")
        current_activity = (ROOT / ACTIVITY).read_text(encoding="utf-8")
        receipt["source_binding"] = binding(current_main, current_activity)
        receipt["test_source_sha256"] = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in HERE.iterdir() if p.is_file()}
        require("gcc_version", [args.gcc, "--version"])
        require("javac_version", [args.jdk / "bin/javac.exe", "-version"])
        require("java_version", [args.jdk / "bin/java.exe", "-version"])
        c_template = (HERE / "uart_mock.c").read_text(encoding="utf-8")
        guard = "if(!read_connected || !bridge.connected || read_epoch!=bridge.epoch || read_conn!=conn) n=0;"
        c_variants = {"uart_current": current_main,
                      "uart_no_guard": current_main.replace(guard, guard.replace("if(", "if(0 && (", 1).replace(") n=0;", ")) n=0;")),
                      "uart_legacy": old[MAIN]}
        for label, text in c_variants.items():
            folder = out / (label + "_source")
            folder.mkdir()
            code = c_template.replace("/* SOURCE_FUNCTIONS: injected verbatim from approved current or old main.c. */", c_functions(text))
            source = folder / "uart_host.c"
            source.write_text(code, encoding="utf-8", newline="\n")
            exe = folder / "uart_host.exe"
            require(label + "_compile", [args.gcc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic",
                                        "-I", ROOT / "code/software/score_ble_bridge_candidate/core",
                                        ROOT / "code/software/score_ble_bridge_candidate/core/bridge.c", source, "-o", exe])
            result, data = execute(label + "_run", [exe])
            if label == "uart_current":
                if result or b"PASS UART" not in data:
                    raise ValueError("UART normal regression")
                receipt["uart_summary"] = data.decode("utf-8").strip()
            elif result != 1 or b"UART_GENERATION_STALE_QUEUE" not in data:
                raise ValueError("UART semantic negative not rejected " + label)
        region = kotlin_region(current_activity)
        java_template = (HERE / "android_mock.java.in").read_text(encoding="utf-8")
        variants = {
            "android_current": (region, None, []),
            "android_no_guard": (region.replace("!destroyed && scanning && token == scanGeneration", "scanning"), b"SCAN_TOKEN", []),
            "android_no_cancel": (region.replace("handler.removeCallbacks(it)", "handler.keepCallbacks(it)"), b"SCAN_CANCEL", []),
            "android_utf16_count": (region.replace("line.toByteArray(Charsets.UTF_8).size", "line.length"), b"UTF8_COUNT", []),
            "android_text_only_count": (region.replace("line.toByteArray(Charsets.UTF_8).size", "text.toByteArray(Charsets.UTF_8).size"), b"UTF8_COUNT", []),
        }
        for label, (fragment, token, extra) in variants.items():
            folder = out / (label + "_source")
            folder.mkdir()
            source = folder / "AndroidAdapterHost.java"
            source.write_text(java_template.replace("/* SOURCE_HELPERS */", java_helpers(fragment)), encoding="utf-8", newline="\n")
            classes = folder / "classes"
            classes.mkdir()
            require(label + "_compile", [args.jdk / "bin/javac.exe", "-encoding", "UTF-8", "--release", "8", "-Xlint:all", "-Werror", "-d", classes, source, ROOT / PROTOCOL])
            result, data = execute(label + "_run", [args.jdk / "bin/java.exe", "-cp", classes, "AndroidAdapterHost", *extra])
            if token is None:
                if result or b"PASS Android" not in data:
                    raise ValueError("Android source-derived regression")
                receipt["android_summary"] = data.decode("utf-8").strip()
            elif result != 1 or token not in data:
                raise ValueError("Android semantic negative not rejected " + label)
        # Old Android algorithms are evidence-bound models, NOT old APK execution.
        old_activity = old[ACTIVITY]
        if "handler.postDelayed({ if (scanning)" not in old_activity:
            raise ValueError("old scan source binding")
        old_log = function(old_activity, "private fun log(text: String)")
        old_line = next(line.strip() for line in old_log.splitlines() if "rawLog.length" in line)
        for label, mode, token in (("android_legacy_scan", "legacy-scan", b"SCAN_LEGACY"),
                                   ("android_legacy_log", "legacy-cap", b"UTF8_LEGACY")):
            helper = java_helpers(region)
            if mode == "legacy-scan":
                helper = helper.replace("return !destroyed && scanning && token == scanGeneration;", "return scanning;")
            else:
                old_statement = old_line.replace("SystemClock.elapsedRealtime()", "now")
                old_statement = old_statement.replace("rawLog.length", "rawLog.length()").replace("text.length", "text.length()")
                new_body = function(helper, "private synchronized boolean appendLogLine")
                replacement = "private synchronized boolean appendLogLine(long now, String text) {\n" + old_statement + ";\nreturn true;\n}"
                helper = helper.replace(new_body, replacement)
            folder = out / (label + "_source")
            folder.mkdir()
            source = folder / "AndroidAdapterHost.java"
            source.write_text(java_template.replace("/* SOURCE_HELPERS */", helper), encoding="utf-8", newline="\n")
            classes = folder / "classes"
            classes.mkdir()
            require(label + "_compile", [args.jdk / "bin/javac.exe", "-encoding", "UTF-8", "--release", "8", "-Xlint:all", "-Werror", "-d", classes, source, ROOT / PROTOCOL])
            result, data = execute(label + "_run", [args.jdk / "bin/java.exe", "-cp", classes, "AndroidAdapterHost", mode])
            if result != 1 or token not in data:
                raise ValueError("old Android bug not rejected " + label)
        for name, info in versions.items():
            if sha((ROOT / name).read_bytes()) != info["new_sha256"]:
                raise ValueError("source changed during regression")
        receipt["passed"] = True
    except Exception as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)
    receipt["seconds"] = round(time.monotonic() - started, 6)
    receipt["artifacts"] = {p.relative_to(out).as_posix(): {"sha256": sha(p.read_bytes()), "bytes": p.stat().st_size}
                            for p in out.rglob("*") if p.is_file()}
    (out / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("PASS D040 isolated host regression" if receipt["passed"] else "FAIL " + receipt.get("error", "unknown"), flush=True)
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
