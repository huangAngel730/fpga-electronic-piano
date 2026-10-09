"""Seal this failed single attempt and profile/gate evidence; never build."""
from pathlib import Path
import base64
import gzip
import hashlib
import importlib.util
import json
import shutil
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
SPEC = importlib.util.spec_from_file_location("target_runner", ROOT / "code/software/score_ble_test_candidate/target_build_20261008/run.py")
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)
OUT = ROOT / "code/output/m3_t059_target_20261009_header_delivery_01"
TARGET = ROOT / "code/output/m3_t059_target_20261009_c3_header_01/m3_t059_target_20261009_c3_header_build_01"
CHECK = ROOT / "code/output/m3_t059_target_20261009_header_checks_01"
GATE = ROOT / "code/output/m3_t059_target_20261009_header_gate_01"


def main():
    if OUT.exists() or (HERE / "evidence").exists():
        raise ValueError("Refuse overwriting evidence")
    OUT.mkdir()
    payload = OUT / "payload"
    payload.mkdir()
    receipt = json.loads((TARGET / "receipt.json").read_text(encoding="utf-8"))
    gate = json.loads((GATE / "invocation_receipt.json").read_text(encoding="utf-8"))
    check = json.loads((CHECK / "invocation_receipt.json").read_text(encoding="utf-8"))
    if receipt["exit_code"] != 1 or receipt["target_build_passed"] or receipt["runner_sha256"] != RUN.digest(Path(RUN.__file__)):
        raise ValueError("Unexpected actual build/runner identity")
    if gate["exit_code"] or len(gate["pass_lines"]) != 9 or check["exit_code"]:
        raise ValueError("Missing passing checks")
    if not gate["tracked_inputs_unchanged"]:
        raise ValueError("Gate inputs changed")
    index = {}

    def copy(source, relative, expected=None):
        actual = RUN.digest(source)
        if expected is not None and actual != expected:
            raise ValueError("Original evidence changed: " + str(source))
        target = payload / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if actual != RUN.digest(target):
            raise ValueError("Payload copy failed")
        index[relative] = {"bytes": source.stat().st_size, "sha256": actual}

    for source_root, prefix in ((TARGET, "target"), (GATE, "gate"), (CHECK, "selftest")):
        for source in sorted(source_root.rglob("*")):
            if not source.is_file():
                continue
            relative = source.relative_to(source_root).as_posix()
            include = (relative.startswith("logs/") or relative in (
                "receipt.json", "invocation_receipt.json", "sdkconfig",
                "tracked_inputs_before.json", "tracked_inputs_after.json",
                "build/compile_commands.json", "build/CMakeCache.txt")
                or relative.startswith(("project/", "build/log/")))
            if include:
                expected = receipt["artifact_sha256"].get(relative) if prefix == "target" else None
                copy(source, prefix + "/" + relative, expected)
    outer = TARGET.parent / "invocation_receipt.json"
    copy(outer, "target_invocation/receipt.json")
    for source in sorted((TARGET.parent / "logs").rglob("*")):
        if source.is_file():
            copy(source, "target_invocation/" + source.relative_to(TARGET.parent).as_posix())
    identity, errors = RUN.frozen_sources("c3_header_fix_20261009")
    if errors:
        raise ValueError(str(errors))
    for relative, item in identity.items():
        copy(ROOT / relative, "reference/" + relative, item["sha256"])
    copy(RUN.BASELINE, "reference/D040_baseline.json", RUN.BASELINE_SHA)
    copy(RUN.HEADER_APPROVAL, "reference/M2_APPROVAL.md", RUN.APPROVAL_SHA)
    for source in sorted(HERE.glob("*")):
        if source.is_file():
            copy(source, "delivery/" + source.name)
    for name in ("run.py", "test_run.py"):
        source = Path(RUN.__file__).with_name(name)
        copy(source, "reference/" + name)
    for relative, expected in receipt["source_config_sha256"].items():
        if RUN.digest(ROOT / relative) != expected:
            raise ValueError("Build configuration changed since execution")
    old_root = ROOT / "code/output/m3_t059_target_20261009_c3_01"
    old_receipt = json.loads((old_root / "receipt.json").read_text(encoding="utf-8"))
    copy(old_root / "receipt.json", "old_failure/receipt.json")
    for suffix in ("stdout.log", "stderr.log"):
        relative = "logs/c3_build/" + suffix
        copy(old_root / relative, "old_failure/" + suffix, old_receipt["artifact_sha256"][relative])
    old_main = old_root / "project/main/main.c"
    copy(old_main, "old_failure/main.c", RUN.OLD_MAIN_SHA)
    copy(RUN.ROOT / "code/output/m3_t059_target_20261009_apk_01/receipt.json", "reference/previous_apk_receipt.json")
    diff = subprocess.check_output(["git", "diff", "--", "code/software/score_ble_bridge_candidate/main/main.c"], cwd=ROOT)
    (payload / "approved_include_actual.patch").write_bytes(diff)
    index["approved_include_actual.patch"] = {"bytes": len(diff), "sha256": hashlib.sha256(diff).hexdigest()}
    dep = TARGET / "build/esp-idf/esp_driver_usb_serial_jtag/CMakeFiles/__idf_esp_driver_usb_serial_jtag.dir/src/usb_serial_jtag_connection_monitor.c.obj.d"
    facts = {"sdk_tools_sha256": receipt["tool_executable_sha256"],
             "idf_python_executable_sha256": RUN.digest(Path(receipt["explicit_paths"]["idf_python"])),
             "current_ten_source_identity": identity,
             "target_source_config_unchanged": receipt["source_config_unchanged"],
             "target_runner_profile_unchanged": receipt["runner_profile_unchanged"],
             "failed_dependency_absolute_path": str(dep), "dependency_path_characters": len(str(dep)),
             "main_object_present": (TARGET / "build/esp-idf/main/CMakeFiles/__idf_main.dir/main.c.obj").is_file(),
             "application_bin_present": (TARGET / "build/score_ble_bridge_candidate.bin").is_file(),
             "application_elf_present": (TARGET / "build/score_ble_bridge_candidate.elf").is_file(),
             "application_map_present": (TARGET / "build/score_ble_bridge_candidate.map").is_file(),
             "native_c3_attempts_this_phase": 1, "additional_build_performed": False,
             "selftest_count": 13, "gate_pass_count": 9, "gate_exit_code": 0,
             "gate_input_count": len(json.loads((GATE / "tracked_inputs_before.json").read_text(encoding="utf-8"))),
             "business_change": "one include only", "git_commit_created": False, "git_push_executed": False,
             "device_operations": False, "complete_t059_passed": False}
    RUN.dump(OUT / "facts.json", facts)
    copy(OUT / "facts.json", "facts.json")
    RUN.dump(payload / "FILE_LIST.json", {"scope": "selected evidence subset, not entire build objects",
                                        "index_excludes_itself": True, "files": index})
    evidence = HERE / "evidence"
    evidence.mkdir()
    carriers = {}
    for relative, item in index.items():
        name = relative.replace("/", "__") + ".gz.b64"
        raw = (payload / relative).read_bytes()
        carrier = evidence / name
        carrier.write_text(base64.b64encode(gzip.compress(raw, mtime=0)).decode("ascii") + "\n", encoding="ascii")
        if gzip.decompress(base64.b64decode(carrier.read_text(encoding="ascii"))) != raw:
            raise ValueError("Carrier round trip failed")
        carriers[relative] = {**item, "carrier": name, "carrier_sha256": RUN.digest(carrier)}
    RUN.dump(evidence / "raw_manifest.json", carriers)
    archive_path = OUT / "M3_D041_include_exact_C3_environment_FAIL_20261009.zip"
    with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in sorted(payload.rglob("*")):
            if source.is_file():
                archive.write(source, source.relative_to(payload).as_posix())
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failed")
        for relative, item in index.items():
            raw = archive.read(relative)
            if hashlib.sha256(raw).hexdigest() != item["sha256"] or len(raw) != item["bytes"]:
                raise ValueError("ZIP member identity failed")
    result = {"zip": str(archive_path), "bytes": archive_path.stat().st_size,
              "sha256": RUN.digest(archive_path), "payload_count": len(index) + 1,
              "all_carriers_roundtrip_verified": True, "zip_crc_and_member_sha_verified": True,
              "facts": facts}
    RUN.dump(HERE / "delivery_manifest.json", result)
    print(json.dumps({k: result[k] for k in ("zip", "bytes", "sha256", "payload_count")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
