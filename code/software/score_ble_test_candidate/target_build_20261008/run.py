"""T059 target-only preparation/build. No installs, downloads or devices.

Exit 0: requested stage passed; 2: missing environment; 1: failed check/build.
Preflight success is never target-build success or complete T059 success.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[4]
CORE = ROOT / "code/software/score_ble_bridge_candidate"
APP = ROOT / "code/software/score_ble_android_candidate"
BASE = "6c8e0b83ac0e83f516386b7b06abcbdca4fe98e2"
PINNED_IDF = "f5c3654a1c2d2a01f7f67def7a0dc48e691f63c0"
BASELINE = ROOT / "code/docs/hardware/score_ble_v1/target_adapter_repair_20261008/baseline.json"
SDK = Path("E:/FPGA/SDKs")
KNOWN_ROOTS = [SDK, Path("C:/Espressif"), Path("D:/Espressif"), Path("E:/Espressif"),
               Path.home() / ".espressif", Path.home() / ".gradle",
               Path.home() / "AppData/Local/Android/Sdk", Path("C:/Program Files/Java"),
               Path("C:/Program Files/Eclipse Adoptium"), Path("C:/Program Files/Android")]


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def dump(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8", newline="\n")


def check_configs():
    checks = {
        APP / "build.gradle.kts": [r'id\("com.android.application"\) version "8\.7\.3"',
                                  r'id\("org.jetbrains.kotlin.android"\) version "2\.0\.21"'],
        APP / "app/build.gradle.kts": [r'compileSdk\s*=\s*35\b', r'targetSdk\s*=\s*35\b',
                                       r'buildToolsVersion\s*=\s*"34\.0\.0"',
                                       r'minSdk\s*=\s*26\b', r'jvmTarget\s*=\s*"17"',
                                       r'JavaVersion\.VERSION_17'],
        CORE / "sdkconfig.defaults": [r'CONFIG_IDF_TARGET="esp32c3"',
                                      r'CONFIG_BT_NIMBLE_ENABLED=y'],
        CORE / "main/CMakeLists.txt": [r'"main\.c"', r'"\.\./core/bridge\.c"'],
    }
    errors = []
    for path, patterns in checks.items():
        content = path.read_text(encoding="utf-8")
        errors.extend(f"CONFIG_PIN: {path.relative_to(ROOT)}: {pattern}"
                      for pattern in patterns if not re.search(pattern, content))
    return errors


def frozen_sources():
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    expected = dict(baseline["eight_unchanged_sources"])
    expected.update({path: item["new_sha256"]
                     for path, item in baseline["adapter_versions"].items()})
    result, errors = {}, []
    for relative, wanted in expected.items():
        raw = (ROOT / relative).read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        lf = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
        result[relative] = {"sha256": actual, "lf_sha256": lf,
                            "expected": wanted, "matched": wanted in (actual, lf)}
        if not result[relative]["matched"]:
            errors.append("FROZEN_SOURCE_IDENTITY: " + relative)
    return result, errors


def audit_downloads(folder):
    """Read archive metadata only. Never extract/execute downloaded payloads."""
    receipt_path = folder / "DOWNLOAD_RECEIPT.json"
    if not receipt_path.is_file():
        return {"status": "NOT_FOUND", "path": str(folder)}
    prior = json.loads(receipt_path.read_text(encoding="utf-8"))
    result = {"prior_receipt_sha256": digest(receipt_path), "packages": [],
              "extracted": False, "installed": False}
    for package in prior["packages"]:
        path = folder / package["name"]
        item = {"name": path.name, "exists": path.is_file()}
        if path.is_file():
            item.update(bytes=path.stat().st_size, sha256=digest(path))
            item["matches_prior_verified_receipt"] = (
                item["sha256"] == package["sha256"] and item["bytes"] == package["bytes"])
            if path.suffix == ".zip":
                with zipfile.ZipFile(path) as archive:
                    item["expanded_member_bytes"] = sum(entry.file_size for entry in archive.infolist())
                    markers = {"OpenJDK17U-jdk_x64_windows_hotspot_17.0.20.1_1.zip": "jdk-17.0.20.1+1/release",
                               "platform-35_r02.zip": "android-35/source.properties",
                               "build-tools_r34-windows.zip": "android-14/source.properties",
                               "commandlinetools-win-11479570_latest.zip": "cmdline-tools/source.properties"}
                    if path.name in markers:
                        item["version_marker"] = archive.read(markers[path.name]).decode("utf-8").strip()
                    if path.name == "gradle-8.9-bin.zip":
                        item["gradle_8_9_launcher_present"] = "gradle-8.9/lib/gradle-launcher-8.9.jar" in archive.namelist()
                    if path.name == "esp-idf-v5.4.2.zip":
                        tools = json.loads(archive.read("esp-idf-v5.4.2/tools/tools.json"))
                        result["idf_tools_json_sha256"] = hashlib.sha256(
                            archive.read("esp-idf-v5.4.2/tools/tools.json")).hexdigest()
                        chosen = []
                        for tool in tools["tools"]:
                            targets = tool.get("supported_targets", ["all"])
                            if ("all" not in targets and "esp32c3" not in targets
                                    or tool["install"] != "always" and tool["name"] not in ("cmake", "ninja")):
                                continue
                            for version in tool["versions"]:
                                data = version.get("win64", version.get("any"))
                                if version["status"] == "recommended" and data:
                                    chosen.append({"name": tool["name"], "version": version["name"], **data})
                        result["idf_win64_tools"] = chosen
                        result["idf_tools_download_bytes"] = sum(t["size"] for t in chosen)
                        result["idf_archive_head"] = archive.read(
                            "esp-idf-v5.4.2/.git/HEAD").decode().strip()
        result["packages"].append(item)
    result["all_existing_packages_match"] = all(
        item.get("matches_prior_verified_receipt", False) for item in result["packages"])
    result["total_downloaded_bytes"] = sum(item.get("bytes", 0) for item in result["packages"])
    return result


class Commands:
    def __init__(self, out, env, timeout):
        self.out, self.env, self.timeout = out, env, timeout
        self.started = time.monotonic()
        self.steps = []

    def run(self, label, command, cwd=ROOT, limit=30):
        argv = [str(arg) for arg in command]
        if any(any(char in arg for char in "\r\n") for arg in argv):
            raise ValueError("invalid command argument")
        folder = self.out / "logs" / label
        folder.mkdir(parents=True)
        seconds = min(limit, self.timeout - (time.monotonic() - self.started))
        if seconds <= 0:
            raise TimeoutError("overall timeout exhausted")
        actual = argv
        # Explicit cmd wrapper only for fixed Gradle .bat commands; no shell writes.
        if os.name == "nt" and argv[0].lower().endswith((".bat", ".cmd")):
            if any(any(char in arg for char in '&|<>^%!') for arg in argv):
                raise ValueError("unsafe batch argument")
            actual = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c",
                      subprocess.list2cmdline(argv)]
        begun = time.monotonic()
        timed_out = False
        tree_cleanup_exit = None
        with (folder / "stdout.log").open("wb") as stdout, (folder / "stderr.log").open("wb") as stderr:
            process = subprocess.Popen(actual, cwd=cwd, env=self.env, stdout=stdout, stderr=stderr,
                                       start_new_session=os.name != "nt")
            try:
                process.wait(timeout=seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                if os.name == "nt":
                    cleanup = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                             capture_output=True, timeout=15, check=False)
                    tree_cleanup_exit = cleanup.returncode
                    (folder / "timeout_cleanup.stdout.log").write_bytes(cleanup.stdout)
                    (folder / "timeout_cleanup.stderr.log").write_bytes(cleanup.stderr)
                    if process.poll() is None:
                        process.kill()
                else:
                    import signal
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=15)
        item = {"label": label, "command": argv, "executed_command": actual,
                "cwd": str(cwd), "exit_code": process.returncode, "timed_out": timed_out,
                "timeout_tree_cleanup_exit": tree_cleanup_exit,
                "seconds": round(time.monotonic() - begun, 3),
                "stdout_sha256": digest(folder / "stdout.log"),
                "stderr_sha256": digest(folder / "stderr.log")}
        self.steps.append(item)
        text = (folder / "stdout.log").read_text(encoding="utf-8", errors="replace")
        text += (folder / "stderr.log").read_text(encoding="utf-8", errors="replace")
        if timed_out or item["exit_code"]:
            raise ValueError(f"COMMAND_FAIL: {label}, exit={item['exit_code']}, timeout={timed_out}")
        return text.strip()


def tracked_inputs(commands):
    files = commands.run("candidate_inputs", ["git", "ls-files", "--",
                                               CORE.relative_to(ROOT), APP.relative_to(ROOT)]).splitlines()
    return {name: digest(ROOT / name) for name in files if (ROOT / name).is_file()}


def missing_paths(paths):
    return [name + ": " + str(path) for name, path in paths.items() if not path.is_file()]


def require_match(text, pattern, label):
    if not re.search(pattern, text):
        raise ValueError("VERSION_MISMATCH: " + label)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("preflight", "c3", "apk"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--downloads", type=Path, default=SDK / "downloads/20261008")
    parser.add_argument("--idf-root", type=Path, default=Path(os.environ.get("IDF_PATH", str(SDK / "espressif/esp-idf-v5.4.2"))))
    parser.add_argument("--idf-tools", type=Path, default=Path(os.environ.get("IDF_TOOLS_PATH", str(SDK / "espressif/tools"))))
    parser.add_argument("--idf-python", type=Path)
    parser.add_argument("--java17", type=Path, default=SDK / "java/jdk17")
    parser.add_argument("--gradle", type=Path, default=SDK / "gradle/gradle-8.9/bin/gradle.bat")
    parser.add_argument("--android-sdk", type=Path, default=SDK / "android/sdk")
    parser.add_argument("--gradle-cache", type=Path, default=SDK / "cache/gradle")
    args = parser.parse_args()
    out = args.output.resolve()
    if (out.exists() or not out.is_relative_to((ROOT / "code/output").resolve())
            or not out.name.startswith("m3_t059_target_") or not 30 <= args.timeout <= 3600):
        parser.error("require NEW code/output/m3_t059_target_* and timeout 30..3600")
    out.mkdir(parents=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PIP_NO_INDEX="1",
               IDF_COMPONENT_MANAGER="0", IDF_TARGET="esp32c3")
    for name in ("JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS"):
        env.pop(name, None)
    commands = Commands(out, env, args.timeout)
    receipt = {"schema": 1, "stage": args.stage, "utc": datetime.now(timezone.utc).isoformat(),
               "status": "FAIL", "target_build_passed": False, "complete_t059_passed": False,
               "installed": False, "downloaded": False, "device_operations": False,
               "runner_python": {"path": sys.executable, "version": sys.version},
               "invocation": sys.argv, "runner_sha256": digest(__file__), "steps": commands.steps}
    before = {}
    exit_code = 1
    try:
        receipt["commit"] = commands.run("commit", ["git", "rev-parse", "HEAD"])
        commands.run("approved_base", ["git", "merge-base", "--is-ancestor", BASE, "HEAD"])
        before = tracked_inputs(commands)
        receipt["source_config_sha256"] = before
        identity, errors = frozen_sources()
        receipt["frozen_ten_source_identity"] = identity
        errors.extend(check_configs())
        if errors:
            raise ValueError("; ".join(errors))
        receipt["configuration_check"] = "PASS"
        receipt["environment"] = {name: os.environ.get(name) for name in (
            "IDF_PATH", "IDF_TOOLS_PATH", "IDF_PYTHON_ENV_PATH", "ANDROID_HOME",
            "ANDROID_SDK_ROOT", "JAVA_HOME", "GRADLE_USER_HOME")}
        receipt["path_tools"] = {name: shutil.which(name) for name in (
            "java", "javac", "gradle", "idf.py", "cmake", "ninja", "riscv32-esp-elf-gcc")}
        receipt["known_root_scope"] = {str(path): path.exists() for path in KNOWN_ROOTS}
        if shutil.which("java"):
            receipt["path_java_version"] = commands.run("path_java", [shutil.which("java"), "-version"])
        receipt["git_version"] = commands.run("git_version", ["git", "--version"])
        receipt["disk"] = {str(drive): {"free": shutil.disk_usage(drive).free}
                           for drive in (ROOT.anchor, Path(sys.executable).anchor) if drive}
        receipt["downloads"] = audit_downloads(args.downloads)
        if receipt["downloads"].get("all_existing_packages_match") is False:
            raise ValueError("DOWNLOAD_IDENTITY_MISMATCH")
        c3 = {"IDF": args.idf_root / "tools/idf.py",
              "NimBLE submodule": args.idf_root / "components/bt/host/nimble/nimble/nimble/host/include/host/ble_hs.h"}
        if args.idf_python:
            c3["IDF Python"] = args.idf_python
        c3_missing = missing_paths(c3)
        if not args.idf_python:
            c3_missing.append("explicit --idf-python for existing IDF virtual environment")
        for name in ("riscv32-esp-elf-gcc", "cmake", "ninja"):
            if not shutil.which(name):
                c3_missing.append("exported PATH tool: " + name)
        apk = {"JDK java": args.java17 / "bin/java.exe", "JDK javac": args.java17 / "bin/javac.exe",
               "Gradle": args.gradle, "SDK API35": args.android_sdk / "platforms/android-35/android.jar",
               "BuildTools34": args.android_sdk / "build-tools/34.0.0/aapt2.exe",
               "BuildTools34 properties": args.android_sdk / "build-tools/34.0.0/source.properties",
               "SDK accepted license": args.android_sdk / "licenses/android-sdk-license"}
        apk_missing = missing_paths(apk)
        for group, version in (("com.android.tools.build/gradle", "8.7.3"),
                               ("org.jetbrains.kotlin/kotlin-gradle-plugin", "2.0.21")):
            path = args.gradle_cache / "caches/modules-2/files-2.1" / group / version
            if not path.is_dir():
                apk_missing.append("offline plugin cache: " + str(path))
        receipt["missing"] = {"c3": c3_missing, "apk": apk_missing}
        receipt["explicit_paths"] = {key: str(getattr(args, key)) for key in (
            "idf_root", "idf_tools", "idf_python", "java17", "gradle", "android_sdk", "gradle_cache")}
        receipt["cache_scope"] = "plugin roots only; complete transitive resolution requires real offline build"
        if args.stage == "preflight" or receipt["missing"][args.stage]:
            receipt["status"] = "BLOCKED_MISSING_ENVIRONMENT" if (
                any(receipt["missing"].values()) if args.stage == "preflight" else receipt["missing"][args.stage]) else "PREFLIGHT_ONLY"
            exit_code = 2 if receipt["status"].startswith("BLOCKED") else 0
        else:
            project = CORE if args.stage == "c3" else APP
            copy = out / "project"
            for relative in before:
                source = ROOT / relative
                if source.is_relative_to(project):
                    destination = copy / source.relative_to(project)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
                    if digest(source) != digest(destination):
                        raise ValueError("COPY_IDENTITY")
            if args.stage == "c3":
                env.update(IDF_PATH=str(args.idf_root.resolve()), IDF_TOOLS_PATH=str(args.idf_tools.resolve()))
                tag = commands.run("idf_tag", ["git", "-C", args.idf_root, "describe", "--tags", "--exact-match"])
                commit = commands.run("idf_commit", ["git", "-C", args.idf_root, "rev-parse", "HEAD"])
                if tag != "v5.4.2" or commit != PINNED_IDF:
                    raise ValueError("IDF_IDENTITY_MISMATCH")
                commands.run("idf_clean_source", ["git", "-C", args.idf_root, "diff", "HEAD", "--exit-code"])
                receipt["idf_metadata_sha256"] = {name: digest(args.idf_root / name) for name in (
                    "tools/idf.py", "tools/tools.json", "tools/cmake/version.cmake", ".gitmodules")}
                submodules = commands.run("idf_submodules", ["git", "-C", args.idf_root, "submodule", "status", "--recursive"], limit=120)
                if any(line.startswith(("-", "+", "U")) for line in submodules.splitlines()):
                    raise ValueError("IDF_SUBMODULE_IDENTITY")
                for tool, expected in (("riscv32-esp-elf-gcc", r"14\.2\.0"),
                                       ("cmake", r"cmake version 3\.30\.2\b"), ("ninja", r"1\.12\.1\b")):
                    version = commands.run(tool + "_version", [shutil.which(tool), "--version"])
                    require_match(version, expected, tool)
                receipt["tool_executable_sha256"] = {name: digest(shutil.which(name)) for name in (
                    "riscv32-esp-elf-gcc", "cmake", "ninja")}
                commands.run("idf_python_version", [args.idf_python, "--version"])
                commands.run("idf_dependencies", [args.idf_python, args.idf_root / "tools/idf_tools.py", "check-python-dependencies"], limit=120)
                commands.run("c3_build", [args.idf_python, args.idf_root / "tools/idf.py", "-C", copy,
                             "-B", out / "build", "-D", "IDF_TARGET=esp32c3", "-D",
                             "SDKCONFIG=" + str(out / "sdkconfig"), "build"], limit=args.timeout)
                needed = [out / "sdkconfig", out / "build/score_ble_bridge_candidate.bin",
                          out / "build/score_ble_bridge_candidate.elf", out / "build/score_ble_bridge_candidate.map",
                          out / "build/bootloader/bootloader.bin", out / "build/partition_table/partition-table.bin",
                          out / "build/compile_commands.json"]
                if 'CONFIG_IDF_TARGET="esp32c3"' not in (out / "sdkconfig").read_text(encoding="utf-8"):
                    raise ValueError("C3_CONFIG_TARGET")
                compilation = json.loads((out / "build/compile_commands.json").read_text(encoding="utf-8"))
                if not any(Path(row["file"]).resolve() == (copy / "main/main.c").resolve() for row in compilation):
                    raise ValueError("REAL_MAIN_NOT_COMPILED")
            else:
                env.update(JAVA_HOME=str(args.java17.resolve()), ANDROID_HOME=str(args.android_sdk.resolve()),
                           ANDROID_SDK_ROOT=str(args.android_sdk.resolve()), GRADLE_USER_HOME=str(args.gradle_cache.resolve()),
                           ANDROID_USER_HOME=str(out / "android_user"))
                env["PATH"] = str(args.java17 / "bin") + os.pathsep + env.get("PATH", "")
                require_match(commands.run("jdk_version", [apk["JDK java"], "-version"]), r'version "17\.', "JDK17")
                require_match(commands.run("javac_version", [apk["JDK javac"], "-version"]), r"javac 17\.", "javac17")
                properties = apk["BuildTools34 properties"].read_text(encoding="utf-8")
                require_match(properties, r"Pkg.Revision\s*=\s*34\.0\.0", "BuildTools34")
                require_match(commands.run("gradle_version", [args.gradle, "--offline", "--version"]), r"Gradle 8\.9\b", "Gradle8.9")
                build_log = commands.run("apk_build", [args.gradle, "--offline", "--no-daemon", "--console=plain", "--stacktrace", "--info",
                             "--project-cache-dir", out / "project_cache", "-p", copy,
                             "-PcandidateBuildDir=" + str(out / "build"), "-Pandroid.builder.sdkDownload=false",
                             "-Dorg.gradle.java.installations.auto-download=false", "assembleDebug"], limit=args.timeout)
                needed = [out / "build/app/outputs/apk/debug/app-debug.apk"]
                with zipfile.ZipFile(needed[0]) as archive:
                    if not {"AndroidManifest.xml", "classes.dex"}.issubset(archive.namelist()):
                        raise ValueError("APK_REQUIRED_ENTRIES")
                    dex = b"".join(archive.read(name) for name in archive.namelist() if re.fullmatch(r"classes\d*\.dex", name))
                    if b"Lorg/m3/score/MainActivity;" not in dex or b"Lorg/m3/score/Protocol;" not in dex:
                        raise ValueError("REAL_ACTIVITY_NOT_PACKAGED")
                for task in ("compileDebugKotlin", "processDebugResources"):
                    require_match(build_log, r"Task :app:" + task + r"\b", "Android task " + task)
                receipt["tool_executable_sha256"] = {str(path): digest(path) for path in (
                    apk["JDK java"], apk["JDK javac"], args.gradle, apk["SDK API35"], apk["BuildTools34"])}
            if any(not path.is_file() or path.stat().st_size == 0 for path in needed):
                raise ValueError("MISSING_TARGET_ARTIFACT")
            receipt["required_artifacts"] = {str(p.relative_to(out)): digest(p) for p in needed}
            receipt.update(status="TARGET_COMPILED_ONLY", target_build_passed=True)
            exit_code = 0
    except Exception as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)
    finally:
        if before:
            receipt["source_config_unchanged"] = all((ROOT / name).is_file() and digest(ROOT / name) == sha
                                                     for name, sha in before.items())
            if not receipt["source_config_unchanged"]:
                receipt.update(status="FAIL", error="SOURCE_MUTATION", target_build_passed=False)
                exit_code = 1
        receipt["artifact_sha256"] = {p.relative_to(out).as_posix(): digest(p) for p in out.rglob("*") if p.is_file()}
        receipt["exit_code"] = exit_code
        receipt["seconds"] = round(time.monotonic() - commands.started, 3)
        dump(out / "receipt.json", receipt)
    print(json.dumps({"status": receipt["status"], "exit_code": exit_code,
                      "missing": receipt.get("missing"), "error": receipt.get("error"),
                      "receipt": str(out / "receipt.json")}, ensure_ascii=False), flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
