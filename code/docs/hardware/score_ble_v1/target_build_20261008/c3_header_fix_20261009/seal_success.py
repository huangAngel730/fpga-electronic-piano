"""Verify and seal existing C3 success; never install, build or access devices."""
from pathlib import Path
import base64
import gzip
import hashlib
import importlib.util
import json
import shutil
import struct
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
SPEC = importlib.util.spec_from_file_location("target_runner", ROOT / "code/software/score_ble_test_candidate/target_build_20261008/run.py")
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)
TARGET = ROOT / "code/output/m3_t059_target_20261009_c3_header_02"
EXPORT = ROOT / "code/output/m3_t059_target_20261009_header_export_02"
GATE = ROOT / "code/output/m3_t059_target_20261009_header_gate_02"
CHECK = ROOT / "code/output/m3_t059_target_20261009_header_checks_01"
OUT = ROOT / "code/output/m3_t059_target_20261009_header_success_delivery_02"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    if OUT.exists() or (HERE / "success_evidence").exists():
        raise ValueError("refuse evidence overwrite")
    receipt = load(TARGET / "receipt.json")
    gate, check = (load(p / "invocation_receipt.json") for p in (GATE, CHECK))
    exported = load(EXPORT / "exported_build_receipt.json")
    outer = load(EXPORT / "invocation_receipt.json")
    if receipt["exit_code"] or not receipt["target_build_passed"] or receipt["complete_t059_passed"]:
        raise ValueError("target not compile-only success")
    if not receipt["source_config_unchanged"] or not receipt["runner_profile_unchanged"]:
        raise ValueError("source or runner mutation")
    for item in (gate, check, exported, outer):
        if item["exit_code"]:
            raise ValueError("required execution not passed")
    if len(gate["pass_lines"]) != 9 or not gate["tracked_inputs_unchanged"]:
        raise ValueError("gate invalid")
    identity, errors = RUN.frozen_sources("c3_header_fix_20261009")
    if errors:
        raise ValueError(str(errors))
    for snapshot in (receipt["source_config_sha256"], receipt["runner_inputs_before_sha256"],
                     check["source_config_before_sha256"], outer["inputs_before_sha256"]):
        for relative, expected in snapshot.items():
            if RUN.digest(ROOT / relative) != expected:
                raise ValueError("executed input changed: " + relative)
    elf = (TARGET / "build/score_ble_bridge_candidate.elf").read_bytes()
    if elf[:6] != b"\x7fELF\x01\x01" or struct.unpack_from("<H", elf, 18)[0] != 243:
        raise ValueError("not ELF32 little-endian RISC-V")
    from esptool.bin_image import ESP32C3FirmwareImage
    with (TARGET / "build/score_ble_bridge_candidate.bin").open("rb") as firmware:
        image = ESP32C3FirmwareImage(firmware)
    image.verify()
    if image.chip_id != 5 or image.stored_digest != image.calc_digest:
        raise ValueError("C3 firmware image digest/target invalid")
    OUT.mkdir()
    payload = OUT / "payload"
    payload.mkdir()
    index = {}

    def copy(source, relative, expected=None):
        actual = RUN.digest(source)
        if expected is not None and actual != expected:
            raise ValueError("evidence SHA changed: " + str(source))
        destination = payload / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        if RUN.digest(destination) != actual:
            raise ValueError("copy SHA mismatch")
        index[relative] = {"bytes": source.stat().st_size, "sha256": actual}

    required = {str(Path(name)).replace("\\", "/"): sha for name, sha in receipt["required_artifacts"].items()}
    for folder, prefix in ((TARGET, "target"), (EXPORT, "export"), (GATE, "gate"), (CHECK, "selftest")):
        for source in sorted(folder.rglob("*")):
            if not source.is_file():
                continue
            relative = source.relative_to(folder).as_posix()
            include = (relative.startswith(("logs/", "project/", "build/log/")) or relative in required
                       or relative.endswith("receipt.json") or relative.endswith("environment.json")
                       or relative in ("build/CMakeCache.txt", "build/project_description.json",
                                       "build/esp-idf/main/CMakeFiles/__idf_main.dir/main.c.obj",
                                       "tracked_inputs_before.json", "tracked_inputs_after.json"))
            if include:
                copy(source, prefix + "/" + relative,
                     receipt["artifact_sha256"].get(relative) if prefix == "target" else None)
    for relative, entry in identity.items():
        copy(ROOT / relative, "reference/" + relative, entry["sha256"])
    for relative in receipt["source_config_sha256"]:
        copy(ROOT / relative, "reference/" + relative, receipt["source_config_sha256"][relative])
    for source in (RUN.BASELINE, RUN.HEADER_APPROVAL, Path(RUN.__file__), Path(RUN.__file__).with_name("test_run.py")):
        copy(source, "reference/" + source.name)
    for name in ("profile.json", "invoke_export.py", "export_build.cmd", "seal_success.py",
                 "FOLLOWUP_REPORT.md", "FOLLOWUP_M2_HANDOFF.md"):
        copy(HERE / name, "delivery/" + name)
    previous = load(HERE / "delivery_manifest.json")
    copy(Path(previous["zip"]), "previous_failure/" + Path(previous["zip"]).name, previous["sha256"])
    copy(HERE / "delivery_manifest.json", "previous_failure/delivery_manifest.json")
    copy(ROOT / "code/output/m3_t059_target_20261009_apk_01/receipt.json", "reference/previous_apk_receipt.json")
    facts = {"target_build_passed": True, "complete_t059_passed": False, "device_operations": False,
             "build_exit_code": 0, "runner_exit_code": 0, "build_seconds": receipt["steps"][-1]["seconds"],
             "runner_seconds": receipt["seconds"], "elf_machine": "ELF32 little-endian RISC-V (243)",
             "bin_chip_id": image.chip_id, "bin_embedded_sha_verified": True,
             "gate_pass_count": 9, "profile_test_count": 13, "source_identity": identity,
             "stage_attempts": [{"name": "header_01", "passed": False}, {"name": "header_02", "passed": True}],
             "additional_attempt_authorized_by_user": True, "business_change": "approved one include only",
             "git_commit_created": False, "git_push_executed": False}
    RUN.dump(OUT / "facts.json", facts)
    copy(OUT / "facts.json", "facts.json")
    RUN.dump(payload / "FILE_LIST.json", {"scope": "selected logs, source/config and actual firmware; not all build objects",
                                         "index_excludes_itself": True, "files": index})
    evidence = HERE / "success_evidence"
    evidence.mkdir()
    carriers = {}
    external = {}
    for relative, item in index.items():
        raw = (payload / relative).read_bytes()
        if relative.endswith((".bin", ".elf", ".map", ".obj", ".zip")):
            external[relative] = item
            continue
        name = relative.replace("/", "__") + ".gz.b64"
        carrier = evidence / name
        carrier.write_text(base64.b64encode(gzip.compress(raw, mtime=0)).decode("ascii") + "\n", encoding="ascii")
        if gzip.decompress(base64.b64decode(carrier.read_text(encoding="ascii"))) != raw:
            raise ValueError("carrier verification failed")
        carriers[relative] = {**item, "carrier": name, "carrier_sha256": RUN.digest(carrier)}
    RUN.dump(evidence / "raw_manifest.json", {"carriers": carriers, "actual_artifacts_in_zip_only": external})
    archive_path = OUT / "M3_D041_C3_TARGET_PASS_20261009.zip"
    with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in sorted(payload.rglob("*")):
            if source.is_file():
                archive.write(source, source.relative_to(payload).as_posix())
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("zip CRC invalid")
        for relative, item in index.items():
            raw = archive.read(relative)
            if hashlib.sha256(raw).hexdigest() != item["sha256"] or len(raw) != item["bytes"]:
                raise ValueError("zip member identity invalid")
    result = {"zip": str(archive_path), "bytes": archive_path.stat().st_size,
              "sha256": RUN.digest(archive_path), "payload_count": len(index) + 1,
              "zip_crc_and_member_sha_verified": True, "all_carriers_roundtrip_verified": True, "facts": facts}
    RUN.dump(HERE / "success_manifest.json", result)
    print(json.dumps({key: result[key] for key in ("zip", "bytes", "sha256", "payload_count")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
